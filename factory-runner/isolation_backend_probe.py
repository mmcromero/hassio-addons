"""Read-only capability probe for a possible chroot + seccomp backend.
Runs synthetic operations in a forked child only. No project code or HA secrets.
"""
import ctypes, errno, json, os, pwd, resource, signal, tempfile, time, sys
from pathlib import Path

sys.path.insert(0, "/app")
try:
    import seccomp_policy
    SECCOMP_LIBRARY = seccomp_policy._load_library()
except Exception:
    seccomp_policy = None
    SECCOMP_LIBRARY = None

CAP_KILL, CAP_SETGID, CAP_SETUID, CAP_SYS_CHROOT, CAP_SYS_ADMIN, CAP_SYS_RESOURCE = 5, 6, 7, 18, 21, 24
PR_SET_NO_NEW_PRIVS, PR_GET_NO_NEW_PRIVS = 38, 39
SAFE_FOR_UNTRUSTED_CODE = False


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


def path_is_absent(path, stat_fn=os.stat):
    """Only ENOENT/ENOTDIR prove absence; EACCES is not a containment proof."""
    try:
        stat_fn(path)
    except OSError as exc:
        return exc.errno in (errno.ENOENT, errno.ENOTDIR)
    return False


def path_access_status(path, directory=False, open_fn=os.open, read_fn=os.read,
                       listdir_fn=os.listdir, close_fn=os.close):
    """Return access state only; never return or log file contents."""
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    try:
        fd = open_fn(path, flags)
    except FileNotFoundError:
        return "absent"
    except PermissionError:
        return "permission_denied"
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            return "absent"
        if exc.errno in (errno.EACCES, errno.EPERM):
            return "permission_denied"
        return f"other_error_errno_{exc.errno}"
    try:
        try:
            if directory:
                listdir_fn(fd)
            else:
                read_fn(fd, 1)
        except PermissionError:
            return "permission_denied"
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EPERM):
                return "permission_denied"
            if exc.errno in (errno.ENOENT, errno.ENOTDIR):
                return "absent"
            return f"other_error_errno_{exc.errno}"
        return "readable"
    finally:
        close_fn(fd)


def effective_capabilities_mask(low, high):
    return (int(high) << 32) | int(low)


class _CapHeader(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int32)]


class _CapData(ctypes.Structure):
    _fields_ = [("effective", ctypes.c_uint32), ("permitted", ctypes.c_uint32),
                ("inheritable", ctypes.c_uint32)]


def effective_capabilities_via_capget():
    """Read effective capability mask without depending on procfs visibility."""
    machine = os.uname().machine.lower()
    syscall_number = {"aarch64": 90, "x86_64": 125}.get(machine)
    if syscall_number is None:
        return {"status": "unsupported_arch"}
    header = _CapHeader(0x20080522, 0)
    data = (_CapData * 2)()
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    ctypes.set_errno(0)
    result = libc.syscall(ctypes.c_long(syscall_number), ctypes.byref(header),
                          ctypes.byref(data))
    if result != 0:
        return {"status": "error", "errno": ctypes.get_errno()}
    mask = effective_capabilities_mask(data[0].effective, data[1].effective)
    return {"status": "ok", "mask": f"{mask:016x}", "zero": mask == 0}


def prepare_probe_root(root):
    root = Path(root)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    os.chmod(root / "tmp", 0o1777)
    return root


def _append_error(report, stage, exc):
    number = getattr(exc, "errno", None)
    report["errors"].append(f"{stage}:{type(exc).__name__}:errno={number}")


