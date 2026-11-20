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

    def test_synchronized_git_checkout_prepares_local_bundle(self):
        import server
        result = self.run_sync()
        self.assertTrue(result["eligible"])
        before = {"source": self.git(self.source,"rev-parse","HEAD"),
                  "dist": self.git(self.dist,"rev-parse","HEAD")}
        with (patch.object(server,"PROJECTS_DIR",self.projects),
              patch.object(server,"WORKSPACES_DIR",self.workspaces),
              patch.object(server,"PREPARATIONS_DIR",self.root/"preparations")):
            prepared = server.prepare_project("fixture", result["source_sha"], "fixture-op")
        self.assertTrue(prepared["eligible"])
        self.assertFalse(prepared["published"])
        self.assertEqual(prepared["state"],"PREPARED_NOT_PUBLISHED")
        self.assertEqual(prepared["method"],"declarative_no_script")
        output=next((self.root/"preparations").iterdir())
        provenance=json.loads((output/"demo/SOURCE_PROVENANCE.json").read_text())
        self.assertEqual(len(provenance["files"]),2)
        self.assertEqual(provenance["commit"],result["source_sha"])
        self.assertEqual(self.git(self.source,"rev-parse","HEAD"),before["source"])
        self.assertEqual(self.git(self.dist,"rev-parse","HEAD"),before["dist"])

    def test_repeat_same_sha_is_idempotent_no_reclone(self):
        self.run_sync()
        def fail_clone(*args):
            raise AssertionError("unexpected clone on identical pinned SHAs")
        r = sync.synchronize("fixture", token="notlogged", projects_dir=self.projects,
            workspaces_dir=self.workspaces, remote_head=self.fake_remote, clone=fail_clone)
        self.assertEqual(r["state"],"UNCHANGED")
        self.assertFalse(list(self.workspaces.glob(".archive-*")))

    def test_unrelated_public_catalog_update_reuses_verified_snapshot(self):
        original = self.run_sync()
        self.assertEqual(original["state"], "SYNCED")
        # Already at the maximum retention cap. Unrelated catalog updates
        # must not require deleting a snapshot or adding a fifth archive.
        for i in range(sync.MAX_ARCHIVES):
            (self.workspaces / (".archive-fixture-" + str(i))).mkdir()
        # Public head advances outside the approved project's distribution
        # scope. A closed package must not create another large snapshot.
        with (patch.object(sync, "_public_scope_unchanged", return_value=True),
              patch.object(sync, "_verified_profile_report", return_value={
                  "eligible_for_preparation": False, "errors": ["NO_OPEN_PACKAGE"]
              })):
            result = sync.synchronize(
                "fixture", token="notlogged", projects_dir=self.projects,
                workspaces_dir=self.workspaces,
                remote_head=lambda repo, ref, token: (
                    self.source_sha if repo == "fixture/source" else "b" * 40),
                clone=lambda *args: self.fail("unexpected clone"))
        self.assertEqual(result["state"], "UNCHANGED_SCOPE")
        self.assertEqual(result["public_sha"], self.public_sha)
        self.assertEqual(result["remote_public_sha"], "b" * 40)
        self.assertFalse(result["eligible"])
        self.assertIn("PUBLIC_HEAD_OUTSIDE_APPROVED_SCOPE", result["errors"])
        self.assertEqual(len(list(self.workspaces.glob(".archive-*"))),
                         sync.MAX_ARCHIVES)

    def test_updated_public_scope_must_archive_or_block_not_skip(self):
        self.run_sync()
        with patch.object(sync, "_public_scope_unchanged", return_value=False):
            for i in range(sync.MAX_ARCHIVES):
                (self.workspaces / (".archive-fixture-" + str(i))).mkdir()
            with self.assertRaisesRegex(sync.SyncError, "workspace_archive_limit"):
                sync.synchronize(
                    "fixture", token="notlogged", projects_dir=self.projects,
                    workspaces_dir=self.workspaces,
                    remote_head=lambda repo, ref, token: (
                        self.source_sha if repo == "fixture/source" else "b" * 40),
                    clone=lambda *args: self.fail("must block before clone"))
        self.assertEqual(len(list(self.workspaces.glob(".archive-*"))),
                         sync.MAX_ARCHIVES)

    def test_unrelated_catalog_fast_path_never_releases_eligible_package(self):
        self.run_sync()
        with (patch.object(sync, "_public_scope_unchanged", return_value=True),
              patch.object(sync, "_verified_profile_report", return_value={
                  "eligible_for_preparation": True, "errors": []
              }),
              patch.object(sync, "_clone", side_effect=AssertionError("not used"))):
            # Reaches the standard clone path; deliberately do not bypass
            # the fresh public checkout when a package is eligible.
            with self.assertRaisesRegex(sync.SyncError, "workspace_archive_limit"):
                for i in range(sync.MAX_ARCHIVES):
                    (self.workspaces / (".archive-fixture-" + str(i))).mkdir()
                sync.synchronize(
                    "fixture", token="notlogged", projects_dir=self.projects,
                    workspaces_dir=self.workspaces,
                    remote_head=lambda repo, ref, token: (
                        self.source_sha if repo == "fixture/source" else "b" * 40),
                    clone=lambda *args: self.fail("must block before clone"))

    def test_public_scope_compare_requires_ancestry_and_unrelated_files(self):
        original = "a" * 40
        incoming = "b" * 40
        self.profile["distribution_prefix"] = "demo/"
        self.profile["allowed_shared_paths"] = [".github/workflows/demo.yml"]
        def fake_reply(changed, status="ahead", behind=0, merge=None):
            class Reply:
                status = 200
                def __enter__(self): return self
                def __exit__(self, *args): return None
                def read(self, *args):
                    return json.dumps({
                        "status": status, "behind_by": behind,
                        "merge_base_commit": {"sha": merge or original},
                        "files": [{"filename": name} for name in changed],
                    }).encode()
            return Reply()
        with patch.object(sync.request, "build_opener") as build:
            build.return_value.open.return_value = fake_reply(["instagram-central/config.yaml"])
            self.assertTrue(sync._public_scope_unchanged(self.profile, original, incoming))
            for modified in (["demo/config.yaml"],
                             [".github/workflows/demo.yml"]):
                build.return_value.open.return_value = fake_reply(modified)
                self.assertFalse(sync._public_scope_unchanged(self.profile, original, incoming))
            build.return_value.open.return_value = fake_reply(
                ["instagram-central/config.yaml"], behind=1)
            self.assertFalse(sync._public_scope_unchanged(self.profile, original, incoming))
            build.return_value.open.return_value = fake_reply(
                ["instagram-central/config.yaml"] * 300)
            self.assertFalse(sync._public_scope_unchanged(self.profile, original, incoming))

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

    def test_github_head_is_independently_verified(self):
        class Reply:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): return json.dumps({"sha":"a"*40}).encode()
        class Client:
            def open(self, req, timeout):
                self.url=req.full_url
                self.auth=req.get_header("Authorization")
                return Reply()
        client=Client()
        with patch.object(sync.request,"build_opener",return_value=client):
            sha=sync._remote_head("fixture/source","refs/remotes/origin/release/rc","secret")
        self.assertEqual(sha,"a"*40)
        self.assertEqual(client.url,"https://api.github.com/repos/fixture/source/commits/release%2Frc")
        self.assertEqual(client.auth,"Bearer secret")

    def test_failed_publish_of_staging_preserves_previous_checkout(self):
        self.run_sync()
        original_sha=self.source_sha
        self.put(self.source,"next.txt","changed source")
        self.commit(self.source,"next")
        self.git(self.source,"branch","-f","desenvolvimento","main")
        actual=sync.os.rename
        def guarded(a,b):
            if str(a).split("/")[-1].startswith(".stage-fixture-") and str(b).endswith("/fixture"):
                raise OSError("synthetic swap failure")
            return actual(a,b)
        with patch.object(sync.os,"rename",side_effect=guarded):
            with self.assertRaises(OSError): self.run_sync()
        active=json.loads((self.workspaces/"fixture"/sync.MANAGED).read_text())
        self.assertEqual(active["source_sha"],original_sha)

    def test_clone_credential_process_only_sees_secret_file_path(self):
        from unittest.mock import Mock
        def fake_run(*args, **kwargs):
            env=kwargs["env"]
            self.assertNotIn("RUNNER_GITHUB_READ_TOKEN",env)
            self.assertNotIn("secret-value",repr(args))
            secret_path=Path(env["FACTORY_GIT_SECRET_FILE"])
            self.assertEqual(secret_path.read_text(),"secret-value")
            self.assertEqual(secret_path.stat().st_mode & 0o077,0)
            return Mock(returncode=1)
        with patch.object(sync.subprocess,"run",side_effect=fake_run):
            with self.assertRaisesRegex(sync.SyncError,"clone_unavailable"):
                sync._clone("fixture/source",self.root/"candidate","secret-value")

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


    def sync_only_profile(self):
        """Artesão Digital-shaped fixture with no Avisaqui release policy."""
        self.put(self.source, "apps/umdoislab/artesao-release.json",
                 json.dumps({"version": "0.2.0-dev.28", "distributions":
                             ["home-assistant", "debian"]}))
        self.commit(self.source, "artesao version")
        self.git(self.source, "branch", "-f", "desenvolvimento", "main")
        self.profile = {"schema_version": 1, "mode": "sync_only",
            "id": "fixture", "product": "Artesão Digital",
            "source_repo": "fixture/source", "distribution_repo": "fixture/catalog",
            "source_ref": "refs/remotes/origin/desenvolvimento",
            "public_ref": "refs/remotes/origin/main",
            "source_version_file": "apps/umdoislab/artesao-release.json"}
        (self.projects / "fixture.json").write_text(json.dumps(self.profile))
        return self.git(self.source, "rev-parse", "HEAD")

    def test_artesao_sync_only_git_and_version_verified(self):
        from rc_fastlane import load_profile
        source_sha = self.sync_only_profile()
        self.assertEqual(load_profile(self.projects / "fixture.json")["mode"], "sync_only")
        result = self.run_sync()
        self.assertEqual(result["state"], "SYNCED")
        self.assertEqual(result["source_sha"], source_sha)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["errors"], ["SYNC_ONLY_NO_PREPARATION"])
        self.assertTrue((self.workspaces / "fixture" / "source" / ".git").is_dir())
        self.assertFalse((self.workspaces / "fixture" / "source" /
                          "apps/umdoislab/artesao-release.json").exists())
        self.assertEqual(self.run_sync()["state"], "UNCHANGED")

    def test_artesao_sync_only_invalid_profile_is_rejected(self):
        from rc_fastlane import PreflightError, load_profile
        self.sync_only_profile()
        for extra in ({"exporter_path": "scripts/run.py"},
                      {"source_version_file": "../options.json"},
                      {"source_ref": "refs/remotes/origin/../main"},
                      {"source_repo": "https://unapproved.invalid/repo"}):
            invalid = dict(self.profile, **extra)
            (self.projects / "fixture.json").write_text(json.dumps(invalid))
            with self.assertRaises(PreflightError):
                load_profile(self.projects / "fixture.json")
        (self.projects / "fixture.json").write_text(json.dumps(self.profile))

    def test_artesao_sync_only_missing_version_refuses_adoption(self):
        self.sync_only_profile()
        self.profile["source_version_file"] = "apps/umdoislab/missing.json"
        (self.projects / "fixture.json").write_text(json.dumps(self.profile))
        with self.assertRaisesRegex(sync.SyncError, "source_version_unavailable"):
            self.run_sync()
        self.assertFalse((self.workspaces / "fixture").exists())

    def test_artesao_sync_only_prepare_and_preflight_are_denied(self):
        import server
        from rc_fastlane import PreflightError, evaluate
        self.sync_only_profile()
        result = self.run_sync()
        with (patch.object(server, "PROJECTS_DIR", self.projects),
              patch.object(server, "WORKSPACES_DIR", self.workspaces),
              patch.object(server, "PREPARATIONS_DIR", self.root / "preparations")):
            status = server.listed_projects()["fixture"]
            self.assertEqual(status["preparation"], "disabled_sync_only")
            with self.assertRaises(PreflightError):
                server.preflight_project("fixture", result["source_sha"])
            with self.assertRaises(PreflightError):
                server.prepare_project("fixture", result["source_sha"], "fixture-op")
            with self.assertRaises(PreflightError):
                server.prepare_project_declarative("fixture", result["source_sha"], "fixture-op")
        with self.assertRaises(PreflightError):
            evaluate(self.source, self.dist, result["source_sha"], profile=self.profile)
        self.assertFalse((self.root / "preparations").exists())

    def test_artesao_sync_only_auto_prepare_cannot_bypass_gate(self):
        import io
        import contextlib
        import server
        self.sync_only_profile()
        result = self.run_sync()
        logs = io.StringIO()
        with (patch.object(sync, "synchronize", return_value=result),
              patch.object(server, "PROJECTS_DIR", self.projects),
              patch.object(server, "WORKSPACES_DIR", self.workspaces),
              patch.object(server, "AUDIT_PATH", self.root / "audit.jsonl"),
              patch.object(server, "prepare_project",
                           side_effect=AssertionError("must never prepare")),
              patch.object(server, "preflight_project",
                           side_effect=AssertionError("must never preflight")),
              contextlib.redirect_stdout(logs)):
            server.run_workspace_sync("fixture", "secret-not-for-log", auto_prepare=True)
        self.assertIn("[WORKSPACE] SYNC_ONLY:", logs.getvalue())
        self.assertIn("[WORKSPACE] PREPARE_BLOCKED_BY_PROFILE:", logs.getvalue())
        self.assertNotIn("secret-not-for-log", logs.getvalue())

if __name__=="__main__": unittest.main()
