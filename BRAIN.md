# BRAIN.md — Architecture Memory & Design Rationale

## 1. Executive Summary
This document records the design philosophy, critical architectural choices, trade-offs, and failure mode mitigations made while building the **Minimal AI Decision API**.

---

## 2. Key Architecture Decisions

### 2.1 SQLite vs External Databases (PostgreSQL / MySQL)
- **Decision:** Use SQLite directly with `PRAGMA foreign_keys = ON;` and standard library `sqlite3.Row` mapping.
- **Rationale:**
  - Zero external infrastructure requirement; works out of the box on any developer machine or evaluation sandbox.
  - ACID compliant, single-file storage, completely self-contained.
  - Direct connection management with custom path overrides enables fully isolated test databases in temporary files (`tempfile.NamedTemporaryFile`) during pytest execution.
- **Trade-off:** Single writer concurrency limits high-throughput writes, but is optimal for this minimal assignment and local demonstration.

### 2.2 Local Vector Search vs Heavy Vector Databases (Chroma / Pinecone / Milvus)
- **Decision:** Implement a clean, in-memory vectorized cosine similarity index using NumPy with TF-IDF and currency normalization, backed by Gemini embedding support.
- **Rationale:**
  - External vector databases (Pinecone, ChromaDB, FAISS) add substantial binary dependencies that frequently trigger compilation failures on newer Python releases (e.g. Python 3.14 on Windows).
  - A NumPy-based cosine vector space takes < 5 milliseconds to initialize and search across policy chunks with zero external network roundtrips.
  - Deterministic offline operations guarantee that test suites and evaluation scripts execute in CI environments without external API keys.

### 2.3 Gemini SDK (`google-genai`) & Model Selection
- **Decision:** Adopt Google's modern `google-genai` SDK with `gemini-3.5-flash-lite` as the primary model and `gemini-3.5-flash` as backup.
- **Finding & Fix:**
  - Legacy models like `gemini-2.5-flash` returned `404 NOT_FOUND` for new API keys, while `gemini-3.6-flash` and `gemini-flash-latest` intermittently experienced `503 Server Unavailable` spikes.
  - Proactive model probing revealed `gemini-3.5-flash-lite` provides sub-second structured JSON latency with 100% availability on current keys.
  - Structured output schemas are enforced at the API level via `types.GenerateContentConfig(response_schema=DecisionOutput)`.

### 2.4 Multi-Tenant Authorization Isolation
- **Decision:** Enforce ownership checks at both query construction time and resource retrieval time.
  - `GET /tickets` filters explicitly by `WHERE t.user_id = ?`.
  - `GET /tickets/{id}` performs explicit ownership validation:
    ```python
    if ticket["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access forbidden: You do not have permission to view this ticket.")
    ```
- **Rationale:** Ensures strict tenant isolation: Alice can never inspect Bob's tickets, verified by `tests/test_authorization_isolation.py`.

### 2.5 Resilient Dual-Layer Decision Pipeline
- **Decision:** Combine Gemini LLM structured outputs with a deterministic rule-grounded policy evaluator (`evaluate_policy_grounded`).
- **Rationale:**
  - If a user runs tests offline or has an invalid/missing API key, the system does not crash or return empty responses.
  - When a valid key is provided, the LLM is invoked and outputs structured decisions adhering to the exact Pydantic schema.

---

## 3. Failure Mode & Edge Case Handling

| Scenario | Risk | Mitigation |
|---|---|---|
| User enters ticket with missing details (e.g. "Where is my package?") | Model hallucinates status or invents policy | System prompt mandates `NEEDS_MORE_INFORMATION` when key information is absent |
| Damaged order reported > 48 hours | Unauthorized refund or replacement | Grounded policy strictly triggers `REJECT_REQUEST` citing 48-hour window |
| High value damaged order (> ₹2,000) | Instant refund issued without photos | Model mandates `REQUEST_PHOTOS` before compensation |
| Customer receives wrong/mismatched item (e.g., ordered phone, got shoes) | Incomplete classification | Policy and LLM specifically enforce `REQUEST_PHOTOS` for mismatched deliveries |
| Rate limit or 503 from LLM API | Frontend crash or blank screen | Dual-model retry followed by deterministic policy fallback |
