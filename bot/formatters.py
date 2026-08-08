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
            return f"${v / 1000:.2f}k"
        return f"${v:.2f}"
    except (TypeError, ValueError):
        return "N/A"


def format_market_info(market: dict, orderbook: dict) -> str:
    title = market.get("title", "Unknown Market")
    slug = market.get("slug", "")
    end_date = market.get(
        "expirationDate",
        market.get("endDate", market.get("closeTime", "TBD")),
    )
    volume = market.get("volume", market.get("totalVolume", 0))
    liquidity = market.get("liquidity", 0)
    metadata = market.get("metadata") or {}
    categories = market.get("categories") or []
    trade_type = market.get("tradeType", "")

    yes_price = "N/A"
    no_price = "N/A"

    prices = market.get("prices", [])
    if isinstance(prices, list) and len(prices) >= 2:
        try:
            yp = float(prices[0])
            np = float(prices[1])
            if yp > 1:
                yp /= 100
                np /= 100
            yes_price = f"{yp:.3f}"
            no_price = f"{np:.3f}"
        except (TypeError, ValueError):
            pass

    if orderbook:
        asks = orderbook.get("asks") or []
        bids = orderbook.get("bids") or []
        if asks:
            try:
                yes_price = f"{float(asks[0].get('price', 0)):.3f}"
            except (TypeError, ValueError, IndexError):
                pass
        if bids:
            try:
                best_bid = float(bids[0].get("price", 0))
                no_price = f"{max(0.0, 1.0 - best_bid):.3f}"
            except (TypeError, ValueError, IndexError):
                pass

    trade_prices = market.get("tradePrices") or {}
    buy_market = (trade_prices.get("buy") or {}).get("market") or []
    if yes_price == "N/A" and len(buy_market) >= 2:
        try:
            yes_price = f"{float(buy_market[0]):.3f}"
            no_price = f"{float(buy_market[1]):.3f}"
        except (TypeError, ValueError):
            pass

    lines = [f"<b>{title}</b>", ""]

    home_team = metadata.get("homeTeam")
    away_team = metadata.get("awayTeam")
    if home_team and away_team:
        lines.append(f"<b>{home_team}</b> vs <b>{away_team}</b>")

    league = metadata.get("leagueNameFull") or metadata.get("leagueName")
    if league:
        lines.append(str(league))

    if categories:
        lines.append(" | ".join(str(c) for c in categories[:6]))

    lines.extend([
        f"<code>{slug}</code>",
        f"Closes: <b>{str(end_date)[:19]}</b>",
        f"Type: <b>{trade_type or 'n/a'}</b>",
        "",
        f"YES: <b>{yes_price}</b>",
        f"NO:  <b>{no_price}</b>",
        "",
        f"Volume:    {_usdc(volume)}",
        f"Liquidity: {_usdc(liquidity)}",
    ])
    return "\n".join(lines)


def format_orderbook(orderbook: dict, slug: str) -> str:
    asks = (orderbook.get("asks") or [])[:5]
    bids = (orderbook.get("bids") or [])[:5]

    lines = [f"<b>Orderbook</b>", f"<code>{slug}</code>", ""]
    lines.append("<b>ASKS</b>")
    lines.append("<code>Price    Size</code>")
    for ask in reversed(asks):
        p = float(ask.get("price", 0))
        s = float(ask.get("size", 0))
        lines.append(f"<code>{p:.3f}    {s:.2f}</code>")

    lines.append("----------------------")
    lines.append("<b>BIDS</b>")
    lines.append("<code>Price    Size</code>")
    for bid in bids:
        p = float(bid.get("price", 0))
        s = float(bid.get("size", 0))
        lines.append(f"<code>{p:.3f}    {s:.2f}</code>")

    return "\n".join(lines)


def format_portfolio(profile: dict, positions: Any, pnl: Any, points: Any) -> str:
    display_name = profile.get("displayName") or profile.get("name") or profile.get("username") or "—"
    wallet = profile.get("account") or profile.get("walletAddress") or "—"
    wallet_short = wallet[:6] + "..." + wallet[-4:] if len(wallet) > 12 else wallet

    pos_list = _normalize_positions(positions)
    total_value = 0.0
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

    total_points = 0
    if isinstance(points, dict):
        total_points = points.get("totalPoints", points.get("points", points.get("accumulativePoints", 0)))
    elif profile.get("points") is not None:
        total_points = profile.get("points")

    try:
        pnl_float = float(pnl_value or 0)
    except (TypeError, ValueError):
        pnl_float = 0.0
    pnl_icon = "+" if pnl_float >= 0 else ""

    scaled_value = total_value / 1e6 if total_value > 1000 else total_value

    lines = [
        "<b>Portfolio Overview</b>",
        "",
        f"Name:   <b>{display_name}</b>",
        f"Wallet: <code>{wallet_short}</code>",
        "",
        f"Value:    <b>{_usdc(scaled_value)}</b>",
        f"PnL:      <b>{pnl_icon}{_usdc(pnl_value)}</b>",
        f"Points:   <b>{int(float(total_points or 0)):,}</b>",
        "",
        f"Open Positions: <b>{len(pos_list)}</b>",
    ]
    return "\n".join(lines)


