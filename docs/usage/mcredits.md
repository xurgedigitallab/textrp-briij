# mCredits and Premium Features

TextRP-Briij includes an mCredits subsystem for premium feature gating.

This page documents:

- Matrix client APIs for reading and spending mCredits
- Legacy compatibility endpoints used by existing mobile clients
- Admin APIs for managing the premium feature catalog
- Configuration and bootstrap behavior

## Prerequisites

The mCredits schema is created by database migration delta 94.

- `mcredit_balances`
- `premium_features`
- `mcredit_transactions`

When the homeserver starts, it seeds default rows into `premium_features` if the
table exists and is empty.

## Configuration

Set initial credits for newly registered non-guest users in `homeserver.yaml`:

```yaml
briij:
  mcredits_initial: 1000
```

Notes:

- Default: `1000`
- Must be an integer `>= 0`
- Applied once per user at registration time

## Client API (Matrix)

All endpoints below require Matrix bearer authentication.

Base prefix:

- `/_matrix/client/v3`

### Get balance

- `GET /_matrix/client/v3/mcredits/balance`

Response:

```json
{
  "balance": 1000
}
```

### List active premium features

- `GET /_matrix/client/v3/mcredits/features`

Response:

```json
{
  "features": [
    {
      "feature_key": "voip_premium",
      "name": "VoIP Premium",
      "description": "Premium voice call quality",
      "mcredits_cost": 200,
      "category": "communication",
      "is_active": true
    }
  ]
}
```

### Spend mCredits

- `POST /_matrix/client/v3/mcredits/spend`

Request body:

```json
{
  "feature_key": "voip_premium"
}
```

Response:

```json
{
  "feature_key": "voip_premium",
  "balance": 800
}
```

## Legacy compatibility endpoints

These are root-level paths provided for TextRP-Backend compatibility.

- `POST /my-address`
- `GET /my-features/{walletAddress}/main/enabled`

Both endpoints require Matrix authentication and enforce requester ownership
(requesters can only query their own data).

### `POST /my-address`

Request body:

```json
{
  "address": "@alice:example.org"
}
```

Response:

```json
{
  "user": {
    "address": "rExampleWalletAddress",
    "credit": {
      "balance": "1000"
    }
  },
  "address": "rExampleWalletAddress"
}
```

### `GET /my-features/{walletAddress}/main/enabled`

Notes:

- `network` must be exactly `main`
- Only features affordable by the current wallet owner's balance are returned

Response:

```json
{
  "nfts": [
    {
      "feature": "voip_premium",
      "name": "VoIP Premium",
      "description": "Premium voice call quality",
      "mcredits_cost": 200,
      "category": "communication"
    }
  ]
}
```

## Admin API (premium feature catalog)

These APIs require a server admin access token.

Supported prefixes:

- `/_synapse/admin/v2`
- `/_briij/admin/v2`

### List features

- `GET /{admin_prefix}/briij/premium_features`

### Create feature

- `POST /{admin_prefix}/briij/premium_features`

Request body:

```json
{
  "feature_key": "priority_support",
  "name": "Priority Support",
  "description": "Priority queue for support requests",
  "mcredits_cost": 500,
  "category": "support"
}
```

### Update feature

- `PUT /{admin_prefix}/briij/premium_features/{feature_key}`

Updatable fields:

- `mcredits_cost` (positive integer)
- `description` (string or null)
- `is_active` (boolean)

### Soft-delete (deactivate) feature

- `DELETE /{admin_prefix}/briij/premium_features/{feature_key}`

This marks `is_active=false` and does not hard-delete the row.
