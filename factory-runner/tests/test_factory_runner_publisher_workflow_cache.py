import unittest
from unittest.mock import patch

from publisher_service import PublisherCoordinator


class FakeApproval:
    def public_key(self):
        return "cHVibGlj"

    def status(self, *args):
        return {"active": True}


class PublisherWorkflowCacheTests(unittest.TestCase):
    def config(self):
        return {
            "schema_version": 1,
            "owner_id": "owner-1",
            "authority": "authority-1",
            "public_key_sha256": "0" * 64,
            "approval_uid": 10,
            "runner_uid": 11,
        }

    @patch("publisher_service.PublicationWorkflow")
    @patch("publisher_service.GitHubBytesTransport")
    @patch("publication_contract.ArtifactContract")
    @patch("server.project_workspace")
    def test_workflow_cache_is_bound_to_project_and_issue(
        self, project_workspace, artifact_contract, transport, workflow
    ):
        project_workspace.return_value = (
            {
                "distribution_repo": "owner/distribution",
                "public_ref": "refs/heads/main",
            },
            "/tmp/source",
            "/tmp/distribution",
        )
        coordinator = PublisherCoordinator(
            self.config(),
            approval=FakeApproval(),
            verifier=object(),
            http=object(),
        )

        first = coordinator._workflow("project_one", 10)
        same_binding = coordinator._workflow("project_one", 10)
        different_issue = coordinator._workflow("project_one", 11)
        different_project = coordinator._workflow("project_two", 10)

        self.assertIs(first, same_binding)
        self.assertIsNot(first, different_issue)
        self.assertIsNot(first, different_project)
        self.assertEqual(workflow.call_count, 3)
        self.assertEqual(artifact_contract.call_args_list[0].args[1], 10)
        self.assertEqual(artifact_contract.call_args_list[1].args[1], 11)
        self.assertEqual(artifact_contract.call_args_list[2].args[1], 10)


if __name__ == "__main__":
    unittest.main()
