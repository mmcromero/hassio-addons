"""Read-only capability probe for a possible chroot + seccomp backend.
Runs synthetic operations in a forked child only. No project code or HA secrets.
"""
import ctypes, errno, json, os, pwd, resource, signal, tempfile, time
from pathlib import Path

CAP_KILL, CAP_SETGID, CAP_SETUID, CAP_SYS_CHROOT, CAP_SYS_ADMIN, CAP_SYS_RESOURCE = 5, 6, 7, 18, 21, 24
PR_SET_NO_NEW_PRIVS, PR_GET_NO_NEW_PRIVS = 38, 39\nSAFE_FOR_UNTRUSTED_CODE = False


def _status_fields(path=Path("/proc/self/status")):
    result = {}
    try:
        for line in path.read_text().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                result[key] = value.strip()
    except OSError:
        pass
    return result


def root_capabilities_from_masks(effective, bounding):
    def has(mask, cap):
        return bool(mask & (1 << cap))
    return {
        "effective_available": True,
        "sys_chroot": has(effective, CAP_SYS_CHROOT),
        "kill": has(effective, CAP_KILL),
        "setuid": has(effective, CAP_SETUID),
        "setgid": has(effective, CAP_SETGID),
        "sys_resource": has(effective, CAP_SYS_RESOURCE),
        "sys_admin": has(effective, CAP_SYS_ADMIN),
        "bounding_sys_chroot": has(bounding, CAP_SYS_CHROOT),
        "bounding_kill": has(bounding, CAP_KILL),
    }


def root_capabilities():
    fields = _status_fields()
    try:
        effective, bounding = int(fields.get("CapEff", "0"), 16), int(fields.get("CapBnd", "0"), 16)
    except ValueError:
        effective = bounding = 0
    result = root_capabilities_from_masks(effective, bounding)
    result["effective_available"] = "CapEff" in fields
    return result


def _unescape_mount_field(value):
    return value.replace("\\040", " ").replace("\\011", "\t").replace("\\012", "\n").replace("\\134", "\\")


def memory_mounts():
    result = {}
    try:
        lines = Path("/proc/self/mountinfo").read_text().splitlines()
    except OSError:
        return result
    for line in lines:
        try:
            left, right = line.split(" - ", 1)
            fields, fs = left.split(), right.split()
            mountpoint = _unescape_mount_field(fields[4])
            if mountpoint not in ("/tmp", "/dev/shm"):
                continue
            values = {}
            try:
                st = os.statvfs(mountpoint)
                values = {"total_bytes": st.f_blocks * st.f_frsize,
                          "available_bytes": st.f_bavail * st.f_frsize}
            except OSError:
                pass
            options = set(fields[5].split(","))
            super_options = set(fs[2].split(",")) if len(fs) > 2 else set()
            result[mountpoint] = {
                "filesystem": fs[0],
                "read_only": "ro" in options or "ro" in super_options,
                "tmpfs_size_option": next((x.split("=", 1)[1] for x in super_options if x.startswith("size=")), None),
                **values,
            }
        except (ValueError, IndexError):
            continue
    return result


