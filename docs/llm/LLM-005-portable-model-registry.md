# LLM-005 — Registru Portabil Modele Self-Hosted

| Câmp          | Valoare                              |
|---------------|--------------------------------------|
| Versiune      | 1.0.0                               |
| Data          | 2026-03-22                           |
| Gateway       | https://infraq.app                   |
| Prefix API    | /llm/v1                             |
| Protocol      | HTTPS (TLS via Cloudflare)           |
| Rate Limit    | 60 req/s burst 120 (modele), 30 req/s burst 60 (guard) |
| Autentificare | Fără (modele), Bearer token (guard)  |

---

## Manifest JSON

Manifestul de mai jos poate fi copiat și consumat direct de orice aplicație.
Toate endpoint-urile au fost verificate live la data emiterii.

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-03-22T15:10:00Z",
  "gateway": {
    "base_url": "https://infraq.app",
    "prefix": "/llm/v1",
    "protocol": "https",
    "tls": true,
    "rate_limit": {
      "models": { "average": 60, "burst": 120 },
      "guard":  { "average": 30, "burst": 60 }
    }
  },

  "models": [
    {
      "id": "reasoning",
      "model_id": "Qwen/QwQ-32B-AWQ",
      "base_url": "https://infraq.app/llm/v1/reasoning",
      "role": "Complex reasoning, chain-of-thought, analysis",
      "engine": "vLLM",
      "engine_version": "0.16.0",
      "architecture": "Qwen2.5 (QwQ variant)",
      "parameters": "32B",
      "quantization": "AWQ (4-bit)",
      "max_model_len": 24576,
      "gpu": "NVIDIA L40S 48GB",
      "vram_allocated_pct": 0.65,
      "streaming": true,
      "auth": null,

      "api_compatibility": [
        "openai",
        "anthropic"
      ],

      "endpoints": {
        "chat_completions": {
          "method": "POST",
          "path": "/chat/completions",
          "full_url": "https://infraq.app/llm/v1/reasoning/chat/completions",
          "description": "OpenAI Chat Completions API — mesaje multi-turn, streaming SSE",
          "request_example": {
            "model": "Qwen/QwQ-32B-AWQ",
            "messages": [{"role": "user", "content": "Explain quantum computing"}],
            "max_tokens": 2048,
            "temperature": 0.7,
            "stream": false
          }
        },
        "completions": {
          "method": "POST",
          "path": "/completions",
          "full_url": "https://infraq.app/llm/v1/reasoning/completions",
          "description": "OpenAI Completions API — text completion cu prompt brut",
          "request_example": {
            "model": "Qwen/QwQ-32B-AWQ",
            "prompt": "The capital of France is",
            "max_tokens": 64
          }
        },
        "messages": {
          "method": "POST",
          "path": "/messages",
          "full_url": "https://infraq.app/llm/v1/reasoning/messages",
          "description": "Anthropic Messages API — format compatibil Claude SDK",
          "request_example": {
            "model": "Qwen/QwQ-32B-AWQ",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 256
          }
        },
        "responses": {
          "method": "POST",
          "path": "/responses",
          "full_url": "https://infraq.app/llm/v1/reasoning/responses",
          "description": "OpenAI Responses API — format nou OpenAI cu response ID tracking",
          "request_example": {
            "model": "Qwen/QwQ-32B-AWQ",
            "input": "Summarize this document",
            "max_output_tokens": 1024
          }
        },
        "responses_get": {
          "method": "GET",
          "path": "/responses/{response_id}",
          "full_url": "https://infraq.app/llm/v1/reasoning/responses/{response_id}",
          "description": "Retrieve o response anterioară după ID"
        },
        "responses_cancel": {
          "method": "POST",
          "path": "/responses/{response_id}/cancel",
          "full_url": "https://infraq.app/llm/v1/reasoning/responses/{response_id}/cancel",
          "description": "Anulează o response în curs de generare"
        },
        "chat_completions_render": {
          "method": "POST",
          "path": "/chat/completions/render",
          "full_url": "https://infraq.app/llm/v1/reasoning/chat/completions/render",
          "description": "Renderizează template-ul chat fără a genera — util pentru debugging și token counting",
          "request_example": {
            "model": "Qwen/QwQ-32B-AWQ",
            "messages": [{"role": "user", "content": "Hello"}]
          }
        },
        "completions_render": {
          "method": "POST",
          "path": "/completions/render",
          "full_url": "https://infraq.app/llm/v1/reasoning/completions/render",
          "description": "Renderizează prompt-ul completion fără a genera"
        },
        "models": {
          "method": "GET",
          "path": "/models",
          "full_url": "https://infraq.app/llm/v1/reasoning/models",
          "description": "Lista modelelor disponibile pe acest engine"
        },
        "tokenize": {
          "method": "POST",
          "path": "/tokenize",
          "full_url": "https://infraq.app/llm/v1/reasoning/tokenize",
          "description": "Tokenizare text → token IDs + count + max_model_len",
          "request_example": {
            "model": "Qwen/QwQ-32B-AWQ",
            "prompt": "Hello world"
          },
          "response_example": {
            "count": 2,
            "max_model_len": 24576,
            "tokens": [9707, 1879]
          }
        },
        "detokenize": {
          "method": "POST",
          "path": "/detokenize",
          "full_url": "https://infraq.app/llm/v1/reasoning/detokenize",
          "description": "Detokenizare token IDs → text",
          "request_example": {
            "model": "Qwen/QwQ-32B-AWQ",
            "tokens": [9707, 1879]
          },
          "response_example": {
            "prompt": "Hello world"
          }
        },
        "health": {
          "method": "GET",
          "path": "/health",
          "full_url": "https://infraq.app/llm/v1/reasoning/health",
          "description": "Health check — 200 dacă engine-ul este activ"
        },
        "ping": {
          "method": "GET",
          "path": "/ping",
          "full_url": "https://infraq.app/llm/v1/reasoning/ping",
          "description": "Ping rapid — latență minimă"
        },
        "version": {
          "method": "GET",
          "path": "/version",
          "full_url": "https://infraq.app/llm/v1/reasoning/version",
          "description": "Versiunea engine-ului vLLM",
          "response_example": { "version": "0.16.0" }
        },
        "load": {
          "method": "GET",
          "path": "/load",
          "full_url": "https://infraq.app/llm/v1/reasoning/load",
          "description": "Încărcarea curentă a serverului (0 = idle)",
          "response_example": { "server_load": 0 }
        },
        "openapi_spec": {
          "method": "GET",
          "path": "/openapi.json",
          "full_url": "https://infraq.app/llm/v1/reasoning/openapi.json",
          "description": "Specificația OpenAPI completă a engine-ului (20 paths)"
        }
      }
    },

    {
      "id": "fast",
      "model_id": "Qwen/Qwen2.5-14B-Instruct-AWQ",
      "base_url": "https://infraq.app/llm/v1/fast",
      "role": "Fast inference, classification, extraction, simple Q&A",
      "engine": "vLLM",
      "engine_version": "0.16.0",
      "architecture": "Qwen2.5",
      "parameters": "14B",
      "quantization": "AWQ (4-bit)",
      "max_model_len": 12288,
      "gpu": "NVIDIA L40S 48GB (shared with reasoning)",
      "vram_allocated_pct": 0.28,
      "streaming": true,
      "auth": null,

      "api_compatibility": [
        "openai",
        "anthropic"
      ],

      "endpoints": {
        "chat_completions": {
          "method": "POST",
          "path": "/chat/completions",
          "full_url": "https://infraq.app/llm/v1/fast/chat/completions",
          "description": "OpenAI Chat Completions API",
          "request_example": {
            "model": "Qwen/Qwen2.5-14B-Instruct-AWQ",
            "messages": [{"role": "user", "content": "Classify this text"}],
            "max_tokens": 512,
            "temperature": 0.3,
            "stream": false
          }
        },
        "completions": {
          "method": "POST",
          "path": "/completions",
          "full_url": "https://infraq.app/llm/v1/fast/completions",
          "description": "OpenAI Completions API"
        },
        "messages": {
          "method": "POST",
          "path": "/messages",
          "full_url": "https://infraq.app/llm/v1/fast/messages",
          "description": "Anthropic Messages API"
        },
        "responses": {
          "method": "POST",
          "path": "/responses",
          "full_url": "https://infraq.app/llm/v1/fast/responses",
          "description": "OpenAI Responses API"
        },
        "responses_get": {
          "method": "GET",
          "path": "/responses/{response_id}",
          "full_url": "https://infraq.app/llm/v1/fast/responses/{response_id}",
          "description": "Retrieve response după ID"
        },
        "responses_cancel": {
          "method": "POST",
          "path": "/responses/{response_id}/cancel",
          "full_url": "https://infraq.app/llm/v1/fast/responses/{response_id}/cancel",
          "description": "Anulează response"
        },
        "chat_completions_render": {
          "method": "POST",
          "path": "/chat/completions/render",
          "full_url": "https://infraq.app/llm/v1/fast/chat/completions/render",
          "description": "Render template chat"
        },
        "completions_render": {
          "method": "POST",
          "path": "/completions/render",
          "full_url": "https://infraq.app/llm/v1/fast/completions/render",
          "description": "Render prompt completion"
        },
        "models": {
          "method": "GET",
          "path": "/models",
          "full_url": "https://infraq.app/llm/v1/fast/models",
          "description": "Lista modelelor"
        },
        "tokenize": {
          "method": "POST",
          "path": "/tokenize",
          "full_url": "https://infraq.app/llm/v1/fast/tokenize",
          "description": "Tokenizare text → token IDs",
          "request_example": {
            "model": "Qwen/Qwen2.5-14B-Instruct-AWQ",
            "prompt": "Hello world"
          }
        },
        "detokenize": {
          "method": "POST",
          "path": "/detokenize",
          "full_url": "https://infraq.app/llm/v1/fast/detokenize",
          "description": "Detokenizare token IDs → text"
        },
        "health": {
          "method": "GET",
          "path": "/health",
          "full_url": "https://infraq.app/llm/v1/fast/health",
          "description": "Health check"
        },
        "ping": {
          "method": "GET",
          "path": "/ping",
          "full_url": "https://infraq.app/llm/v1/fast/ping",
          "description": "Ping rapid"
        },
        "version": {
          "method": "GET",
          "path": "/version",
          "full_url": "https://infraq.app/llm/v1/fast/version",
          "description": "Versiunea engine vLLM"
        },
        "load": {
          "method": "GET",
          "path": "/load",
          "full_url": "https://infraq.app/llm/v1/fast/load",
          "description": "Server load"
        },
        "openapi_spec": {
          "method": "GET",
          "path": "/openapi.json",
          "full_url": "https://infraq.app/llm/v1/fast/openapi.json",
          "description": "Specificația OpenAPI"
        }
      }
    },

    {
      "id": "embeddings",
      "model_id": "qwen3-embedding-8b-q5km",
      "base_url": "https://infraq.app/llm/v1/embeddings",
      "role": "Text embeddings for semantic search, RAG, similarity",
      "engine": "Ollama",
      "engine_version": "0.17.7",
      "architecture": "Qwen3",
      "parameters": "7.6B",
      "quantization": "Q5_K_M (GGUF)",
      "embedding_dimension": 4096,
      "context_length": 4096,
      "gpu": "NVIDIA RTX 4060 Ti 16GB",
      "vram_loaded": "6.4 GB",
      "streaming": false,
      "auth": null,

      "api_compatibility": [
        "openai",
        "ollama"
      ],

      "endpoints": {
        "embeddings": {
          "method": "POST",
          "path": "/embeddings",
          "full_url": "https://infraq.app/llm/v1/embeddings/embeddings",
          "description": "OpenAI Embeddings API — returnează vectori de dimensiune 4096",
          "request_example": {
            "model": "qwen3-embedding-8b-q5km",
            "input": "Text to embed"
          },
          "response_shape": {
            "object": "list",
            "data": [{ "object": "embedding", "index": 0, "embedding": ["<4096 floats>"] }],
            "model": "qwen3-embedding-8b-q5km",
            "usage": { "prompt_tokens": "N", "total_tokens": "N" }
          }
        },
        "models": {
          "method": "GET",
          "path": "/models",
          "full_url": "https://infraq.app/llm/v1/embeddings/models",
          "description": "Lista modelelor (format OpenAI)"
        },
        "api_embed": {
          "method": "POST",
          "path": "/api/embed",
          "full_url": "https://infraq.app/llm/v1/embeddings/api/embed",
          "description": "Ollama native embed — suportă batch input, format diferit de OpenAI",
          "request_example": {
            "model": "qwen3-embedding-8b-q5km",
            "input": "Text to embed"
          },
          "response_shape": {
            "model": "qwen3-embedding-8b-q5km",
            "embeddings": ["<array of 4096-dim vectors>"]
          }
        },
        "api_tags": {
          "method": "GET",
          "path": "/api/tags",
          "full_url": "https://infraq.app/llm/v1/embeddings/api/tags",
          "description": "Ollama native — lista modelelor cu detalii (size, quantization, family)"
        },
        "api_version": {
          "method": "GET",
          "path": "/api/version",
          "full_url": "https://infraq.app/llm/v1/embeddings/api/version",
          "description": "Versiunea Ollama"
        },
        "api_ps": {
          "method": "GET",
          "path": "/api/ps",
          "full_url": "https://infraq.app/llm/v1/embeddings/api/ps",
          "description": "Modele încărcate în VRAM cu detalii (size_vram, context_length, expires_at)"
        }
      }
    }
  ],

  "guardrails": {
    "id": "guard",
    "service": "LLM Guard",
    "image": "laiyer/llm-guard-api:latest",
    "base_url": "https://infraq.app/llm/v1/guard",
    "role": "Input/output scanning — prompt injection detection, PII anonymization, toxicity, topic banning",
    "auth": {
      "type": "bearer",
      "header": "Authorization",
      "format": "Bearer <token>",
      "note": "Token-ul este configurat pe server. Contactați administratorul pentru acces."
    },

    "scanners_input": [
      "PromptInjection",
      "BanTopics",
      "Toxicity",
      "Anonymize"
    ],
    "scanners_output": [
      "Sensitive",
      "Toxicity",
      "Relevance",
      "Deanonymize"
    ],

    "endpoints": {
      "analyze_prompt": {
        "method": "POST",
        "path": "/analyze/prompt",
        "full_url": "https://infraq.app/llm/v1/guard/analyze/prompt",
        "description": "Scanează un prompt de intrare pentru injecții, toxicitate, PII",
        "request_example": {
          "prompt": "User input text to scan"
        },
        "response_example": {
          "is_valid": true,
          "scanners": {
            "PromptInjection": 0.0,
            "BanTopics": -0.4,
            "Toxicity": -1.0,
            "Anonymize": 0.0
          }
        }
      },
      "analyze_output": {
        "method": "POST",
        "path": "/analyze/output",
        "full_url": "https://infraq.app/llm/v1/guard/analyze/output",
        "description": "Scanează output-ul generat de model pentru date sensibile, toxicitate, relevanță",
        "request_example": {
          "prompt": "Original user prompt",
          "output": "Model generated output to scan"
        },
        "response_example": {
          "is_valid": true,
          "scanners": {
            "Sensitive": -1.0,
            "Toxicity": -1.0,
            "Relevance": 0.1,
            "Deanonymize": -1.0
          }
        }
      },
      "scan_prompt": {
        "method": "POST",
        "path": "/scan/prompt",
        "full_url": "https://infraq.app/llm/v1/guard/scan/prompt",
        "description": "Alias pentru /analyze/prompt — aceeași funcționalitate"
      },
      "scan_output": {
        "method": "POST",
        "path": "/scan/output",
        "full_url": "https://infraq.app/llm/v1/guard/scan/output",
        "description": "Alias pentru /analyze/output — aceeași funcționalitate"
      },
      "healthz": {
        "method": "GET",
        "path": "/healthz",
        "full_url": "https://infraq.app/llm/v1/guard/healthz",
        "description": "Liveness check",
        "response_example": { "status": "alive" }
      },
      "readyz": {
        "method": "GET",
        "path": "/readyz",
        "full_url": "https://infraq.app/llm/v1/guard/readyz",
        "description": "Readiness check — scannerele sunt încărcate",
        "response_example": { "status": "ready" }
      }
    }
  },

  "infrastructure": {
    "cluster": "Hetzner bare-metal + cloud",
    "ingress": "Traefik v3 (reverse proxy, TLS termination, path routing)",
    "dns": "infraq.app (Cloudflare)",
    "network": "Private vSwitch 10.0.1.0/24",
    "health_checks": "Traefik active health checks every 30s per service",
    "hosts": [
      {
        "role": "gpu-node",
        "services": ["vLLM reasoning", "vLLM fast", "Ollama embeddings"],
        "gpu": "NVIDIA L40S 48GB + NVIDIA RTX 4060 Ti 16GB"
      },
      {
        "role": "orchestrator",
        "services": ["Traefik ingress", "LLM Guard", "PostgreSQL", "Redis"]
      }
    ]
  }
}
```

---

## Ghid de Integrare

### Python — OpenAI SDK

```python
from openai import OpenAI

