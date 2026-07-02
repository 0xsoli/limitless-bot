from typing import Any


def _pct(value) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def _usdc(value) -> str:
    try:
        v = float(value)
        if abs(v) >= 1_000_000:
            v = v / 1_000_000
        elif abs(v) >= 1000:
            v = v / 1000
            return f"${v:.2f}k"
        return f"${v:.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _num(value, decimals: int = 2) -> str:
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def format_market_info(market: dict, orderbook: dict) -> str:
    title = market.get("title", "Unknown Market")
    slug = market.get("slug", "")
    market_type = market.get("type", "")
    end_date = market.get("endDate", market.get("closeTime", "TBD"))
    volume = market.get("volume", market.get("totalVolume", 0))
    liquidity = market.get("liquidity", 0)

    yes_price = "N/A"
    no_price = "N/A"

    if orderbook:
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        if asks:
            yes_price = f"{float(asks[0].get('price', 0)):.2f}" if asks else "N/A"
        if bids:
            no_price = f"{1 - float(bids[0].get('price', 0)):.2f}" if bids else "N/A"

    lines = [
        f"📊 <b>{title}</b>",
        f"",
        f"🔖 <code>{slug}</code>",
        f"📅 Closes: <b>{str(end_date)[:10]}</b>",
        f"",
        f"💵 YES Price:  <b>{yes_price}</b>",
        f"💵 NO Price:   <b>{no_price}</b>",
        f"",
        f"📦 Volume:     {_usdc(volume)}",
        f"💧 Liquidity:  {_usdc(liquidity)}",
    ]
    return "\n".join(lines)


def format_orderbook(orderbook: dict, slug: str) -> str:
    asks = orderbook.get("asks", [])[:5]
    bids = orderbook.get("bids", [])[:5]

    lines = [f"📖 <b>Orderbook — {slug}</b>", ""]
    lines.append("<b>     ASKS (YES sellers)</b>")
    lines.append("<code>  Price    Size</code>")
    for ask in reversed(asks):
        p = float(ask.get("price", 0))
        s = float(ask.get("size", 0))
        lines.append(f"<code>  {p:.3f}    {s:.1f}</code>")

    lines.append("─" * 22)

    lines.append("<b>     BIDS (YES buyers)</b>")
    lines.append("<code>  Price    Size</code>")
    for bid in bids:
        p = float(bid.get("price", 0))
        s = float(bid.get("size", 0))
        lines.append(f"<code>  {p:.3f}    {s:.1f}</code>")

    return "\n".join(lines)


def format_portfolio(profile: dict, positions: dict, pnl: dict, points: dict) -> str:
    display_name = profile.get("displayName", profile.get("name", "—"))
    wallet = profile.get("account", profile.get("walletAddress", "—"))
    wallet_short = wallet[:6] + "…" + wallet[-4:] if len(wallet) > 12 else wallet

    total_value = 0
    pos_list = positions if isinstance(positions, list) else positions.get("positions", [])
    for p in pos_list:
        mv = p.get("marketValue", p.get("value", 0))
        try:
            total_value += float(mv)
        except (TypeError, ValueError):
            pass

    pnl_value = 0
    pnl_data = pnl.get("data", pnl) if isinstance(pnl, dict) else {}
    if isinstance(pnl_data, list) and pnl_data:
        last = pnl_data[-1]
        pnl_value = last.get("pnl", last.get("value", 0))
    elif isinstance(pnl_data, dict):
        pnl_value = pnl_data.get("totalPnl", pnl_data.get("pnl", 0))

    total_points = points.get("totalPoints", points.get("points", 0)) if isinstance(points, dict) else 0

    pnl_icon = "🟢" if float(pnl_value or 0) >= 0 else "🔴"

    lines = [
        "💼 <b>Portfolio Overview</b>",
        "",
        f"👤 Name:    <b>{display_name}</b>",
        f"🔑 Wallet:  <code>{wallet_short}</code>",
        "",
        f"💰 Portfolio Value:  <b>{_usdc(total_value / 1e6 if total_value > 1000 else total_value)}</b>",
        f"{pnl_icon} Total PnL:         <b>{_usdc(pnl_value)}</b>",
        f"⭐ Points:           <b>{int(total_points):,}</b>",
        "",
        f"📈 Open Positions: <b>{len(pos_list)}</b>",
    ]
    return "\n".join(lines)


