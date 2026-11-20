"""Offline real Git checkout provisioning with trusted, injected local remotes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import workspace_sync as sync


@unittest.skipIf(os.geteuid() == 0, "non-root tests also run as runner in Docker validation")
class WorkspaceSyncTests(unittest.TestCase):
    def git(self, path, *args):
        return subprocess.check_output(["git", "-C", str(path), *args], text=True,
            stderr=subprocess.DEVNULL, env={"PATH":"/usr/bin:/bin", "HOME":"/nonexistent",
               "GIT_CONFIG_NOSYSTEM":"1", "GIT_CONFIG_GLOBAL":os.devnull}).strip()

    def setup_repo(self, name):
        target = self.root / name
        target.mkdir()
        self.git(target, "init", "-q", "-b", "main")
        return target

    def put(self, root, path, content):
        dest = root / path
        dest.parent.mkdir(exist_ok=True, parents=True)
        dest.write_text(content)

    def commit(self, repo, msg):
        self.git(repo, "add", ".")
        self.git(repo, "-c", "user.name=Fixture", "-c", "user.email=x@invalid.test",
                 "commit", "-qm", msg)
        return self.git(repo, "rev-parse", "HEAD")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.setup_repo("source")
        self.dist = self.setup_repo("distribution")
        self.put(self.source, "scripts/export.py", "raise Exception('NEVER EXECUTE')\n")
        self.put(self.source, "policy.json", json.dumps({"schema_version":1,
            "product":"Fixture", "active_package":{"status":"open", "candidate_version":"0.1.1",
            "branches":{"fixture/source":"release/rc"}}}))
        self.put(self.source, "package.json", '{"version":"0.1.1"}\n')
        self.put(self.source, "config.yaml", 'version: "0.1.1"\n')
        self.source_sha = self.commit(self.source, "source")
        self.git(self.source, "branch", "desenvolvimento")
        self.git(self.source, "branch", "release/rc")
        self.exporter_sha = self.git(self.source, "rev-parse", "HEAD:scripts/export.py")
        self.put(self.dist, "demo/SOURCE_PROVENANCE.json", json.dumps({"commit":"1"*40, "version":"0.1.0"}))
        self.public_sha = self.commit(self.dist, "dist")
        self.projects=self.root/"projects"; self.projects.mkdir()
        self.workspaces=self.root/"workspaces"; self.workspaces.mkdir()
        self.profile={"schema_version":1,"id":"fixture","product":"Fixture",
            "source_repo":"fixture/source","distribution_repo":"fixture/catalog",
            "source_ref":"refs/remotes/origin/desenvolvimento",
            "rc_ref":"refs/remotes/origin/release/rc",
            "public_ref":"refs/remotes/origin/main",
            "package_policy_path":"policy.json","package_json_path":"package.json",
            "manifest_path":"config.yaml","provenance_path":"demo/SOURCE_PROVENANCE.json",
            "distribution_prefix":"demo/", "exporter_path":"scripts/export.py",
            "exporter_git_blob_sha": self.exporter_sha,
            "allowed_shared_paths":[], "declarative_mapping":{"demo/config.yaml":"config.yaml","demo/package.json":"package.json"}}
        (self.projects/"fixture.json").write_text(json.dumps(self.profile))

    def fake_remote(self, repo, ref, token):
        if repo == "fixture/source":
            return self.git(self.source,"rev-parse", "refs/heads/desenvolvimento")
        return self.git(self.dist,"rev-parse", "refs/heads/main")

    def fake_clone(self, repo, dest, token):
        base = self.source if repo == "fixture/source" else self.dist
        subprocess.run(["git", "clone", "-q", "--no-checkout", str(base), str(dest)],check=True)
        self.git(dest, "remote", "set-url", "origin", "https://github.com/"+repo+".git")

    def run_sync(self):
        return sync.synchronize("fixture", token="notlogged", projects_dir=self.projects,
            workspaces_dir=self.workspaces, remote_head=self.fake_remote, clone=self.fake_clone)

    def test_new_sync_has_real_refs_and_preflight(self):
        r=self.run_sync()
        self.assertEqual(r["state"],"SYNCED")
        self.assertTrue(r["eligible"],r)
        self.assertEqual(r["source_sha"],self.source_sha)
        self.assertTrue((self.workspaces/"fixture"/"source"/".git").is_dir())
        self.assertEqual([x.name for x in (self.workspaces/"fixture"/"source").iterdir()], [".git"])
        self.assertEqual(len(list(self.workspaces.glob(".stage-*"))),0)

    def test_repeat_same_sha_is_idempotent_no_reclone(self):
        self.run_sync()
        with patch.object(sync, "_clone", side_effect=AssertionError("unexpected clone")):
            r=self.run_sync()
        self.assertEqual(r["state"],"UNCHANGED")
        self.assertFalse(list(self.workspaces.glob(".archive-*")))

    def test_updated_source_archives_without_overwrite(self):
        self.run_sync()
        (self.source/"change.txt").write_text("changed")
        self.commit(self.source,"next")
        self.git(self.source,"branch","-f","desenvolvimento","main")
        r=self.run_sync()
        self.assertEqual(r["state"],"SYNCED")
        self.assertEqual(len(list(self.workspaces.glob(".archive-fixture-*"))),1)
        old=next(self.workspaces.glob(".archive-fixture-*"))
        self.assertEqual(json.loads((old/sync.MANAGED).read_text())["source_sha"],self.source_sha)

    def test_unmanaged_directory_is_preserved(self):
        work=self.workspaces/"fixture"; work.mkdir()
        (work/"personal.txt").write_text("preserve")
        with self.assertRaisesRegex(sync.SyncError,"unmanaged_workspace_preserved"):
            self.run_sync()
        self.assertEqual((work/"personal.txt").read_text(),"preserve")

    def test_moved_remote_head_does_not_adopt_stage(self):
        def wrong_sha(repo,ref,token):
            return "0"*40 if repo=="fixture/source" else self.public_sha
        with self.assertRaisesRegex(sync.SyncError,"source_head_moved"):
            sync.synchronize("fixture",token="hidden",projects_dir=self.projects,
                workspaces_dir=self.workspaces,remote_head=wrong_sha,clone=self.fake_clone)
        self.assertFalse((self.workspaces/"fixture").exists())
        self.assertFalse(list(self.workspaces.glob(".stage-*")))

    def test_missing_token_never_leaks_through_clone(self):
        with patch.object(sync.subprocess, "run") as invoke:
            invoke.return_value.returncode=1
            with self.assertRaisesRegex(sync.SyncError,"clone_unavailable"):
                sync._clone("fixture/source",self.root/"new", "very-secret-value")
            self.assertNotIn("very-secret-value",str(invoke.call_args))

    def test_reject_malicious_repository_or_branch(self):
        for name in ("https://evil/gh", "foo/../../bar", "foo;ls/bar"):
            with self.assertRaises(sync.SyncError):
                sync._clone(name, self.root/"new", "token")
        for ref in ("refs/remotes/origin/../main","refs/remotes/origin/a//b","refs/heads/main"):
            with self.assertRaises(sync.SyncError):
                sync._branch(ref)

    def test_closed_package_may_sync_but_never_prepare(self):
        self.put(self.source,"policy.json",json.dumps({"schema_version":1,"product":"Fixture",
            "active_package":{"status":"closed","candidate_version":"0.1.1",
                "branches":{"fixture/source":"release/rc"}}}))
        self.commit(self.source,"closed")
        self.git(self.source,"branch","-f","desenvolvimento","main")
        self.git(self.source,"branch","-f","release/rc","main")
        r=self.run_sync()
        self.assertFalse(r["eligible"])
        self.assertIn("NO_OPEN_PACKAGE",r["errors"])

if __name__=="__main__": unittest.main()