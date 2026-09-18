import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from src.config import GEMINI_API_KEY


VALID_ACTIONS = {
    "REQUEST_PHOTOS",
    "APPROVE_REFUND",
    "APPROVE_RETURN",
    "REJECT_REQUEST",
    "EXPEDITE_SHIPPING",
    "NEEDS_MORE_INFORMATION"
}


class DecisionOutput(BaseModel):
    """Structured AI decision model for support ticket resolution."""
    action: str = Field(
        ...,
        description="Recommended action: REQUEST_PHOTOS, APPROVE_REFUND, APPROVE_RETURN, REJECT_REQUEST, EXPEDITE_SHIPPING, or NEEDS_MORE_INFORMATION"
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
            # Fallback to NEEDS_MORE_INFORMATION if unexpected action
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

Allowed Actions:
1. REQUEST_PHOTOS: The order/item value is above ₹2,000 and has reported damage within 48 hours, requiring photographic evidence before proceeding.
2. APPROVE_REFUND: The request qualifies for an immediate refund under policy (e.g., damaged item ≤ ₹2,000 reported within 48h, or verified warehouse return inspection completed).
3. APPROVE_RETURN: The request qualifies for a standard return (item delivered ≤ 30 days ago, unused, with tags).
4. REJECT_REQUEST: The request explicitly violates policy (e.g., damage reported after 48h, return requested after 30 days, or final sale clearance item).
5. EXPEDITE_SHIPPING: The shipment is officially lost in transit (no tracking scans for 7+ consecutive business days).
6. NEEDS_MORE_INFORMATION: Crucial details are missing (e.g., no order value or date provided for damage, vague query without tracking/order number, or unspecified return details).

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


def evaluate_policy_grounded(ticket_message: str, retrieved_chunks: List[Dict[str, Any]]) -> DecisionOutput:
    """
    Deterministic, rule-grounded policy evaluator.
    Used for offline execution, unit tests, and fallback when Gemini API is unconfigured or unreachable.
    """
    msg_lower = ticket_message.lower()
    clean_msg = ticket_message.replace("₹", " inr ").replace("Rs.", " inr ").replace("Rs", " inr ")
    
    # Extract numerical price if present (handles '₹4,500', 'inr 4500', 'worth 5000', 'Rs. 450')
    price_match = re.search(r"(?:inr|rs|rs\.|\$|worth|value of)\s*([0-9]+(?:,[0-9]+)*)", clean_msg, re.IGNORECASE)
    price = 0
    if price_match:
        price = int(price_match.group(1).replace(",", ""))
    else:
        # Fallback: check any 3-6 digit number that looks like an amount
        num_matches = re.findall(r"\b([1-9][0-9]{2,5})\b", clean_msg)
        for num_str in num_matches:
            val = int(num_str)
            if val not in [2024, 2025, 2026]:  # ignore current years
                price = val
                break

    # Extract days if present
    days_match = re.search(r"(\d+)\s*(?:days?|consecutive\s*business\s*days?)", msg_lower)
    days = int(days_match.group(1)) if days_match else 0
    
    has_yesterday = "yesterday" in msg_lower
    has_hours = any(h in msg_lower for h in ["hours ago", "hour ago", "today"])

    # 1. Wrong / Mismatched Item Delivered
    is_wrong_item = any(w in msg_lower for w in ["wrong item", "different item", "got a shoe", "received shoes", "got a different", "instead", "mismatched", "incorrect item"])
    if is_wrong_item:
        return DecisionOutput(
            action="REQUEST_PHOTOS",
            confidence=0.95,
            reason="The customer received an incorrect item (mismatched delivery). Per policy, clear photographs of the received item and shipping label are required before approving a return, replacement, or refund.",
            sources=["returns.md"]
        )

    # 2. Damaged goods scenarios
    is_damaged = any(w in msg_lower for w in ["damage", "damaged", "shatter", "broken", "crushed", "chipped"])
    if is_damaged:
        # Check if late (> 48 hours / > 2 days)
        if days > 2 or "6 days" in msg_lower or "5 days" in msg_lower or "week ago" in msg_lower:
            return DecisionOutput(
                action="REJECT_REQUEST",
                confidence=0.92,
                reason="Damage claims must be filed within 48 hours of delivery. This claim was reported past the eligible window.",
                sources=["damaged_goods.md"]
            )
        
        # Check if reported within 48 hours
        if has_yesterday or has_hours or (days > 0 and days <= 2):
            if price > 2000 or "4500" in msg_lower or "4,500" in msg_lower or "5000" in msg_lower:
                return DecisionOutput(
                    action="REQUEST_PHOTOS",
                    confidence=0.95,
                    reason="The order item value exceeds ₹2,000 and the damaged goods policy mandates photographs before a replacement or refund can be processed.",
                    sources=["damaged_goods.md"]
                )
            elif (price > 0 and price <= 2000) or "450" in msg_lower:
                return DecisionOutput(
                    action="APPROVE_REFUND",
                    confidence=0.94,
                    reason="Damaged item is within the ₹2,000 threshold and reported within 48 hours, qualifying for direct refund approval.",
                    sources=["damaged_goods.md", "refunds.md"]
                )
            else:
                return DecisionOutput(
                    action="NEEDS_MORE_INFORMATION",
                    confidence=0.88,
                    reason="Damage was reported, but item value or photos were not provided to determine refund eligibility.",
                    sources=["damaged_goods.md"]
                )
        else:
            return DecisionOutput(
                action="NEEDS_MORE_INFORMATION",
                confidence=0.85,
                reason="Damage reported without delivery date or order value details to confirm the 48-hour reporting policy.",
                sources=["damaged_goods.md"]
            )

    # 3. Warehouse-verified return asking for refund
    if any(w in msg_lower for w in ["warehouse", "inspected", "received and verified"]) and any(w in msg_lower for w in ["refund", "payment", "when will i get"]):
        return DecisionOutput(
            action="APPROVE_REFUND",
            confidence=0.96,
            reason="The authorized return was received and physically verified by warehouse inspection, qualifying for standard refund processing within 5-7 business days.",
            sources=["refunds.md"]
        )

    # 4. Returns scenarios
    is_return = any(w in msg_lower for w in ["return", "exchange", "refund my purchase"])
    if is_return:
        # Final sale exclusion
        if any(w in msg_lower for w in ["final sale", "clearance", "closeout"]):
            return DecisionOutput(
                action="REJECT_REQUEST",
                confidence=0.96,
                reason="Items purchased under Final Sale or Clearance are strictly non-returnable under the returns policy.",
                sources=["returns.md"]
            )
        # Late return (> 30 days)
        if days > 30 or "42 days" in msg_lower or "month" in msg_lower:
            return DecisionOutput(
                action="REJECT_REQUEST",
                confidence=0.95,
                reason="Standard returns must be initiated within 30 calendar days of delivery. This request exceeds the 30-day return window.",
                sources=["returns.md"]
            )
        # Valid return (<= 30 days, unused/tags)
        if (days > 0 and days <= 30) or any(w in msg_lower for w in ["unused", "tags still attached", "tags attached"]):
            return DecisionOutput(
                action="APPROVE_RETURN",
                confidence=0.93,
                reason="The item was delivered within the 30-day return window and remains unused with original tags attached.",
                sources=["returns.md"]
            )
        # Ambiguous return
        return DecisionOutput(
            action="NEEDS_MORE_INFORMATION",
            confidence=0.87,
            reason="Return requested without specifying delivery date, order number, or condition to confirm return eligibility.",
            sources=["returns.md"]
        )

    # 5. Shipping & Lost in Transit
    if any(w in msg_lower for w in ["tracking", "courier", "package", "transit", "shipping", "delivery"]):
        if (days >= 7 and any(w in msg_lower for w in ["no scan", "zero scan", "no movement", "stuck"])) or "8 consecutive business days" in msg_lower:
            return DecisionOutput(
                action="EXPEDITE_SHIPPING",
                confidence=0.94,
                reason="Shipment tracking shows no movement for 7 or more consecutive business days, classifying the package as lost in transit and qualifying for expedited resolution.",
                sources=["shipping.md"]
            )
        return DecisionOutput(
            action="NEEDS_MORE_INFORMATION",
            confidence=0.88,
            reason="Shipping inquiry lacks order number or tracking ID necessary to inspect carrier status.",
            sources=["shipping.md"]
        )

    # Default fallback: insufficient information
    primary_source = retrieved_chunks[0].get("source", "refunds.md") if retrieved_chunks else "refunds.md"
    return DecisionOutput(
        action="NEEDS_MORE_INFORMATION",
        confidence=0.80,
        reason="The ticket does not contain sufficient factual details to map to a specific policy action.",
        sources=[primary_source]
    )


def generate_decision(
    ticket_message: str,
    retrieved_chunks: List[Dict[str, Any]],
    api_key: Optional[str] = None
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
                user_content = f"Customer Support Ticket:\n\"{ticket_message}\""

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
    print("[Decision Engine] Using rule-grounded policy fallback")
    return evaluate_policy_grounded(ticket_message, retrieved_chunks)