def _child_report(write_fd, root, outside_file, uid, gid):
    report = {
        "chroot_entered": False, "uid_dropped": False,
        "outside_path_hidden": False, "procfs_absent": False,
        "ha_options_hidden": False, "second_chroot_denied": False,
        "no_new_privs": False, "rlimit_nproc_enforced": False,
        "rlimit_as_enforced": False, "rlimit_fsize_enforced": False,
        "seccomp_loaded": False, "seccomp_denials": {},
        "descendants_inherit_filter": False, "errors": [],
    }
    try:
        os.chroot(root)
        os.chdir("/")
        report["chroot_entered"] = True
        os.setgroups([])
        os.setgid(gid)
        os.setuid(uid)
        report["uid_dropped"] = os.geteuid() == uid and os.getegid() == gid
        try:
            Path(outside_file).read_bytes()
        except OSError:
            report["outside_path_hidden"] = True
        report["procfs_absent"] = not Path("/proc/self/status").exists()
        report["ha_options_hidden"] = not Path("/data/options.json").exists()
        try:
            os.chroot("/")
        except OSError as exc:
            report["second_chroot_denied"] = exc.errno in (errno.EPERM, errno.EACCES)
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == 0:
            report["no_new_privs"] = libc.prctl(PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) == 1
        resource.setrlimit(resource.RLIMIT_NPROC, (4, 4))
        children, denied = [], False
        try:
            for _ in range(8):
                try:
                    pid = os.fork()
                except OSError as exc:
                    denied = exc.errno == errno.EAGAIN
                    break
                if pid == 0:
                    time.sleep(0.5)
                    os._exit(0)
                children.append(pid)
        finally:
            for pid in children:
                try: os.kill(pid, signal.SIGKILL)
                except ProcessLookupError: pass
            for pid in children:
                try: os.waitpid(pid, 0)
                except ChildProcessError: pass
        report["rlimit_nproc_enforced"] = denied and len(children) < 4
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        try: bytearray(512 * 1024 * 1024)
        except MemoryError: report["rlimit_as_enforced"] = True
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024, 1024))
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        try:
            with open("/tmp/size-limit-probe", "wb") as stream:
                stream.write(b"x" * 1024)
                try:
                    stream.write(b"x")
                except OSError as exc:
                    report["rlimit_fsize_enforced"] = exc.errno == errno.EFBIG
        except OSError as exc:
            report["rlimit_fsize_enforced"] = exc.errno == errno.EFBIG
        from seccomp_policy import install_restrictions, self_test
        report["seccomp_loaded"] = install_restrictions()
        if report["seccomp_loaded"]:
            report["seccomp_denials"] = self_test()
            pid = os.fork()
            if pid == 0:
                os._exit(0 if self_test().get("getppid") else 1)
            _, status = os.waitpid(pid, 0)
            report["descendants_inherit_filter"] = os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
    except Exception as exc:
        report["errors"].append("probe:" + type(exc).__name__)
    try: os.write(write_fd, json.dumps(report, sort_keys=True).encode("utf-8"))
    except OSError: pass
    os._exit(0)


def run_probe():
    report = {
        "mode": "capability_probe_only", "root": os.geteuid() == 0,
        "root_capabilities": root_capabilities(), "memory_mounts": memory_mounts(),
        "executor_account": False, "chroot_seccomp": None,
        "safe_for_untrusted_code": SAFE_FOR_UNTRUSTED_CODE,
    }
    try: account = pwd.getpwnam("executor")
    except KeyError:
        print("[ISOLATION-BACKEND] " + json.dumps(report, sort_keys=True), flush=True)
        return report
    report["executor_account"] = True
    if os.geteuid() != 0 or not report["root_capabilities"]["sys_chroot"]:
        report["chroot_seccomp"] = {"status": "blocked_root_or_cap_sys_chroot"}
        print("[ISOLATION-BACKEND] " + json.dumps(report, sort_keys=True), flush=True)
        return report
    try:
        with tempfile.TemporaryDirectory(prefix="fr-isolation-probe-") as temp:
            root = Path(temp) / "root"
            (root / "tmp").mkdir(parents=True)
            outside = Path(temp) / "outside-sentinel"
            outside.write_text("synthetic-only")
            read_fd, write_fd = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(read_fd)
                _child_report(write_fd, str(root), str(outside), account.pw_uid, account.pw_gid)
            os.close(write_fd)
            chunks = []
            while True:
                data = os.read(read_fd, 4096)
                if not data: break
                chunks.append(data)
            os.close(read_fd)
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0:
                report["chroot_seccomp"] = json.loads(b"".join(chunks).decode("utf-8"))
            else:
                report["chroot_seccomp"] = {"status": "child_probe_failed"}
    except Exception as exc:
        report["chroot_seccomp"] = {"status": "probe_error", "error": type(exc).__name__}
    print("[ISOLATION-BACKEND] " + json.dumps(report, sort_keys=True), flush=True)
    return report


if __name__ == "__main__":
    run_probe()
