# OpenBao Agent template for internalCMDB AppRole authentication.
#
# Renders no secret files on disk — the application reads directly from OpenBao
# using AppRole credentials mounted at /run/secrets/bao_secret_id.
#
# Install:
#   sudo cp deploy/openbao/bao-agent-internalcmdb.hcl /etc/openbao/agent-internalcmdb.hcl
#   sudo systemctl enable --now openbao-agent-internalcmdb
#
# Replace placeholders before use:
#   __BAO_ADDR__       — OpenBao API address (e.g. https://127.0.0.1:8200)
#   __VAULT_ROLE_ID__  — AppRole role_id for internalcmdb policy

pid_file = "/var/run/openbao/agent-internalcmdb.pid"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path   = "/etc/openbao/internalcmdb-role-id"
      secret_id_file_path = "/run/secrets/bao_secret_id"
    }
  }

  sink "file" {
    config = {
      path = "/var/run/openbao/agent-internalcmdb-token"
      mode = 0600
    }
  }
}

vault {
  address = "__BAO_ADDR__"
}

# Optional: expose token to co-located processes via env_file rendering.
# The internalCMDB API container uses AppRole directly; this agent is for
# host-level sidecars (e.g. postgres-exporter DSN refresh) if needed.

template {
  destination = "/var/run/openbao/internalcmdb-token.env"
  perms       = 0600
  contents    = <<EOH
VAULT_ADDR=__BAO_ADDR__
VAULT_TOKEN={{ with secret "auth/token/lookup-self" }}{{ .Data.id }}{{ end }}
VAULT_ROLE_ID=__VAULT_ROLE_ID__
EOH
}

template {
  destination = "/var/run/openbao/internalcmdb-health"
  perms       = 0644
  contents    = <<EOH
# Written by OpenBao Agent — presence indicates successful auto-auth.
# Do NOT store secrets in this file.
agent_status=ok
updated_at={{ timestamp "2006-01-02T15:04:05Z07:00" }}
EOH
}
