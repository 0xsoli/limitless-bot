from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Markets", callback_data="menu_market"),
            InlineKeyboardButton("💼 Portfolio", callback_data="menu_portfolio"),
        ],
        [
            InlineKeyboardButton("📈 Positions", callback_data="menu_positions"),
            InlineKeyboardButton("📜 History", callback_data="menu_history"),
        ],
    ])


def timeframe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ 5 Minutes", callback_data="tf_5m"),
            InlineKeyboardButton("🕒 15 Minutes", callback_data="tf_15m"),
        ],
        [
            InlineKeyboardButton("📅 Hourly", callback_data="tf_1h"),
            InlineKeyboardButton("🗓 Daily", callback_data="tf_1d"),
        ],
        [InlineKeyboardButton("⚽ Football", callback_data="tf_football")],
        [InlineKeyboardButton("◀️ Back", callback_data="menu_main")],
    ])


def football_league_keyboard(options: list) -> InlineKeyboardMarkup:
    buttons = []
    priority = {
        "fifa-world-cup": 0,
        "matches": 1,
        "props": 2,
        "player-props": 3,
        "england-premier-league": 4,
        "uefa-champions-league": 5,
        "off-the-pitch": 6,
    }
    sorted_options = sorted(
        options,
        key=lambda o: (priority.get(o.get("value", ""), 99), -o.get("count", 0)),
    )
    for option in sorted_options[:10]:
        count = option.get("count", 0)
        if count <= 0:
            continue
        label = option.get("label", option.get("value", "Football"))
        if count:
            label = f"{label} ({count})"
        if len(label) > 40:
            label = label[:37] + "…"
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"fb_{option['value']}")
        ])
    buttons.append([InlineKeyboardButton("🌍 All Football", callback_data="fb_all")])
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data="menu_market")])
    return InlineKeyboardMarkup(buttons)


def market_list_keyboard(
    markets: list,
    back_callback: str = "menu_market",
    page: int = 1,
    total_pages: int = 1,
    page_callback_prefix: str = "",
) -> InlineKeyboardMarkup:
    buttons = []
    for market in markets[:15]:
        slug = market.get("slug", "")
        title = market.get("title", slug)
        label = title[:32] + "…" if len(title) > 32 else title
        if market.get("marketType") == "group" and market.get("markets"):
            buttons.append([InlineKeyboardButton(f"⚽ {label}", callback_data=f"fbgroup_{slug}")])
        else:
            buttons.append([InlineKeyboardButton(label, callback_data=f"market_{slug}")])
    if total_pages > 1 and page_callback_prefix:
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"{page_callback_prefix}{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"{page_callback_prefix}{page + 1}"))
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data=back_callback)])
    return InlineKeyboardMarkup(buttons)


def football_group_keyboard(group_market: dict, back_callback: str) -> InlineKeyboardMarkup:
    buttons = []
    parent_title = group_market.get("title", "Match")
    for sub_market in group_market.get("markets", [])[:8]:
        slug = sub_market.get("slug", "")
        title = sub_market.get("title", slug)
        label = f"{title}"
        if len(label) > 34:
            label = label[:31] + "…"
        buttons.append([InlineKeyboardButton(label, callback_data=f"market_{slug}")])
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data=back_callback)])
    return InlineKeyboardMarkup(buttons)


def order_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📌 GTC (Limit)", callback_data="ordertype_GTC"),
            InlineKeyboardButton("⚡ FAK (Fill & Kill)", callback_data="ordertype_FAK"),
        ],
        [InlineKeyboardButton("🎯 FOK (Market)", callback_data="ordertype_FOK")],
        [InlineKeyboardButton("◀️ Back", callback_data="menu_main")],
    ])


def side_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 YES", callback_data="side_YES"),
            InlineKeyboardButton("🔴 NO", callback_data="side_NO"),
        ],
        [InlineKeyboardButton("◀️ Back", callback_data="menu_main")],
    ])


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_order"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_order"),
        ],
    ])


def portfolio_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Positions", callback_data="menu_positions"),
            InlineKeyboardButton("📜 History", callback_data="menu_history"),
        ],
        [InlineKeyboardButton("🚫 Cancel All Orders", callback_data="cancel_all_orders")],
        [InlineKeyboardButton("◀️ Back", callback_data="menu_main")],
    ])


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Back to Menu", callback_data="menu_main")],
    ])
