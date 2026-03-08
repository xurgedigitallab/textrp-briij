# Briij wallet auth module config

Add this under the `modules:` section in `homeserver.yaml`:

```yaml
modules:
  - module: briij.auth.wallet_provider.WalletProvider
    config:
      allowed_networks:
        - xrpl
        - xahau
      default_network: xrpl
      xrpl:
        jsonrpc_urls:
          - https://s1.ripple.com:51234/
          - https://xrplcluster.com/
      xahau:
        jsonrpc_urls:
          - https://xahau.network/
          - https://xahau-test.net/
```
