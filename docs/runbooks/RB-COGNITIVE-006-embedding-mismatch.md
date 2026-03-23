---
id: RB-COGNITIVE-006
title: Embedding Dimension Mismatch Runbook Procedure
doc_class: runbook
domain: infrastructure
version: "1.0"
status: draft
created: 2026-03-22
updated: 2026-03-23
owner: sre_observability_owner
binding:
  - entity_type: registry.service
    entity_id: embedding-pipeline
    relation: describes
---

# RB-COGNITIVE-006 — Embedding Dimension Mismatch

## Problem

Vector search or similarity queries fail because embeddings stored in
pgvector have a different dimensionality than what the current embedding
model produces.

## Symptoms

- API errors: `"ValueError: expected 4096 dimensions, got 1024"`
- Cognitive `/query` returns 500 with pgvector dimension error
- Migration `0006_embedding_dim_4096` was applied but old embeddings
  still have the previous dimension
- RAG retrieval returns zero results despite matching documents existing
- Embedding generation succeeds but insert/query fails

## Impact

- **High** — All vector-based retrieval (RAG, similarity search, semantic
  dedup) stops working until embeddings are re-generated.
- Cognitive query accuracy drops to zero for affected documents.

## Steps to Resolve

1. **Confirm the mismatch:**
   ```sql
   -- Check stored embedding dimensions
   SELECT
     vector_dims(embedding) as dims,
     count(*) as cnt
   FROM retrieval.document_chunk
   WHERE embedding IS NOT NULL
   GROUP BY vector_dims(embedding);
   ```

2. **Check current model output dimension:**
   ```bash
   curl -s https://infraq.app/api/v1/cognitive/debug/embed-test \
     -d '{"text": "test"}' | jq '.dimensions'
   ```

3. **If model changed (e.g., 1024 → 4096):**
   - Option A: Re-embed all documents (preferred)
     ```bash
     curl -X POST https://infraq.app/api/v1/workers/enqueue \
       -d '{"task": "reindex_embeddings", "scope": "all"}'
     ```
   - Option B: Rollback to the previous model

4. **If migration was applied but re-embedding not completed:**
   ```sql
   -- Null out mismatched embeddings so they're re-generated
   UPDATE retrieval.document_chunk
   SET embedding = NULL
   WHERE vector_dims(embedding) != 4096;
   ```

5. **Trigger re-embedding:**
   ```bash
   # Queue all null-embedding chunks for processing
   curl -X POST https://infraq.app/api/v1/retrieval/reindex
   ```

6. **Monitor progress:**
   ```sql
   SELECT
     count(*) FILTER (WHERE embedding IS NOT NULL) as embedded,
     count(*) FILTER (WHERE embedding IS NULL) as pending,
     count(*) as total
   FROM retrieval.document_chunk;
   ```

## Prevention

- Always re-embed documents as part of model migration
- Include embedding dimension check in `make migrate-check`
- Pin the embedding model version in LLM-005 model registry
- Add a pre-deployment test that verifies embedding dimensions match
  the pgvector column definition
- Keep a dimension constant in `src/internalcmdb/retrieval/chunker.py`
  and validate on startup
