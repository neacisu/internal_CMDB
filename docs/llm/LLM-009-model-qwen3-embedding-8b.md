---
id: LLM-009
title: Model qwen3-embedding-8b-q5km — Documentație Completă
doc_class: reference
domain: llm-runtime
version: "1.0"
status: active
created: 2026-04-14
updated: 2026-07-05
owner: platform_architecture_lead
tags: [llm, ollama, embeddings, qwen3, gguf, q5km, rag, semantic-search, hz.62]
---

# LLM-009 — qwen3-embedding-8b-q5km (Model Embeddings)

> **OpenRouter migration (2026-07-05):** Alias `qwen3-embedding-8b-q5km` routes to **qwen/qwen3-embedding-8b** via LiteLLM (OpenAI `/v1/embeddings`). Dimension **4096** preserved; pgvector cosine vs Ollama vectors ~0.996 on sample text. hz.62 Ollama stopped.

| Câmp          | Valoare                                     |
|---------------|---------------------------------------------|
| Versiune      | 1.0                                         |
| Data          | 2026-04-14                                  |
| Alias intern  | `embeddings`                                |
| Status        | active                                      |
| Node          | hz.62 (10.0.1.62)                           |
| Base URL      | `https://infraq.app/llm/v1/embeddings`      |

---

## 1. Infrastructură

| Câmp             | Valoare                                        |
|------------------|------------------------------------------------|
| Node             | hz.62 — 95.216.66.62 / 10.0.1.62             |
| GPU              | NVIDIA GeForce GTX 1080                        |
| VRAM total       | 8,192 MiB                                      |
| VRAM folosit     | 6,190 MiB (75%) — model încărcat              |
| VRAM liber       | ~2,002 MiB                                     |
| Temperatură GPU  | 40°C (idle)                                    |
| Power draw       | 11.59 W (idle)                                 |
| Container        | `ollama-embed`                                 |
| Image            | `ollama` (Ollama **0.17.7**)                   |
| Port intern      | `11434` (Ollama default)                       |
| Port extern      | `10.0.1.62:8003 → container:11434`             |
| HAProxy VIP      | `10.0.1.10:49003 → 10.0.1.62:8003`            |
| Traefik prefix   | `/llm/v1/embeddings` → `http://10.0.1.10:49003` |
| Status           | running din 2026-03-06 (~5 săptămâni uptime)  |
| Compose file     | `/ai-infrastructure/docker-compose.yml` pe hz.62 |
| Uptime monitorizare | Traefik health check la 30s                 |

### Variabile de mediu container

```env
OLLAMA_HOST=0.0.0.0:11434
OLLAMA_KEEP_ALIVE=24h
OLLAMA_NUM_PARALLEL=2
OLLAMA_MAX_LOADED_MODELS=1
```

| Variabilă | Valoare | Efect |
|-----------|---------|-------|
| `OLLAMA_KEEP_ALIVE` | 24h | Modelul rămâne în VRAM 24h de la ultimul request |
| `OLLAMA_NUM_PARALLEL` | 2 | Maxim 2 request-uri de embedding simultane |
| `OLLAMA_MAX_LOADED_MODELS` | 1 | Un singur model în VRAM (nu se pot încărca alte modele) |

---

## 2. Model

| Câmp                | Valoare                                          |
|---------------------|--------------------------------------------------|
| Nume Ollama         | `qwen3-embedding-8b-q5km:latest`                 |
| Familie             | qwen3                                            |
| Parametri           | 7,567,295,488 (7.6B)                             |
| Format              | GGUF                                             |
| Quantizare          | Q5_K_M                                           |
| Dimensiune fișier   | 5,422,342,729 bytes (≈5.05 GB)                   |
| VRAM la runtime     | 6,869,710,624 bytes (≈6.4 GB)                    |
| Context length      | **4,096 tokens** (limitat runtime de Ollama)     |
| Dimensiune embedding| **4,096 float32** per text                       |
| Digest              | `710582d18cdd13b29f65179076f5fd59364117a005d3e11e751a02d4b6605016` |
| Keep-alive          | 24h de la ultimul request → auto-unload          |
| Tool calling        | ❌ Nu este suportat (model de embeddings)        |

---

## 3. Endpoint-uri Disponibile

| Metodă | Path               | Descriere                                           |
|--------|--------------------|-----------------------------------------------------|
| GET    | `/api/version`     | `{"version":"0.17.7"}` — versiune Ollama            |
| GET    | `/api/tags`        | Lista modelelor instalate cu detalii complete       |
| GET    | `/api/ps`          | Modele încărcate în VRAM cu `size_vram` și `expires_at` |
| POST   | `/api/show`        | Detalii complete model (model_info, details, parameters) |
| POST   | `/api/embed`       | Embed format nativ Ollama (input: array de strings) |
| POST   | `/v1/embeddings`   | Embed format OpenAI-compatible (recomandat)         |
| GET    | `/v1/models`       | Lista modele format OpenAI                          |

