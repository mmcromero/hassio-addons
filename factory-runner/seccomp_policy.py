"""Seccomp deny policy prototype; not connected to production execution."""
import ctypes
import errno
import os

SCMP_ACT_ALLOW = 0x7FFF0000
SCMP_ACT_ERRNO = 0x00050000 | errno.EPERM
SCMP_CMP_MASKED_EQ = 7
CLONE_NAMESPACE_FLAGS = (
    0x00020000, 0x02000000, 0x04000000, 0x08000000,
    0x10000000, 0x20000000, 0x40000000, 0x00000080,
)
DENIED_SYSCALLS = (
    "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
    "sendto", "recvfrom", "sendmsg", "recvmsg", "shutdown", "getsockname",
    "getpeername", "setsockopt", "getsockopt",
    "kill", "tkill", "tgkill", "pidfd_send_signal", "setsid", "setpgid",
    "shmget", "shmat", "shmctl", "shmdt", "semget", "semop", "semctl",
    "msgget", "msgsnd", "msgrcv", "msgctl", "mq_open", "mq_unlink",
    "mq_timedsend", "mq_timedreceive", "mq_notify", "mq_getsetattr",
    "clone3", "unshare", "setns", "mount", "umount2", "pivot_root", "chroot",
    "open_tree", "move_mount", "fsopen", "fsconfig", "fsmount", "fspick",
    "mount_setattr", "ptrace", "process_vm_readv", "process_vm_writev",
    "pidfd_open", "pidfd_getfd", "bpf", "perf_event_open", "userfaultfd",
    "io_uring_setup", "io_uring_enter", "io_uring_register",
    "open_by_handle_at", "name_to_handle_at", "openat2", "keyctl", "add_key", "request_key",
    "capset", "setuid", "setgid", "setgroups", "setresuid", "setresgid",
    "setfsuid", "setfsgid", "mknod", "mknodat", "fanotify_init",
    "iopl", "ioperm", "reboot", "kexec_load", "kexec_file_load",
    "init_module", "finit_module", "delete_module", "swapon", "swapoff",
    "acct", "settimeofday", "clock_settime", "sethostname", "setdomainname",
    "syslog", "getppid",
    "personality", "kcmp", "quotactl", "quotactl_fd", "lookup_dcookie",
)

# Essential syscalls that must remain allowed for normal single/subprocess worker operation
WORKER_ALLOWED_SYSCALLS = (
    "read", "write", "close", "fstat", "newfstatat", "lseek", "mmap", "mprotect",
    "munmap", "brk", "rt_sigaction", "rt_sigprocmask", "rt_sigreturn", "ioctl",
    "pread64", "pwrite64", "readv", "writev", "access", "pipe2", "select",
    "pselect6", "poll", "ppoll", "nanosleep", "gettimeofday", "getpid", "getuid",
    "getgid", "geteuid", "getegid", "execve", "clone", "wait4", "exit", "exit_group",
)


FILESYSTEM_MUTATION_SYSCALLS = (
    "creat", "unlink", "unlinkat", "rename", "renameat", "renameat2",
    "mkdir", "mkdirat", "rmdir", "link", "linkat", "symlink", "symlinkat",
    "truncate", "ftruncate", "fallocate", "chmod", "fchmod", "fchmodat",
    "fchmodat2", "chown", "fchown", "lchown", "fchownat", "utime",
    "utimes", "utimensat",
)
WRITE_OPEN_FLAGS = (
    os.O_WRONLY, os.O_RDWR, os.O_CREAT, os.O_TRUNC, os.O_APPEND,
    getattr(os, "O_TMPFILE", 0x410000),
)


class ScmpArgCmp(ctypes.Structure):
    _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]


def _load_library():
    lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                           ctypes.c_uint, ctypes.POINTER(ScmpArgCmp)]
    lib.seccomp_rule_add_array.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.restype = None
    return lib


