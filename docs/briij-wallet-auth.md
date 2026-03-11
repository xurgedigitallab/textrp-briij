# Briij XRPL/Xahau wallet login

TextRP-Briij supports a native Matrix login flow for XRPL and Xahau wallets via
the custom login type `io.briij.login.xrpl`.

## Homeserver configuration

Add this top-level section to `homeserver.yaml`:

```yaml
xrpl_auth:
  enabled: true
  allow_account_creation: true
  xrpl_node_url: "https://s.altnet.rippletest.net:51234"
  xahau_node_url: "https://xahau-testnet.xrpl-labs.com"
  challenge_ttl_seconds: 300
```

## Login flow

### 1. Client requests a challenge

```json
{
  "type": "io.briij.login.xrpl",
  "address": "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
  "network": "xrpl"
}
```

The homeserver replies with HTTP `401` and a short-lived challenge payload:

```json
{
  "session": "abc123...",
  "challenge": "textrp-briij|2026-03-10T19:41:00Z|nonce:random-32-char-string|rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
}
```

### 2. Client signs the challenge locally

The wallet signs the exact challenge string locally using the private key
derived from the wallet seed. The seed never leaves the client.

### 3. Client completes the login

```json
{
  "type": "io.briij.login.xrpl",
  "session": "abc123...",
  "address": "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
  "signature": "hex-encoded-signature",
  "public_key": "optional-hex-public-key"
}
```

If the signature verifies successfully, TextRP-Briij links the wallet address to
the local Matrix account and returns a standard Matrix login response with an
access token.

## Notes

- Existing Xaman/OIDC SSO flows continue to work in parallel.
- Challenges are short-lived and single-use.
- Linked wallet metadata is persisted on the homeserver; wallet seeds are not.
