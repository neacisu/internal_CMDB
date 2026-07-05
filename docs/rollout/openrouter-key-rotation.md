# OpenRouter API key rotation

Keys were exposed in chat on 2026-07-05. **Rotate all keys in OpenRouter dashboard before production cutover:**

1. Management Key
2. Cerniq.app API Key
3. Infra.app API Key

After rotation, write new values via OpenBao (never commit):

```bash
export BAO_ADDR=https://s3cr3ts.neanelu.ro:8200
export BAO_TOKEN=<admin>
export OPENROUTER_MANAGEMENT_KEY_FILE=/run/secrets/openrouter_management_key
export OPENROUTER_CERNIQ_APP_KEY_FILE=/run/secrets/openrouter_cerniq_key
export OPENROUTER_INFRA_APP_KEY_FILE=/run/secrets/openrouter_infra_key
./deploy/openbao/setup-openrouter.sh
```

Restart OpenBao agent on lxc-llm-guard to refresh `/var/run/openbao/llm-gateway.env`.
