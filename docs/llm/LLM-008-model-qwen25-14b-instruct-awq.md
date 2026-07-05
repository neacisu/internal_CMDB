---
id: LLM-008
title: Model Qwen2.5-14B-Instruct-AWQ — Documentație Completă
doc_class: reference
domain: llm-runtime
version: "1.0"
status: active
created: 2026-04-14
updated: 2026-07-05
owner: platform_architecture_lead
tags: [llm, vllm, fast, qwen2.5-14b, awq, tool-calling, hz.113]
---

# LLM-008 — Qwen2.5-14B-Instruct-AWQ (Model Fast)

> **OpenRouter migration (2026-07-05):** Alias `Qwen/Qwen2.5-14B-Instruct-AWQ` routes to **deepseek/deepseek-v4-flash** via LiteLLM on 10.0.1.115:8001. Tool calling validated post-cutover.

| Câmp          | Valoare                                    |
|---------------|--------------------------------------------|
| Versiune      | 1.0                                        |
| Data          | 2026-04-14                                 |
| Alias intern  | `fast`                                     |
| Status        | active                                     |
| Node          | hz.113 (10.0.1.13)                         |
| Base URL      | `https://infraq.app/llm/v1/fast`           |

---

## 1. Infrastructură

| Câmp             | Valoare                                        |
|------------------|------------------------------------------------|
| Node             | hz.113 — 49.13.97.113 / 10.0.1.13             |
| GPU              | NVIDIA RTX 6000 Ada Generation (partajat cu QwQ-32B) |
| VRAM total       | 49,140 MiB (48 GB GDDR6 ECC)                  |
| VRAM alocat      | `gpu_memory_utilization: 0.28` → ~13.7 GB     |
| Container        | `vllm-qwen-14b`                                |
| Image            | `vllm/vllm-openai:latest` (vLLM **0.16.0**)   |
| Port intern      | `10.0.1.13:8002 → container:8000`              |
| HAProxy VIP      | `10.0.1.10:49002 → 10.0.1.13:8002`            |
| Traefik prefix   | `/llm/v1/fast` → `http://10.0.1.10:49002`     |
| Status           | running — restartat 2026-04-14                 |
| Compose file     | `/ai-infrastructure/docker-compose.yml` pe hz.113 |
| Uptime monitorizare | Traefik health check `/health` la 30s       |

---

## 2. Model

| Câmp             | Valoare                                        |
|------------------|------------------------------------------------|
| model_id         | `Qwen/Qwen2.5-14B-Instruct-AWQ`               |
| Arhitectură      | Qwen2.5                                        |
| Parametri        | 14B                                            |
| Quantizare       | AWQ 4-bit                                      |
| max_model_len    | **12,288 tokens**                              |
| HF snapshot      | `539535859b135b0244c91f3e59816150c8056698`     |
| Context window   | 12,288 tokens input + output combinat          |
| Tool calling     | ✅ activat din 2026-04-14 (`hermes` parser)    |

---

## 3. Flags de Start

```
--model Qwen/Qwen2.5-14B-Instruct-AWQ
--quantization awq
--tensor-parallel-size 1
--gpu-memory-utilization 0.28
--max-model-len 12288
--enable-auto-tool-choice
--tool-call-parser hermes
--port 8000
```

### Note despre flags

| Flag | Motivație | Impact |
|------|-----------|--------|
| `--gpu-memory-utilization 0.28` | Coexistare cu QwQ-32B (0.65) pe același GPU | ~13.7 GB din 49.1 GB |
| Fără `--enforce-eager` | Suficient VRAM pentru CUDA graphs la 0.28 | TTFT optim ~150-300ms |
| `--tool-call-parser hermes` | Format nativ Qwen — `<tool_call>{...}</tool_call>` | Parser traduce în `tool_calls[]` OpenAI |

> **Diferență față de QwQ-32B**: Qwen2.5-14B-Instruct **nu** activează `--enforce-eager` — CUDA graphs funcționează normal la această alocare VRAM.

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
| GET    | `/metrics`                    | Prometheus metrics                            |
| GET    | `/openapi.json`               | Specificație OpenAPI completă (20 paths)      |

---

## 5. Parametri de Sampling

| Parametru            | Tip      | Default | Note                                     |
|----------------------|----------|---------|------------------------------------------|
| `temperature`        | float    | 1.0     | 0.0 = determinist; 0.0-0.3 pentru clasificare |
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
| `tool_choice`        | str/obj  | "none"  | Control apelare tools                    |
| `parallel_tool_calls`| bool     | true    | Apeluri simultane de tools               |
| `guided_json`        | object   | null    | **Atenție**: produce proză, nu JSON pur (vLLM 0.16.0) |
| `guided_regex`       | string   | null    | Constrained generation cu regex          |

