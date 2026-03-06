# Cluster SSH Checker

Subproject dedicated to SSH connectivity validation for cluster hosts defined in `~/.ssh/config`.

## Run

```bash
python subprojects/cluster-ssh-checker/test_cluster_ssh.py
```

## Useful Options

```bash
python subprojects/cluster-ssh-checker/test_cluster_ssh.py --timeout 4 --workers 12
python subprojects/cluster-ssh-checker/test_cluster_ssh.py --include-regex '^(hz\\.|orchestrator|postgres-main)'
python subprojects/cluster-ssh-checker/test_cluster_ssh.py --exclude-regex '^imac$'
```

## Exit Codes

- `0`: all hosts reachable and command execution succeeded
- `1`: at least one host failed
- `2`: no concrete hosts found in config
