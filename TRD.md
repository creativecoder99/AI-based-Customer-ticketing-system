# Technical Requirements Document (TRD)

## 1. System Architecture

```
+-------------------------------------------------------------+
|                      Streamlit Frontend                     |
|                 (Port 8501, Session State)                  |
+------------------------------+------------------------------+
                               |
                               | HTTP / REST (Bearer JWT)
                               v
+-------------------------------------------------------------+
|                     FastAPI REST Backend                    |
|                         (Port 8000)                         |
|                                                             |
|  +---------------------+  +-------------------------------+ |
|  |   Auth & Security   |  |        Ticket Endpoints       | |
|  | (Bcrypt, PyJWT, /me)|  |   (Submit, List, Detail View) | |
|  +----------+----------+  +---------------+---------------+ |
+-------------|-----------------------------|-----------------+
              |                             |
              v                             v
+-----------------------------+  +----------------------------+
|       SQLite Database       |  |        RAG Engine          |
|  (users, tickets, decisions)|  | (Markdown Chunker, Cosine) |
+-----------------------------+  +--------------+-------------+
                                                |
                                                v
                                 +----------------------------+
                                 |    Decision Engine (LLM)   |
                                 | (Google GenAI Gemini 3.5 / |
                                 |   Grounded Policy Rules)   |
                                 +----------------------------+
```

---

## 2. Component Specifications

### 2.1 Database Schema (SQLite)
Foreign keys are enforced per-connection using `PRAGMA foreign_keys = ON;`.

#### `users`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique user identifier |
| `email` | TEXT | UNIQUE NOT NULL | User email address |
| `password_hash` | TEXT | NOT NULL | Bcrypt hashed password |
| `created_at` | TIMESTAMP | NOT NULL | ISO 8601 UTC creation timestamp |

#### `tickets`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique ticket identifier |
| `user_id` | INTEGER | NOT NULL, FK -> users(id) ON DELETE CASCADE | Submitting user ID |
| `message` | TEXT | NOT NULL | Ticket customer message |
| `created_at` | TIMESTAMP | NOT NULL | ISO 8601 UTC creation timestamp |

#### `decisions`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique decision identifier |
| `ticket_id` | INTEGER | NOT NULL, FK -> tickets(id) ON DELETE CASCADE | Associated ticket ID |
| `action` | TEXT | NOT NULL | Recommended action |
| `reason` | TEXT | NOT NULL | Policy-grounded rationale |
| `confidence` | REAL | NOT NULL | Confidence score (0.0 to 1.0) |
| `sources` | TEXT | NOT NULL | JSON string array of filenames |
| `created_at` | TIMESTAMP | NOT NULL | ISO 8601 UTC creation timestamp |

---

### 2.2 REST API Specification

| Method | Endpoint | Auth | Request Body | Response Status & Body | Description |
|---|---|---|---|---|---|
| `GET` | `/health` | None | None | 200 OK: `{"status": "healthy", "rag_chunks_loaded": 26}` | Health and readiness check |
| `POST` | `/register` | None | `{"email": "...", "password": "..."}` | 201 Created: `UserResponse` (400 if duplicate email) | Registers a new user account |
| `POST` | `/login` | None | `{"email": "...", "password": "..."}` | 200 OK: `{"access_token": "...", "token_type": "bearer"}` (401 if invalid) | Issues signed JWT |
| `GET` | `/me` | Bearer JWT | None | 200 OK: `UserResponse` (401 if unauthenticated) | Returns current user profile |
| `POST` | `/tickets` | Bearer JWT | `{"message": "..."}` | 201 Created: `TicketDetailResponse` | Runs RAG + LLM, stores ticket & decision |
| `GET` | `/tickets` | Bearer JWT | None | 200 OK: `List[TicketDetailResponse]` | Lists tickets owned by requesting user |
| `GET` | `/tickets/{id}` | Bearer JWT | None | 200 OK / 403 Forbidden / 404 Not Found | Tenant-isolated ticket inspection |

---

### 2.3 RAG Retrieval Pipeline Mechanics
1. **Document Parsing:** Loads markdown files from `knowledge_base/` (`refunds.md`, `returns.md`, `shipping.md`, `damaged_goods.md`).
2. **Semantic Section Chunking:** Decomposes markdown files on heading boundaries (`# `, `## `), maintaining document title and section headers.
3. **Vector Transformation:**
   - Text is normalized (currency conversion `₹`/`$` -> `inr`/`usd`, lowercase tokenization, lightweight stemming).
   - Local TF-IDF matrix is computed with smoothed inverse document frequencies: $\text{IDF} = \log\left(\frac{N+1}{\text{DF}+1}\right) + 1$.
   - Vectors are L2-normalized: $\hat{v} = \frac{v}{\|v\|_2}$.
4. **Retrieval Algorithm:** Computes dot-product cosine similarity $\text{sim}(q, d) = \hat{q} \cdot \hat{d}$ across all chunks and returns the top 3 scoring segments.

---

### 2.4 LLM Decision Engine & Structured Output
- **Primary LLM:** Google Gemini via the official `google-genai` SDK (`gemini-3.5-flash-lite` with fallback to `gemini-3.5-flash`).
- **Structured Schema:** `types.GenerateContentConfig(response_mime_type="application/json", response_schema=DecisionOutput)`.
- **Validation:** Pydantic `DecisionOutput` enforces `action` within allowable enum set and `confidence` within $[0.0, 1.0]$.
- **Graceful Degradation:** If external API quota or network issues arise, the system falls back to `evaluate_policy_grounded` without breaking downstream applications.

---

### 2.5 Security & Data Isolation
- **Password Protection:** Salting and hashing via `bcrypt.gensalt()` and `bcrypt.hashpw()`. Plaintext passwords are never logged or stored.
- **JWT Signing:** Signed using HMAC-SHA256 with expiration (`exp`) and subject (`sub`) claims.
- **Strict Authorization Isolation:**
  ```python
  if ticket["user_id"] != current_user["id"]:
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Access forbidden: You do not have permission to view this ticket."
      )
  ```
  Verified by `tests/test_authorization_isolation.py`.
