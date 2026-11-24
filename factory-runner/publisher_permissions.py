"""Grant the publisher group read-only access to verified snapshots."""
from __future__ import annotations
import grp, os, stat
from pathlib import Path

def share_root_traverse(root, *, group_name="publisher", group_gid=None):
    """Expose only traversal of the workspace root; never recurse unverified data."""
    root = Path(root).absolute()
    if root.resolve() != root or root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe_publisher_workspace_root")
    if root.stat().st_uid != os.geteuid():
        raise ValueError("publisher_workspace_root_owner_mismatch")
    gid = grp.getgrnam(group_name).gr_gid if group_gid is None else group_gid
    if os.geteuid() != 0 and gid not in os.getgroups() and gid != os.getegid():
        raise ValueError("publisher_group_not_available")
    os.chown(root, -1, gid, follow_symlinks=False)
    os.chmod(root, 0o2710, follow_symlinks=False)
    return root


def share_readonly(root, *, group_name="publisher", group_gid=None):
    root = Path(root).absolute()
    if root.resolve() != root or root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe_publisher_snapshot")
    if root.stat().st_uid != os.geteuid():
        raise ValueError("publisher_snapshot_owner_mismatch")
    gid = grp.getgrnam(group_name).gr_gid if group_gid is None else group_gid
    if os.geteuid() != 0 and gid not in os.getgroups() and gid != os.getegid():
        raise ValueError("publisher_group_not_available")
    entries = []
    def walk_error(error):
        raise ValueError("publisher_snapshot_unreadable") from error
    for base, dirs, files in os.walk(root, topdown=True, followlinks=False, onerror=walk_error):
        parent = Path(base)
        for name in list(dirs):
            path = parent / name
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError("unsafe_publisher_snapshot_entry")
            entries.append((path, True, info.st_mode))
        for name in files:
            path = parent / name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("unsafe_publisher_snapshot_entry")
            entries.append((path, False, info.st_mode))
    entries.append((root, True, root.stat().st_mode))
    for path, is_dir, original_mode in entries:
        if is_dir:
            mode = 0o2750
        else:
            owner = stat.S_IMODE(original_mode) & 0o700
            mode = owner | 0o040 | (0o010 if owner & 0o100 else 0)
        os.chown(path, -1, gid, follow_symlinks=False)
        os.chmod(path, mode, follow_symlinks=False)
    return root
