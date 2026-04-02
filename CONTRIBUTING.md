# Welcome to Synapse

Please see the [contributors' guide](https://docs.briij.example/synapse/latest/development/contributing_guide.html) in our rendered documentation.

## Extending XRPL DID/Credential/ZKP auth

When extending the XRPL identity stack in TextRP-Briij:

1. Keep the primary authentication path XRPL-first and wallet-native.
2. Do not introduce server-side private key handling.
3. Keep ZKP additive and optional; baseline DID + credential login must still work.
4. Treat DID/credential/ZKP artifacts as opaque metadata for Matrix compatibility.
5. Add failing tests first, then minimal implementation:
   - Python API/login tests (`poetry run trial ...`)
   - Rust module tests (`cargo test`)
   - SDK integration tests (`pnpm test ...` in `briij-js-sdk`)
6. If changing schema, use Postgres-only migration deltas.
7. Validate abuse controls:
   - per-IP and per-wallet ratelimits
   - payload size bounds
   - suspicious-event logging

Reference docs:

- `docs/did-zkp-e2ee-plan.md`
- `docs/architecture/xrpl-sovereign-e2ee.md`
