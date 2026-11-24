import os, stat, sys, tempfile, unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publisher_permissions import share_readonly, share_root_traverse

class PublisherPermissionsTests(unittest.TestCase):
    def test_recursive_group_read_only_and_owner_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); root.chmod(0o700)
            nested=root/"source"/".git"/"objects"; nested.mkdir(parents=True)
            executable=nested/"pack"; executable.write_text("git object"); executable.chmod(0o700)
            data=root/"receipt"; data.write_text("fixture"); data.chmod(0o600)
            share_readonly(root, group_gid=os.getgid())
            self.assertEqual(stat.S_IMODE(root.stat().st_mode),0o2750)
            self.assertEqual(stat.S_IMODE(nested.stat().st_mode),0o2750)
            self.assertEqual(stat.S_IMODE(executable.stat().st_mode),0o750)
            self.assertEqual(stat.S_IMODE(data.stat().st_mode),0o640)
            self.assertTrue(os.access(data,os.W_OK))
    def test_symlink_refused_before_permission_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); root.chmod(0o700)
            data=root/"receipt"; data.write_text("x"); data.chmod(0o600)
            (root/"link").symlink_to(data)
            with self.assertRaisesRegex(ValueError,"unsafe_publisher_snapshot_entry"):
                share_readonly(root,group_gid=os.getgid())
            self.assertEqual(stat.S_IMODE(data.stat().st_mode),0o600)
    def test_workspace_root_grants_traversal_without_changing_unverified_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o700)
            private=root/"unmanaged";private.mkdir(mode=0o700)
            data=private/"secret";data.write_text("private");data.chmod(0o600)
            share_root_traverse(root,group_gid=os.getgid())
            self.assertEqual(stat.S_IMODE(root.stat().st_mode),0o2710)
            self.assertEqual(stat.S_IMODE(private.stat().st_mode),0o700)
            self.assertEqual(stat.S_IMODE(data.stat().st_mode),0o600)

    def test_wrong_owner_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); root.chmod(0o700)
            with patch("publisher_permissions.os.geteuid", return_value=os.geteuid()+1):
                with self.assertRaisesRegex(ValueError,"publisher_snapshot_owner_mismatch"):
                    share_readonly(root,group_gid=os.getgid())
