"""Offline tests for isolated Artesao build executor; never run Docker or npm."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import artesao_isolated_executor as executor


class IsolatedBuilderTests(unittest.TestCase):
    SHA = "a" * 40
    VERSION = "0.2.0-dev.29"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, data):
        dest = self.root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, (dict, list)):
            data = json.dumps(data) + "\n"
        if isinstance(data, str):
            data = data.encode()
        dest.write_bytes(data)
        return dest

    def sums(self, folder, paths):
        lines = [hashlib.sha256((folder / name).read_bytes()).hexdigest() +
                 "  " + name for name in paths]
        (folder / "SHA256SUMS").write_text("\n".join(lines) + "\n")

    def test_checksum_valid_and_mismatch(self):
        folder = self.root / "bundle"
        folder.mkdir()
        (folder / "a").write_text("hello")
        self.sums(folder, ["a"])
        self.assertEqual(executor.verify_sums(folder), 1)
        (folder / "a").write_text("tampered")
        with self.assertRaisesRegex(executor.ExecutorBlocked, "CHECKSUM_MISMATCH"):
            executor.verify_sums(folder)

    def test_checksum_missing_entry_and_root_archive_list(self):
        folder = self.root / "bundle"
        folder.mkdir()
        (folder / "a").write_text("hello")
        (folder / "b").write_text("unlisted")
        self.sums(folder, ["a"])
        with self.assertRaisesRegex(executor.ExecutorBlocked, "CHECKSUM_LIST_INCOMPLETE"):
            executor.verify_sums(folder)
        self.assertEqual(executor.verify_sums(folder, require_complete=False), 1)

    def test_checksum_traversal_symlink_and_duplicate_rejected(self):
        folder = self.root / "bundle"
        folder.mkdir()
        (folder / "a").write_text("hello")
        digest = hashlib.sha256(b"hello").hexdigest()
        line = digest + "  "
        for record in (line+"../secret\n", line+"/etc/passwd\n",
                       line+"a\n"+line+"a\n"):
            (folder / "SHA256SUMS").write_text(record)
            with self.assertRaises(executor.ExecutorBlocked):
                executor.verify_sums(folder)
        (folder / "SHA256SUMS").write_text(line+"a\n")
        (folder / "alias").symlink_to(folder / "a")
        with self.assertRaisesRegex(executor.ExecutorBlocked, "CHECKSUM_SYMLINK"):
            executor.verify_sums(folder)

    def good_receipt(self):
        return {"sourceCommit": self.SHA, "status": "passed",
                "checks": [{"name": key, "status": "passed"} for key in
                           ("build", "application-tests",
                            "distribution-helper", "operations")],
                "schemaChecksums": {scope: [{"version": 1, "name": scope, "checksum": "c"*64}] for scope in ("tenant", "control", "interest", "support", "legal")},
                "physicalValidation": "not-performed"}

    def test_receipt_requires_real_exact_sha_and_checks(self):
        path = self.write("receipt.json", self.good_receipt())
        result = executor.verify_receipt(path, self.SHA)
        self.assertEqual(len(result["sha256"]), 64)
        with self.assertRaisesRegex(executor.ExecutorBlocked, "RECEIPT_SOURCE_OR_STATUS"):
            executor.verify_receipt(path, "b" * 40)
        for change in ({"status": "failed"}, {"checks": []},
                       {"schemaChecksums": {}}, {"physicalValidation": "passed"}):
            changed = dict(self.good_receipt(), **change)
            self.write("receipt.json", changed)
            with self.assertRaises(executor.ExecutorBlocked):
                executor.verify_receipt(path, self.SHA)

    def test_release_checks_ha_and_debian_architectures(self):
        common = {"sourceCommit": self.SHA, "releaseVersion": self.VERSION,
                  "validation": {"sourceCommit": self.SHA, "status": "passed"},
                  "schemaChecksums": {"tenant": []}}
        ha = {**common, "distribution": "home-assistant",
              "packageKind": "home-assistant-precompiled-aarch64",
              "architecture": "linux/arm64", "runtimeSourceCommit": self.SHA,
              "addonSlug": "artesaos_piloto"}
        path = self.write("release.json", ha)
        self.assertEqual(executor.verify_package_release(
            path, self.SHA, self.VERSION, "home-assistant"), ha)
        ha["architecture"] = "linux/amd64"
        self.write("release.json", ha)
        with self.assertRaisesRegex(executor.ExecutorBlocked, "HA_RUNTIME_OR_ARCH"):
            executor.verify_package_release(path, self.SHA, self.VERSION, "home-assistant")
        debian = {**common, "distribution": "debian",
                  "packageKind": "compose-with-image",
                  "imageArchitecture": "linux/amd64",
                  "imageSourceCommit": self.SHA,
                  "imageArchiveSha256": "b" * 64}
        self.write("release.json", debian)
        self.assertEqual(executor.verify_package_release(
            path, self.SHA, self.VERSION, "debian"), debian)
        debian["imageArchitecture"] = "linux/arm64"
        self.write("release.json", debian)
        with self.assertRaisesRegex(executor.ExecutorBlocked, "DEBIAN_RUNTIME_OR_ARCH"):
            executor.verify_package_release(path, self.SHA, self.VERSION, "debian")

    def good_policy(self):
        return {"kind": "factory-runner-disposable-builder-v1",
                "host_role": "dedicated_disposable_vm",
                "network_policy": "blocked_external",
                "production_access": False,
                "docker_endpoint": "unix:///var/run/docker.sock",
                "source_repository": "mmcromero/fabricacao_e_orcamentos",
                "expected_source_sha": self.SHA,
                "expected_version": self.VERSION,
                "npm_cache": "/var/cache/factory-runner/npm"}

    def test_builder_rejects_missing_policy_and_root(self):
        source = self.root / "source"
        dist = self.root / "dist"
        source.mkdir()
        dist.mkdir()
        out = self.root / "result"
        policy = self.write("policy.json", self.good_policy())
        with patch.object(executor.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(executor.ExecutorBlocked, "DEDICATED_NON_ROOT"):
                executor.isolated_builder_preflight(source, dist, out, policy, self.SHA, self.VERSION)
        with patch.object(executor.os, "geteuid", return_value=12345):
            wrong = dict(self.good_policy(), network_policy="online")
            self.write("policy.json", wrong)
            with self.assertRaisesRegex(executor.ExecutorBlocked, "BUILDER_POLICY_NOT_APPROVED"):
                executor.isolated_builder_preflight(source, dist, out, policy)

    def plan_report(self):
        return {"blocking_errors": [], "candidate_version": self.VERSION,
                "public_sha": "b"*40, "source_sha": self.SHA,
                "errors": ["VALIDATION_RECEIPT_NOT_VERIFIED"]}

    def test_plan_never_executes_or_writes(self):
        source = self.root / "source"
        dist = self.root / "dist"
        out = self.root / "result"
        with (patch.object(executor, "_checked_profile", return_value={}),
              patch.object(executor, "evaluate_artesao",
                           return_value=self.plan_report()),
              patch.object(executor, "_run", side_effect=AssertionError("execution forbidden")),
              patch.object(executor, "_docker", side_effect=AssertionError("docker forbidden"))):
            plan = executor.build(source, dist, self.root / "profile.json",
                                  self.SHA, out, None, execute=False)
        self.assertEqual(plan["state"], "PLAN_ONLY")
        self.assertFalse(out.exists())

    def test_blocking_policy_prevents_every_stage(self):
        blocked = dict(self.plan_report(), blocking_errors=[
            "VERSION_ALREADY_PUBLISHED_WITH_DIFFERENT_SOURCE"])
        with (patch.object(executor, "_checked_profile", return_value={}),
              patch.object(executor, "evaluate_artesao", return_value=blocked),
              patch.object(executor, "_run", side_effect=AssertionError("run forbidden"))):
            with self.assertRaisesRegex(executor.ExecutorBlocked, "SOURCE_RELEASE_POLICY_BLOCKED"):
                executor.build(self.root / "source", self.root / "dist",
                               self.root / "profile.json", self.SHA,
                               self.root / "new", None, execute=True)
        self.assertFalse((self.root / "new").exists())

    def test_missing_builder_policy_denies_execute(self):
        with (patch.object(executor, "_checked_profile", return_value={}),
              patch.object(executor, "evaluate_artesao",
                           return_value=self.plan_report())):
            with self.assertRaisesRegex(executor.ExecutorBlocked, "ISOLATED_BUILDER_POLICY_REQUIRED"):
                executor.build(self.root / "source", self.root / "dist",
                               self.root / "profile.json", self.SHA,
                               self.root / "new", None, execute=True)


    def test_relative_paths_are_rejected_before_profile_load(self):
        with patch.object(executor, "_checked_profile",
                          side_effect=AssertionError("must not read profile")):
            with self.assertRaisesRegex(executor.ExecutorBlocked,
                                        "ABSOLUTE_PATHS_REQUIRED"):
                executor.build(Path("source"), self.root / "dist",
                               self.root / "profile.json", self.SHA,
                               self.root / "new", None, execute=False)

    def test_builder_checkout_head_mismatch_does_not_create_output(self):
        source = self.root / "source"
        source.mkdir()
        dist = self.root / "dist"
        dist.mkdir()
        output = self.root / "new"
        with (patch.object(executor, "_checked_profile", return_value={}),
              patch.object(executor, "evaluate_artesao",
                           return_value=self.plan_report()),
              patch.object(executor, "isolated_builder_preflight"),
              patch.object(executor, "_run", return_value=b"b"*40)):
            with self.assertRaisesRegex(executor.ExecutorBlocked,
                                        "BUILDER_CHECKOUT_SHA_MISMATCH"):
                executor.build(source, dist, self.root / "profile.json",
                               self.SHA, output, self.root / "policy.json",
                               execute=True)
        self.assertFalse(output.exists())

    def test_ignored_source_files_refuse_build(self):
        source = self.root / "source"
        source.mkdir()
        dist = self.root / "dist"
        dist.mkdir()
        output = self.root / "new"
        with (patch.object(executor, "_checked_profile", return_value={}),
              patch.object(executor, "evaluate_artesao",
                           return_value=self.plan_report()),
              patch.object(executor, "isolated_builder_preflight"),
              patch.object(executor, "_run",
                           side_effect=[self.SHA.encode(), b"!! node_modules\x00"])):
            with self.assertRaisesRegex(executor.ExecutorBlocked,
                                        "SOURCE_CHECKOUT_NOT_CLEAN"):
                executor.build(source, dist, self.root / "profile.json",
                               self.SHA, output, self.root / "policy.json",
                               execute=True)
        self.assertFalse(output.exists())

    def test_policy_bound_to_source_and_version(self):
        source = self.root / "source"
        source.mkdir()
        dist = self.root / "dist"
        dist.mkdir()
        output = self.root / "new"
        policy = self.good_policy()
        policy["expected_source_sha"] = "b"*40
        path = self.write("policy.json", policy)
        with patch.object(executor.os, "geteuid", return_value=12345):
            with self.assertRaisesRegex(executor.ExecutorBlocked,
                                        "BUILDER_POLICY_NOT_APPROVED"):
                executor.isolated_builder_preflight(
                    source, dist, output, path, self.SHA, self.VERSION)


    def test_preexisting_builder_docker_tag_is_never_overwritten(self):
        from unittest.mock import patch as mock_patch
        def docker_fake(args, **kwargs):
            if args[0] == "version":
                return b"27.0"
            if args[0] == "image":
                return b"artesao-digital:0.2.0-dev.29\n"
            raise AssertionError("unapproved Docker command")
        with mock_patch.object(executor, "_docker", side_effect=docker_fake):
            with self.assertRaisesRegex(executor.ExecutorBlocked,
                                        "BUILDER_IMAGE_TAG_ALREADY_EXISTS"):
                executor._ensure_docker_tags_free(
                    "artesao-digital-ha:0.2.0-dev.29",
                    "artesao-digital:0.2.0-dev.29", self.root)

    def test_failed_first_stage_writes_incomplete_marker_not_success(self):
        source = self.root / "source"
        (source / "apps/umdoislab").mkdir(parents=True)
        dist = self.root / "dist"
        dist.mkdir()
        output = self.root / "new"
        with (patch.object(executor, "_checked_profile", return_value={}),
              patch.object(executor, "evaluate_artesao",
                           return_value=self.plan_report()),
              patch.object(executor, "isolated_builder_preflight"),
              patch.object(executor, "_ensure_docker_tags_free"),
              patch.object(executor, "_run", side_effect=[
                  self.SHA.encode(), b"", executor.ExecutorBlocked("BUILDER_STAGE_FAILED")
              ])):
            with self.assertRaisesRegex(executor.ExecutorBlocked, "BUILDER_STAGE_FAILED"):
                executor.build(source, dist, self.root / "profile.json",
                               self.SHA, output, self.root / "policy.json",
                               execute=True)
        self.assertTrue((output / "INCOMPLETE-NOT-FOR-PUBLICATION").is_file())
        self.assertFalse((output / "FACTORY_ARTESAO_BUILD_REPORT.json").exists())


if __name__ == "__main__":
    unittest.main()
