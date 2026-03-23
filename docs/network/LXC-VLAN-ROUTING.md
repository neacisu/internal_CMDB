# LXC VLAN Routing — Cerniq Containers (10.10.1.x)

## Problem Statement

Cerniq LXC containers on Proxmox (hz.164) live on an isolated VLAN
`10.10.1.0/24` that has no direct route to the orchestrator
(`77.42.76.185`) or the API endpoint (`infraq.app`).

The collector agent running inside each LXC needs to push telemetry to
the internalCMDB API.

---

## Options

### Option A — NAT on hz.164 Gateway

Configure hz.164 as a NAT gateway for the `10.10.1.0/24` subnet so LXC
containers can reach the internet directly.

**Pros:** Standard Linux networking; LXC agents run identically to bare-metal agents.
**Cons:** Requires `iptables` MASQUERADE rules and `ip_forward=1` on hz.164;
opens the LXC subnet to outbound traffic which increases attack surface.

```bash
# On hz.164:
sysctl -w net.ipv4.ip_forward=1
iptables -t nat -A POSTROUTING -s 10.10.1.0/24 -o eth0 -j MASQUERADE
```

### Option B — SSH Proxy Tunnel via hz.164

Each LXC container establishes an SSH tunnel through hz.164 to reach the
API endpoint.

**Pros:** No network reconfiguration needed.
**Cons:** Fragile — tunnels must be restarted if hz.164 reboots; adds SSH
key management overhead per LXC container.

```bash
# Inside LXC:
ssh -N -L 4444:infraq.app:443 root@10.10.1.1
```

### Option C — Agent on hz.164 Collects via `pct exec` (Recommended)

Run the collector agent on **hz.164 only** and use `pct exec` to reach
into each LXC container for data collection.  The agent reports each LXC
as a sub-entity under the hz.164 host.

**Pros:** Simplest — no network changes; single agent to manage; leverages
existing Proxmox API access; no credentials inside LXC containers.
**Cons:** Requires `pct exec` access (root on Proxmox host); all LXC data
funnels through one agent.

```toml
# /etc/internalcmdb/agent.toml on hz.164
[agent]
api_url = "https://infraq.app/api/v1/collectors"
host_code = "hz.164"
log_level = "INFO"

[lxc]
enabled = true
container_ids = [100, 101, 102]
collect_via = "pct_exec"
```

---

## Recommendation

**Option C** is recommended as the simplest and most secure approach:

1. No network topology changes needed
2. Single point of management (agent on hz.164)
3. LXC containers require zero additional software
4. Proxmox already grants `pct exec` access to the host
5. Telemetry is aggregated efficiently before transmission

The agent on hz.164 should use the `proxmox` profile which includes the
LXC collector module that iterates over configured container IDs.

---

## DNS Considerations

With Option C the LXC containers themselves do **not** need external DNS
resolution because all API communication goes through the agent on hz.164
(which already has full network access).

If LXC containers need DNS for other purposes (apt updates, NTP, etc.):

- Configure hz.164 as a DNS forwarder using `dnsmasq` or
  `systemd-resolved` listening on `10.10.1.1`.
- Set each LXC container's `/etc/resolv.conf` to `nameserver 10.10.1.1`.
- **Do not** open port 53 externally — bind only to the VLAN interface.

---

## Validation & Testing

After deploying the agent on hz.164 with the `[lxc]` config section:

1. **Connectivity**: verify the agent can reach the API:
   ```bash
   curl -sf https://infraq.app/api/v1/collectors/health && echo OK
   ```
2. **LXC access**: verify `pct exec` works for each container:
   ```bash
   for ctid in 100 101 102; do
       pct exec $ctid -- hostname && echo "ct$ctid OK"
   done
   ```
3. **Enrollment**: check the CMDB API to confirm hz.164 enrolled:
   ```bash
   curl -s https://infraq.app/api/v1/collectors/agents | grep hz.164
   ```
4. **Telemetry flow**: wait 60 s then verify snapshots appear:
   ```bash
   curl -s 'https://infraq.app/api/v1/collectors/snapshots?kind=system_vitals' \
     | python3 -m json.tool | head -20
   ```

---

## Rollback Plan

If the proxy agent approach fails:

1. **Immediate**: Stop the agent on hz.164:
   ```bash
   systemctl stop internalcmdb-agent
   ```
2. **Fallback to Option A** (NAT): Apply the iptables MASQUERADE rule
   documented above and deploy individual agents inside each LXC.
3. **Revert config**: Remove the `[lxc]` section from
   `/etc/internalcmdb/agent.toml` on hz.164 and restart.

Rollback does **not** require any changes on the API side — orphaned
agent records are automatically marked as `offline` by the staleness
checker after 5 minutes of missed heartbeats.

---

## Monitoring & Alerting

- The fleet health endpoint (`GET /api/v1/collectors/health`) will show
  hz.164 as `degraded` or `offline` if the proxy agent stops reporting.
- Configure an alert in Prometheus/Alertmanager if
  `cmdb_collector_ingest_total{host="hz.164"}` stops incrementing for
  more than 2× the longest tier interval (10 min).