def format_positions(positions: Any) -> str:
    pos_list = positions if isinstance(positions, list) else positions.get("positions", [])

    if not pos_list:
        return "📈 <b>Open Positions</b>\n\nNo open positions found."

    lines = ["📈 <b>Open Positions</b>", ""]
    for pos in pos_list[:10]:
        slug = pos.get("marketSlug", pos.get("market", {}).get("slug", "unknown"))
        token = pos.get("tokenId", "")
        mv = float(pos.get("marketValue", pos.get("value", 0)))
        avg = float(pos.get("averageFillPrice", pos.get("avgPrice", 0)))
        cost = float(pos.get("costBasis", 0))
        balance = float(pos.get("ctfBalance", pos.get("balance", 0)))

        pnl = mv - cost
        pnl_icon = "🟢" if pnl >= 0 else "🔴"
        scaled_mv = mv / 1e6 if mv > 1e5 else mv
        scaled_cost = cost / 1e6 if cost > 1e5 else cost
        scaled_pnl = pnl / 1e6 if abs(pnl) > 1e5 else pnl

        lines.extend([
            f"📌 <code>{slug}</code>",
            f"   Avg: <b>{avg:.3f}</b>  |  Bal: <b>{balance / 1e6 if balance > 1e5 else balance:.2f}</b>",
            f"   Value: <b>{_usdc(scaled_mv)}</b>  {pnl_icon} PnL: <b>{_usdc(scaled_pnl)}</b>",
            "",
        ])

    return "\n".join(lines)


def format_history(history: Any) -> str:
    trades = history if isinstance(history, list) else history.get("trades", history.get("history", []))

    if not trades:
        return "📜 <b>Trade History</b>\n\nNo trades found."

    lines = ["📜 <b>Recent Trades</b>", ""]
    for trade in trades[:10]:
        slug = trade.get("marketSlug", trade.get("market", {}).get("slug", "—"))
        side = trade.get("side", "—")
        price = float(trade.get("price", 0))
        size = float(trade.get("size", 0))
        ts = str(trade.get("createdAt", trade.get("timestamp", "—")))[:16]
        outcome = trade.get("outcome", trade.get("tokenId", ""))

        side_icon = "🟢" if side == "BUY" else "🔴"
        lines.extend([
            f"{side_icon} <code>{slug}</code>",
            f"   <b>{side}</b> {size:.2f} @ {price:.3f}  —  {ts}",
            "",
        ])

    return "\n".join(lines)


def format_order_result(result: dict, slug: str, outcome: str, order_type: str) -> str:
    order = result.get("order", {})
    execution = result.get("execution", {})
    order_id = order.get("id", result.get("orderId", result.get("id", "—")))
    status = execution.get("settlementStatus", result.get("status", "SUBMITTED"))
    reason = execution.get("reason", "")
    matched = execution.get("matched", False)
    matches = result.get("makerMatches", result.get("fills", []))

    failed_statuses = {"FAILED", "ERROR", "CANCELED"}
    icon = "✅" if status not in failed_statuses else "❌"

    lines = [
        f"{icon} <b>Order {status}</b>",
        "",
        f"Market:   <code>{slug}</code>",
        f"Outcome:  <b>{outcome}</b>",
        f"Type:     <b>{order_type}</b>",
        f"Order ID: <code>{str(order_id)[:36]}</code>",
    ]

    if matched or matches:
        lines.append(f"Matched:  <b>{'Yes' if matched else len(matches)}</b>")
    if reason:
        lines.append(f"Reason:   <b>{reason}</b>")

    eligible_at = execution.get("eligibleAt")
    if status == "DELAYED" and eligible_at:
        lines.append(f"Eligible: <b>{eligible_at[:19]}</b>")

    tx_hash = execution.get("txHash")
    if tx_hash:
        lines.append(f"Tx:       <code>{tx_hash[:18]}…</code>")

    return "\n".join(lines)


def format_pnl(pnl_data: Any) -> str:
    data = pnl_data.get("data", []) if isinstance(pnl_data, dict) else []
    if not data:
        return "📊 <b>PnL Chart</b>\n\nNo data available."
    last = data[-1] if data else {}
    total = last.get("pnl", last.get("value", 0))
    icon = "🟢" if float(total or 0) >= 0 else "🔴"
    return f"📊 <b>PnL Summary</b>\n\n{icon} Total PnL: <b>{_usdc(total)}</b>\nData points: <b>{len(data)}</b>"