# Reasoning (chain-of-thought, analiză complexă)
reasoning = OpenAI(
    base_url="https://infraq.app/llm/v1/reasoning",
    api_key="unused",
)

response = reasoning.chat.completions.create(
    model="Qwen/QwQ-32B-AWQ",
    messages=[{"role": "user", "content": "Analyze this contract for risks"}],
    max_tokens=4096,
    temperature=0.7,
    stream=True,
)
for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")


# Fast (clasificare, extracție, Q&A rapid)
fast = OpenAI(
    base_url="https://infraq.app/llm/v1/fast",
    api_key="unused",
)

result = fast.chat.completions.create(
    model="Qwen/Qwen2.5-14B-Instruct-AWQ",
    messages=[{"role": "user", "content": "Classify: positive or negative?"}],
    max_tokens=16,
    temperature=0.0,
)
print(result.choices[0].message.content)


# Embeddings
embeddings = OpenAI(
    base_url="https://infraq.app/llm/v1/embeddings",
    api_key="unused",
)

vectors = embeddings.embeddings.create(
    model="qwen3-embedding-8b-q5km",
    input=["First document", "Second document"],
)
print(f"Dimension: {len(vectors.data[0].embedding)}")  # 4096
```

### Python — Anthropic SDK

```python
import anthropic

