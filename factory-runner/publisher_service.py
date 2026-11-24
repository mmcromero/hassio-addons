"""Publisher coordinator: trusted profiles, frozen receipts, independent owner IPC."""
from __future__ import annotations
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import tempfile
import threading

from approval_ipc import ApprovalRPCClient
from github_bytes_transport import GitHubBytesHTTP, GitHubBytesTransport
from owner_approval import GrantVerifier, protected_file
from publication_contract import PublicationError
from publication_workflow import PublicationWorkflow, capabilities
from release_receipt import digest, verify_receipt

AUTHORITY_ROOT = Path("/data/factory-runner-authority")
RUNTIME_CONFIG = AUTHORITY_ROOT / "publisher-config" / "runtime.json"
TOKEN_FILE = AUTHORITY_ROOT / "publisher" / "github-token"
APPROVAL_SOCKET = AUTHORITY_ROOT / "consent-ipc" / "approval.sock"
PUBLISHER_SOCKET = AUTHORITY_ROOT / "publisher-ipc" / "publisher.sock"
ACTIVATION_FILE = AUTHORITY_ROOT / "publisher-config" / "activation.json"


def _trusted_json(path, *, group_name="publisher"):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.resolve() != path.absolute():
        raise PublicationError("publisher_runtime_config_unavailable")
    info = path.stat()
    import grp
    if (info.st_uid != 0 or info.st_gid != grp.getgrnam(group_name).gr_gid
            or stat.S_IMODE(info.st_mode) != 0o440 or info.st_nlink != 1
            or info.st_size > 8192):
        raise PublicationError("publisher_runtime_config_untrusted")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PublicationError("publisher_runtime_config_invalid") from None
    if not isinstance(value, dict):
        raise PublicationError("publisher_runtime_config_invalid")
    return value


PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")
RECEIPT_DIGEST = re.compile(r"^[0-9a-f]{64}$")
PROPOSAL_ID = re.compile(r"^[a-f0-9]{32}$")
NONCE = re.compile(r"^[a-f0-9]{32}$")


