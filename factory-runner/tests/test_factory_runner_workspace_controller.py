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
    def test_opt_in_default_does_nothing(self):
        with (patch.dict(os.environ, {"RUNNER_WORKSPACE_SYNC_PROJECT": ""}),
             patch.object(server, "run_workspace_sync") as worker):
            self.assertIsNone(server.launch_workspace_sync())
            worker.assert_not_called()

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

    def test_invalid_project_fails_before_thread(self):
        with (patch.dict(os.environ,{"RUNNER_WORKSPACE_SYNC_PROJECT":"../evil",
                                 "RUNNER_GITHUB_READ_TOKEN":"fixture-secret",
                                 "RUNNER_WORKSPACE_AUTO_PREPARE":"true"}),
             patch.object(server,"run_workspace_sync") as worker,
             contextlib.redirect_stdout(io.StringIO())):
            self.assertIsNone(server.launch_workspace_sync())
            self.assertNotIn("RUNNER_GITHUB_READ_TOKEN",os.environ)
            worker.assert_not_called()

    def test_sync_failure_cannot_expose_token(self):
        output=io.StringIO()
        with (patch.object(workspace_sync,"synchronize",side_effect=workspace_sync.SyncError("clone_unavailable")),
             patch.object(server,"record"),
             contextlib.redirect_stdout(output)):
            self.assertIsNone(server.run_workspace_sync("avisaqui","topsecret",True))
        self.assertIn("[WORKSPACE] BLOCKED: clone_unavailable",output.getvalue())
        self.assertNotIn("topsecret",output.getvalue())

if __name__=="__main__": unittest.main()
