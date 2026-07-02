import secrets
import time
from typing import Optional

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import to_checksum_address

CHAIN_ID = 8453
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
SCALE = 1_000_000

# EIP-712 Order type — matches https://docs.limitless.exchange/developers/eip712-signing
ORDER_MESSAGE_TYPES = {
    "Order": [
        {"name": "salt", "type": "uint256"},
        {"name": "maker", "type": "address"},
        {"name": "signer", "type": "address"},
        {"name": "taker", "type": "address"},
        {"name": "tokenId", "type": "uint256"},
        {"name": "makerAmount", "type": "uint256"},
        {"name": "takerAmount", "type": "uint256"},
        {"name": "expiration", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
        {"name": "feeRateBps", "type": "uint256"},
        {"name": "side", "type": "uint8"},
        {"name": "signatureType", "type": "uint8"},
    ],
}


def _checksum(address: str) -> str:
    return to_checksum_address(address)


def _generate_salt() -> int:
    return secrets.randbits(64) ^ int(time.time() * 1_000_000)


def calculate_amounts(
    *,
    side: int,
    order_type: str,
    price: Optional[float] = None,
    size: Optional[float] = None,
    usdc_amount: Optional[float] = None,
) -> tuple[int, int, Optional[float]]:
    if order_type == "FOK":
        if side == 0:
            if usdc_amount is None or usdc_amount <= 0:
                raise ValueError("FOK buy orders require a positive USDC amount")
            return int(usdc_amount * SCALE), 1, None
        if size is None or size <= 0:
            raise ValueError("FOK sell orders require a positive share size")
        return int(size * SCALE), 1, None

    if price is None or size is None:
        raise ValueError(f"{order_type} orders require price and size")
    if not (0.01 <= price <= 0.99):
        raise ValueError("Price must be between 0.01 and 0.99")
    if size <= 0:
        raise ValueError("Size must be positive")

    if side == 0:
        maker_amount = int(price * size * SCALE)
        taker_amount = int(size * SCALE)
    else:
        maker_amount = int(size * SCALE)
        taker_amount = int(price * size * SCALE)

    return maker_amount, taker_amount, price


def sign_order(order_data: dict, verifying_contract: str, private_key: str) -> str:
    """Sign order with EIP-712 using venue.exchange as verifyingContract."""
    domain = {
        "name": "Limitless CTF Exchange",
        "version": "1",
        "chainId": CHAIN_ID,
        "verifyingContract": _checksum(verifying_contract),
    }
    message = {
        "salt": int(order_data["salt"]),
        "maker": _checksum(order_data["maker"]),
        "signer": _checksum(order_data["signer"]),
        "taker": _checksum(order_data["taker"]),
        "tokenId": int(order_data["tokenId"]),
        "makerAmount": int(order_data["makerAmount"]),
        "takerAmount": int(order_data["takerAmount"]),
        "expiration": int(order_data["expiration"]),
        "nonce": int(order_data["nonce"]),
        "feeRateBps": int(order_data["feeRateBps"]),
        "side": int(order_data["side"]),
        "signatureType": int(order_data["signatureType"]),
    }

    # eth-account 0.11+ requires keyword arguments — a bare dict is treated as
    # domain_data and raises "Invalid domain key: types".
    encoded = encode_typed_data(
        domain_data=domain,
        message_types=ORDER_MESSAGE_TYPES,
        message_data=message,
    )
    signed = Account.sign_message(encoded, private_key=private_key)
    signature = signed.signature.hex()
    if not signature.startswith("0x"):
        signature = f"0x{signature}"
    return signature


def build_signed_order(
    *,
    private_key: str,
    token_id: str,
    verifying_contract: str,
    side: int,
    order_type: str,
    fee_rate_bps: int,
    price: Optional[float] = None,
    size: Optional[float] = None,
    usdc_amount: Optional[float] = None,
) -> dict:
    account = Account.from_key(private_key)
    maker = _checksum(account.address)
    maker_amount, taker_amount, limit_price = calculate_amounts(
        side=side,
        order_type=order_type,
        price=price,
        size=size,
        usdc_amount=usdc_amount,
    )

    salt = _generate_salt()
    order_data = {
        "salt": salt,
        "maker": maker,
        "signer": maker,
        "taker": ZERO_ADDRESS,
        "tokenId": str(token_id),
        "makerAmount": maker_amount,
        "takerAmount": taker_amount,
        "expiration": 0,
        "nonce": 0,
        "feeRateBps": fee_rate_bps,
        "side": side,
        "signatureType": 0,
    }
    signature = sign_order(order_data, verifying_contract, private_key)

    signed_order = {
        **order_data,
        "salt": str(salt),
        "expiration": "0",
        "signature": signature,
        "signatureType": 0,
    }
    if limit_price is not None:
        signed_order["price"] = limit_price

    return signed_order
