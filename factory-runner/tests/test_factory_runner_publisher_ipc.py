import os, sys, tempfile, threading, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publisher_ipc import PublisherRPCServer, PublisherRPCClient
from publication_contract import PublicationError

class FakePublisher:
    def preview(self, project, issue, receipt_digest):
        return {"project": project, "issue": issue, "state": "PREVIEW_NOT_CONSENT"}
    def propose(self, project, issue, receipt_digest):
        return {"proposal_id": "a" * 32}
    def publish(self, project, issue, receipt_digest, proposal_id):
        return {"state": "PUBLISHED_VERIFIED_PENDING_HOMOLOGATION"}
    def status(self):
        return {"publication": "disabled"}
    def reconcile(self, project, nonce):
        return {"state": "READ_ONLY_RECONCILIATION"}

class PublisherIPCTests(unittest.TestCase):
    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp); parent.chmod(0o2750)
            path=parent/"publisher.sock"
            server=PublisherRPCServer(path,FakePublisher(),os.geteuid(),group_gid=os.getgid())
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                import socket
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
                    sock.connect(str(path))
                    sock.sendall(b'{"action":"status","action":"publish"}\n')
                    response=__import__("json").loads(sock.makefile("rb").readline())
                self.assertFalse(response["ok"])
            finally:
                server.shutdown();server.server_close()

    def test_authenticated_local_rpc_and_action_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp); parent.chmod(0o2750)
            path=parent/"publisher.sock"
            server=PublisherRPCServer(path,FakePublisher(),os.geteuid(),group_gid=os.getgid())
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            try:
                client=PublisherRPCClient(path,os.geteuid())
                self.assertEqual(client.request("preview",project="avisaqui",issue=7,receipt_digest="b"*64)["state"],"PREVIEW_NOT_CONSENT")
                self.assertEqual(client.request("status")["publication"],"disabled")
                with self.assertRaisesRegex(PublicationError,"invalid_publisher_contract"):
                    client.request("publish",project="avisaqui",issue=7,receipt_digest="b"*64,proposal_id="a"*32,grant={"forged":True})
                with self.assertRaisesRegex(PublicationError,"publisher_peer_mismatch"):
                    PublisherRPCClient(path,os.geteuid()+100).request("status")
            finally:
                server.shutdown();server.server_close()
