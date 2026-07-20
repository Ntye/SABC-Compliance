"""SSH key rotation: add-before-remove across the fleet.

The rotation must never lock the platform out. These tests pin the safety
contract: a reachable node that can't verify the new key aborts the whole
rotation with no on-disk change; a fully reachable fleet ends with the new key
active and the old public key stripped from every node; unreachable nodes keep
the old key and don't block promotion of the reachable ones.
"""
from __future__ import annotations

import os

import pytest

from infrastructure.ssh.key_manager import SshKeyManager
from modules.settings.ssh_key import RotateSshKeyUseCase


class StubKeyManager(SshKeyManager):
    """SshKeyManager that fabricates key material instead of shelling out to
    ssh-keygen, so the rotation orchestration is testable without OpenSSH
    installed. Promotion, .prev/.pending file handling and reads are the real
    thing — only the crypto is faked."""
    _counter = 0

    async def generate_pending(self, comment: str = "sabc-ansible") -> str:
        self.discard_pending()
        parent = os.path.dirname(self.pending_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        StubKeyManager._counter += 1
        pub = f"ssh-ed25519 AAAAFAKEKEY{StubKeyManager._counter} {comment}"
        with open(self.pending_path, "w") as fh:
            fh.write(f"PRIV{StubKeyManager._counter}\n")
        with open(self.pending_pub_path, "w") as fh:
            fh.write(pub + "\n")
        os.chmod(self.pending_path, 0o600)
        return pub

    async def fingerprint(self, pub_path=None):
        p = pub_path or self.pub_path
        if not os.path.exists(p):
            return None
        return {"bits": "256", "fingerprint": "SHA256:fake", "type": "ED25519"}


class _Node:
    def __init__(self, nid: str, ip: str = "10.0.0.9") -> None:
        self.id = nid
        self.hostname = nid
        self.ip = ip
        self.ssh_port = 22
        self.ssh_user = "ansible"
        self.ssh_key_path = None


class FakeNodeRepo:
    def __init__(self, nodes): self._nodes = nodes
    async def find_all(self, _f=None): return list(self._nodes)


class FakeSsh:
    """Simulates each node's authorized_keys. ``unreachable`` nodes fail every
    op; ``reject_new`` nodes accept the append but fail verification with the
    new (pending) key."""
    def __init__(self, km: SshKeyManager, *, unreachable=(), reject_new=()):
        self._km = km
        self.authorized: dict[str, set[str]] = {}
        self._unreachable = set(unreachable)
        self._reject_new = set(reject_new)

    def _pending_pub(self): return self._km.read_pending_public_key() or self._km.read_public_key()

    async def run_command(self, ip, port, user, key_path, command):
        host = ip
        if host in self._unreachable:
            return "", "unreachable", 1
        ks = self.authorized.setdefault(host, set())
        if "authorized_keys || printf" in command:            # append
            # extract the quoted pubkey
            pub = command.split("printf '%s\\n' '", 1)[1].rsplit("'", 1)[0]
            ks.add(pub)
            return "", "", 0
        if "grep -vxF" in command:                            # remove
            pub = command.split("grep -vxF '", 1)[1].split("'", 1)[0]
            ks.discard(pub)
            return "", "", 0
        return "", "", 0

    async def test_connectivity(self, ip, port, user, key_path):
        host = ip
        if host in self._unreachable:
            return False, "unreachable"
        # Verification uses the pending key explicitly. A reject_new node has the
        # key in authorized_keys but its sshd refuses it.
        if key_path == self._km.pending_path and host in self._reject_new:
            return False, "denied"
        return True, None


@pytest.fixture()
def km(tmp_path):
    key_path = str(tmp_path / "ansible_id_rsa")
    return StubKeyManager(key_path, key_type="ed25519")


async def _seed_active_key(km: SshKeyManager) -> str:
    """Create an initial active keypair (as the entrypoint would) and pretend
    every node already trusts it."""
    pub = await km.generate_pending(comment="orig")
    km.promote_pending()
    return pub


class FakeConfig:
    def __init__(self): self.v = {}
    async def get(self, k): return self.v.get(k)
    async def set(self, k, val): self.v[k] = val


def _build(km, nodes, **ssh_kw):
    ssh = FakeSsh(km, **ssh_kw)
    uc = RotateSshKeyUseCase(FakeNodeRepo(nodes), ssh, km, config_repo=FakeConfig())
    return uc, ssh


class TestHappyPath:
    async def test_rotates_and_strips_old_key_everywhere(self, km) -> None:
        old_pub = await _seed_active_key(km)
        nodes = [_Node("a", "10.0.0.1"), _Node("b", "10.0.0.2")]
        uc, ssh = _build(km, nodes)
        # Pre-seed every node with the current (old) key.
        for n in nodes:
            ssh.authorized[n.ip] = {old_pub}

        res = await uc.execute(actor="alice")

        assert res["rotated"] is True
        new_pub = km.read_public_key()
        assert new_pub != old_pub
        # Old key removed, new key present, on every node.
        for n in nodes:
            assert ssh.authorized[n.ip] == {new_pub}
        assert all(r["status"] == "rotated" for r in res["nodes"])
        assert res["reachable"] == 2 and res["unreachable"] == 0
        # Previous key retained locally as a fallback identity.
        assert km.has_prev()

    async def test_active_key_actually_changed_on_disk(self, km) -> None:
        old_pub = await _seed_active_key(km)
        uc, ssh = _build(km, [_Node("a", "10.0.0.1")])
        ssh.authorized["10.0.0.1"] = {old_pub}
        await uc.execute()
        assert km.read_public_key() != old_pub
        assert km.read_prev_public_key() == old_pub


class TestSafetyGate:
    async def test_verify_failure_aborts_with_no_change(self, km) -> None:
        old_pub = await _seed_active_key(km)
        nodes = [_Node("a", "10.0.0.1"), _Node("b", "10.0.0.2")]
        # Node b accepts the appended key but sshd rejects a login with it.
        uc, ssh = _build(km, nodes, reject_new={"10.0.0.2"})
        for n in nodes:
            ssh.authorized[n.ip] = {old_pub}

        res = await uc.execute()

        assert res["rotated"] is False
        # Active key unchanged; no pending left dangling; no prev created.
        assert km.read_public_key() == old_pub
        assert not os.path.exists(km.pending_path)
        assert not km.has_prev()


class TestUnreachableNodes:
    async def test_unreachable_node_does_not_block_rotation(self, km) -> None:
        old_pub = await _seed_active_key(km)
        nodes = [_Node("a", "10.0.0.1"), _Node("down", "10.0.0.9")]
        uc, ssh = _build(km, nodes, unreachable={"10.0.0.9"})
        ssh.authorized["10.0.0.1"] = {old_pub}

        res = await uc.execute()

        assert res["rotated"] is True
        assert res["unreachable"] == 1 and res["reachable"] == 1
        new_pub = km.read_public_key()
        # Reachable node fully rotated; unreachable node left as-is (still old key).
        assert ssh.authorized["10.0.0.1"] == {new_pub}
        statuses = {r["hostname"]: r["status"] for r in res["nodes"]}
        assert statuses["a"] == "rotated"
        assert statuses["down"] == "unreachable"
