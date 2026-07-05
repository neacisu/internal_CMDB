# OpenBao Agent template for Traefik Cloudflare DNS token rendering.
#
# Reads CF_DNS_API_TOKEN from secret/traefik (KV-v2) and renders a file consumed
# by Traefik via CF_DNS_API_TOKEN_FILE.  Restarts Traefik on token rotation.
#
# Install:
#   sudo cp deploy/openbao/bao-agent-traefik.hcl /etc/openbao/agent-traefik.hcl
#   sudo systemctl enable --now openbao-agent-traefik
#
# Replace placeholders before use:
#   __BAO_ADDR__  — OpenBao API address
#   __TRAefik_RESTART_CMD__ — e.g. docker restart traefik

pid_file = "/var/run/openbao/agent-traefik.pid"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path   = "/etc/openbao/traefik-role-id"
      secret_id_file_path = "/run/secrets/traefik_bao_secret_id"
    }
  }

  sink "file" {
    config = {
      path = "/var/run/openbao/agent-traefik-token"
      mode = 0600
    }
  }
}

vault {
  address = "__BAO_ADDR__"
}

template {
  destination = "/opt/traefik/secrets/cf_token"
  perms       = 0600
  command     = "__TRAEFIK_RESTART_CMD__"
  contents    = <<EOH
{{ with secret "secret/data/traefik" }}{{ .Data.data.CF_DNS_API_TOKEN }}{{ end }}
EOH
}

template {
  destination = "/var/run/openbao/traefik-health"
  perms       = 0644
  contents    = <<EOH
# Written by OpenBao Agent — presence indicates successful auto-auth.
agent_status=ok
updated_at={{ timestamp "2006-01-02T15:04:05Z07:00" }}
EOH
}