---

## 6. Exemple Apeluri API

### Chat Completion — Sync (clasificare)

```http
POST https://infraq.app/llm/v1/fast/v1/chat/completions
Content-Type: application/json

{
  "model": "Qwen/Qwen2.5-14B-Instruct-AWQ",
  "messages": [
    {"role": "system", "content": "Clasifică sentimentul textului. Răspunde cu un singur cuvânt: pozitiv, negativ sau neutru."},
    {"role": "user", "content": "Produsul a depășit așteptările mele!"}
  ],
  "max_tokens": 5,
  "temperature": 0.0
}
```

**Răspuns:**
```json
{"choices": [{"message": {"content": "pozitiv"}, "finish_reason": "stop"}]}
```

### Chat Completion — Extracție JSON

```http
POST https://infraq.app/llm/v1/fast/v1/chat/completions
Content-Type: application/json

{
  "model": "Qwen/Qwen2.5-14B-Instruct-AWQ",
  "messages": [
    {
      "role": "system",
      "content": "Extrage datele și returnează STRICT JSON valid, fără text suplimentar:\n{\"name\": string, \"email\": string, \"phone\": string}"
    },
    {
      "role": "user",
      "content": "Mă numesc Ion Popescu, email ion.popescu@example.com, tel 0722000111"
    }
  ],
  "max_tokens": 100,
  "temperature": 0.0
}
```

### Chat Completion — Streaming SSE

```http
POST https://infraq.app/llm/v1/fast/v1/chat/completions
Content-Type: application/json

{
  "model": "Qwen/Qwen2.5-14B-Instruct-AWQ",
  "messages": [{"role": "user", "content": "Rezumă în 3 puncte principalele beneficii ale energiei solare."}],
  "max_tokens": 512,
  "stream": true
}
```

**Răspuns SSE:**
```
data: {"id":"chatcmpl-...","choices":[{"delta":{"role":"assistant","content":""},"index":0}]}
data: {"choices":[{"delta":{"content":"1. "},"index":0}]}
data: {"choices":[{"delta":{"content":"Energie regenerabilă..."},"index":0}]}
...
data: {"choices":[{"delta":{},"finish_reason":"stop","index":0}]}
data: [DONE]
```

### Tool Calling — Apel Simplu

```http
POST https://infraq.app/llm/v1/fast/v1/chat/completions
Content-Type: application/json

{
  "model": "Qwen/Qwen2.5-14B-Instruct-AWQ",
  "messages": [{"role": "user", "content": "Ce temperatură e la Cluj?"}],
  "tools": [{
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "Returnează temperatura curentă pentru un oraș",
      "parameters": {
        "type": "object",
        "properties": {
          "city": {"type": "string", "description": "Numele orașului"}
        },
        "required": ["city"]
      }
    }
  }],
  "tool_choice": "auto",
  "max_tokens": 200
}
```

**Răspuns (confirmat live):**
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "chatcmpl-tool-ba52590b6aa47b23",
        "type": "function",
        "function": {
          "name": "get_weather",
          "arguments": "{\"city\": \"Cluj\"}"
        }
      }]
    },
    "finish_reason": "tool_calls"
  }]
}
```

> **Diferență față de QwQ-32B**: `content` este `null` (fără raționament vizibil) — răspuns direct, fără `<think>` expus.

### Text Completion (non-chat)

```http
POST https://infraq.app/llm/v1/fast/v1/completions
Content-Type: application/json

{
  "model": "Qwen/Qwen2.5-14B-Instruct-AWQ",
  "prompt": "Capitala României este",
  "max_tokens": 50,
  "temperature": 0.1
}
```

### Tokenizare

```http
POST https://infraq.app/llm/v1/fast/tokenize
Content-Type: application/json

{"model": "Qwen/Qwen2.5-14B-Instruct-AWQ", "prompt": "Hello world"}
```

**Răspuns:**
```json
{"count": 2, "max_model_len": 12288, "tokens": [9707, 1879]}
```

---

## 7. Integrare Python — OpenAI SDK

```python
from openai import OpenAI
import json

client = OpenAI(
    base_url="https://infraq.app/llm/v1/fast",
    api_key="unused",
)

