# Product Requirements Document (PRD)

## 1. Project Overview & Vision
**Product Name:** Maxsorlabs AI Support Ticket Decision Assistant  
**Role / Assignment:** Applied Gen AI Engineer Shortlist Assignment  
**Objective:** Provide an end-to-end AI-powered support decision system that automates ticket triage, grounds decisions in official policy documents via Retrieval-Augmented Generation (RAG), and delivers structured, auditable recommendations to support staff with zero hallucination.

---

## 2. Target Personas
1. **Customer Support Specialist (Tier 1 & 2):**
   - Needs instant, accurate, policy-backed guidance on ticket actions (e.g. approve refund, request photo verification, reject expired return).
   - Needs transparent confidence metrics and traceable source policy citations.
2. **Support Operations Lead / Auditor:**
   - Needs consistent enforcement of business rules across return windows, damage reporting thresholds, and carrier transit timelines.
   - Needs access to ticket history and historical decision audit trails.
3. **Engineering Evaluator / Recruiter:**
   - Evaluates system architecture, JWT security, strict tenant authorization isolation (e.g., Alice cannot view Bob's tickets), database schema fidelity, and structured LLM outputs.

---

## 3. Core Functional Requirements

### 3.1 Authentication & Authorization
- **FR-AUTH-1 (User Registration):** New users can create an account with email and password (minimum 6 characters). Passwords must be hashed using bcrypt.
- **FR-AUTH-2 (User Login):** Users can authenticate with credentials to receive a signed JWT Bearer token with expiration.
- **FR-AUTH-3 (Current User Profile):** The `/me` endpoint returns identity details for the currently authenticated user.
- **FR-AUTH-4 (Tenant Authorization Isolation):** Users can only access tickets belonging to their own account. Requests attempting to inspect another user's ticket return HTTP 403 Forbidden.

### 3.2 Knowledge Base & RAG Pipeline
- **FR-RAG-1 (Document Ingestion):** Ingest markdown policy documents (`refunds.md`, `returns.md`, `shipping.md`, `damaged_goods.md`).
- **FR-RAG-2 (Chunking):** Decompose policy documents into semantically coherent sections while preserving metadata (source filename, section title).
- **FR-RAG-3 (Vector Indexing & Similarity Search):** Index chunks and compute cosine similarity against user ticket queries using normalized vector representations with support for Gemini embeddings and offline local vector search.
- **FR-RAG-4 (Top-K Context Retrieval):** Retrieve the top 3 most relevant policy excerpts to serve as grounding context for the LLM.

### 3.3 Structured AI Decision Engine
- **FR-AI-1 (Model Grounding):** Analyze support tickets against retrieved policy context using Google Gemini LLM (`gemini-3.5-flash-lite` / `gemini-3.5-flash`).
- **FR-AI-2 (Structured Pydantic Output):** Validate and enforce structured JSON output:
  - `action`: One of `REQUEST_PHOTOS`, `APPROVE_REFUND`, `APPROVE_RETURN`, `REJECT_REQUEST`, `EXPEDITE_SHIPPING`, `NEEDS_MORE_INFORMATION`.
  - `confidence`: Numeric float between `0.0` and `1.0`.
  - `reason`: Explanation grounded strictly in retrieved policy documents.
  - `sources`: Array of referenced markdown filenames (e.g. `["damaged_goods.md"]`).
- **FR-AI-3 (Strict Hallucination Prevention):** Return `NEEDS_MORE_INFORMATION` whenever essential information (e.g., order value, delivery date, item condition, or tracking number) is missing.
- **FR-AI-4 (Resilient Fallback):** Fall back gracefully to deterministic rule-grounded policy evaluation if the remote LLM experiences quota or network interruptions.

### 3.4 Data Persistence
- **FR-DB-1 (Relational Schema):** Store `users`, `tickets`, and `decisions` in SQLite with foreign key enforcement (`PRAGMA foreign_keys = ON;`).
- **FR-DB-2 (Auditability):** Every decision is persistently linked to its parent ticket with timestamps, confidence scores, and source citations.

### 3.5 Frontend User Experience (Streamlit)
- **FR-UI-1 (3-Tab Architecture):** Clean, reactive Streamlit interface with Login/Register, New Decision, and History tabs.
- **FR-UI-2 (HTTP Communication):** Frontend communicates strictly via HTTP REST API calls to FastAPI without direct SQLite database access.
- **FR-UI-3 (Visual Decision Card):** Present AI output with distinct color-coded badges, confidence progress bars, policy reasoning blocks, and source tags.

---

## 4. Non-Functional Requirements
- **NFR-SEC-1 (Zero Plaintext Secrets):** All passwords hashed with bcrypt salts. JWT signed with HMAC-SHA256. API keys and JWT secrets stored in `.env`.
- **NFR-PERF-1 (Latency):** Fast local vector retrieval (< 5ms) and rapid LLM decision turnaround (< 2s).
- **NFR-REL-1 (Test Coverage):** 100% test pass rate across 20 automated tests covering auth, tenant isolation, RAG, and decisions.
- **NFR-ACC-1 (Evaluation Accuracy):** Achieve ≥ 90% accuracy on the standardized 10-ticket evaluation benchmark.

---

## 5. Acceptance Criteria
1. Registering user Alice and Bob creates distinct accounts in SQLite.
2. Bob cannot access Alice's ticket via `GET /tickets/{alice_ticket_id}` (returns 403 Forbidden).
3. Submitting `"I received my ₹4,500 ceramic dinner set yesterday, but the bowls arrived completely shattered"` returns `REQUEST_PHOTOS` with source `damaged_goods.md`.
4. Submitting ambiguous queries returns `NEEDS_MORE_INFORMATION`.
5. Running `python evaluate.py` outputs total test cases, correct count, incorrect count, and accuracy percentage.
