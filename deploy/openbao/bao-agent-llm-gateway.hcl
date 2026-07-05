# OpenBao Agent template for LLM Gateway (LiteLLM on lxc-llm-guard).
#
# Renders /var/run/openbao/llm-gateway.env with OpenRouter API keys for docker compose.
#
# Install on lxc-llm-guard (10.0.1.115):
#   sudo cp deploy/openbao/bao-agent-llm-gateway.hcl /etc/openbao/agent-llm-gateway.hcl
#   echo "<role_id>" | sudo tee /etc/openbao/llm-gateway-role-id
#   sudo cp secret_id to /run/secrets/bao_llm_gateway_secret_id
#   sudo systemctl enable --now openbao-agent-llm-gateway

pid_file = "/var/run/openbao/agent-llm-gateway.pid"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path   = "/etc/openbao/llm-gateway-role-id"
      secret_id_file_path = "/run/secrets/bao_llm_gateway_secret_id"
    }
  }

  sink "file" {
    config = {
      path = "/var/run/openbao/agent-llm-gateway-token"
      mode = 0600
    }
  }
}

vault {
  address = "__BAO_ADDR__"
}

template {
  destination = "/var/run/openbao/llm-gateway.env"
  perms       = 0600
  contents    = <<EOH
OPENROUTER_MANAGEMENT_KEY={{ with secret "kv-llm/data/openrouter" }}{{ .Data.data.MANAGEMENT_KEY }}{{ end }}
OPENROUTER_CERNIQ_APP_KEY={{ with secret "kv-llm/data/openrouter" }}{{ .Data.data.CERNIQ_APP_KEY }}{{ end }}
OPENROUTER_INFRA_APP_KEY={{ with secret "kv-llm/data/openrouter" }}{{ .Data.data.INFRA_APP_KEY }}{{ end }}
LITELLM_MASTER_KEY=sk-litellm-internal-gateway
EOH
}

template {
  destination = "/var/run/openbao/llm-gateway-health"
  perms       = 0644
  contents    = <<EOH
agent_status=ok
updated_at={{ timestamp "2006-01-02T15:04:05Z07:00" }}
EOH
}
