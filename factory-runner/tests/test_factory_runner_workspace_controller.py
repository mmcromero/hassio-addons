"""Startup GitHub sync may never bypass the API's locking and policy gates."""
import io
import os
import contextlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import server
import workspace_sync

class ControllerTests(unittest.TestCase):
    def test_opt_in_default_does_nothing_and_drops_old_selector(self):
        with (patch.dict(os.environ, {"RUNNER_WORKSPACE_SYNC_ENABLED": "false",
                                   "RUNNER_WORKSPACE_SYNC_PROJECT": "avisaqui",
                                   "RUNNER_GITHUB_READ_TOKEN": "test-secret"}),
              patch.object(server, "listed_projects") as list_profiles,
              patch.object(server, "run_workspace_sync") as worker):
            self.assertIsNone(server.launch_workspace_sync())
            list_profiles.assert_not_called()
            worker.assert_not_called()
            self.assertNotIn("RUNNER_GITHUB_READ_TOKEN", os.environ)
            self.assertNotIn("RUNNER_WORKSPACE_SYNC_PROJECT", os.environ)

    def test_all_approved_profiles_run_without_single_project_selector(self):
        with (patch.dict(os.environ, {"RUNNER_WORKSPACE_SYNC_ENABLED": "true",
                                   "RUNNER_GITHUB_READ_TOKEN": "test-secret",
                                   "RUNNER_WORKSPACE_AUTO_PREPARE": "false"}),
              patch.object(server, "listed_projects", return_value={
                  "avisaqui": {}, "artesao-digital": {}, "projeto-futuro": {}}),
              patch.object(server, "run_workspace_sync") as worker,
              contextlib.redirect_stdout(io.StringIO()) as output):
            thread = server.launch_workspace_sync()
            self.assertIsNotNone(thread)
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual([x.args[0] for x in worker.call_args_list], [
            "artesao-digital", "avisaqui", "projeto-futuro"])
        for call in worker.call_args_list:
            self.assertEqual(call.args[1], "test-secret")
            self.assertFalse(call.kwargs["auto_prepare"])
        self.assertNotIn("test-secret", output.getvalue())
        self.assertIn("[WORKSPACE] FINISHED: approved_projects=3", output.getvalue())

    def test_one_sync_failure_does_not_block_other_projects(self):
        seen = []
        def fail_first(project, token, auto_prepare=False):
            seen.append(project)
            if project == "alpha":
                raise RuntimeError("secret must not be shown")
        with (patch.dict(os.environ, {"RUNNER_WORKSPACE_SYNC_ENABLED": "true",
                                   "RUNNER_GITHUB_READ_TOKEN": "test-secret"}),
              patch.object(server, "listed_projects", return_value={
                  "alpha": {}, "beta": {}}),
              patch.object(server, "run_workspace_sync", side_effect=fail_first),
              contextlib.redirect_stdout(io.StringIO()) as output):
            thread = server.launch_workspace_sync()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(seen, ["alpha", "beta"])
        self.assertNotIn("secret", output.getvalue())
        self.assertIn("BLOCKED: unexpected_sync_error", output.getvalue())

    def test_no_profiles_is_blocked_without_network_calls(self):
        with (patch.dict(os.environ, {"RUNNER_WORKSPACE_SYNC_ENABLED": "true"}),
              patch.object(server, "listed_projects", return_value={}),
              patch.object(server, "run_workspace_sync") as worker,
              contextlib.redirect_stdout(io.StringIO()) as output):
            self.assertIsNone(server.launch_workspace_sync())
            worker.assert_not_called()
        self.assertIn("no_approved_projects", output.getvalue())

    def test_excessive_profiles_do_not_start_network_sync(self):
        projects={f"profile{i:03}":{} for i in range(server.MAX_SYNC_PROJECTS+1)}
        with (patch.dict(os.environ, {"RUNNER_WORKSPACE_SYNC_ENABLED": "true"}),
              patch.object(server, "listed_projects", return_value=projects),
              patch.object(server, "run_workspace_sync") as worker,
              contextlib.redirect_stdout(io.StringIO()) as output):
            self.assertIsNone(server.launch_workspace_sync())
            worker.assert_not_called()
        self.assertIn("approved_project_limit",output.getvalue())

    def test_automatic_prepare_requires_explicit_switch(self):
        with (patch.dict(os.environ, {"RUNNER_WORKSPACE_SYNC_ENABLED": "true",
                                   "RUNNER_WORKSPACE_AUTO_PREPARE": "true"}),
              patch.object(server, "listed_projects", return_value={"avisaqui": {}}),
              patch.object(server, "run_workspace_sync") as worker,
              contextlib.redirect_stdout(io.StringIO())):
            thread=server.launch_workspace_sync()
            thread.join(timeout=5)
        worker.assert_called_once_with("avisaqui", "", auto_prepare=True)

    def test_sync_success_uses_only_configured_profile(self):
        output=io.StringIO()
        result={"state":"SYNCED","source_sha":"a"*40,"public_sha":"b"*40,
                "eligible":False,"errors":["NO_OPEN_PACKAGE"]}
        with (patch.object(workspace_sync, "synchronize", return_value=result) as worker,
             patch.object(server, "record") as audit,
             patch.object(server, "prepare_project") as prepare,
             contextlib.redirect_stdout(output)):
            response=server.run_workspace_sync("avisaqui", "synthetic-secret", False)
        self.assertEqual(response, result)
        self.assertIn("POLICY_BLOCKED: NO_OPEN_PACKAGE",output.getvalue())
        self.assertNotIn("synthetic-secret",output.getvalue())
        self.assertNotIn("synthetic-secret",str(audit.call_args_list))
        self.assertEqual(worker.call_args.args,("avisaqui",))
        self.assertEqual(worker.call_args.kwargs["token"],"synthetic-secret")
        prepare.assert_not_called()

    def test_auto_prepare_only_when_policy_allows(self):
        current={"state":"SYNCED","source_sha":"c"*40,"public_sha":"d"*40,
                 "eligible":True,"errors":[]}
        report={"eligible_for_preparation":True}
        with (patch.object(workspace_sync, "synchronize",return_value=current),
             patch.object(server,"record"),
             patch.object(server,"preflight_project",return_value=report),
             patch.object(server,"prepare_project", return_value={
                "eligible":True,"published":False,"state":"PREPARED_NOT_PUBLISHED"}) as prep,
             contextlib.redirect_stdout(io.StringIO())):
            server.run_workspace_sync("avisaqui","token",True)
        prep.assert_called_once()

    def test_auto_prepare_rechecks_policy(self):
        current={"state":"UNCHANGED","source_sha":"c"*40,"public_sha":"d"*40,
                 "eligible":None,"errors":[]}
        report={"eligible_for_preparation":False,"errors":["NO_OPEN_PACKAGE"]}
        with (patch.object(workspace_sync,"synchronize",return_value=current),
             patch.object(server,"record"),
             patch.object(server,"preflight_project",return_value=report),
             patch.object(server,"prepare_project") as prep,
             contextlib.redirect_stdout(io.StringIO())):
            server.run_workspace_sync("avisaqui","token",True)
        prep.assert_not_called()

    def test_legacy_project_never_overrides_approved_profiles(self):
        with (patch.dict(os.environ, {
                "RUNNER_WORKSPACE_SYNC_ENABLED": "true",
                "RUNNER_WORKSPACE_SYNC_PROJECT": "../evil",
                "RUNNER_GITHUB_READ_TOKEN": "fixture-secret"}),
             patch.object(server, "listed_projects", return_value={"avisaqui":{}}),
             patch.object(server, "run_workspace_sync") as worker,
             contextlib.redirect_stdout(io.StringIO())):
            thread = server.launch_workspace_sync()
            thread.join(timeout=5)
            self.assertNotIn("RUNNER_WORKSPACE_SYNC_PROJECT", os.environ)
            self.assertNotIn("RUNNER_GITHUB_READ_TOKEN", os.environ)
        worker.assert_called_once_with("avisaqui", "fixture-secret", auto_prepare=False)

    def test_sync_failure_cannot_expose_token(self):
        output=io.StringIO()
        with (patch.object(workspace_sync,"synchronize",side_effect=workspace_sync.SyncError("clone_unavailable")),
             patch.object(server,"record"),
             contextlib.redirect_stdout(output)):
            self.assertIsNone(server.run_workspace_sync("avisaqui","topsecret",True))
        self.assertIn("[WORKSPACE] BLOCKED: clone_unavailable",output.getvalue())
        self.assertNotIn("topsecret",output.getvalue())

if __name__=="__main__": unittest.main()
