"""Non-mutating Landlock ABI capability query for Factory Runner.

This is NOT an isolation mechanism. It does not create or apply a ruleset,
change no_new_privs, run untrusted code, or alter the Home Assistant host.
"""
import errno
import platform
import sys

# Linux asm-generic/unistd.h and x86_64 syscall table.
_NR_LANDLOCK_CREATE_RULESET = 444
_LANDLOCK_CREATE_RULESET_VERSION = 1
_SUPPORTED_MACHINES = frozenset(("aarch64", "x86_64"))


def _kernel_query():
    """Call landlock_create_ruleset(NULL, 0, VERSION) -- ABI query only."""
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    syscall = libc.syscall
    syscall.restype = ctypes.c_long
    ctypes.set_errno(0)
    result = syscall(ctypes.c_long(_NR_LANDLOCK_CREATE_RULESET),
                     ctypes.c_void_p(None), ctypes.c_size_t(0),
                     ctypes.c_uint(_LANDLOCK_CREATE_RULESET_VERSION))
    return int(result), ctypes.get_errno() if result == -1 else 0


def landlock_status(*, query=None, machine=None, os_name=None):
    """Report the interface; unsupported/unknown results are never a PASS."""
    machine = platform.machine().lower() if machine is None else machine.lower()
    os_name = sys.platform if os_name is None else os_name
    result = {
        "status": "unknown", "abi": None,
        "filesystem_rules": False, "tcp_port_rules": False,
        "udp_port_rules": False, "ipc_scoping": False,
        "enforcement_verified": False,
        "safe_for_untrusted_code": False,
    }
    if os_name != "linux" or machine not in _SUPPORTED_MACHINES:
        result["status"] = "unsupported_arch_or_os"
        return result
    try:
        abi, error = _kernel_query() if query is None else query()
    except (OSError, ImportError, AttributeError, TypeError, ValueError):
        result["status"] = "query_failed"
        return result
    if abi >= 1 and error == 0:
        result.update(status="supported", abi=abi,
                      filesystem_rules=True, tcp_port_rules=abi >= 4,
                      udp_port_rules=abi >= 10, ipc_scoping=abi >= 6)
    elif abi == -1:
        result["status"] = {
            errno.ENOSYS: "syscall_unavailable",
            errno.EOPNOTSUPP: "disabled",
            errno.EPERM: "permission_denied",
            errno.EACCES: "permission_denied",
        }.get(error, "query_failed")
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(landlock_status(), sort_keys=True, separators=(",", ":")))
