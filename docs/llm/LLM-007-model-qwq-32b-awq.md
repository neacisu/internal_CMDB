---
id: LLM-007
title: Model QwQ-32B-AWQ — Documentație Completă
doc_class: reference
domain: llm-runtime
version: "1.0"
status: active
created: 2026-04-14
updated: 2026-07-05
owner: platform_architecture_lead
tags: [llm, vllm, reasoning, qwq-32b, awq, tool-calling, qwen2.5, hz.113]
---

# LLM-007 — QwQ-32B-AWQ (Model Reasoning)

> **OpenRouter migration (2026-07-05):** Alias `Qwen/QwQ-32B-AWQ` routes to **deepseek/deepseek-v4-pro** via LiteLLM on 10.0.1.115:8001. hz.113 vLLM decommissioned. Public URL unchanged.

| Câmp          | Valoare                                   |
|---------------|-------------------------------------------|
| Versiune      | 1.0                                       |
| Data          | 2026-04-14                                |
| Alias intern  | `reasoning`                               |
| Status        | active                                    |
| Node          | hz.113 (10.0.1.13)                        |
| Base URL      | `https://infraq.app/llm/v1/reasoning`     |

---

## 1. Infrastructură

| Câmp             | Valoare                                        |
|------------------|------------------------------------------------|
| Node             | hz.113 — 49.13.97.113 / 10.0.1.13             |
| GPU              | NVIDIA RTX 6000 Ada Generation                 |
| VRAM total       | 49,140 MiB (48 GB GDDR6 ECC)                  |
| VRAM alocat      | `gpu_memory_utilization: 0.65` → ~31.9 GB     |
| VRAM liber total | ~754 MiB (ambele modele pe același GPU)        |
| Temperatură GPU  | 33°C (idle)                                    |
| Container        | `vllm-qwq-32b`                                 |
| Image            | `vllm/vllm-openai:latest` (vLLM **0.16.0**)   |
| Port intern      | `10.0.1.13:8001 → container:8000`              |
| HAProxy VIP      | `10.0.1.10:49001 → 10.0.1.13:8001`            |
| Traefik prefix   | `/llm/v1/reasoning` → `http://10.0.1.10:49001` |
| Status           | running — restartat 2026-04-14                 |
| Compose file     | `/ai-infrastructure/docker-compose.yml` pe hz.113 |
| Uptime monitorizare | Traefik health check `/health` la 30s       |

---

## 2. Model

| Câmp             | Valoare                                        |
|------------------|------------------------------------------------|
| model_id         | `Qwen/QwQ-32B-AWQ`                             |
| Arhitectură      | Qwen2.5 (QwQ reasoning variant)                |
| Parametri        | 32B                                            |
| Quantizare       | AWQ 4-bit                                      |
| max_model_len    | **24,576 tokens**                              |
| HF snapshot      | `dc9f21221581580ccfa51b74077db6056b56cb69`     |
| Context window   | 24,576 tokens input + output combinat          |
| Tool calling     | ✅ activat din 2026-04-14 (`hermes` parser)    |

---

## 3. Flags de Start

```
--model Qwen/QwQ-32B-AWQ
--quantization awq
--tensor-parallel-size 1
--gpu-memory-utilization 0.65
--max-model-len 24576
--enforce-eager
--enable-auto-tool-choice
--tool-call-parser hermes
--port 8000
```

### Note critice despre flags

| Flag | Motivație | Impact |
|------|-----------|--------|
| `--enforce-eager` | VRAM liber doar ~754 MiB — insuficient pentru CUDA graph capture (~3-4 GB necesari) | TTFT 600-800ms (vs 150-300ms fără) |
| `--tool-call-parser hermes` | Modelele Qwen generează format Hermes/NousResearch `<tool_call>{...}</tool_call>` | Parser traduce în `tool_calls[]` OpenAI |
| `--gpu-memory-utilization 0.65` | Coexistare cu Qwen2.5-14B pe același GPU (0.28) | ~31.9 GB rezervați din 49.1 GB |

> **Atenție**: Nu elimina `--enforce-eager` fără să reduci `--gpu-memory-utilization` la 0.55 mai întâi. Risc OOM la startup.

---

