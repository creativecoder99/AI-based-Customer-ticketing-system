# DEVELOPMENT.md — AI Coding Agent Usage & Workflow

## 1. Overview
This project was developed pair-programming with the **Antigravity** autonomous AI coding assistant. This document records the methodology, verification loops, prompt strategies, and architectural decisions made throughout the project lifecycle.

---

## 2. Iterative Development Workflow

### Phase 1: Environment Diagnostics & Compatibility
- **Observation:** The host system runs Windows with Python 3.14.4. Binary wheels for C-extensions (like older versions of certain packages) can face build failures.
- **Agent Action:** Diagnosed package compatibility upfront by spinning up a clean virtual environment (`.venv`) and testing wheels for `fastapi`, `pydantic`, `pyjwt`, `bcrypt`, `numpy`, `streamlit`, and `google-genai`.
- **Validation:** All dependencies installed without requiring manual compilation.

### Phase 2: Knowledge Base & Ground Truth Policy Synthesis
- **Agent Action:** Authored four realistic policy documents in `knowledge_base/` (`refunds.md`, `returns.md`, `shipping.md`, `damaged_goods.md`), embedding specific quantitative boundaries (e.g. ₹2,000 threshold for photos, 48-hour damage reporting window, 30-day return window, 7 business days lost in transit).
- **Validation:** Constructed `data/tickets.csv` with 10 representative test cases mapping to distinct policy actions.

### Phase 3: Core Backend Architecture & RAG Pipeline
- **Agent Action:**
  - Implemented SQLite database layer (`src/database.py`) with foreign key constraints.
  - Implemented JWT authentication and password hashing with bcrypt (`src/auth.py`).
  - Implemented RAG pipeline (`src/retrieval.py`) with currency token normalization (`₹` -> `inr`), stem reduction, and cosine similarity vector retrieval.
  - Implemented Gemini structured output decision engine (`src/decision.py`) using Pydantic validation schemas.
  - Implemented FastAPI REST endpoints (`src/api.py`) adhering to all contract requirements.

### Phase 4: Model Discovery & Resiliency Optimization
- **Agent Action:**
  - When testing user queries with live Gemini keys, discovered that `gemini-2.5-flash` returned a 404 deprecation error and `gemini-3.6-flash` returned 503 high demand errors.
  - Wrote a probing utility to test all available Gemini models against the user's API key.
  - Discovered that `gemini-3.5-flash-lite` has sub-second structured JSON response times and 100% uptime. Configured multi-model fallback (`gemini-3.5-flash-lite` -> `gemini-3.5-flash` -> policy rules).
  - Extended policy context to handle "mismatched / wrong item delivered" scenarios (e.g. ordered phone, got shoes).

### Phase 5: Verification & Automated Testing
- **Agent Action:** Built 20 unit and integration tests across 5 test modules (`test_auth.py`, `test_authorization_isolation.py`, `test_rag.py`, `test_decision.py`, `test_api.py`).
- **Validation:** 100% test pass rate in under 2 seconds.

---

## 3. Human-Agent Collaboration Principles Applied
1. **Verification Over Assumption:**
   - Rather than assuming external APIs or models are available, the agent programmatically verified model availability and logged exact HTTP status codes.
2. **Tenant Isolation Verification:**
   - Wrote dedicated tests specifically verifying that Alice's token cannot read Bob's tickets (403 Forbidden).
3. **Graceful Degradation:**
   - Ensured the application functions in offline CI environments without requiring external API keys, while automatically utilizing live LLM features when keys are present.
