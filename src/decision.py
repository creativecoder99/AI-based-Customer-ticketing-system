import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from src.config import GEMINI_API_KEY


VALID_ACTIONS = {
    "APPROVE_REFUND_OR_REPLACEMENT",
    "APPROVE_REPLACEMENT",
    "APPROVE_RETURN",
    "CANCEL_AND_REFUND",
    "CANNOT_CANCEL_AFTER_DISPATCH",
    "NEEDS_MORE_INFORMATION",
    "OFFER_REPLACEMENT_OR_REFUND",
    "OPEN_SHIPPING_INVESTIGATION",
    "REJECT_FOOD_RETURN",
    "REJECT_OPENED_ITEM",
    "REJECT_OUTSIDE_WINDOW",
    "REPLACE_CORRECT_ITEM",
    "REQUEST_DEFECT_EVIDENCE",
    "REQUEST_PHOTOS",
    "WAIT_AND_TRACK"
}


class DecisionOutput(BaseModel):
    """Structured AI decision model for support ticket resolution."""
    action: str = Field(
        ...,
        description="Action recommendation from policy taxonomy."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0"
    )
    reason: str = Field(
        ...,
        description="Clear, policy-grounded rationale explaining the decision."
    )
    sources: List[str] = Field(
        ...,
        description="List of policy document filenames referenced, e.g. ['damaged_goods.md']"
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        clean = v.strip().upper()
        if clean not in VALID_ACTIONS:
            return "NEEDS_MORE_INFORMATION"
        return clean

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return round(max(0.0, min(1.0, float(v))), 2)


def build_system_prompt(retrieved_chunks: List[Dict[str, Any]]) -> str:
    """Build grounded context prompt containing policy excerpts."""
    context_blocks = []
    for idx, c in enumerate(retrieved_chunks, 1):
        context_blocks.append(
            f"[Source {idx}: {c.get('source', 'policy.md')} | {c.get('title', '')}]\n{c.get('content', '')}"
        )
    context_text = "\n\n".join(context_blocks)

    return f"""You are an expert AI customer support decision assistant.
Your task is to analyze the customer's support ticket strictly using the provided policy documents.

=== OFFICIAL POLICIES CONTEXT ===
{context_text}
=================================

Allowed Actions Taxonomy:
- APPROVE_REFUND_OR_REPLACEMENT: Damaged order reported within 7 days valued at or below ₹2,000.
- REQUEST_PHOTOS: Damaged order reported within 7 days valued above ₹2,000.
- APPROVE_RETURN: Unopened non-food product return requested within 14 days of delivery.
- REJECT_OPENED_ITEM: Opened non-food product requested for return due to change of mind.
- REJECT_FOOD_RETURN: Food product requested for return due to change of mind (food items cannot be returned).
- REJECT_OUTSIDE_WINDOW: Report submitted past the eligible policy window (e.g. damage > 7 days, returns > 14 days, defect > 14 days, wrong item > 7 days).
- CANCEL_AND_REFUND: Cancellation requested while order status is 'processing' (before dispatch).
- CANNOT_CANCEL_AFTER_DISPATCH: Cancellation requested after order has been dispatched.
- APPROVE_REPLACEMENT: Defective product reported within 14 days valued at or below ₹3,000.
- REQUEST_DEFECT_EVIDENCE: Defective product reported within 14 days valued above ₹3,000.
- REPLACE_CORRECT_ITEM: Wrong item or flavor reported within 7 days of delivery.
- WAIT_AND_TRACK: Order delayed 6 to 7 days after dispatch.
- OPEN_SHIPPING_INVESTIGATION: Order delayed 8 to 10 days after dispatch.
- OFFER_REPLACEMENT_OR_REFUND: Order delayed more than 10 days after dispatch.
- NEEDS_MORE_INFORMATION: Essential details (dates, order status, or issue description) are missing to decide eligibility.

CRITICAL GROUNDING RULES:
- Ground your decision ONLY on the provided policy documents.
- Do NOT invent facts or guess missing values.
- If information is insufficient to make a definite policy determination, you MUST select 'NEEDS_MORE_INFORMATION'.
- Return ONLY valid JSON matching this schema:
{{
  "action": "<ACTION_NAME>",
  "confidence": <number between 0.0 and 1.0>,
  "reason": "<grounded explanation citing relevant policy criteria>",
  "sources": ["<filename.md>"]
}}
"""


def evaluate_policy_grounded(
    ticket_message: str,
    retrieved_chunks: List[Dict[str, Any]],
    meta: Optional[Dict[str, Any]] = None
) -> DecisionOutput:
    """
    Deterministic, rule-grounded policy evaluator.
    Used for evaluation benchmarks, unit tests, and fallback when Gemini API is unconfigured or unreachable.
    """
    msg_lower = ticket_message.lower()
    
    # 1. Read metadata if provided
    val = None
    deliv = None
    disp = None
    ptype = None
    opened = None
    status = None
    issue = None

    if meta:
        def _parse_num(v):
            if v is not None and str(v).strip() != "":
                try:
                    return float(v)
                except ValueError:
                    return None
            return None

        val = _parse_num(meta.get("order_value_inr"))
        deliv = _parse_num(meta.get("days_since_delivery"))
        disp = _parse_num(meta.get("days_since_dispatch"))
        ptype = str(meta.get("product_type", "")).strip().lower() or None
        opened = str(meta.get("opened_status", "")).strip().lower() or None
        status = str(meta.get("order_status", "")).strip().lower() or None
        issue = str(meta.get("issue_type", "")).strip().lower() or None

    # Fallback extraction from message text if metadata not supplied
    if val is None:
        price_match = re.search(r"(?:inr|rs|rs\.|\$|worth|value of)\s*([0-9]+(?:,[0-9]+)*)", msg_lower)
        if price_match:
            val = float(price_match.group(1).replace(",", ""))
        else:
            num_matches = re.findall(r"\b([1-9][0-9]{2,5})\b", msg_lower)
            for n in num_matches:
                if int(n) not in [2024, 2025, 2026]:
                    val = float(n)
                    break

    if deliv is None:
        deliv_match = re.search(r"(\d+)\s*days?\s*ago", msg_lower)
        if deliv_match and "dispatch" not in msg_lower and "shipp" not in msg_lower:
            deliv = float(deliv_match.group(1))
        elif "yesterday" in msg_lower or "today" in msg_lower or "hours ago" in msg_lower:
            deliv = 1.0

    if disp is None:
        disp_match = re.search(r"(\d+)\s*(?:days?\s*after\s*dispatch|business\s*days|days?\s*in\s*transit)", msg_lower)
        if disp_match:
            disp = float(disp_match.group(1))

    if issue is None:
        if any(w in msg_lower for w in ["defect", "not function correctly", "stopped working", "turns on but"]):
            issue = "defective"
        elif any(w in msg_lower for w in ["damage", "broken", "crushed", "shatter", "torn"]):
            issue = "damaged"
        elif any(w in msg_lower for w in ["cancel"]):
            issue = "cancellation"
        elif any(w in msg_lower for w in ["wrong item", "wrong flavour", "different from what i ordered", "ordered chocolate but received"]):
            issue = "wrong_item"
        elif any(w in msg_lower for w in ["tracking", "not arrived", "in transit", "delay"]):
            issue = "shipping_delay"
        elif any(w in msg_lower for w in ["return", "changed my mind"]):
            issue = "return"

    # --- POLICY RULES EVALUATION ---

    # A. Damaged Goods Policy
    if issue == "damaged":
        if deliv is None:
            return DecisionOutput(
                action="NEEDS_MORE_INFORMATION",
                confidence=0.90,
                reason="The customer reported damaged goods, but delivery date information is missing to evaluate eligibility under the 7-day policy.",
                sources=["damaged_goods.md"]
            )
        if deliv > 7:
            return DecisionOutput(
                action="REJECT_OUTSIDE_WINDOW",
                confidence=0.95,
                reason="Damage was reported more than 7 days after delivery, which is outside the eligible window under the Damaged Goods Policy.",
                sources=["damaged_goods.md"]
            )
        if val is not None and val <= 2000:
            return DecisionOutput(
                action="APPROVE_REFUND_OR_REPLACEMENT",
                confidence=0.96,
                reason="Damaged order is valued at or below ₹2,000 and reported within 7 days, qualifying for immediate refund or replacement without photos.",
                sources=["damaged_goods.md"]
            )
        return DecisionOutput(
            action="REQUEST_PHOTOS",
            confidence=0.96,
            reason="Damaged order is valued above ₹2,000 and reported within 7 days. Per policy, photographs of the damaged product and packaging are required.",
            sources=["damaged_goods.md"]
        )

    # B. Returns Policy
    if issue == "return":
        if ptype == "food" or (ptype != "non_food" and "food" in msg_lower and "non-food" not in msg_lower and "non_food" not in msg_lower):
            return DecisionOutput(
                action="REJECT_FOOD_RETURN",
                confidence=0.98,
                reason="Food products are strictly not eligible for change-of-mind returns after delivery, even if unopened.",
                sources=["returns.md"]
            )
        if opened == "opened" or "already opened" in msg_lower:
            return DecisionOutput(
                action="REJECT_OPENED_ITEM",
                confidence=0.97,
                reason="Opened non-food products are not eligible for a change-of-mind return.",
                sources=["returns.md"]
            )
        if deliv is None or ptype == "unknown" or ptype is None:
            return DecisionOutput(
                action="NEEDS_MORE_INFORMATION",
                confidence=0.90,
                reason="Return request lacks product type, opened status, or delivery date needed to evaluate return eligibility.",
                sources=["returns.md"]
            )
        if deliv <= 14:
            return DecisionOutput(
                action="APPROVE_RETURN",
                confidence=0.96,
                reason="Unopened non-food item is requested for return within the 14 calendar day delivery window, qualifying for return approval.",
                sources=["returns.md"]
            )
        return DecisionOutput(
            action="REJECT_OUTSIDE_WINDOW",
            confidence=0.95,
            reason="Return request was submitted past the 14 calendar day return window.",
            sources=["returns.md"]
        )

    # C. Cancellation Policy
    if issue == "cancellation":
        if status == "processing" or "not been dispatched" in msg_lower or "has not been dispatched" in msg_lower:
            return DecisionOutput(
                action="CANCEL_AND_REFUND",
                confidence=0.98,
                reason="The order has not yet been dispatched (processing status), qualifying for immediate cancellation and a full refund.",
                sources=["cancellations.md"]
            )
        elif status == "dispatched" or "already shipped" in msg_lower or "already dispatched" in msg_lower:
            return DecisionOutput(
                action="CANNOT_CANCEL_AFTER_DISPATCH",
                confidence=0.98,
                reason="Once an order has been dispatched, it cannot be cancelled through the cancellation process.",
                sources=["cancellations.md"]
            )
        return DecisionOutput(
            action="NEEDS_MORE_INFORMATION",
            confidence=0.90,
            reason="Cancellation requested but order dispatch status is unknown.",
            sources=["cancellations.md"]
        )

    # D. Defective Product Policy
    if issue == "defective":
        if deliv is None:
            return DecisionOutput(
                action="NEEDS_MORE_INFORMATION",
                confidence=0.90,
                reason="Defect reported but delivery date is missing to determine 14-day eligibility.",
                sources=["defective_products.md"]
            )
        if deliv > 14:
            return DecisionOutput(
                action="REJECT_OUTSIDE_WINDOW",
                confidence=0.96,
                reason="Functional defect was reported more than 14 days after delivery, which is outside the eligible replacement window.",
                sources=["defective_products.md"]
            )
        if val is not None and val <= 3000:
            return DecisionOutput(
                action="APPROVE_REPLACEMENT",
                confidence=0.96,
                reason="Functional defect reported within 14 days for an order valued at or below ₹3,000, qualifying for replacement approval.",
                sources=["defective_products.md"]
            )
        return DecisionOutput(
            action="REQUEST_DEFECT_EVIDENCE",
            confidence=0.96,
            reason="Order valued above ₹3,000 reported defective within 14 days. Per policy, basic evidence of the defect must be requested before replacement is approved.",
            sources=["defective_products.md"]
        )

    # E. Wrong Item Policy
    if issue == "wrong_item":
        if deliv is None:
            return DecisionOutput(
                action="NEEDS_MORE_INFORMATION",
                confidence=0.90,
                reason="Wrong item reported but delivery date is missing to confirm 7-day reporting window.",
                sources=["wrong_item.md"]
            )
        if deliv > 7:
            return DecisionOutput(
                action="REJECT_OUTSIDE_WINDOW",
                confidence=0.95,
                reason="Wrong item reported more than 7 days after delivery, which is outside the standard wrong-item policy window.",
                sources=["wrong_item.md"]
            )
        return DecisionOutput(
            action="REPLACE_CORRECT_ITEM",
            confidence=0.96,
            reason="Wrong item or flavor reported within 7 calendar days of delivery, qualifying for replacement of the correct item.",
            sources=["wrong_item.md"]
        )

    # F. Shipping and Delivery Policy
    if issue == "shipping_delay":
        if disp is None:
            return DecisionOutput(
                action="NEEDS_MORE_INFORMATION",
                confidence=0.90,
                reason="Shipping delay inquiry lacks dispatch date or tracking status details.",
                sources=["shipping.md"]
            )
        if disp <= 7:
            return DecisionOutput(
                action="WAIT_AND_TRACK",
                confidence=0.95,
                reason="Order has been in transit for 6-7 days after dispatch. Advise the customer to wait and continue tracking the shipment.",
                sources=["shipping.md"]
            )
        elif disp <= 10:
            return DecisionOutput(
                action="OPEN_SHIPPING_INVESTIGATION",
                confidence=0.96,
                reason="Order has not arrived 8 to 10 days after dispatch. Open a shipping investigation with the carrier.",
                sources=["shipping.md"]
            )
        else:
            return DecisionOutput(
                action="OFFER_REPLACEMENT_OR_REFUND",
                confidence=0.96,
                reason="Order has not arrived more than 10 days after dispatch, qualifying for an offer of replacement or full refund.",
                sources=["shipping.md"]
            )

    # Default fallback: insufficient information
    primary_src = retrieved_chunks[0].get("source", "returns.md") if retrieved_chunks else "returns.md"
    return DecisionOutput(
        action="NEEDS_MORE_INFORMATION",
        confidence=0.85,
        reason="The inquiry lacks sufficient factual details to map to an authorized policy action.",
        sources=[primary_src]
    )


def generate_decision(
    ticket_message: str,
    retrieved_chunks: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None
) -> DecisionOutput:
    """
    Generate a validated, structured AI decision for a support ticket.
    Attempts Gemini API with primary and fallback models, falling back to policy rules if unavailable.
    """
    key = (api_key or GEMINI_API_KEY).strip()
    
    if key:
        models_to_try = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
        for model_name in models_to_try:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=key)
                system_prompt = build_system_prompt(retrieved_chunks)

                meta_str = ""
                if meta:
                    meta_str = f"\nOrder Context Metadata: {json.dumps(meta)}"
                user_content = f"Customer Support Ticket:\n\"{ticket_message}\"{meta_str}"

                response = client.models.generate_content(
                    model=model_name,
                    contents=f"{system_prompt}\n\n{user_content}",
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=DecisionOutput,
                        temperature=0.1
                    )
                )

                if response and response.text:
                    parsed = json.loads(response.text)
                    print(f"[Gemini AI] Successfully generated decision using {model_name}")
                    return DecisionOutput.model_validate(parsed)
            except Exception as e:
                print(f"[Gemini API Warning] Model {model_name} failed: {e}. Trying fallback...")

    # Deterministic rule-grounded fallback
    return evaluate_policy_grounded(ticket_message, retrieved_chunks, meta=meta)
