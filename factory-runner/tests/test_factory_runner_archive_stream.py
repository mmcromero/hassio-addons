"""Security tests for the trusted bounded archive-stream validator."""
import io
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import archive_stream as module


def archive(members, format=tarfile.USTAR_FORMAT):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=format) as tar:
        for info, payload in members:
            tar.addfile(info, io.BytesIO(payload) if payload is not None else None)
    return output.getvalue()


def file_member(name, payload=b"data", mode=0o777):
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = mode
    info.uid = 0
    info.gid = 0
    return info, payload


def dir_member(name):
    info = tarfile.TarInfo(name.rstrip("/") + "/")
    info.type = tarfile.DIRTYPE
    info.size = 0
    return info, None


class ArchiveStreamTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / "candidate"

    def validate(self, data, **kwargs):
        options = {
            "allowed_paths": ["pkg/a.txt"],
            "required_paths": ["pkg/a.txt"],
            "max_files": 10,
            "max_file_bytes": 64,
            "max_total_bytes": 128,
            "max_archive_bytes": 16384,
            "max_elapsed_seconds": 5,
        }
        options.update(kwargs)
        return module.validate_and_extract_tar(io.BytesIO(data), self.target, **options)

    def test_valid_archive_extracts_allowlisted_files_and_hashes(self):
        data = archive([
            (dir_member("pkg"), None),
            file_member("pkg/a.txt", b"alpha"),
            file_member("pkg/bin.sh", b"#!/bin/sh\necho safe\n", 0o777),
        ])
        result = self.validate(
            data,
            allowed_paths=["pkg/a.txt", "pkg/bin.sh"],
            required_paths=["pkg/a.txt", "pkg/bin.sh"],
            executable_paths=["pkg/bin.sh"],
        )
        self.assertEqual(result["state"], "VALIDATED_NOT_PUBLISHED")
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["total_bytes"], len(b"alpha") + len(b"#!/bin/sh\necho safe\n"))
        self.assertEqual((self.target / "pkg/a.txt").read_bytes(), b"alpha")
        self.assertEqual((self.target / "pkg/bin.sh").read_bytes(), b"#!/bin/sh\necho safe\n")
        self.assertEqual((self.target / "pkg/a.txt").stat().st_mode & 0o777, 0o644)
        self.assertEqual((self.target / "pkg/bin.sh").stat().st_mode & 0o777, 0o755)
        self.assertEqual(len(result["archive_sha256"]), 64)

    def test_archive_owner_and_mode_are_not_trusted(self):
        data = archive([file_member("pkg/a.txt", b"safe", 0o777)])
        self.validate(data)
        self.assertEqual((self.target / "pkg/a.txt").stat().st_mode & 0o777, 0o644)

    def test_absolute_path_rejected(self):
        data = archive([file_member("/etc/passwd", b"x")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "unsafe_archive_path"):
            self.validate(data, allowed_paths=["/etc/passwd"], required_paths=[])

    def test_parent_traversal_rejected(self):
        data = archive([file_member("pkg/../escape", b"x")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "unsafe_archive_path"):
            self.validate(data, allowed_paths=["pkg/../escape"], required_paths=[])

    def test_backslash_and_windows_drive_paths_rejected(self):
        for name in ("pkg\\escape", "C:/escape"):
            with self.subTest(name=name):
                data = archive([file_member(name, b"x")])
                with self.assertRaises(module.ArchiveStreamError):
                    self.validate(data, allowed_paths=[name], required_paths=[])

    def test_symlink_rejected_and_partial_stage_removed(self):
        link = tarfile.TarInfo("pkg/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "a.txt"
        data = archive([file_member("pkg/a.txt", b"ok"), (link, None)])
        with self.assertRaisesRegex(module.ArchiveStreamError, "archive_links_not_allowed"):
            self.validate(data, allowed_paths=["pkg/a.txt", "pkg/link"], required_paths=[])
        self.assertFalse(self.target.exists())

    def test_hardlink_rejected(self):
        link = tarfile.TarInfo("pkg/link")
        link.type = tarfile.LNKTYPE
        link.linkname = "pkg/a.txt"
        data = archive([(link, None)])
        with self.assertRaises(module.ArchiveStreamError):
            self.validate(data, allowed_paths=["pkg/link"], required_paths=[])

    def test_fifo_and_other_special_files_rejected(self):
        fifo = tarfile.TarInfo("pkg/pipe")
        fifo.type = tarfile.FIFOTYPE
        data = archive([(fifo, None)])
        with self.assertRaises(module.ArchiveStreamError):
            self.validate(data, allowed_paths=["pkg/pipe"], required_paths=[])

    def test_unapproved_file_rejected(self):
        data = archive([file_member("pkg/extra.txt", b"x")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "unapproved_archive_file"):
            self.validate(data)

    def test_required_file_must_be_present(self):
        data = archive([file_member("pkg/b.txt", b"x")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "required_archive_file_missing"):
            self.validate(data, allowed_paths=["pkg/a.txt", "pkg/b.txt"], required_paths=["pkg/a.txt"])

    def test_duplicate_file_rejected(self):
        data = archive([file_member("pkg/a.txt", b"one"), file_member("pkg/a.txt", b"two")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "duplicate_or_conflicting"):
            self.validate(data)

    def test_file_directory_collision_rejected(self):
        data = archive([file_member("pkg/a", b"x"), file_member("pkg/a/b", b"y")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "archive_path_collision"):
            self.validate(data, allowed_paths=["pkg/a", "pkg/a/b"], required_paths=[])

    def test_directory_must_be_parent_of_allowlisted_file(self):
        data = archive([dir_member("pkg/unused"), file_member("pkg/a.txt", b"x")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "unapproved_archive_directory"):
            self.validate(data)

    def test_file_size_budget(self):
        data = archive([file_member("pkg/a.txt", b"x" * 65)])
        with self.assertRaisesRegex(module.ArchiveStreamError, "archive_file_budget_exceeded"):
            self.validate(data)

    def test_total_size_budget(self):
        data = archive([file_member("pkg/a.txt", b"x" * 64), file_member("pkg/b.txt", b"y" * 64)])
        with self.assertRaisesRegex(module.ArchiveStreamError, "archive_total_budget_exceeded"):
            self.validate(data, allowed_paths=["pkg/a.txt", "pkg/b.txt"], required_paths=[], max_total_bytes=127)

    def test_file_count_budget(self):
        data = archive([file_member("pkg/a.txt", b"a"), file_member("pkg/b.txt", b"b")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "archive_file_count_exceeded"):
            self.validate(data, allowed_paths=["pkg/a.txt", "pkg/b.txt"], required_paths=[], max_files=1)

    def test_member_count_budget_includes_directories(self):
        data = archive([dir_member("pkg"), file_member("pkg/a.txt", b"x")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "archive_member_count_exceeded"):
            self.validate(data, max_members=1)

    def test_path_depth_budget(self):
        name = "pkg/" + "/".join(["a"] * 32)
        data = archive([file_member(name, b"x")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "unsafe_archive_path"):
            self.validate(data, allowed_paths=[name], required_paths=[])

    def test_archive_byte_budget(self):
        data = archive([file_member("pkg/a.txt", b"alpha")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "archive_byte_budget_exceeded"):
            self.validate(data, max_archive_bytes=len(data) - 1)

    def test_nonzero_trailing_data_rejected(self):
        data = archive([file_member("pkg/a.txt", b"alpha")]) + b"UNEXPECTED"
        with self.assertRaisesRegex(module.ArchiveStreamError, "nonzero_archive_trailing_data"):
            self.validate(data)

    def test_malformed_archive_rejected(self):
        with self.assertRaises(module.ArchiveStreamError):
            self.validate(b"not a tar archive")

    def test_setuid_mode_rejected(self):
        data = archive([file_member("pkg/a.txt", b"x", 0o4755)])
        with self.assertRaisesRegex(module.ArchiveStreamError, "unsafe_archive_mode"):
            self.validate(data)

    def test_pax_metadata_rejected(self):
        info = tarfile.TarInfo("pkg/a.txt")
        info.size = 1
        info.pax_headers = {"path": "pkg/a.txt"}
        data = archive([(info, b"x")], format=tarfile.PAX_FORMAT)
        with self.assertRaisesRegex(module.ArchiveStreamError, "unsupported_archive_metadata"):
            self.validate(data)

    def test_output_directory_must_be_new(self):
        self.target.mkdir()
        (self.target / "keep").write_text("preserve")
        data = archive([file_member("pkg/a.txt", b"x")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "archive_output_already_exists"):
            self.validate(data)
        self.assertEqual((self.target / "keep").read_text(), "preserve")

    def test_symlink_output_parent_rejected(self):
        real = self.root / "real"
        real.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(real, target_is_directory=True)
        target = alias / "candidate"
        data = archive([file_member("pkg/a.txt", b"x")])
        with self.assertRaisesRegex(module.ArchiveStreamError, "symlink_archive_output_parent"):
            module.validate_and_extract_tar(
                io.BytesIO(data), target, allowed_paths=["pkg/a.txt"],
                required_paths=["pkg/a.txt"], max_archive_bytes=16384)

    def test_sensitive_paths_rejected_even_if_allowlisted(self):
        for name in ("pkg/.env", "pkg/.git/config", "pkg/options.json"):
            with self.subTest(name=name):
                data = archive([file_member(name, b"x")])
                with self.assertRaises(module.ArchiveStreamError):
                    self.validate(data, allowed_paths=[name], required_paths=[])

    def test_elapsed_budget_checked_between_reads(self):
        data = archive([file_member("pkg/a.txt", b"x")])
        with patch.object(module.time, "monotonic", side_effect=[0, 2]):
            with self.assertRaisesRegex(module.ArchiveStreamError, "archive_elapsed_budget_exceeded"):
                self.validate(data, max_elapsed_seconds=1)


if __name__ == "__main__":
    unittest.main()