## 4. Endpoint-uri Disponibile

| Metodă | Path                          | Descriere                                     |
|--------|-------------------------------|-----------------------------------------------|
| GET    | `/health`                     | Liveness check — `{}` HTTP 200                |
| GET    | `/v1/models`                  | Lista modelelor disponibile                   |
| GET    | `/version`                    | `{"version": "0.16.0"}`                       |
| GET    | `/ping`                       | Ping rapid, body gol                          |
| GET    | `/load`                       | `{"server_load": 0}` — load curent            |
| POST   | `/v1/chat/completions`        | Chat OpenAI-compatible (sync + SSE stream)    |
| POST   | `/v1/completions`             | Text completion (prompt brut, non-chat)       |
| POST   | `/messages`                   | Anthropic Messages API compatible             |
| POST   | `/responses`                  | OpenAI Responses API                          |
| GET    | `/responses/{id}`             | Retrieve response după ID                     |
| POST   | `/responses/{id}/cancel`      | Anulează response activ                       |
| POST   | `/v1/chat/completions/render` | Render template fără generare                 |
| POST   | `/v1/completions/render`      | Render prompt fără generare                   |
| POST   | `/tokenize`                   | Text → token IDs + count + max_model_len      |
| POST   | `/detokenize`                 | Token IDs → text                              |
| GET    | `/metrics`                    | Prometheus metrics (latency, throughput etc.) |
| GET    | `/openapi.json`               | Specificație OpenAPI completă (20 paths)      |

---

## 5. Parametri de Sampling

| Parametru            | Tip      | Default | Note                                     |
|----------------------|----------|---------|------------------------------------------|
| `temperature`        | float    | 1.0     | 0.0 = determinist, 0.6 recomandat CoT   |
| `top_p`              | float    | 1.0     | Nucleus sampling                         |
| `top_k`              | int      | -1      | -1 = dezactivat                          |
| `max_tokens`         | int      | —       | **Recomandat obligatoriu**               |
| `min_tokens`         | int      | 0       | Forțează răspuns minim                   |
| `stream`             | bool     | false   | SSE streaming                            |
| `stop`               | str/list | null    | Stop sequences                           |
| `presence_penalty`   | float    | 0.0     | Penalizare repetare topici               |
| `frequency_penalty`  | float    | 0.0     | Penalizare repetare token-uri            |
| `repetition_penalty` | float    | 1.0     | >1.0 reduce repetiții                    |
| `logprobs`           | bool     | false   | Returnează log-probabilități             |
| `top_logprobs`       | int      | null    | Top N logprobs per token                 |
| `seed`               | int      | null    | Reproducibilitate deterministă           |
| `tools`              | array    | null    | Definire funcții pentru tool calling     |
| `tool_choice`        | str/obj  | "none"  | Control apelare tools (auto/required/none/specific) |
| `parallel_tool_calls`| bool     | true    | Apeluri simultane de tools               |
| `guided_json`        | object   | null    | **Atenție**: produce proză, nu JSON pur (limitare CoT) |
| `guided_regex`       | string   | null    | Constrained generation cu regex          |

---

## 6. Exemple Apeluri API

### Chat Completion — Sync

```http
POST https://infraq.app/llm/v1/reasoning/v1/chat/completions
Content-Type: application/json

{
  "model": "Qwen/QwQ-32B-AWQ",
  "messages": [
    {"role": "system", "content": "Ești un expert în analiza contractelor juridice."},
    {"role": "user", "content": "Analizează riscurile din contractul următor: [text contract]"}
  ],
  "max_tokens": 2048,
  "temperature": 0.6,
  "top_p": 0.95
}
```

### Chat Completion — Streaming SSE

```http
POST https://infraq.app/llm/v1/reasoning/v1/chat/completions
Content-Type: application/json

{
  "model": "Qwen/QwQ-32B-AWQ",
  "messages": [{"role": "user", "content": "Explică în detaliu cum funcționează quantum computing."}],
  "max_tokens": 2048,
  "temperature": 0.7,
  "stream": true
}
```

**Răspuns SSE:**
```
data: {"id":"chatcmpl-...","choices":[{"delta":{"role":"assistant","content":""},"index":0}]}
data: {"choices":[{"delta":{"content":"Quantum computing "},"index":0}]}
...
data: {"choices":[{"delta":{},"finish_reason":"stop","index":0}]}
data: [DONE]
```