client = anthropic.Anthropic(
    base_url="https://infraq.app/llm/v1/reasoning",
    api_key="unused",
)

message = client.messages.create(
    model="Qwen/QwQ-32B-AWQ",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain quantum computing"}],
)
print(message.content[0].text)
```

### Python — Guardrails Integration

```python
import requests

GUARD_URL = "https://infraq.app/llm/v1/guard"
GUARD_TOKEN = "<your-token>"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {GUARD_TOKEN}",
}

def scan_input(prompt: str) -> dict:
    r = requests.post(
        f"{GUARD_URL}/analyze/prompt",
        headers=HEADERS,
        json={"prompt": prompt},
    )
    return r.json()

def scan_output(prompt: str, output: str) -> dict:
    r = requests.post(
        f"{GUARD_URL}/analyze/output",
        headers=HEADERS,
        json={"prompt": prompt, "output": output},
    )
    return r.json()

# Pre-generation: scan user input
input_result = scan_input("Tell me about machine learning")
if not input_result["is_valid"]:
    raise ValueError(f"Input blocked: {input_result['scanners']}")

# Generate with your preferred model...
generated_text = "Machine learning is a subset of AI..."

# Post-generation: scan model output
output_result = scan_output("Tell me about machine learning", generated_text)
if not output_result["is_valid"]:
    raise ValueError(f"Output blocked: {output_result['scanners']}")
