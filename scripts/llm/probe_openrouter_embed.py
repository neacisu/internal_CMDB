#!/usr/bin/env python3
"""Probe OpenRouter embedding model for dimension compatibility with pgvector (4096).

Usage:
  export OPENROUTER_INFRA_APP_KEY_FILE=/run/secrets/openrouter_infra_key
  python scripts/llm/probe_openrouter_embed.py

Exits 0 when a provider returns 4096-dim vectors; prints provider recommendation.
"""

from __future__ import annotations

import json
import math
import os
import sys
import urllib.error
import urllib.request

MODEL = "qwen/qwen3-embedding-8b"
API_URL = "https://openrouter.ai/api/v1/embeddings"
EXPECTED_DIM = 4096
SAMPLE_TEXT = "internalCMDB embedding compatibility probe"


def _read_key() -> str:
    key_file = os.environ.get("OPENROUTER_INFRA_APP_KEY_FILE", "")
    if key_file and os.path.isfile(key_file):
        return open(key_file, encoding="utf-8").read().strip()
    key = os.environ.get("OPENROUTER_INFRA_APP_KEY", "")
    if key:
        return key.strip()
    print("ERROR: set OPENROUTER_INFRA_APP_KEY or OPENROUTER_INFRA_APP_KEY_FILE", file=sys.stderr)
    sys.exit(2)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _request(api_key: str, provider_only: str | None = None) -> list[float]:
    body: dict[str, object] = {"model": MODEL, "input": [SAMPLE_TEXT]}
    if provider_only:
        body["provider"] = {"order": [provider_only], "only": [provider_only]}
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://infraq.app",
            "X-Title": "internalCMDB embed probe",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode())
    data = payload.get("data") or []
    if not data:
        raise RuntimeError(f"empty data: {payload}")
    embedding = data[0].get("embedding")
    if not isinstance(embedding, list):
        raise RuntimeError(f"unexpected embedding type: {type(embedding)}")
    return [float(x) for x in embedding]


def main() -> int:
    api_key = _read_key()
    providers_to_try = [
        None,
        "DeepInfra",
        "Together",
        "Fireworks",
    ]
    results: list[tuple[str, int, list[float]]] = []
    for prov in providers_to_try:
        label = prov or "default-routing"
        try:
            vec = _request(api_key, prov)
            results.append((label, len(vec), vec))
            print(f"OK provider={label} dim={len(vec)}")
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            print(f"FAIL provider={label} error={exc}")

    good = [(l, d, v) for l, d, v in results if d == EXPECTED_DIM]
    if not good:
        print(f"ERROR: no provider returned dim={EXPECTED_DIM}", file=sys.stderr)
        return 1

    label, dim, vec_a = good[0]
    if len(good) > 1:
        _, _, vec_b = good[1]
        sim = _cosine(vec_a, vec_b)
        print(f"cosine_similarity({good[0][0]},{good[1][0]})={sim:.6f}")

    print(f"RECOMMENDED_PROVIDER={label}")
    print(f"EMBED_DIM={dim}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
