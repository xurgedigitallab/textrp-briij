# Chain-Agnostic Wallet Auth and E2EE Recovery Contract

This document defines the chain-agnostic contract used by TextRP-Briij wallet authentication
and wallet-backed E2EE recovery envelopes.

## DID/Credential architecture context

- Current baseline login type remains `io.briij.login.xrpl`.
- The target architecture binds login sessions to XRPL-native DID identity
  claims plus credential verification semantics.
- Optional ZKP assertions are additive and must not break baseline DID +
  credential flow.
- For full implementation sequencing and phase gates, see
  `did-zkp-e2ee-plan.md`.

## Objectives

- Keep Matrix/Synapse Olm and Megolm behavior unchanged.
- Keep wallet login pluggable by chain adapter.
- Keep E2EE recovery envelope schema stable across clients and chains.

## Canonical Wallet Identity

Wallet-capable clients and server handlers should normalize identity to:

- `chain_id` (example: `xrpl`)
- `account_id` (chain-specific canonical account/address string)
- `public_key` (chain canonical string format)
- optional `network`
- optional `key_type`

Server account data type:

- `org.textrp.wallet.identity`

Compatibility account data type (XRPL-specific, existing):

- `org.textrp.xrpl.wallet`

## Server Chain Adapter Contract

Each wallet chain adapter should implement:

- `chain_id() -> str`
- `login_type() -> str`
- `session_type() -> str`
- `validate_account_id(raw) -> canonical_account_id`
- `validate_network(raw) -> normalized_network`
- `build_challenge(canonical_account_id, issued_at_ms, nonce) -> str`
- `verify_login_proof(account_id, challenge, signature, public_key?) -> canonical_public_key`

## Recovery Envelope Schema

Account data type:

- `org.textrp.wallet.e2ee_recovery.v1`

Schema:

```json
{
  "envelope_version": 1,
  "chain_id": "xrpl",
  "account_id": "r...",
  "created_at_ms": 1742492912000,
  "key_id": "k-...",
  "wallet_wrap": {
    "alg": "xchacha20poly1305",
    "kdf": "blake3",
    "salt": "base64",
    "nonce": "base64",
    "ciphertext": "base64",
    "aad": "base64"
  },
  "password_wrap": {
    "alg": "xchacha20poly1305",
    "kdf": "argon2id",
    "salt": "base64",
    "nonce": "base64",
    "ciphertext": "base64",
    "aad": "base64",
    "params": {
      "m": 19456,
      "t": 2,
      "p": 1,
      "v": 19
    }
  }
}
```

Server validation requirements:

- Reject unsupported `envelope_version`.
- Reject non-base64 `salt`, `nonce`, `ciphertext`, `aad`.
- Enforce authenticated wallet binding: `chain_id` and `account_id` must match the wallet that just authenticated.
- Enforce size limits.

## Client Conformance Checklist

For each chain client implementation:

1. Implement the chain signer adapter.
2. Use the chain adapter to sign challenge and produce canonical account identity.
3. Generate dual-wrap envelope using:
   - wallet-derived wrap key with domain-separated context
   - password-derived wrap key with Argon2id (or stronger future version)
4. Upload envelope to `org.textrp.wallet.e2ee_recovery.v1`.
5. Support recovery by either:
   - wallet path (no password), or
   - backup password path.

## Compatibility Guidance

- Envelope support is optional and additive.
- Clients not implementing envelope support continue to function.
- Existing XRPL login type (`io.briij.login.xrpl`) remains unchanged.
