import os
import json
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import stat
import sys
import tempfile
import subprocess
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_bootstrap import LAYOUT, provision_layout, configure_from_options


class BootstrapTests(unittest.TestCase):
    def provision(self, root):
        return provision_layout(
            root, uid_for=lambda _: os.getuid(), gid_for=lambda _: os.getgid(),
            root_uid=os.getuid(), root_gid=os.getgid(), root_mode=0o711,
        )

    def test_idempotent_preserves_existing_state_and_creates_no_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o711)
            options = root / "options.json"
            options.write_text("fixture")
            paths = self.provision(root)
            state = paths[0] / "ledger.sqlite3"
            state.write_text("existing")
            self.assertEqual(self.provision(root), paths)
            self.assertEqual(state.read_text(), "existing")
            self.assertEqual(options.read_text(), "fixture")
            for path, (_, _, _, mode) in zip(paths, LAYOUT):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)
            self.assertEqual(sorted(p.name for p in paths[0].iterdir()), ["ledger.sqlite3"])

    def test_symlink_refused_before_any_directory_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o711)
            (root / LAYOUT[-1][0]).symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "unsafe_existing_service_directory"):
                self.provision(root)
            self.assertFalse((root / "approval").exists())

    def test_unsafe_mode_refused_without_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o711)
            path = self.provision(root)[0]
            path.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "unsafe_existing_service_directory"):
                self.provision(root)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755)

    def test_existing_directory_reports_relative_name_and_safe_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o711)
            path = self.provision(root)[0]
            path.chmod(0o755)
            with self.assertRaisesRegex(
                ValueError,
                r"unsafe_existing_service_directory:approval:mode=0755_expected=0700",
            ):
                self.provision(root)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755)

    def test_unsafe_root_mode_or_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "unsafe_authority_root"):
                self.provision(root)
            root.chmod(0o711)
            link = root.parent / (root.name + "-link")
            link.symlink_to(root, target_is_directory=True)
            try:
                with self.assertRaisesRegex(ValueError, "unsafe_authority_root"):
                    self.provision(link)
            finally:
                link.unlink()

    def test_owner_runtime_config_is_derived_and_root_owned_without_enrolling_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o711)
            for name,_,_,mode in LAYOUT:
                (root/name).mkdir(mode=mode)
                (root/name).chmod(mode)
            options=root/"options.json"
            options.write_text(json.dumps({
                "owner_ha_user_id":"ha-user-123456",
                "owner_ingress_origin":"https://ha.example.invalid",
                "owner_ingress_enabled":True,
            }))
            options.chmod(0o600)
            fake_groups=lambda name: SimpleNamespace(gr_gid=os.getgid())
            fake_users=lambda name: SimpleNamespace(pw_uid=os.getuid())
            with patch("owner_bootstrap.grp.getgrnam",side_effect=fake_groups), patch("owner_bootstrap.pwd.getpwnam",side_effect=fake_users):
                self.assertTrue(configure_from_options(root,options))
                self.assertTrue(configure_from_options(root,options))
            ingress=root/"owner-ui-config"/"ingress.json"
            approval=root/"approval-config"/"runtime.json"
            self.assertEqual(stat.S_IMODE(ingress.stat().st_mode),0o440)
            self.assertEqual(stat.S_IMODE(approval.stat().st_mode),0o440)
            self.assertEqual(json.loads(ingress.read_text())["owner_id"],
                             json.loads(approval.read_text())["owner_id"])
            self.assertFalse((root/"approval"/"signing.pem").exists())
            self.assertFalse((root/"approval"/"owner.json").exists())

    def test_owner_runtime_config_rejects_origin_change_after_provisioning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o711)
            for name,_,_,mode in LAYOUT:
                (root/name).mkdir(mode=mode)
                (root/name).chmod(mode)
            options=root/"options.json"
            options.write_text(json.dumps({"owner_ha_user_id":"ha-user-123456",
                "owner_ingress_origin":"https://ha.example.invalid","owner_ingress_enabled":True}))
            options.chmod(0o600)
            fake_groups=lambda name: SimpleNamespace(gr_gid=os.getgid())
            fake_users=lambda name: SimpleNamespace(pw_uid=os.getuid())
            with patch("owner_bootstrap.grp.getgrnam",side_effect=fake_groups), patch("owner_bootstrap.pwd.getpwnam",side_effect=fake_users):
                configure_from_options(root,options)
                options.write_text(json.dumps({"owner_ha_user_id":"ha-user-123456",
                    "owner_ingress_origin":"https://changed.example.invalid","owner_ingress_enabled":True}))
                options.chmod(0o600)
                with self.assertRaisesRegex(ValueError,"reenrollment"):
                    configure_from_options(root,options)

    def test_invalid_owner_origin_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o711)
            for name,_,_,mode in LAYOUT:
                (root/name).mkdir(mode=mode)
                (root/name).chmod(mode)
            options=root/"options.json"
            options.write_text(json.dumps({"owner_ha_user_id":"ha-user-123456",
                "owner_ingress_origin":"http://ha.example.invalid","owner_ingress_enabled":True}))
            options.chmod(0o600)
            with self.assertRaisesRegex(ValueError,"https_owner_origin_required"):
                configure_from_options(root,options)

    def test_owner_ingress_disabled_does_not_write_identity_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o711)
            for name,_,_,mode in LAYOUT:
                (root/name).mkdir(mode=mode)
                (root/name).chmod(mode)
            options=root/"options.json"
            options.write_text(json.dumps({
                "owner_ingress_enabled":False,
                "owner_ha_user_id":"ha-user-123456",
                "owner_ingress_origin":"https://ha.example.invalid",
            }))
            options.chmod(0o600)
            self.assertFalse(configure_from_options(root,options))
            self.assertFalse((root/"approval-config"/"runtime.json").exists())
            self.assertFalse((root/"owner-ui-config"/"ingress.json").exists())


    def test_root_config_directories_enforce_real_uid_gid_boundaries(self):
        if os.geteuid() != 0:
            self.fail("P1 permission integration test requires root; refusing a false PASS")

        users = {
            "approval": 21001,
            "publisher": 21002,
            "owner_ui": 21003,
            "runner": 21004,
        }
        groups = {
            "root": 0,
            "approval": 22001,
            "publisher": 22002,
            "owner_ui": 22003,
            "runner": 22004,
            "consent_clients": 22005,
            "publisher_clients": 22006,
        }
        uid_for = lambda name: 0 if name == "root" else users[name]
        gid_for = lambda name: groups[name]

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp).chmod(0o711)
            root = Path(tmp) / "authority"
            root.mkdir()
            os.chown(root, 0, 0)
            root.chmod(0o711)
            paths = provision_layout(
                root, uid_for=uid_for, gid_for=gid_for,
                root_uid=0, root_gid=0, root_mode=0o711,
            )
            by_name = {p.name: p for p in paths}

            config_groups = {
                "approval-config": groups["approval"],
                "publisher-config": groups["publisher"],
                "owner-ui-config": groups["owner_ui"],
            }
            sentinels = {}
            for dirname, gid in config_groups.items():
                directory = by_name[dirname]
                info = directory.lstat()
                self.assertTrue(stat.S_ISDIR(info.st_mode))
                self.assertEqual((info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)),
                                 (0, gid, 0o750))
                sentinel = directory / "authority.json"
                fd = os.open(
                    sentinel, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                try:
                    os.fchown(fd, 0, gid)
                    os.fchmod(fd, 0o440)
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(dirname.encode("ascii"))
                        stream.flush()
                        os.fsync(stream.fileno())
                except Exception:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    raise
                finfo = sentinel.lstat()
                self.assertTrue(stat.S_ISREG(finfo.st_mode))
                self.assertEqual(
                    (finfo.st_uid, finfo.st_gid, stat.S_IMODE(finfo.st_mode), finfo.st_nlink),
                    (0, gid, 0o440, 1),
                )
                sentinels[dirname] = sentinel

            state_expected = {
                "approval": (users["approval"], groups["approval"], 0o700),
                "publisher": (users["publisher"], groups["publisher"], 0o700),
                "owner-ui": (users["owner_ui"], groups["owner_ui"], 0o700),
                "consent-ipc": (users["approval"], groups["consent_clients"], 0o2750),
                "publisher-ipc": (users["publisher"], groups["publisher_clients"], 0o2750),
            }
            for dirname, expected in state_expected.items():
                info = by_name[dirname].lstat()
                self.assertTrue(stat.S_ISDIR(info.st_mode))
                self.assertEqual(
                    (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)), expected
                )

            child_code = r"""
import json, os, sys, tempfile
spec = json.loads(sys.argv[1])
own = spec["own"]
directories = spec["directories"]
sentinels = spec["sentinels"]
assert os.listdir(own)
with open(sentinels[own], "rb") as stream:
    assert stream.read() == own.rsplit("/", 1)[-1].encode("ascii")
for directory in directories:
    sentinel = sentinels[directory]
    if directory == own:
        assert os.path.isdir(directory)
        with open(sentinel, "rb") as stream:
            assert stream.read() == directory.rsplit("/", 1)[-1].encode("ascii")
    else:
        try:
            os.listdir(directory)
        except PermissionError:
            pass
        else:
            raise AssertionError("service traversed another service config directory")
        try:
            open(sentinel, "rb").close()
        except PermissionError:
            pass
        else:
            raise AssertionError("service read another service config file")
    attacker = os.path.join(directory, "attacker.json")
    try:
        fd = os.open(attacker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    except PermissionError:
        pass
    else:
        raise AssertionError("service created an entry in root-managed config")
    try:
        os.unlink(sentinel)
    except PermissionError:
        pass
    else:
        raise AssertionError("service removed a root-managed config file")
    fd, replacement = tempfile.mkstemp(dir="/tmp")
    os.write(fd, b"attacker")
    os.close(fd)
    try:
        os.replace(replacement, sentinel)
    except PermissionError:
        os.unlink(replacement)
    else:
        raise AssertionError("service replaced a root-managed config file")
"""
            config_dirs = [str(by_name[name]) for name in config_groups]
            sentinel_paths = {str(by_name[name]): str(sentinels[name]) for name in config_groups}
            for service, uid, gid, own_name in (
                ("approval", users["approval"], groups["approval"], "approval-config"),
                ("publisher", users["publisher"], groups["publisher"], "publisher-config"),
                ("owner_ui", users["owner_ui"], groups["owner_ui"], "owner-ui-config"),
            ):
                spec = json.dumps({
                    "own": str(by_name[own_name]),
                    "directories": config_dirs,
                    "sentinels": sentinel_paths,
                })
                result = subprocess.run(
                    [sys.executable, "-I", "-c", child_code, spec],
                    capture_output=True, text=True, timeout=10,
                    preexec_fn=lambda uid=uid, gid=gid: (
                        os.setgroups([]), os.setgid(gid), os.setuid(uid)
                    ),
                )
                self.assertEqual(
                    result.returncode, 0,
                    f"{service} UID/GID boundary failed: {result.stderr or result.stdout}",
                )

            for dirname, sentinel in sentinels.items():
                self.assertTrue(sentinel.is_file(), dirname)
                self.assertEqual(sentinel.read_bytes(), dirname.encode("ascii"))
                self.assertFalse((by_name[dirname] / "attacker.json").exists())

    def test_missing_account_is_detected_before_any_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o711)
            def uid_for(name):
                if name == "publisher":
                    raise KeyError(name)
                return os.getuid()
            with self.assertRaises(KeyError):
                provision_layout(root, uid_for=uid_for, gid_for=lambda _: os.getgid(),
                                 root_uid=os.getuid(), root_gid=os.getgid())
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
