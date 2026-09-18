import os
import re
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from src.config import KNOWLEDGE_BASE_DIR, GEMINI_API_KEY


class DocumentChunk:
    def __init__(self, chunk_id: str, source: str, title: str, content: str):
        self.chunk_id = chunk_id
        self.source = source
        self.title = title
        self.content = content
        self.embedding: Optional[np.ndarray] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source": self.source,
            "title": self.title,
            "content": self.content
        }


class PolicyRAG:
    """RAG pipeline for chunking policy markdown files, generating embeddings, and retrieving relevant context."""

    def __init__(self, kb_dir: Optional[Path] = None, api_key: Optional[str] = None):
        self.kb_dir = kb_dir or KNOWLEDGE_BASE_DIR
        self.api_key = api_key if api_key is not None else GEMINI_API_KEY
        self.chunks: List[DocumentChunk] = []
        self.gemini_client = None
        self.vocabulary: Dict[str, int] = {}
        self.idf: np.ndarray = np.array([])
        self.tfidf_matrix: np.ndarray = np.array([])
        
        # Initialize Gemini client if key is provided
        if self.api_key and self.api_key.strip():
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.api_key.strip())
            except Exception:
                self.gemini_client = None

        self.load_and_index()

    def _normalize_token(self, t: str) -> str:
        """Lightweight stemmer for English inflections."""
        if len(t) > 4:
            for sfx in ["ing", "ed", "es", "s"]:
                if t.endswith(sfx) and len(t) - len(sfx) >= 3:
                    return t[:-len(sfx)]
        return t

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text with currency normalization and lightweight stemming."""
        cleaned = text.replace("₹", " inr ").replace("Rs.", " inr ").replace("Rs", " inr ").replace("$", " usd ")
        raw_tokens = re.findall(r"[a-zA-Z0-9]+", cleaned.lower())
        tokens = [self._normalize_token(t) for t in raw_tokens if len(t) > 1]
        return tokens

    def load_and_index(self) -> None:
        """Load markdown files from knowledge base directory, split into sections, and build index."""
        self.chunks = []
        if not self.kb_dir.exists():
            return

        for filepath in sorted(self.kb_dir.glob("*.md")):
            filename = filepath.name
            try:
                content = filepath.read_text(encoding="utf-8")
            except Exception:
                continue

            # Split document by markdown headings (# or ##)
            sections = re.split(r"(?m)^(?=##? )", content)
            doc_title = filename.replace(".md", "").replace("_", " ").title()
            chunk_idx = 1

            for section in sections:
                clean_sec = section.strip()
                if not clean_sec:
                    continue

                lines = clean_sec.splitlines()
                first_line = lines[0].strip() if lines else ""
                section_title = first_line.lstrip("#").strip() if first_line.startswith("#") else doc_title
                body = "\n".join(lines[1:]).strip() if len(lines) > 1 else clean_sec

                if not body:
                    body = clean_sec

                chunk_id = f"{filename}_{chunk_idx}"
                chunk_idx += 1

                self.chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    source=filename,
                    title=f"{doc_title} - {section_title}",
                    content=f"Document: {filename}\nSection: {section_title}\n{body}"
                ))

        self._build_local_vector_index()
        self._build_gemini_embeddings()

    def _build_local_vector_index(self) -> None:
        """Build a local TF-IDF vector index for fast, deterministic, offline similarity."""
        if not self.chunks:
            return

        # Build vocabulary
        doc_tokens_list = [self._tokenize(chunk.content) for chunk in self.chunks]
        vocab_set = set()
        for tokens in doc_tokens_list:
            vocab_set.update(tokens)

        self.vocabulary = {term: idx for idx, term in enumerate(sorted(vocab_set))}
        num_docs = len(self.chunks)
        vocab_size = len(self.vocabulary)

        if vocab_size == 0 or num_docs == 0:
            return

        # Compute document frequency (DF)
        df = np.zeros(vocab_size)
        tf_matrix = np.zeros((num_docs, vocab_size))

        for doc_idx, tokens in enumerate(doc_tokens_list):
            seen_terms = set()
            for token in tokens:
                if token in self.vocabulary:
                    term_idx = self.vocabulary[token]
                    tf_matrix[doc_idx, term_idx] += 1
                    seen_terms.add(term_idx)
            for term_idx in seen_terms:
                df[term_idx] += 1

        # Smooth IDF: log((N + 1) / (df + 1)) + 1
        self.idf = np.log((num_docs + 1.0) / (df + 1.0)) + 1.0

        # Compute TF-IDF matrix
        tfidf = tf_matrix * self.idf
        norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.tfidf_matrix = tfidf / norms

    def _build_gemini_embeddings(self) -> None:
        """Fetch remote Gemini embeddings if client is configured."""
        if not self.gemini_client:
            return

        for chunk in self.chunks:
            try:
                res = self.gemini_client.models.embed_content(
                    model="text-embedding-004",
                    contents=chunk.content
                )
                if hasattr(res, "embedding") and hasattr(res.embedding, "values"):
                    chunk.embedding = np.array(res.embedding.values, dtype=np.float32)
                elif hasattr(res, "embeddings") and res.embeddings:
                    chunk.embedding = np.array(res.embeddings[0].values, dtype=np.float32)
            except Exception:
                chunk.embedding = None

    def _query_local_vector(self, query: str) -> np.ndarray:
        """Convert query string to a normalized TF-IDF vector."""
        if not self.vocabulary or len(self.idf) == 0:
            return np.zeros(len(self.vocabulary))

        tokens = self._tokenize(query)
        vec = np.zeros(len(self.vocabulary))
        for token in tokens:
            if token in self.vocabulary:
                vec[self.vocabulary[token]] += 1

        tfidf_vec = vec * self.idf
        norm = np.linalg.norm(tfidf_vec)
        if norm > 0:
            tfidf_vec = tfidf_vec / norm
        return tfidf_vec

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve the top-k most relevant chunks for a user query."""
        if not self.chunks:
            return []

        # If Gemini embeddings are available across all chunks, try embedding query with Gemini
        has_gemini_vectors = (
            self.gemini_client is not None
            and all(chunk.embedding is not None for chunk in self.chunks)
        )

        if has_gemini_vectors:
            try:
                res = self.gemini_client.models.embed_content(
                    model="text-embedding-004",
                    contents=query
                )
                q_vec = None
                if hasattr(res, "embedding") and hasattr(res.embedding, "values"):
                    q_vec = np.array(res.embedding.values, dtype=np.float32)
                elif hasattr(res, "embeddings") and res.embeddings:
                    q_vec = np.array(res.embeddings[0].values, dtype=np.float32)

                if q_vec is not None:
                    q_norm = np.linalg.norm(q_vec)
                    if q_norm > 0:
                        q_vec = q_vec / q_norm

                    scores = []
                    for idx, chunk in enumerate(self.chunks):
                        c_norm = np.linalg.norm(chunk.embedding)
                        c_vec = chunk.embedding / c_norm if c_norm > 0 else chunk.embedding
                        sim = float(np.dot(q_vec, c_vec))
                        scores.append((sim, idx))

                    scores.sort(key=lambda x: x[0], reverse=True)
                    results = []
                    for sim, idx in scores[:top_k]:
                        item = self.chunks[idx].to_dict()
                        item["score"] = round(sim, 4)
                        results.append(item)
                    return results
            except Exception:
                pass  # Fall back to local vector index

        # Local TF-IDF cosine similarity
        if self.tfidf_matrix.size > 0:
            q_vec = self._query_local_vector(query)
            sims = np.dot(self.tfidf_matrix, q_vec)
            top_indices = np.argsort(sims)[::-1][:top_k]
            results = []
            for idx in top_indices:
                item = self.chunks[idx].to_dict()
                item["score"] = round(float(sims[idx]), 4)
                results.append(item)
            return results

        # Basic fallback: return first top_k
        return [chunk.to_dict() for chunk in self.chunks[:top_k]]


# Global singleton instance
rag_pipeline = PolicyRAG()