def _child_report(write_fd, root, outside_file, uid, gid, scratch_fd, scratch_setup_error):
    report = {
        "chroot_entered": False, "uid_dropped": False,
        "outside_path_hidden": False, "outside_path_permission_denied": False,
        "outside_path_status": "not_tested",
        "procfs_absent": False, "procfs_status": "not_tested",
        "procfs_directory_status": "not_tested",
        "procfs_pid1_cmdline_status": "not_tested",
        "procfs_pid1_environ_status": "not_tested",
        "ha_options_hidden": False, "ha_options_status": "not_tested",
        "effective_capabilities_after_drop_zero": None,
        "effective_capabilities_after_drop": None,
        "effective_capabilities_source": "capget",
        "second_chroot_denied": False, "no_new_privs": False,
        "no_new_privs_errno": None,
        "rlimit_nproc_enforced": False, "rlimit_nproc_limit": None,
        "rlimit_as_enforced": False, "rlimit_as_bytes": None,
        "rlimit_fsize_enforced": False, "rlimit_fsize_bytes": None,
        "seccomp_loaded": False, "seccomp_denials": {},
        "descendants_inherit_filter": False, "errors": [],
    }
    stage = "chroot"
    try:
        os.chroot(root)
        os.chdir("/")
        report["chroot_entered"] = True

        stage = "drop_supplementary_groups"
        os.setgroups([])
        stage = "drop_gid"
        os.setgid(gid)
        stage = "drop_uid"
        os.setuid(uid)
        report["uid_dropped"] = os.geteuid() == uid and os.getegid() == gid

        stage = "outside_path_visibility"
        report["outside_path_status"] = path_access_status(outside_file)
        report["outside_path_hidden"] = report["outside_path_status"] == "absent"
        report["outside_path_permission_denied"] = report["outside_path_status"] == "permission_denied"

        stage = "procfs_visibility"
        report["procfs_status"] = path_access_status("/proc/self/status")
        report["procfs_directory_status"] = path_access_status("/proc", directory=True)
        report["procfs_pid1_cmdline_status"] = path_access_status("/proc/1/cmdline")
        report["procfs_pid1_environ_status"] = path_access_status("/proc/1/environ")
        report["procfs_absent"] = report["procfs_status"] == "absent"

        stage = "capabilities_after_drop"
        capabilities = effective_capabilities_via_capget()
        if capabilities.get("status") == "ok":
            report["effective_capabilities_after_drop"] = capabilities["mask"]
            report["effective_capabilities_after_drop_zero"] = capabilities["zero"]
        else:
            report["effective_capabilities_source"] = capabilities.get("status")
            report["errors"].append(
                f"capget:errno={capabilities.get('errno')}"
                if capabilities.get("status") == "error"
                else "capget:unsupported_arch"
            )

        stage = "ha_options_visibility"
        report["ha_options_status"] = path_access_status("/data/options.json")
        report["ha_options_hidden"] = report["ha_options_status"] == "absent"

        stage = "second_chroot_capability_check"
        try:
            os.chroot("/")
        except OSError as exc:
            report["second_chroot_denied"] = exc.errno in (errno.EPERM, errno.EACCES)
            if not report["second_chroot_denied"]:
                _append_error(report, stage, exc)

        stage = "no_new_privs"
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl.restype = ctypes.c_int
        ctypes.set_errno(0)
        result = libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        if result == 0:
            report["no_new_privs"] = libc.prctl(PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) == 1
        else:
            report["no_new_privs_errno"] = ctypes.get_errno()

        stage = "rlimit_nproc"
        try:
            _, hard = resource.getrlimit(resource.RLIMIT_NPROC)
            limit = 4 if hard == resource.RLIM_INFINITY else min(4, hard)
            resource.setrlimit(resource.RLIMIT_NPROC, (limit, limit))
            report["rlimit_nproc_limit"] = limit
            children, denied = [], False
            try:
                for _ in range(int(limit) + 3):
                    try:
                        pid = os.fork()
                    except OSError as exc:
                        denied = exc.errno == errno.EAGAIN
                        break
                    if pid == 0:
                        time.sleep(0.1)
                        os._exit(0)
                    children.append(pid)
            finally:
                for pid in children:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                for pid in children:
                    try:
                        os.waitpid(pid, 0)
                    except ChildProcessError:
                        pass
            report["rlimit_nproc_enforced"] = denied and len(children) <= max(0, int(limit) - 1)
        except OSError as exc:
            _append_error(report, stage, exc)

        stage = "rlimit_as"
        try:
            _, hard = resource.getrlimit(resource.RLIMIT_AS)
            limit = 256 * 1024 * 1024 if hard == resource.RLIM_INFINITY else min(256 * 1024 * 1024, hard)
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
            report["rlimit_as_bytes"] = limit
            try:
                bytearray(limit + 64 * 1024 * 1024)
            except MemoryError:
                report["rlimit_as_enforced"] = True
        except OSError as exc:
            _append_error(report, stage, exc)

        stage = "rlimit_fsize"
        try:
            _, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
            limit = 1024 if hard == resource.RLIM_INFINITY else min(1024, hard)
            resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
            report["rlimit_fsize_bytes"] = limit
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            if scratch_fd < 0:
                report["errors"].append(scratch_setup_error or "rlimit_fsize:scratch_fd_unavailable")
            else:
                os.lseek(scratch_fd, 0, os.SEEK_SET)
                first_write = os.write(scratch_fd, b"x" * int(limit)) if limit else 0
                if first_write != int(limit):
                    report["errors"].append("rlimit_fsize:short_initial_write")
                else:
                    try:
                        os.write(scratch_fd, b"x")
                    except OSError as exc:
                        report["rlimit_fsize_enforced"] = exc.errno == errno.EFBIG
        except OSError as exc:
            _append_error(report, stage, exc)

        stage = "seccomp_install"
        if seccomp_policy is None or SECCOMP_LIBRARY is None:
            raise RuntimeError("seccomp_library_unavailable")
        report["seccomp_loaded"] = seccomp_policy.install_restrictions(SECCOMP_LIBRARY)
        if report["seccomp_loaded"]:
            stage = "seccomp_self_test"
            report["seccomp_denials"] = seccomp_policy.self_test(SECCOMP_LIBRARY)
            pid = os.fork()
            if pid == 0:
                os._exit(0 if seccomp_policy.self_test(SECCOMP_LIBRARY).get("getppid") else 1)
            _, status = os.waitpid(pid, 0)
            report["descendants_inherit_filter"] = os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
    except Exception as exc:
        _append_error(report, stage, exc)
    try:
        os.write(write_fd, json.dumps(report, sort_keys=True).encode("utf-8"))
    except OSError:
        pass
    os._exit(0)