> **Notă**: Endpointul `/api/chat` și `/api/generate` există în Ollama dar nu sunt funcționale pentru modele de embeddings (nu generează text).

---

## 4. Exemple Apeluri API

### Embedding Format OpenAI (recomandat)

```http
POST https://infraq.app/llm/v1/embeddings/v1/embeddings
Content-Type: application/json

{
  "model": "qwen3-embedding-8b-q5km:latest",
  "input": ["Text de embedat pentru căutare semantică", "Al doilea document"]
}
```

**Răspuns:**
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.024, -0.011, 0.003, ..., -0.007]
    },
    {
      "object": "embedding",
      "index": 1,
      "embedding": [-0.015, 0.032, ...]
    }
  ],
  "model": "qwen3-embedding-8b-q5km:latest",
  "usage": {"prompt_tokens": 14, "total_tokens": 14}
}
```

> Vector de **4,096 float32** per text. Dimensiune totală: 4,096 × 4 bytes = 16,384 bytes per embedding.

### Embedding Format Nativ Ollama (batch)

```http
POST https://infraq.app/llm/v1/embeddings/api/embed
Content-Type: application/json

{
  "model": "qwen3-embedding-8b-q5km:latest",
  "input": ["Primul document", "Al doilea document", "Al treilea document"]
}
```

**Răspuns:**
```json
{
  "embeddings": [
    [0.024, -0.011, ..., -0.007],
    [-0.015, 0.032, ...],
    [0.001, -0.044, ...]
  ]
}
```

### Verificare Model Încărcat în VRAM

```http
GET https://infraq.app/llm/v1/embeddings/api/ps
```

**Răspuns (confirmat live):**
```json
{
  "models": [{
    "name": "qwen3-embedding-8b-q5km:latest",
    "size": 6869710624,
    "size_vram": 6869710624,
    "context_length": 4096,
    "expires_at": "2026-04-15T13:25:45.190656173Z",
    "details": {
      "format": "gguf",
      "family": "qwen3",
      "parameter_size": "7.6B",
      "quantization_level": "Q5_K_M"
    }
  }]
}
```

### Detalii Model

```http
POST https://infraq.app/llm/v1/embeddings/api/show
Content-Type: application/json

{"name": "qwen3-embedding-8b-q5km:latest"}
```

### Verificare Versiune

```bash
curl https://infraq.app/llm/v1/embeddings/api/version
# → {"version":"0.17.7"}
```

---

## 5. Integrare Python — OpenAI SDK

```python
from openai import OpenAI
import numpy as np

client = OpenAI(
    base_url="https://infraq.app/llm/v1/embeddings",
    api_key="unused",
)

# Embed un singur text
response = client.embeddings.create(
    model="qwen3-embedding-8b-q5km:latest",
    input="Documentul de indexat pentru căutare semantică",
)
vector = response.data[0].embedding
print(f"Dimensiune vector: {len(vector)}")  # 4096

# Embed batch de texte
texts = [
    "Factura nr. 1234 din data de 15.03.2026",
    "Contract de prestări servicii IT",
    "Raport lunar de vânzări Q1 2026",
]
response = client.embeddings.create(
    model="qwen3-embedding-8b-q5km:latest",
    input=texts,
)
vectors = [item.embedding for item in response.data]
print(f"Vectori generați: {len(vectors)}, dim: {len(vectors[0])}")

# Similaritate cosinus între două texte
def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

v1 = client.embeddings.create(
    model="qwen3-embedding-8b-q5km:latest",
    input="contract de vânzare imobil",
).data[0].embedding

v2 = client.embeddings.create(
    model="qwen3-embedding-8b-q5km:latest",
    input="acord de vânzare proprietate",
).data[0].embedding

similarity = cosine_similarity(v1, v2)
print(f"Similaritate: {similarity:.4f}")  # ~0.85-0.95 pentru texte semantice similare
```

---

## 6. Integrare RAG cu pgvector (PostgreSQL)

```python
from openai import OpenAI
import psycopg2
import json

embed_client = OpenAI(
    base_url="https://infraq.app/llm/v1/embeddings",
    api_key="unused",
)

conn = psycopg2.connect("postgresql://user:pass@localhost/ragdb")
cur = conn.cursor()

# Creare tabel (execută o dată)
cur.execute("""
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        content TEXT,
        embedding vector(4096),
        metadata JSONB
    );
    CREATE INDEX IF NOT EXISTS documents_embedding_idx
        ON documents USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
""")
conn.commit()

