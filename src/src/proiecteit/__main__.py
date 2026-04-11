"""CLI entrypoint for quick local validation."""

import json

from proiecteit.health import health_check

if __name__ == "__main__":
    print(json.dumps(health_check()))
