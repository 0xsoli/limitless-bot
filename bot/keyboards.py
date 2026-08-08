from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Markets", callback_data="menu_market"),
            InlineKeyboardButton("Portfolio", callback_data="menu_portfolio"),
        ],
        [
            InlineKeyboardButton("Positions", callback_data="menu_positions"),
            InlineKeyboardButton("History", callback_data="menu_history"),
        ],
    ])


def categories_keyboard(categories: list) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for cat in categories:
        name = cat.get("name") or cat.get("slug") or "Market"
        count = cat.get("count")
        label = f"{name} ({count})" if count is not None else name
        if len(label) > 28:
            label = label[:25] + "..."
        slug = cat.get("slug") or ""
        row.append(InlineKeyboardButton(label, callback_data=f"cat_{slug}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("All Markets", callback_data="cat_all")])
    buttons.append([InlineKeyboardButton("Back", callback_data="menu_main")])
    return InlineKeyboardMarkup(buttons)


def filters_keyboard(options: list, back_callback: str = "menu_market") -> InlineKeyboardMarkup:
    buttons = []
    for idx, option in enumerate(options[:20]):
        label = option.get("label") or option.get("value") or "Filter"
        count = option.get("count")
        if count is not None:
            label = f"{label} ({count})"
        if len(label) > 40:
            label = label[:37] + "..."
        buttons.append([InlineKeyboardButton(label, callback_data=f"filt_{idx}")])
    buttons.append([InlineKeyboardButton("Show All", callback_data="filt_all")])
    buttons.append([InlineKeyboardButton("Back", callback_data=back_callback)])
    return InlineKeyboardMarkup(buttons)


def market_list_keyboard(
    markets: list,
    back_callback: str = "menu_market",
    page: int = 1,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    buttons = []
    for idx, market in enumerate(markets[:15]):
        title = market.get("title") or market.get("slug") or "Market"
        label = title[:34] + "..." if len(title) > 34 else title
        if market.get("marketType") == "group" or market.get("markets"):
            buttons.append([InlineKeyboardButton(f"[G] {label}", callback_data=f"grp_{idx}")])
        else:
            buttons.append([InlineKeyboardButton(label, callback_data=f"mkt_{idx}")])
    if total_pages > 1:
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton("Prev", callback_data=f"mp_{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav.append(InlineKeyboardButton("Next", callback_data=f"mp_{page + 1}"))
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("Back", callback_data=back_callback)])
    return InlineKeyboardMarkup(buttons)


def group_markets_keyboard(group_market: dict, back_callback: str) -> InlineKeyboardMarkup:
    buttons = []
    for idx, sub_market in enumerate((group_market.get("markets") or [])[:12]):
        title = sub_market.get("title") or sub_market.get("slug") or "Outcome"
        label = title[:36] + "..." if len(title) > 36 else title
        buttons.append([InlineKeyboardButton(label, callback_data=f"sub_{idx}")])
    buttons.append([InlineKeyboardButton("Back", callback_data=back_callback)])
    return InlineKeyboardMarkup(buttons)


def market_actions_keyboard(back_callback: str = "menu_market") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Buy YES", callback_data="trade_BUY_YES"),
            InlineKeyboardButton("Buy NO", callback_data="trade_BUY_NO"),
        ],
        [
            InlineKeyboardButton("Sell YES", callback_data="trade_SELL_YES"),
            InlineKeyboardButton("Sell NO", callback_data="trade_SELL_NO"),
        ],
        [InlineKeyboardButton("Orderbook", callback_data="orderbook")],
        [InlineKeyboardButton("Back", callback_data=back_callback)],
    ])


def order_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("GTC (Limit)", callback_data="ordertype_GTC"),
            InlineKeyboardButton("FAK (Fill & Kill)", callback_data="ordertype_FAK"),
        ],
        [InlineKeyboardButton("FOK (Market)", callback_data="ordertype_FOK")],
        [InlineKeyboardButton("Back", callback_data="menu_main")],
    ])


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Confirm", callback_data="confirm_order"),
            InlineKeyboardButton("Cancel", callback_data="cancel_order"),
        ],
    ])


def portfolio_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Positions", callback_data="menu_positions"),
            InlineKeyboardButton("History", callback_data="menu_history"),
        ],
        [InlineKeyboardButton("Cancel All Orders", callback_data="cancel_all_orders")],
        [InlineKeyboardButton("Back", callback_data="menu_main")],
    ])


def back_keyboard(callback: str = "menu_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Back", callback_data=callback)],
    ])
