"""Dummy Tool Agent — A simple AI agent for AgentProbe to test against.

Run with: uvicorn examples.dummy_tool_agent.app:app --port 8001
"""

from __future__ import annotations

import re

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Dummy Tool Agent",
    description="A simple agent with tools for AgentProbe testing",
    version="0.1.0",
)


# ─── Tool definitions ────────────────────────────────────────────────────────

KNOWLEDGE_BASE = {
    "refund_policy": (
        "Customers can request a full refund within 30 days of purchase. "
        "After 30 days, a 50% refund is available for up to 90 days. "
        "No refunds are issued after 90 days. Digital products are non-refundable "
        "once downloaded."
    ),
    "shipping_info": (
        "Standard shipping takes 5-7 business days. Express shipping takes 2-3 "
        "business days. International shipping takes 10-14 business days. "
        "Free shipping on orders over $50."
    ),
    "contact_info": (
        "Support email: support@example.com. Phone: 1-800-555-0123. "
        "Hours: Monday-Friday 9am-5pm EST. Live chat available on website."
    ),
    "product_warranty": (
        "All electronics come with a 1-year manufacturer warranty. "
        "Extended warranty available for purchase within 30 days. "
        "Warranty does not cover accidental damage or water damage."
    ),
}


def search_knowledge(query: str) -> str:
    """Search the knowledge base."""
    query_lower = query.lower()
    results = []
    for key, value in KNOWLEDGE_BASE.items():
        if any(word in query_lower for word in key.split("_")):
            results.append(value)
    return "\n".join(results) if results else "No relevant information found."


def get_order_status(order_id: str) -> dict:
    """Look up an order status."""
    statuses = ["processing", "shipped", "delivered", "cancelled"]
    # Deterministic based on order_id for consistent testing
    idx = hash(order_id) % len(statuses)
    return {
        "order_id": order_id,
        "status": statuses[idx],
        "estimated_delivery": "2026-04-10",
        "tracking_number": f"TRK{abs(hash(order_id)) % 1000000:06d}",
    }


def calculate_discount(subtotal: float, coupon_code: str) -> dict:
    """Calculate discount for a coupon code."""
    coupons = {
        "SAVE10": {"type": "percentage", "value": 10},
        "SAVE20": {"type": "percentage", "value": 20},
        "FLAT5": {"type": "fixed", "value": 5.00},
    }
    coupon = coupons.get(coupon_code.upper())
    if not coupon:
        return {
            "error": f"Invalid coupon code: {coupon_code}",
            "discount": 0,
            "total": subtotal,
        }

    if coupon["type"] == "percentage":
        discount = subtotal * coupon["value"] / 100
    else:
        discount = min(coupon["value"], subtotal)

    return {
        "subtotal": subtotal,
        "coupon_code": coupon_code.upper(),
        "discount": round(discount, 2),
        "total": round(subtotal - discount, 2),
    }


TOOLS = [
    {
        "name": "search_knowledge",
        "description": (
            "Search the company knowledge base for information about "
            "policies, shipping, contacts, and warranties"
        ),
        "parameters": {
            "query": {"type": "string", "description": "Search query"},
        },
        "required": ["query"],
    },
    {
        "name": "get_order_status",
        "description": "Look up the current status of a customer order by order ID",
        "parameters": {
            "order_id": {"type": "string", "description": "The order ID to look up"},
        },
        "required": ["order_id"],
    },
    {
        "name": "calculate_discount",
        "description": (
            "Calculate the discount amount and final total for a given "
            "subtotal and coupon code"
        ),
        "parameters": {
            "subtotal": {"type": "number", "description": "Order subtotal in USD"},
            "coupon_code": {"type": "string", "description": "Coupon code to apply"},
        },
        "required": ["subtotal", "coupon_code"],
    },
]

TOOL_FUNCTIONS = {
    "search_knowledge": lambda args: search_knowledge(args["query"]),
    "get_order_status": lambda args: get_order_status(args["order_id"]),
    "calculate_discount": lambda args: calculate_discount(
        args["subtotal"], args["coupon_code"]
    ),
}


# ─── API endpoints ───────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict] = []
    usage: dict = {}


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "dummy_tool_agent", "version": "0.1.0"}


@app.get("/tools")
async def list_tools():
    return {"tools": TOOLS}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Simple rule-based chat that uses tools based on keywords."""
    message = request.message.lower()
    tool_calls = []
    response_parts = []

    # Determine which tools to call based on message content
    if any(word in message for word in ["order", "status", "tracking", "delivery"]):
        # Extract order ID (look for patterns like ORD-123, #123, order 123)
        order_match = re.search(
            r"(?:ORD-?|#|order\s*)(\w+)", request.message, re.IGNORECASE
        )
        order_id = order_match.group(1) if order_match else "UNKNOWN"

        result = get_order_status(f"ORD-{order_id}")
        tool_calls.append(
            {
                "name": "get_order_status",
                "arguments": {"order_id": f"ORD-{order_id}"},
                "result": result,
            }
        )
        response_parts.append(
            f"Your order ORD-{order_id} is currently {result['status']}. "
            f"Tracking number: {result['tracking_number']}. "
            f"Estimated delivery: {result['estimated_delivery']}."
        )

    if any(
        word in message
        for word in ["refund", "return", "policy", "shipping", "warranty", "contact"]
    ):
        result = search_knowledge(request.message)
        tool_calls.append(
            {
                "name": "search_knowledge",
                "arguments": {"query": request.message},
                "result": result,
            }
        )
        response_parts.append(result)

    if any(word in message for word in ["discount", "coupon", "promo"]) or re.search(
        r"\b(coupon\s+code|promo\s+code|discount\s+code)\b", message
    ):
        code_match = re.search(r"\b(SAVE\d+|FLAT\d+)\b", request.message, re.IGNORECASE)
        # Require at least one digit (avoid matching a lone "." as a number)
        amount_match = re.search(r"\$?(\d+(?:\.\d+)?|\.\d+)", request.message)

        code = code_match.group(1) if code_match else "SAVE10"
        amount = float(amount_match.group(1)) if amount_match else 100.0

        result = calculate_discount(amount, code)
        tool_calls.append(
            {
                "name": "calculate_discount",
                "arguments": {"subtotal": amount, "coupon_code": code},
                "result": result,
            }
        )
        if "error" in result:
            response_parts.append(result["error"])
        else:
            response_parts.append(
                f"Applied {code}: ${result['discount']} off. "
                f"Your total is ${result['total']}."
            )

    # Default response if no tools matched
    if not response_parts:
        response_parts.append(
            "I'm a customer support assistant. I can help you with "
            "order status, refund policies, shipping info, warranty details, "
            "and discount calculations. How can I help you today?"
        )

    return ChatResponse(
        response=" ".join(response_parts),
        tool_calls=tool_calls,
        usage={"input_tokens": len(request.message.split()) * 2, "output_tokens": 50},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
