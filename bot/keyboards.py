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
        [InlineKeyboardButton("◀️ Back", callback_data="menu_main")],
    ])


def market_list_keyboard(markets: list) -> InlineKeyboardMarkup:
    buttons = []
    for market in markets[:15]:
        slug = market.get("slug", "")
        title = market.get("title", slug)
        label = title[:32] + "…" if len(title) > 32 else title
        buttons.append([InlineKeyboardButton(label, callback_data=f"market_{slug}")])
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data="menu_market")])
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
