# NFT-based verification trust (XRPL)

TextRP-Briij now stores verification trust on each user's existing mutable soulbound identity NFT, instead of XLS-70 Credentials.

## Model

- Identity NFT is minted once during Xaman-backed SSO onboarding.
- `m.user.verify.request` records intent in Matrix only.
- `m.user.verify.accept` must include a validated `NFTokenModify` transaction hash.
- `NFTokenModify.URI` points to JSON metadata (typically `ipfs://...`) with:

```json
{
  "verifiers": ["r...","r..."]
}
```

## Trust evaluation

- `check_trust(payer, payee)` resolves identity NFT via `account_nfts`.
- Direct trust: payer NFT metadata `verifiers` contains payee address.
- Mutual trust fallback: both payer->payee and payee->payer membership exist.
- Synapse caches trust decisions in Redis for 60 seconds to keep `m.chat.pay` gating fast and stable.

## Why this migration

- No Credential object limits.
- No reserve creep from accumulating new ledger object types.
- Unlimited verifier growth via mutable NFT metadata updates.
