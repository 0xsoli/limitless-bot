"""
Limitless API authentication — HMAC-SHA256 request signing.

Official docs: https://docs.limitless.exchange/developers/authentication

HMAC authenticates every HTTP request to api.limitless.exchange using headers:
  lmts-api-key, lmts-timestamp, lmts-signature

Canonical message:
  {ISO-8601 timestamp}\\n{HTTP METHOD}\\n{path+query}\\n{body}

IMPORTANT: HMAC is NOT a replacement for EIP-712 order signing.
Per the same documentation:
  "Your private key is still required for EIP-712 order signing
   (unless using delegated signing), but the scoped token handles
   request authentication."

So placing an order requires BOTH:
  1. HMAC headers on POST /orders  (this module)
  2. EIP-712 signature inside the order object (order_signer.py)
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional

WS_AUTH_PATH = "/socket.io/?EIO=4&transport=websocket"


def serialize_body(body: Optional[dict]) -> str:
    """Serialize request body exactly as sent on the wire (for HMAC signing)."""
    if not body:
        return ""
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False)


def sign_request(
    token_id: str,
    secret_b64: str,
    method: str,
    path_with_query: str,
    body: str = "",
) -> dict:
    """
    Build HMAC auth headers for a Limitless API request.
    Matches the Python example in the official authentication docs.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    message = f"{timestamp}\n{method.upper()}\n{path_with_query}\n{body}"
    signature = base64.b64encode(
        hmac.new(
            base64.b64decode(secret_b64),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return {
        "lmts-api-key": token_id,
        "lmts-timestamp": timestamp,
        "lmts-signature": signature,
    }


def sign_websocket_handshake(token_id: str, secret_b64: str) -> dict:
    """HMAC headers for the Socket.IO WebSocket handshake."""
    return sign_request(token_id, secret_b64, "GET", WS_AUTH_PATH, "")