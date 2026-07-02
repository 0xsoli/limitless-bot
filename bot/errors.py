from typing import Union

from .limitless_client import LimitlessAPIError


def _truncate(text: str, limit: int = 500) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def format_api_error(
    error: Union[LimitlessAPIError, Exception],
    *,
    action: str = "complete the request",
) -> str:
    if isinstance(error, LimitlessAPIError):
        return _format_limitless_api_error(error, action=action)
    return _format_generic_error(error, action=action)


def _format_limitless_api_error(error: LimitlessAPIError, *, action: str) -> str:
    status = error.status
    raw = _truncate(error.message)
    lower = raw.lower()

    if status in (0, 408) or "timed out" in lower or "timeout" in lower:
        return (
            "❌ <b>Request timed out</b>\n\n"
            f"The bot could not {action} in time.\n"
            "Check connectivity to <code>api.limitless.exchange</code> and try again."
        )

    if status == 401:
        return (
            "❌ <b>Authentication failed</b>\n\n"
            "Your Limitless API token is invalid, expired, or revoked.\n\n"
            "• Derive a new token at limitless.exchange → Profile → API Tokens\n"
            "• Re-run <code>sudo bash install.sh --reconfigure</code>"
        )

    if status == 403:
        return (
            "❌ <b>Access denied</b>\n\n"
            "The API rejected this request. Your token may lack the <b>trading</b> scope "
            "or access may be restricted in your region."
        )

    if status == 425:
        return (
            "❌ <b>Order timestamp expired</b>\n\n"
            "The order was rejected because the server clock drifted too far.\n"
            "Sync server time with NTP and try again."
        )

    if status == 429:
        return (
            "❌ <b>Rate limited</b>\n\n"
            "Too many API requests. Wait a few seconds and try again."
        )

    if status == 503:
        return (
            "❌ <b>Trading temporarily unavailable</b>\n\n"
            f"{_escape_html(raw)}\n\n"
            "Limitless is in maintenance mode. Try again later."
        )

    if status == 409:
        return (
            "❌ <b>Duplicate order</b>\n\n"
            "This order was already submitted. Check your open orders or portfolio."
        )

    if status == 400:
        hint = _hint_for_bad_request(lower, raw)
        return f"❌ <b>Order rejected</b>\n\n{hint}"

    return (
        f"❌ <b>Could not {action}</b>\n\n"
        f"API error <b>{status}</b>:\n<code>{_escape_html(raw)}</code>"
    )


def _hint_for_bad_request(lower: str, raw: str) -> str:
    if any(k in lower for k in ("insufficient balance", "not enough balance", "balance")):
        return (
            "<b>Insufficient USDC balance.</b>\n\n"
            "Deposit more USDC to your trading wallet on Base, then retry."
        )

    if any(k in lower for k in ("allowance", "approval", "not approved")):
        return (
            "<b>USDC not approved for trading.</b>\n\n"
            "Approve USDC for the market exchange contract on limitless.exchange, then retry.\n"
            "For BUY orders, approve USDC → <code>venue.exchange</code>."
        )

    if any(k in lower for k in ("profile id", "owner", "does not match")):
        return (
            "<b>Wallet does not match your API account.</b>\n\n"
            "The private key in your bot config must belong to the same wallet "
            "that derived the Limitless API token.\n\n"
            "Reconfigure with <code>sudo bash install.sh --reconfigure</code>."
        )

    if any(k in lower for k in ("signature", "invalid order", "eip-712", "eip712")):
        return (
            "<b>Invalid order signature.</b>\n\n"
            "The signed order was rejected. Ensure your wallet private key is correct "
            "and matches the API token account."
        )

    if any(k in lower for k in ("deadline", "expired", "resolved", "locked")):
        return (
            "<b>Market is not open for trading.</b>\n\n"
            "This market may be resolved, locked, or past its deadline."
        )

    if any(k in lower for k in ("price", "amount", "size")):
        return (
            "<b>Invalid order parameters.</b>\n\n"
            f"<code>{_escape_html(_truncate(raw, 300))}</code>"
        )

    return f"<code>{_escape_html(_truncate(raw, 300))}</code>"


def _format_generic_error(error: Exception, *, action: str) -> str:
    message = str(error).strip() or error.__class__.__name__

    if isinstance(error, TimeoutError):
        return (
            "❌ <b>Request timed out</b>\n\n"
            f"The bot could not {action} within the time limit.\n"
            "Check server connectivity to api.limitless.exchange and try again."
        )

    lower = message.lower()

    if "wallet" in lower and "match" in lower:
        return f"❌ <b>Configuration error</b>\n\n{_escape_html(message)}"

    if "private key" in lower:
        return (
            "❌ <b>Missing wallet private key</b>\n\n"
            "Add your wallet private key via <code>sudo bash install.sh --reconfigure</code>."
        )

    if "venue.exchange" in lower or "clob" in lower:
        return f"❌ <b>Market not tradeable</b>\n\n{_escape_html(message)}"

    if "token id" in lower:
        return f"❌ <b>Market data error</b>\n\n{_escape_html(message)}"

    if "profile id" in lower:
        return (
            "❌ <b>Profile not found</b>\n\n"
            "Could not load your Limitless profile. Verify the API token belongs to an active account."
        )

    return (
        f"❌ <b>Could not {action}</b>\n\n"
        f"<code>{_escape_html(_truncate(message, 300))}</code>"
    )


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def reply_error(
    update,
    query,
    error: Exception,
    *,
    action: str = "complete the request",
    reply_markup=None,
) -> None:
    from .keyboards import back_keyboard

    text = format_api_error(error, action=action)
    markup = reply_markup or back_keyboard()

    if query:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
    elif update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)