### Tool Calling — Apel Simplu

```http
POST https://infraq.app/llm/v1/reasoning/v1/chat/completions
Content-Type: application/json

{
  "model": "Qwen/QwQ-32B-AWQ",
  "messages": [{"role": "user", "content": "Ce stoc are produsul SKU-99?"}],
  "tools": [{
    "type": "function",
    "function": {
      "name": "get_stock",
      "description": "Returnează stocul curent pentru un SKU",
      "parameters": {
        "type": "object",
        "properties": {
          "sku": {"type": "string", "description": "Codul produsului"}
        },
        "required": ["sku"]
      }
    }
  }],
  "tool_choice": "auto",
  "max_tokens": 512
}
```

**Răspuns (confirmat live):**
```json
{
  "id": "chatcmpl-...",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Okay, the user is asking about stock... <think>I need to call get_stock with SKU-99.</think>",
      "tool_calls": [{
        "id": "chatcmpl-tool-b01ceaafcb8eea5d",
        "type": "function",
        "function": {
          "name": "get_stock",
          "arguments": "{\"sku\": \"SKU-99\"}"
        }
      }]
    },
    "finish_reason": "tool_calls"
  }]
}
```

> **Nota**: QwQ-32B este model reasoning — `content` conține raționamentul intern `<think>...</think>` chiar și în tool calls. Acesta este comportamentul normal al modelului. Filtrează sau ignoră `content` dacă nu ai nevoie de chain-of-thought.

### Tool Calling — Multi-Turn (cu rezultat tool)

```json
{
  "model": "Qwen/QwQ-32B-AWQ",
  "messages": [
    {"role": "user", "content": "Ce stoc are SKU-99?"},
    {
      "role": "assistant",
      "content": "<think>Need to check stock.</think>",
      "tool_calls": [{
        "id": "call_abc",
        "type": "function",
        "function": {"name": "get_stock", "arguments": "{\"sku\": \"SKU-99\"}"}
      }]
    },
    {
      "role": "tool",
      "tool_call_id": "call_abc",
      "content": "142 bucăți"
    }
  ],
  "max_tokens": 256
}
```

### Valori `tool_choice`

| Valoare | Comportament |
|---------|--------------|
| `"auto"` | Modelul decide dacă apelează un tool |
| `"required"` | Forțat să apeleze cel puțin un tool |
| `"none"` | Nu apelează tools, răspunde text direct |
| `{"type":"function","function":{"name":"get_stock"}}` | Forțează apelul funcției specificate |

### Tokenizare

```http
POST https://infraq.app/llm/v1/reasoning/tokenize
Content-Type: application/json

{"model": "Qwen/QwQ-32B-AWQ", "prompt": "Hello world"}
```

**Răspuns:**
```json
{"count": 2, "max_model_len": 24576, "tokens": [9707, 1879]}
```

### Verificare versiune și health

```bash
# Health
curl https://infraq.app/llm/v1/reasoning/health
# → {}  (HTTP 200)

# Version
curl https://infraq.app/llm/v1/reasoning/version
# → {"version": "0.16.0"}

# Prometheus metrics
curl https://infraq.app/llm/v1/reasoning/metrics | grep vllm
```

---

## 7. Integrare Python — OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://infraq.app/llm/v1/reasoning",
    api_key="unused",  # fără autentificare pe rețeaua internă
)

# Chat completion simplă
response = client.chat.completions.create(
    model="Qwen/QwQ-32B-AWQ",
    messages=[
        {"role": "system", "content": "Ești un expert în analiză financiară."},
        {"role": "user", "content": "Calculează IRR pentru fluxul: [-1000, 300, 400, 500]"}
    ],
    max_tokens=1024,
    temperature=0.6,
)
print(response.choices[0].message.content)