def embed_text(text: str) -> list[float]:
    response = embed_client.embeddings.create(
        model="qwen3-embedding-8b-q5km:latest",
        input=text,
    )
    return response.data[0].embedding

def index_document(content: str, metadata: dict):
    vector = embed_text(content)
    cur.execute(
        "INSERT INTO documents (content, embedding, metadata) VALUES (%s, %s, %s)",
        (content, vector, json.dumps(metadata))
    )
    conn.commit()

def search_similar(query: str, top_k: int = 5) -> list[dict]:
    query_vector = embed_text(query)
    cur.execute("""
        SELECT content, metadata,
               1 - (embedding <=> %s::vector) AS similarity
        FROM documents
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_vector, query_vector, top_k))
    return [
        {"content": row[0], "metadata": row[1], "similarity": float(row[2])}
        for row in cur.fetchall()
    ]

# Utilizare
index_document("Contractul de prestări servicii IT din 2026", {"type": "contract", "year": 2026})
results = search_similar("contract IT servicii")
for r in results:
    print(f"[{r['similarity']:.3f}] {r['content'][:80]}")
```

---

## 7. Cazuri de Utilizare

| Caz de utilizare | Detalii |
|------------------|---------|
| **RAG (Retrieval Augmented Generation)** | Indexare documente → căutare semantică → context pentru LLM |
| **Căutare semantică** | Găsire documente similare conceptual, nu doar keyword-based |
| **Deduplicare documente** | Detectare texte similare/duplicate via similaritate cosinus |
| **Clustering documente** | Grupare automată după conținut semantic |
| **Recomandare conținut** | Articole/produse similare cu cel curent vizualizat |
| **Clasificare zero-shot** | Embed text + embed etichete → nearest neighbor |
| **Indexare pentru audit** | Pre-procesare documente pentru căutare CMDB |

---

## 8. Performanță și Latențe

| Metrică | Valoare | Note |
|---------|---------|------|
| Latență `/api/version` via Traefik | ~34ms | măsurat 2026-04-14 |
| Timp embedding un text scurt | ~50-150ms | model pre-încărcat în VRAM |
| Cold start (model descărcat) | ~5-10s | reload GGUF din disk la prima cerere după 24h |
| Batch size recomandat | 10-50 texte | optim pentru throughput |
| Paralelism | max 2 cereri simultane | `OLLAMA_NUM_PARALLEL=2` |

---

## 9. Limitări și Note Operaționale

| Limitare | Detaliu | Workaround |
|----------|---------|-----------|
| **Cold start 24h** | Modelul se descarcă din VRAM după 24h fără cereri | Implementează un ping periodic (cron la fiecare 20h) |
| **Context 4,096 tokens** | Textele mai lungi trebuie trungate sau chunked | Împarte documentele în chunk-uri de ≤ 4,096 tokens |
| **GPU vechi (GTX 1080)** | CUDA Compute 6.1 — nu suportă FP8/BF16 hardware | GGUF Q5_K_M rulează pe CPU/CUDA FP32, compatibil |
| **Fără chat/completions** | Exclusiv embedding — nu generează text | Folosește `fast` sau `reasoning` pentru generare |
| **OLLAMA_MAX_LOADED_MODELS=1** | Nu pot fi două modele simultane în VRAM | Nu instala alte modele Ollama pe hz.62 |
| **Dimensiune fixă 4,096** | Nu configurabilă la runtime | Dimensionează index pgvector cu `vector(4096)` |

### Ping Periodic pentru Evitare Cold Start

```bash
# /etc/cron.d/ollama-keepalive
0 */20 * * * root curl -s -X POST http://10.0.1.62:8003/api/embed \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3-embedding-8b-q5km:latest","input":["ping"]}' > /dev/null
```

---

## 10. Monitorizare

```bash
# Verificare model încărcat în VRAM
curl http://10.0.1.62:8003/api/ps | python3 -m json.tool

# Verificare versiune Ollama
curl http://10.0.1.62:8003/api/version

# Lista modele disponibile
curl http://10.0.1.62:8003/api/tags | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data['models']:
    print(m['name'], m['size'] // 1024**3, 'GB')
"

# Test embedding rapid (intern)
curl -s -X POST http://10.0.1.62:8003/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3-embedding-8b-q5km:latest","input":["test"]}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('dim:', len(d['data'][0]['embedding']))"
# → dim: 4096
```

---

## Changelog

| Versiune | Data | Modificări |
|---------|------|------------|
| 1.0 | 2026-04-14 | Document inițial creat — date verificate live pe hz.62 |
