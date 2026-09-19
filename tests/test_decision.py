import pytest
from src.retrieval import PolicyRAG
from src.decision import generate_decision, DecisionOutput, VALID_ACTIONS


def test_decision_output_validation():
    """Verify Pydantic model validation on DecisionOutput."""
    dec = DecisionOutput(
        action="REQUEST_PHOTOS",
        confidence=0.91,
        reason="The order is above ₹2,000 and the damage policy requires photographs.",
        sources=["damaged_goods.md"]
    )
    assert dec.action in VALID_ACTIONS
    assert 0.0 <= dec.confidence <= 1.0
    assert "damaged_goods.md" in dec.sources


def test_high_value_damage_requires_photos():
    """Verify high value damaged goods trigger REQUEST_PHOTOS."""
    rag = PolicyRAG()
    msg = "I received my ₹4,500 ceramic dinner set yesterday, but the bowls arrived completely shattered inside the box."
    chunks = rag.retrieve(msg, top_k=3)
    dec = generate_decision(msg, chunks)

    assert dec.action == "REQUEST_PHOTOS"
    assert dec.confidence >= 0.85
    assert "damaged_goods.md" in dec.sources


def test_expired_return_rejected():
    """Verify return beyond policy window is rejected outside window."""
    rag = PolicyRAG()
    msg = "I bought running shoes delivered 42 days ago. I realized I don't use them and want to return them."
    chunks = rag.retrieve(msg, top_k=3)
    dec = generate_decision(msg, chunks)

    assert dec.action in ["REJECT_OUTSIDE_WINDOW", "REJECT_REQUEST"]
    assert "returns.md" in dec.sources


def test_insufficient_information_handling():
    """
    CRITICAL REQUIREMENT (Section 8):
    The system must not invent an answer when the available information is insufficient.
    In such cases it should return a clear value such as NEEDS_MORE_INFORMATION.
    """
    rag = PolicyRAG()
    msg = "Hey, where is my package?"
    chunks = rag.retrieve(msg, top_k=3)
    dec = generate_decision(msg, chunks)

    assert dec.action == "NEEDS_MORE_INFORMATION"