# Streaming
with client.chat.completions.stream(
    model="Qwen/QwQ-32B-AWQ",
    messages=[{"role": "user", "content": "Explică teorema Bayes."}],
    max_tokens=2048,
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

# Tool calling
import json

tools = [{
    "type": "function",
    "function": {
        "name": "get_exchange_rate",
        "description": "Returnează cursul de schimb EUR/RON curent",
        "parameters": {
            "type": "object",
            "properties": {
                "from_currency": {"type": "string"},
                "to_currency": {"type": "string"}
            },
            "required": ["from_currency", "to_currency"]
        }
    }
}]

response = client.chat.completions.create(
    model="Qwen/QwQ-32B-AWQ",
    messages=[{"role": "user", "content": "Câți lei face 500 EUR?"}],
    tools=tools,
    tool_choice="auto",
    max_tokens=256,
)

msg = response.choices[0].message
if msg.tool_calls:
    call = msg.tool_calls[0]
    args = json.loads(call.function.arguments)
    print(f"Model cere: {call.function.name}({args})")
```

---

## 8. Integrare Python — Anthropic SDK

```python
import anthropic

client = anthropic.Anthropic(
    base_url="https://infraq.app/llm/v1/reasoning",
    api_key="unused",
)

response = client.messages.create(
    model="Qwen/QwQ-32B-AWQ",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Analizează tendința: [1.2, 1.5, 1.3, 1.8, 2.1]"}
    ],
)
print(response.content[0].text)
```

---

## 9. Cazuri de Utilizare Recomandate

| Caz de utilizare | Motivație |
|------------------|-----------|
| Analiză juridică / contracte | Chain-of-thought profund, 24K context |
| Raționament multi-pas | QwQ este specializat pe CoT |
| Planificare și decompunere task-uri | Raționament intern expus prin `<think>` |
| Tool calling complex (orchestrare agenți) | Suport multi-turn + parallel_tool_calls |
| Debugging cod complex | Raționament paso-cu-paso |
| Analiză financiară / matematică | Precizie ridicată prin CoT |
| Extracție structurată din documente lungi | Max 24K context (vs 12K la fast) |

**Evită pentru**: clasificare simplă, extracție trivială, Q&A scurt → folosește `fast` (Qwen2.5-14B) pentru latență mai mică.

---

## 10. Performanță și Latențe

| Metrică | Valoare | Condiție |
|---------|---------|----------|
| TTFT (time-to-first-token) | 600-800ms | `--enforce-eager` activ |
| TTFT fără enforce-eager | 150-300ms | necesită VRAM liber suplimentar |
| Latență `/health` via Traefik | ~79ms | măsurat 2026-04-14 |
| Throughput | variabil | singleton GPU, partajat cu fast_14b |
| Token rate (generare) | ~30-60 tok/s | depinde de context length |

---

## 11. Limitări Cunoscute și Riscuri

| Limitare | Detaliu | Workaround |
|----------|---------|-----------|
| TTFT crescut | `--enforce-eager` activ → 600-800ms vs 150ms optim | Reduce `gpu_memory_utilization` 0.65→0.55 + activare CUDA graphs (durată ~30 min warm-up) |
| VRAM critic | Doar ~754 MiB liber pe GPU | Nu adăuga modele suplimentare pe hz.113 fără audit VRAM |
| `guided_json` broken | Produce proză (text) în loc de JSON valid | Instruieste modelul în system prompt să genereze JSON + parsare post-hoc |
| Conținut `<think>` în tool calls | `content` conține raționamentul intern | Filtrează tag-ul `<think>...</think>` din `message.content` la nevoie |
| max_model_len 24,576 | Nu 32,768 cum e documentat în unele versiuni vechi | Verificat live cu `/tokenize` |

---

## 12. Monitorizare

```bash
# Metrics Prometheus
curl http://10.0.1.13:8001/metrics | grep -E "vllm_gpu|vllm_request|vllm_cache"

# Key metrics de urmărit
# vllm:gpu_cache_usage_perc  → utilizare KV cache
# vllm:num_requests_running  → requesturi active
# vllm:num_requests_waiting  → queue size
# vllm:request_success_total → requesturi completate

# Health rapid
curl http://10.0.1.13:8001/health  # intern
curl https://infraq.app/llm/v1/reasoning/health  # via Traefik
```

---

## Changelog

| Versiune | Data | Modificări |
|---------|------|------------|
| 1.0 | 2026-04-14 | Document inițial creat — date verificate live pe hz.113 |