```

### cURL — Quick Reference

```bash
# Chat completion (reasoning)
curl -X POST https://infraq.app/llm/v1/reasoning/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/QwQ-32B-AWQ","messages":[{"role":"user","content":"Hello"}],"max_tokens":256}'

# Chat completion (fast)
curl -X POST https://infraq.app/llm/v1/fast/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen2.5-14B-Instruct-AWQ","messages":[{"role":"user","content":"Hello"}],"max_tokens":256}'

# Embeddings
curl -X POST https://infraq.app/llm/v1/embeddings/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3-embedding-8b-q5km","input":"Text to embed"}'

# Tokenize
curl -X POST https://infraq.app/llm/v1/reasoning/tokenize \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/QwQ-32B-AWQ","prompt":"Count my tokens"}'

# Guardrails — scan input
curl -X POST https://infraq.app/llm/v1/guard/analyze/prompt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt":"User input to scan"}'

# Health checks
curl https://infraq.app/llm/v1/reasoning/health
curl https://infraq.app/llm/v1/fast/health
curl https://infraq.app/llm/v1/embeddings/api/version
curl https://infraq.app/llm/v1/guard/healthz
```

### TypeScript / JavaScript

```typescript
import OpenAI from "openai";

const reasoning = new OpenAI({
  baseURL: "https://infraq.app/llm/v1/reasoning",
  apiKey: "unused",
});