def run_probe():
    report = {
        "mode": "capability_probe_only", "root": os.geteuid() == 0,
        "root_capabilities": root_capabilities(), "memory_mounts": memory_mounts(),
        "executor_account": False, "chroot_seccomp": None,
        "safe_for_untrusted_code": SAFE_FOR_UNTRUSTED_CODE,
    }
    try:
        account = pwd.getpwnam("executor")
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
            os.chmod(temp, 0o755)
            root = prepare_probe_root(Path(temp) / "root")
            outside = Path(temp) / "outside-sentinel"
            outside.write_text("synthetic-only")
            os.chmod(outside, 0o644)
            scratch_fd, scratch_setup_error = -1, None
            try:
                scratch_fd = os.open(root / "tmp" / "size-limit-probe",
                                     os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_CLOEXEC", 0),
                                     0o600)
            except OSError as exc:
                scratch_setup_error = f"scratch_setup:{type(exc).__name__}:errno={exc.errno}"
            read_fd, write_fd = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(read_fd)
                _child_report(write_fd, str(root), str(outside), account.pw_uid,
                              account.pw_gid, scratch_fd, scratch_setup_error)
            os.close(write_fd)
            if scratch_fd >= 0:
                os.close(scratch_fd)
            chunks = []
            while True:
                data = os.read(read_fd, 4096)
                if not data:
                    break
                chunks.append(data)
            os.close(read_fd)
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0:
                payload = b"".join(chunks)
                report["chroot_seccomp"] = json.loads(payload.decode("utf-8")) if payload else {"status": "empty_child_report"}
            else:
                report["chroot_seccomp"] = {"status": "child_probe_failed"}
    except Exception as exc:
        report["chroot_seccomp"] = {"status": "probe_error", "error": type(exc).__name__}
    print("[ISOLATION-BACKEND] " + json.dumps(report, sort_keys=True), flush=True)
    return report


if __name__ == "__main__":
    run_probe()
