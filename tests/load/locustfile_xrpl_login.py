from __future__ import annotations

import random
import uuid

from locust import HttpUser, between, task


class XrplLoginUser(HttpUser):
    wait_time = between(0.01, 0.05)

    def _best_effort_post(self, path: str, payload: dict, name: str) -> None:
        with self.client.post(path, json=payload, name=name, catch_response=True) as response:
            if response.status_code in (0, 200):
                response.success()
                return
            response.failure(f"{name} failed: {response.status_code}")

    def _best_effort_get(self, path: str, name: str) -> None:
        with self.client.get(path, name=name, catch_response=True) as response:
            if response.status_code in (0, 200):
                response.success()
                return
            response.failure(f"{name} failed: {response.status_code}")

    def _run_flow(self, include_zkp: bool) -> None:
        address = f"r{uuid.uuid4().hex[:30]}"

        with self.client.post(
            "/_matrix/client/v3/login",
            json={
                "type": "io.briij.login.xrpl",
                "address": address,
                "network": "xrpl",
            },
            name="login.challenge",
            catch_response=True,
        ) as challenge:
            if challenge.status_code in (0, 401):
                challenge.success()
            else:
                challenge.failure(f"challenge failed: {challenge.status_code}")
                return
            if challenge.status_code == 0:
                return
            session = challenge.json().get("session")

        login_body = {
            "type": "io.briij.login.xrpl",
            "session": session,
            "address": address,
            "signature": "deadbeef",
            "public_key": "ed25519pub",
        }
        with self.client.post(
            "/_matrix/client/v3/login",
            json=login_body,
            name="login.complete",
            catch_response=True,
        ) as login:
            if login.status_code in (0, 200):
                login.success()
            else:
                login.failure(f"complete failed: {login.status_code}")
                return

        self._best_effort_get(
            f"/_matrix/client/v3/did/resolve?account={address}",
            name="did.resolve",
        )
        self._best_effort_post(
            "/_matrix/client/v3/credential/create",
            {
                "subject": address,
                "did_uri": f"did:xrpl:testnet:{address}",
                "e2ee_pubkey_commitment": "abc123",
            },
            name="credential.create",
        )
        self._best_effort_post(
            "/_matrix/client/v3/credential/verify",
            {"credential_id": "cred-load"},
            name="credential.verify",
        )
        if include_zkp:
            self._best_effort_post(
                "/_matrix/client/v3/zkp/verify",
                {
                    "proof": {"type": "groth16", "nonce": random.randint(1, 1_000_000)},
                    "public_signals": {
                        "xrpl_address": address,
                        "did_uri": f"did:xrpl:testnet:{address}",
                        "credential_id": "cred-load",
                        "e2ee_pubkey_commitment": "abc123",
                    },
                },
                name="zkp.verify",
            )

    @task(6)
    def flow_with_zkp(self) -> None:
        self._run_flow(include_zkp=True)

    @task(4)
    def flow_without_zkp(self) -> None:
        self._run_flow(include_zkp=False)