# Clasificare sentiment
response = client.chat.completions.create(
    model="Qwen/Qwen2.5-14B-Instruct-AWQ",
    messages=[
        {"role": "system", "content": "Clasifică: pozitiv / negativ / neutru. Răspunde cu un singur cuvânt."},
        {"role": "user", "content": "Serviciul a fost fantastic!"}
    ],
    max_tokens=5,
    temperature=0.0,
)
sentiment = response.choices[0].message.content.strip()

# Rezumare
response = client.chat.completions.create(
    model="Qwen/Qwen2.5-14B-Instruct-AWQ",
    messages=[
        {"role": "system", "content": "Rezumă textul în maxim 3 propoziții."},
        {"role": "user", "content": "[text lung]"}
    ],
    max_tokens=300,
    temperature=0.3,
)

# Streaming
with client.chat.completions.stream(
    model="Qwen/Qwen2.5-14B-Instruct-AWQ",
    messages=[{"role": "user", "content": "Scrie un email de follow-up."}],
    max_tokens=512,
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

# Tool calling
tools = [{
    "type": "function",
    "function": {
        "name": "lookup_product",
        "description": "Caută un produs după cod",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string"}
            },
            "required": ["code"]
        }
    }
}]

response = client.chat.completions.create(
    model="Qwen/Qwen2.5-14B-Instruct-AWQ",
    messages=[{"role": "user", "content": "Găsește produsul P-2045."}],
    tools=tools,
    tool_choice="auto",
    max_tokens=200,
)

msg = response.choices[0].message
if msg.tool_calls:
    args = json.loads(msg.tool_calls[0].function.arguments)
    print(f"Tool request: {args}")  # {'code': 'P-2045'}
```

---

## 8. Integrare Python — Anthropic SDK

```python
import anthropic

client = anthropic.Anthropic(
    base_url="https://infraq.app/llm/v1/fast",
    api_key="unused",
)

response = client.messages.create(
    model="Qwen/Qwen2.5-14B-Instruct-AWQ",
    max_tokens=512,
    messages=[
        {"role": "user", "content": "Traduce în engleză: 'Bun venit la noi!'"}
    ],
)
print(response.content[0].text)
```

---

## 9. Cazuri de Utilizare Recomandate

| Caz de utilizare | Motivație |
|------------------|-----------|
| Clasificare text (sentiment, categorie, intenție) | Latență mică, temperature 0.0 |
| Extracție entități și câmpuri | Instruct-tuned, urmează format JSON din system prompt |
| Rezumare documente | Eficient cost/latență vs reasoning |
| Q&A simplu și rapid | TTFT ~150-300ms, fără overhead CoT |
| Traduceri | Qwen2.5 performant pe limbi multiple inclusiv română |
| Completare formulare / structurare date | Instruct-following precis |
| Chatbot / asistent conversațional | Răspuns direct, fără raționament expus |
| Tool orchestration rapidă | Tool calling fără overhead CoT |

**Folosește `reasoning` (QwQ-32B) pentru**: probleme complexe, raționament multi-pas, contexte > 12K tokens.

---

## 10. Performanță și Latențe

| Metrică | Valoare | Condiție |
|---------|---------|----------|
| TTFT (time-to-first-token) | 150-300ms | fără `--enforce-eager`, CUDA graphs active |
| Latență `/health` via Traefik | ~87ms | măsurat 2026-04-14 |
| Token rate (generare) | ~60-120 tok/s | depinde de context length |
| Tool-Use-20 correctness | 89% (PASS) | benchmark 2026-04-14 |

---

## 11. Limitări Cunoscute

| Limitare | Detaliu | Workaround |
|----------|---------|-----------|
| max_model_len 12,288 | Jumătate față de QwQ-32B | Folosește `reasoning` pentru texte lungi |
| `guided_json` broken | Produce proză în vLLM 0.16.0 | Instruieste modelul în system prompt |
| Fără CoT expus | `content` este direct fără `<think>` | Normal și dorit pentru fast inference |
| GPU partajat cu QwQ-32B | Concurență pentru VRAM și CUDA cores | Evită request-uri simultane mari |

---

## 12. Monitorizare

```bash
# Health
curl https://infraq.app/llm/v1/fast/health
# → {}  (HTTP 200)

# Metrics Prometheus
curl http://10.0.1.13:8002/metrics | grep -E "vllm_gpu|vllm_request|vllm_cache"

# Key metrics
# vllm:gpu_cache_usage_perc  → KV cache utilization
# vllm:num_requests_running  → requesturi active
# vllm:request_success_total → throughput total
```

---

## Changelog

| Versiune | Data | Modificări |
|---------|------|------------|
| 1.0 | 2026-04-14 | Document inițial creat — date verificate live pe hz.113 |