const fast = new OpenAI({
  baseURL: "https://infraq.app/llm/v1/fast",
  apiKey: "unused",
});

const embeddings = new OpenAI({
  baseURL: "https://infraq.app/llm/v1/embeddings",
  apiKey: "unused",
});

// Chat
const chat = await reasoning.chat.completions.create({
  model: "Qwen/QwQ-32B-AWQ",
  messages: [{ role: "user", content: "Hello" }],
  max_tokens: 256,
});

// Embeddings
const emb = await embeddings.embeddings.create({
  model: "qwen3-embedding-8b-q5km",
  input: "Text to embed",
});
console.log(`Dim: ${emb.data[0].embedding.length}`); // 4096
```

---

## Referință Rapidă Endpoint-uri

### Modele de Generare (reasoning + fast)

| Endpoint                       | Metodă | Descriere                                    |
|--------------------------------|--------|----------------------------------------------|
| `/chat/completions`            | POST   | OpenAI Chat API (multi-turn, streaming SSE)  |
| `/completions`                 | POST   | OpenAI Completions API (text completion)     |
| `/messages`                    | POST   | Anthropic Messages API (format Claude)       |
| `/responses`                   | POST   | OpenAI Responses API (cu tracking ID)        |
| `/responses/{id}`              | GET    | Retrieve response după ID                    |
| `/responses/{id}/cancel`       | POST   | Anulare response în curs                     |
| `/chat/completions/render`     | POST   | Render template (debug/token counting)       |
| `/completions/render`          | POST   | Render prompt (debug)                        |
| `/models`                      | GET    | Lista modelelor disponibile                  |
| `/tokenize`                    | POST   | Text → token IDs + count                     |
| `/detokenize`                  | POST   | Token IDs → text                             |
| `/health`                      | GET    | Health check (200 = activ)                   |
| `/ping`                        | GET    | Ping rapid                                   |
| `/version`                     | GET    | Versiune engine vLLM                         |
| `/load`                        | GET    | Server load (0 = idle)                       |
| `/openapi.json`                | GET    | Specificație OpenAPI completă                 |

### Model Embeddings

| Endpoint                       | Metodă | Descriere                                    |
|--------------------------------|--------|----------------------------------------------|
| `/embeddings`                  | POST   | OpenAI Embeddings API (dim 4096)             |
| `/models`                      | GET    | Lista modelelor (format OpenAI)              |
| `/api/embed`                   | POST   | Ollama native embed (batch)                  |
| `/api/tags`                    | GET    | Ollama — modele instalate cu detalii         |
| `/api/version`                 | GET    | Versiune Ollama                              |
| `/api/ps`                      | GET    | Modele active în VRAM                        |

### Guardrails

| Endpoint                       | Metodă | Auth   | Descriere                               |
|--------------------------------|--------|--------|-----------------------------------------|
| `/analyze/prompt`              | POST   | Bearer | Scanare input (injection, PII, toxic)   |
| `/analyze/output`              | POST   | Bearer | Scanare output (sensitive, toxic, rel.) |
| `/scan/prompt`                 | POST   | Bearer | Alias /analyze/prompt                   |
| `/scan/output`                 | POST   | Bearer | Alias /analyze/output                   |
| `/healthz`                     | GET    | —      | Liveness check                          |
| `/readyz`                      | GET    | —      | Readiness check                         |

---

## Alegerea Modelului

| Criteriu                     | Model recomandat   | Motivare                                          |
|------------------------------|--------------------|---------------------------------------------------|
| Raționament complex, analiză | `reasoning`        | QwQ-32B cu chain-of-thought, context 24K tokens   |
| Clasificare, extracție       | `fast`             | 14B parametri, latență mică, context 12K tokens   |
| Embeddings, RAG, search      | `embeddings`       | Vector 4096-dim, optimizat pentru similaritate     |
| Validare input/output        | `guard`            | Pre/post-processing, fără generare                |

---

## Note Operaționale

- **api_key**: Modelele nu necesită autentificare. Setați `api_key="unused"` în SDK-uri.
- **guard auth**: LLM Guard necesită Bearer token. Contactați administratorul.
- **streaming**: Modelele reasoning și fast suportă SSE streaming (`"stream": true`).
- **rate limit**: 60 req/s cu burst 120 pentru modele, 30 req/s cu burst 60 pentru guard.
- **TLS**: Toate conexiunile sunt HTTPS cu certificate Cloudflare.
- **timeout recomandat**: 120s pentru reasoning, 60s pentru fast, 30s pentru embeddings, 10s pentru guard.