def install_restrictions(library=None, *, deny_filesystem_writes=False, deny_process_creation=False):
    lib = library if library is not None else _load_library()
    context = lib.seccomp_init(SCMP_ACT_ALLOW)
    if not context:
        raise RuntimeError("seccomp_init failed")
    try:
        for name in DENIED_SYSCALLS:
            number = lib.seccomp_syscall_resolve_name(name.encode("ascii"))
            if number < 0:
                continue
            result = lib.seccomp_rule_add(context, SCMP_ACT_ERRNO, number, 0)
            if result < 0:
                raise OSError(-result, "seccomp_rule_add failed for " + name)
        if deny_filesystem_writes:
            for name in FILESYSTEM_MUTATION_SYSCALLS:
                number = lib.seccomp_syscall_resolve_name(name.encode("ascii"))
                if number < 0:
                    continue
                result = lib.seccomp_rule_add(context, SCMP_ACT_ERRNO, number, 0)
                if result < 0:
                    raise OSError(-result, "seccomp filesystem mutation rule failed for " + name)
            for syscall_name, flags_arg in (("open", 1), ("openat", 2)):
                number = lib.seccomp_syscall_resolve_name(syscall_name.encode("ascii"))
                if number < 0:
                    continue
                for flag in WRITE_OPEN_FLAGS:
                    if not flag:
                        continue
                    cmp = ScmpArgCmp(flags_arg, SCMP_CMP_MASKED_EQ, flag, flag)
                    result = lib.seccomp_rule_add_array(
                        context, SCMP_ACT_ERRNO, number, 1, ctypes.byref(cmp))
                    if result < 0:
                        raise OSError(-result, "seccomp write-open rule failed for " + syscall_name)
        if deny_process_creation:
            for name in ("clone", "fork", "vfork", "execve", "execveat"):
                number = lib.seccomp_syscall_resolve_name(name.encode("ascii"))
                if number < 0:
                    continue
                result = lib.seccomp_rule_add(context, SCMP_ACT_ERRNO, number, 0)
                if result < 0:
                    raise OSError(-result, "seccomp process creation rule failed for " + name)
        clone_nr = lib.seccomp_syscall_resolve_name(b"clone")
        if clone_nr >= 0:
            for flag in CLONE_NAMESPACE_FLAGS:
                cmp = ScmpArgCmp(0, SCMP_CMP_MASKED_EQ, flag, flag)
                result = lib.seccomp_rule_add_array(context, SCMP_ACT_ERRNO,
                    clone_nr, 1, ctypes.byref(cmp))
                if result < 0:
                    raise OSError(-result, "seccomp clone namespace rule failed")
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(38, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")
        result = lib.seccomp_load(context)
        if result < 0:
            raise OSError(-result, "seccomp_load failed")
        return True
    finally:
        lib.seccomp_release(context)


def _denied(lib, name, *args):
    number = lib.seccomp_syscall_resolve_name(name.encode("ascii"))
    if number < 0:
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    ctypes.set_errno(0)
    result = libc.syscall(ctypes.c_long(number), *[ctypes.c_long(x) for x in args])
    denied = result == -1 and ctypes.get_errno() == errno.EPERM
    if result >= 0 and name == "socket":
        os.close(result)
    elif result >= 0 and name == "shmget":
        shmctl = lib.seccomp_syscall_resolve_name(b"shmctl")
        if shmctl >= 0:
            libc.syscall(ctypes.c_long(shmctl), ctypes.c_long(result),
                         ctypes.c_long(0), ctypes.c_void_p(None))
    return denied


def is_syscall_denied(name: str) -> bool:
    """Check if a syscall name is in the strict denylist."""
    return name in DENIED_SYSCALLS


def is_syscall_allowed_for_workers(name: str) -> bool:
    """Check if a syscall name is in the allowed worker baseline."""
    return name in WORKER_ALLOWED_SYSCALLS and name not in DENIED_SYSCALLS


def self_test(library=None):
    lib = library if library is not None else _load_library()
    pid = os.getpid()
    return {
        "getppid": _denied(lib, "getppid"),
        "socket": _denied(lib, "socket", 2, 1, 0),
        "socketpair": _denied(lib, "socketpair", 1, 1, 0, 0),
        "bind": _denied(lib, "bind", -1, 0, 0),
        "connect": _denied(lib, "connect", -1, 0, 0),
        "setsid": _denied(lib, "setsid"),
        "setpgid": _denied(lib, "setpgid", 0, 0),
        "kill": _denied(lib, "kill", pid, 0),
        "shmget": _denied(lib, "shmget", 0x4652, 4096, 0o1100 | 0o600),
        "mount": _denied(lib, "mount", 0, 0, 0, 0, 0),
        "chroot": _denied(lib, "chroot", 0),
        "ptrace": _denied(lib, "ptrace", 0, 0, 0, 0),
        "bpf": _denied(lib, "bpf", 0, 0, 0),
    }