def _normalize_positions(positions: Any) -> list:
    if positions is None:
        return []
    if isinstance(positions, list):
        return positions
    if isinstance(positions, dict):
        if isinstance(positions.get("positions"), list):
            return positions["positions"]
        if isinstance(positions.get("clob"), list):
            return positions["clob"]
        if isinstance(positions.get("data"), list):
            return positions["data"]
        merged = []
        for key in ("clob", "amm", "positions", "data"):
            val = positions.get(key)
            if isinstance(val, list):
                merged.extend(val)
        if merged:
            return merged
    return []


def format_positions(positions: Any) -> str:
    pos_list = _normalize_positions(positions)
    if not pos_list:
        return "<b>Open Positions</b>\n\nNo open positions found."

    lines = ["<b>Open Positions</b>", ""]
    for pos in pos_list[:12]:
        market = pos.get("market") or {}
        slug = pos.get("marketSlug") or market.get("slug") or "unknown"
        title = market.get("title") or slug
        mv = float(pos.get("marketValue", pos.get("value", 0)) or 0)
        avg = float(pos.get("averageFillPrice", pos.get("avgPrice", 0)) or 0)
        cost = float(pos.get("costBasis", 0) or 0)
        balance = float(pos.get("ctfBalance", pos.get("balance", pos.get("size", 0))) or 0)
        outcome = pos.get("outcome") or pos.get("token") or ""

        pnl = mv - cost
        scaled_mv = mv / 1e6 if abs(mv) > 1e5 else mv
        scaled_cost = cost / 1e6 if abs(cost) > 1e5 else cost
        scaled_pnl = pnl / 1e6 if abs(pnl) > 1e5 else pnl
        scaled_bal = balance / 1e6 if abs(balance) > 1e5 else balance

        lines.extend([
            f"<b>{title[:48]}</b>",
            f"<code>{slug}</code>",
            f"Outcome: <b>{outcome or '—'}</b> | Avg: <b>{avg:.3f}</b> | Size: <b>{scaled_bal:.2f}</b>",
            f"Value: <b>{_usdc(scaled_mv)}</b> | PnL: <b>{_usdc(scaled_pnl)}</b>",
            "",
        ])

    return "\n".join(lines)


def format_history(history: Any) -> str:
    trades = []
    if isinstance(history, list):
        trades = history
    elif isinstance(history, dict):
        for key in ("trades", "history", "data", "items"):
            if isinstance(history.get(key), list):
                trades = history[key]
                break

    if not trades:
        return "<b>Trade History</b>\n\nNo trades found."

    lines = ["<b>Recent Trades</b>", ""]
    for trade in trades[:12]:
        market = trade.get("market") or {}
        slug = trade.get("marketSlug") or market.get("slug") or "—"
        side = trade.get("side", "—")
        try:
            price = float(trade.get("price", 0) or 0)
        except (TypeError, ValueError):
            price = 0.0
        try:
            size = float(trade.get("size", trade.get("contracts", 0)) or 0)
        except (TypeError, ValueError):
            size = 0.0
        ts = str(trade.get("createdAt", trade.get("timestamp", "—")))[:16]
        side_label = str(side).upper()
        lines.extend([
            f"<code>{slug}</code>",
            f"<b>{side_label}</b> {size:.2f} @ {price:.3f} — {ts}",
            "",
        ])

    return "\n".join(lines)


def format_order_result(result: dict, slug: str, outcome: str, order_type: str, side: str) -> str:
    order = result.get("order") if isinstance(result.get("order"), dict) else result
    execution = result.get("execution") if isinstance(result.get("execution"), dict) else {}

    order_id = order.get("id") or result.get("orderId") or result.get("id") or "—"
    status = (
        execution.get("settlementStatus")
        or order.get("status")
        or result.get("status")
        or "SUBMITTED"
    )
    matched = execution.get("matched")
    tx_hash = execution.get("txHash")
    reason = execution.get("reason")

    lines = [
        f"<b>Order {status}</b>",
        "",
        f"Market:  <code>{slug}</code>",
        f"Side:    <b>{side}</b> {outcome}",
        f"Type:    <b>{order_type}</b>",
        f"Order:   <code>{str(order_id)[:36]}</code>",
    ]
    if matched is not None:
        lines.append(f"Matched: <b>{'yes' if matched else 'no'}</b>")
    if reason:
        lines.append(f"Reason:  <b>{reason}</b>")
    if tx_hash:
        lines.append(f"Tx:      <code>{tx_hash[:18]}...</code>")

    return "\n".join(lines)
