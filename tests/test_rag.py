import pytest
from src.retrieval import PolicyRAG


def test_rag_knowledge_base_indexing():
    """Verify that policy documents are loaded and chunked."""
    rag = PolicyRAG()
    assert len(rag.chunks) > 0

    sources = {c.source for c in rag.chunks}
    assert "damaged_goods.md" in sources
    assert "returns.md" in sources
    assert "refunds.md" in sources
    assert "shipping.md" in sources


def test_rag_retrieval_damaged_goods():
    """Verify RAG retrieval retrieves damaged_goods.md for damaged items."""
    rag = PolicyRAG()
    results = rag.retrieve("My ₹4,500 ceramic dinner set arrived completely shattered yesterday", top_k=3)
    assert len(results) > 0
    top_hit = results[0]
    assert top_hit["source"] == "damaged_goods.md"
    assert top_hit["score"] > 0


def test_rag_retrieval_returns():
    """Verify RAG retrieval retrieves returns.md for return inquiries."""
    rag = PolicyRAG()
    results = rag.retrieve("I want to return an unworn jacket delivered 15 days ago with original tags", top_k=3)
    assert len(results) > 0
    top_hit = results[0]
    assert top_hit["source"] == "returns.md"
    assert top_hit["score"] > 0


def test_rag_retrieval_shipping():
    """Verify RAG retrieval retrieves shipping.md for shipping tracking issues."""
    rag = PolicyRAG()
    results = rag.retrieve("My courier package has had no tracking scan movement for 8 days", top_k=3)
    assert len(results) > 0
    top_hit = results[0]
    assert top_hit["source"] == "shipping.md"
    assert top_hit["score"] > 0
