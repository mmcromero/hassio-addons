import unittest
from publisher_service import PublisherCoordinator
from github_bytes_transport import GitHubBytesHTTP
from publication_contract import PublicationError

class FakeApproval:
    def public_key(self): return "cHVibGlj"
    def status(self,*args): return {"active":True}

class PublisherServiceTests(unittest.TestCase):
    def config(self):
        return {"schema_version":1,"owner_id":"owner-1","authority":"authority-1",
                "public_key_sha256":"0"*64,"approval_uid":10,"runner_uid":11}
    def test_config_rejects_unknown_fields_and_invalid_identity(self):
        bad=self.config();bad["token"]="not-allowed"
        with self.assertRaisesRegex(PublicationError,"publisher_runtime_config_invalid"):
            PublisherCoordinator(bad,approval=FakeApproval(),verifier=object(),http=object())
    def test_missing_write_token_allows_only_anonymous_reads(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def __init__(self): self.reads=0
            def read(self,size):
                self.reads+=1
                return b"{}" if self.reads==1 else b""
        class Opener:
            def __init__(self): self.request=None
            def open(self,request,timeout):
                self.request=request
                return Response()
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            client=GitHubBytesHTTP(Path(tmp)/"missing-token",lambda:None)
            opener=Opener();client.opener=opener
            self.assertEqual(client.request("GET","/meta"),{})
            self.assertIsNone(opener.request.get_header("Authorization"))
            with self.assertRaisesRegex(PublicationError,"remote_write_credential_missing"):
                client.request("POST","/git/blobs",{"content":"x"})

    def test_default_gate_is_closed_without_root_activation_manifest(self):
        coordinator=PublisherCoordinator(self.config(),approval=FakeApproval(),verifier=object(),http=object())
        with self.assertRaisesRegex(PublicationError,"publication_disabled"):
            coordinator.gate()