class PublisherCoordinator:
    def __init__(self, config, *, approval=None, verifier=None, http=None):
        required = {"schema_version", "owner_id", "authority", "public_key_sha256",
                    "approval_uid", "runner_uid"}
        if (set(config) != required or config["schema_version"] != 1
                or not isinstance(config["owner_id"], str) or not config["owner_id"]
                or not isinstance(config["authority"], str) or not config["authority"]
                or not isinstance(config["public_key_sha256"], str)
                or len(config["public_key_sha256"]) != 64
                or type(config["approval_uid"]) is not int or type(config["runner_uid"]) is not int):
            raise PublicationError("publisher_runtime_config_invalid")
        self.config = config
        self.lock = threading.RLock()
        self.approval = approval or ApprovalRPCClient(APPROVAL_SOCKET, config["approval_uid"])
        if verifier is None:
            encoded = self.approval.public_key()
            try:
                public_material = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError):
                raise PublicationError("approval_public_key_invalid") from None
            if hashlib.sha256(public_material).hexdigest() != config["public_key_sha256"]:
                raise PublicationError("approval_public_key_pin_mismatch")
            state_dir = AUTHORITY_ROOT / "publisher"
            fd, temp_name = tempfile.mkstemp(prefix=".public-key-", dir=state_dir)
            try:
                os.fchmod(fd, 0o400)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(public_material)
                    stream.flush()
                    os.fsync(stream.fileno())
                verifier = GrantVerifier(
                    temp_name, authority=config["authority"], owner_id=config["owner_id"],
                    status_provider=self.approval.status,
                    public_key_sha256=config["public_key_sha256"])
            finally:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
        self.verifier = verifier
        self.http = http or GitHubBytesHTTP(TOKEN_FILE, self.gate)
        self.workflows = {}

    def gate(self):
        try:
            activation = _trusted_json(ACTIVATION_FILE)
        except PublicationError:
            raise PublicationError("publication_disabled_pending_formal_acceptance") from None
        if (set(activation) != {"schema_version", "enabled", "owner_id", "authority"}
                or activation.get("schema_version") != 1
                or activation.get("enabled") is not True
                or activation.get("owner_id") != self.config["owner_id"]
                or activation.get("authority") != self.config["authority"]):
            raise PublicationError("publication_disabled_pending_formal_acceptance")

    @staticmethod
    def _validate_binding(project, issue=None, receipt_digest=None, proposal_id=None):
        if not isinstance(project,str) or not PROJECT_ID.fullmatch(project):
            raise PublicationError("invalid_project")
        if issue is not None and (type(issue) is not int or issue < 1):
            raise PublicationError("invalid_issue")
        if receipt_digest is not None and (
                not isinstance(receipt_digest,str) or not RECEIPT_DIGEST.fullmatch(receipt_digest)):
            raise PublicationError("invalid_receipt_digest")
        if proposal_id is not None and (
                not isinstance(proposal_id,str) or not PROPOSAL_ID.fullmatch(proposal_id)):
            raise PublicationError("invalid_proposal_id")

    def _workflow(self, project, issue):
        self._validate_binding(project, issue)
        from server import project_workspace, preflight_project
        from publication_contract import ArtifactContract
        from rc_fastlane import load_profile
        cache_key = (project, issue)
        if cache_key not in self.workflows:
            profile, source, distribution = project_workspace(project)
            contract = ArtifactContract(
                profile, issue,
                lambda sha: preflight_project(project, sha),
                source_checkout=source, distribution_checkout=distribution)
            transport = GitHubBytesTransport(
                self.http, profile["distribution_repo"],
                profile["public_ref"].replace("refs/remotes/origin/", "refs/heads/"))
            self.workflows[cache_key] = PublicationWorkflow(
                AUTHORITY_ROOT / "publisher", contract, self.verifier,
                transport, gate=self.gate)
        return self.workflows[cache_key]

    @staticmethod
    def _artifact(project, receipt_digest):
        if not isinstance(project,str) or not PROJECT_ID.fullmatch(project):
            raise PublicationError("invalid_project")
        if not isinstance(receipt_digest,str) or not RECEIPT_DIGEST.fullmatch(receipt_digest):
            raise PublicationError("invalid_receipt_digest")
        from server import PREPARATIONS_DIR
        root = Path(PREPARATIONS_DIR).absolute()
        if root.is_symlink() or root.resolve() != root or not root.is_dir():
            raise PublicationError("prepared_artifact_store_unavailable")
        matches = []
        for candidate in root.glob(project + "-*"):
            if candidate.is_symlink() or not candidate.is_dir():
                continue
            try:
                receipt = verify_receipt(candidate, receipt_digest)
            except Exception:
                continue
            if receipt.get("project") == project and digest(receipt) == receipt_digest:
                matches.append(candidate)
        if len(matches) != 1:
            raise PublicationError("prepared_artifact_not_unique")
        return matches[0]

    def preview(self, project, issue, receipt_digest):
        self._validate_binding(project,issue,receipt_digest)
        with self.lock:
            root = self._artifact(project, receipt_digest)
            result = self._workflow(project, issue).preview(root, receipt_digest)
            return {key: result[key] for key in ("binding", "changes", "state", "publication")}

    def propose(self, project, issue, receipt_digest):
        self._validate_binding(project,issue,receipt_digest)
        self.gate()
        with self.lock:
            root = self._artifact(project, receipt_digest)
            result = self._workflow(project, issue).propose(root, receipt_digest, self.approval)
            return {"proposal_id": result["proposal_id"], "binding": result["binding"],
                    "state": result["state"], "owner_consent_path":
                    "/owner-consent/" + result["proposal_id"], "changes": result["changes"]}

    def publish(self, project, issue, receipt_digest, proposal_id):
        self._validate_binding(project,issue,receipt_digest,proposal_id)
        self.gate()
        with self.lock:
            root = self._artifact(project, receipt_digest)
            grant = self.approval.grant(proposal_id)
            return self._workflow(project, issue).publish(root, receipt_digest, grant)

    def status(self):
        try:
            self.gate()
            gate_state = "open"
        except PublicationError:
            gate_state = "closed"
        return {**capabilities(), "ipc": "ready", "publication_gate": gate_state,
                "write_credential": "present" if self.http.token_path is not None else "missing"}

    def reconcile(self, project, nonce):
        self._validate_binding(project)
        if not isinstance(nonce,str) or not NONCE.fullmatch(nonce):
            raise PublicationError("invalid_nonce")
        with self.lock:
            from server import project_workspace, preflight_project
            from publication_contract import ArtifactContract
            profile, source, distribution = project_workspace(project)
            contract = ArtifactContract(
                profile, 1, lambda sha: preflight_project(project, sha),
                source_checkout=source, distribution_checkout=distribution)
            transport = GitHubBytesTransport(
                self.http, profile["distribution_repo"],
                profile["public_ref"].replace("refs/remotes/origin/", "refs/heads/"))
            workflow = PublicationWorkflow(
                AUTHORITY_ROOT / "publisher", contract, self.verifier,
                transport, gate=self.gate)
            try:
                return workflow.reconcile(nonce)
            finally:
                workflow.close()


def load_runtime():
    config = _trusted_json(RUNTIME_CONFIG)
    return PublisherCoordinator(config)


def serve():
    from publisher_ipc import PublisherRPCServer
    coordinator = load_runtime()
    server = PublisherRPCServer(PUBLISHER_SOCKET, coordinator, coordinator.config["runner_uid"])
    print("[PUBLISHER] READY: trusted Unix IPC; activation gate remains root-managed", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        for workflow in coordinator.workflows.values():
            workflow.close()


if __name__ == "__main__":
    serve()
