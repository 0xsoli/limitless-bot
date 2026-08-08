import logging
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .formatters import (
    format_history,
    format_market_info,
    format_order_result,
    format_orderbook,
    format_portfolio,
    format_positions,
)
from .keyboards import (
    back_keyboard,
    categories_keyboard,
    confirm_keyboard,
    filters_keyboard,
    group_markets_keyboard,
    main_menu_keyboard,
    market_actions_keyboard,
    market_list_keyboard,
    order_type_keyboard,
    portfolio_keyboard,
)

logger = logging.getLogger(__name__)


def get_client(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["client"]


def is_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    allowed_id = str(context.application.bot_data["config"].get("chat_id", "")).strip()
    if not allowed_id:
        return False
    user_id = str(update.effective_user.id) if update.effective_user else ""
    return user_id == allowed_id


async def reject(update: Update) -> None:
    logger.warning(
        "Unauthorized access attempt from user_id=%s",
        update.effective_user.id if update.effective_user else "unknown",
    )
    if update.message:
        await update.message.reply_text("You are not authorized to use this bot.")
    elif update.callback_query:
        await update.callback_query.answer("Unauthorized.", show_alert=True)


def get_session(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> dict:
    sessions = context.application.bot_data.setdefault("user_sessions", {})
    if user_id not in sessions:
        sessions[user_id] = {}
    return sessions[user_id]


def _back_to_markets(session: dict) -> str:
    if session.get("page_id"):
        return "reload_markets"
    if session.get("category_slug"):
        return f"cat_{session['category_slug']}"
    return "menu_market"


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return
    user = update.effective_user
    text = (
        f"Welcome, <b>{user.first_name}</b>!\n\n"
        "<b>Limitless Exchange Trading Bot</b>\n\n"
        "Browse every active market category, place buy and sell orders, "
        "and manage your portfolio from Telegram.\n\n"
        "Your keys stay on this server."
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(),
    )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return
    await update.message.reply_text(
        "<b>Main Menu</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(),
    )


async def market_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return
    await _show_categories(update, context, edit=False)


async def order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return
    user_id = update.effective_user.id
    session = get_session(context, user_id)
    if not session.get("selected_market"):
        await update.message.reply_text(
            "Select a market first from the Markets menu.",
            reply_markup=back_keyboard(),
        )
        return
    await _show_order_type(update, context, edit=False)


async def portfolio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return
    msg = await update.message.reply_text("Loading portfolio...")
    try:
        text = await _load_portfolio_text(context)
        await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
    except Exception as e:
        logger.error("Portfolio error: %s", e)
        await msg.edit_text(f"Failed to load portfolio: {str(e)[:180]}", reply_markup=back_keyboard())


async def _load_portfolio_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    client = get_client(context)
    try:
        profile = await client.get_profile_me()
    except Exception:
        profile = {}
        if client.address:
            try:
                profile = await client.get_profile(client.address)
            except Exception:
                profile = {}
    positions = await client.get_portfolio_positions()
    pnl = await client.get_pnl_chart()
    points = await client.get_points()
    return format_portfolio(profile, positions, pnl, points)


async def _show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = True):
    client = get_client(context)
    query = update.callback_query if edit else None
    if query:
        await query.edit_message_text("Loading categories...")
    try:
        categories = await client.get_navigation()
        if not isinstance(categories, list):
            categories = []
        text = (
            "<b>Market Categories</b>\n\n"
            "Select a category to browse all active Limitless markets."
        )
        markup = categories_keyboard(categories)
        if query:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception as e:
        logger.error("Categories error: %s", e)
        err = f"Failed to load categories: {str(e)[:180]}"
        if query:
            await query.edit_message_text(err, reply_markup=back_keyboard())
        else:
            await update.message.reply_text(err, reply_markup=back_keyboard())


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return

    query = update.callback_query
    await query.answer()
    data = query.data or ""
    user_id = update.effective_user.id
    session = get_session(context, user_id)
    client = get_client(context)

    if data == "menu_main":
        await query.edit_message_text(
            "<b>Main Menu</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(),
        )
        return

    if data == "menu_market":
        await _show_categories(update, context, edit=True)
        return

    if data == "menu_portfolio":
        await query.edit_message_text("Loading portfolio...")
        try:
            text = await _load_portfolio_text(context)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
        except Exception as e:
            logger.error("Portfolio callback error: %s", e)
            await query.edit_message_text(
                f"Failed to load portfolio: {str(e)[:180]}",
                reply_markup=back_keyboard(),
            )
        return

    if data == "menu_positions":
        await query.edit_message_text("Loading positions...")
        try:
            positions = await client.get_portfolio_positions()
            text = format_positions(positions)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
        except Exception as e:
            logger.error("Positions error: %s", e)
            await query.edit_message_text(
                f"Failed to load positions: {str(e)[:180]}",
                reply_markup=back_keyboard(),
            )
        return

    if data == "menu_history":
        await query.edit_message_text("Loading trade history...")
        try:
            history = await client.get_portfolio_history()
            text = format_history(history)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
        except Exception as e:
            logger.error("History error: %s", e)
            await query.edit_message_text(
                f"Failed to load history: {str(e)[:180]}",
                reply_markup=back_keyboard(),
            )
        return

    if data == "noop":
        return

    if data == "back":
        await query.edit_message_text(
            "<b>Main Menu</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(),
        )
        return

    if data.startswith("cat_"):
        slug = data[4:]
        await _open_category(query, context, session, slug)
        return

    if data.startswith("filt_"):
        await _apply_filter(query, context, session, data[5:])
        return

    if data == "reload_markets":
        await _load_markets_page(query, context, session, session.get("market_page", 1))
        return

    if data.startswith("mp_"):
        page = int(data[3:])
        await _load_markets_page(query, context, session, page)
        return

    if data.startswith("mkt_"):
        idx = int(data[4:])
        markets = session.get("market_list") or []
        if idx < 0 or idx >= len(markets):
            await query.edit_message_text("Market expired from list. Please browse again.", reply_markup=back_keyboard("menu_market"))
            return
        market = markets[idx]
        await _open_market(query, context, session, market.get("slug", ""))
        return

    if data.startswith("grp_"):
        idx = int(data[4:])
        markets = session.get("market_list") or []
        if idx < 0 or idx >= len(markets):
            await query.edit_message_text("Group expired from list. Please browse again.", reply_markup=back_keyboard("menu_market"))
            return
        market = markets[idx]
        await _open_group(query, context, session, market.get("slug", ""))
        return

    if data.startswith("sub_"):
        idx = int(data[4:])
        group = session.get("group_data") or {}
        submarkets = group.get("markets") or []
        if idx < 0 or idx >= len(submarkets):
            await query.edit_message_text("Outcome expired. Please open the group again.", reply_markup=back_keyboard("menu_market"))
            return
        await _open_market(query, context, session, submarkets[idx].get("slug", ""))
        return

    if data == "orderbook":
        slug = session.get("selected_market")
        if not slug:
            await query.edit_message_text("No market selected.", reply_markup=back_keyboard("menu_market"))
            return
        await query.edit_message_text("Loading orderbook...")
        try:
            orderbook = await client.get_orderbook(slug)
            text = format_orderbook(orderbook, slug)
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=market_actions_keyboard(_back_to_markets(session)),
            )
        except Exception as e:
            logger.error("Orderbook error: %s", e)
            await query.edit_message_text(f"Failed to load orderbook: {str(e)[:180]}", reply_markup=back_keyboard())
        return

    if data.startswith("trade_"):
        parts = data.split("_")
        if len(parts) < 3:
            await query.edit_message_text("Invalid trade action.", reply_markup=back_keyboard())
            return
        session["trade_side"] = parts[1].upper()
        session["trade_outcome"] = parts[2].upper()
        await _show_order_type(update, context, edit=True)
        return

    if data.startswith("ordertype_"):
        order_type = data[10:].upper()
        session["order_type"] = order_type
        slug = session.get("selected_market", "")
        outcome = session.get("trade_outcome", "YES")
        side = session.get("trade_side", "BUY")
        if order_type == "FOK":
            session["awaiting_input"] = "maker_amount"
            amount_label = "USDC amount to spend" if side == "BUY" else "number of shares to sell"
            await query.edit_message_text(
                f"<b>Market Order (FOK)</b>\n\n"
                f"Market: <code>{slug}</code>\n"
                f"Side: <b>{side} {outcome}</b>\n\n"
                f"Enter the {amount_label} (e.g. <code>10</code>):",
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard("menu_market"),
            )
        else:
            session["awaiting_input"] = "price"
            await query.edit_message_text(
                f"<b>{order_type} Order</b>\n\n"
                f"Market: <code>{slug}</code>\n"
                f"Side: <b>{side} {outcome}</b>\n\n"
                f"Enter the price (0.01 – 0.99):",
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard("menu_market"),
            )
        return

    if data == "confirm_order":
        await _execute_order(update, context, query=query)
        return

    if data == "cancel_order":
        session.pop("pending_order", None)
        session.pop("awaiting_input", None)
        await query.edit_message_text("Order cancelled.", reply_markup=main_menu_keyboard())
        return

    if data.startswith("cancel_order_id_"):
        order_id = data[16:]
        await query.edit_message_text("Cancelling order...")
        try:
            await client.cancel_order(order_id)
            await query.edit_message_text("Order cancelled successfully.", reply_markup=back_keyboard())
        except Exception as e:
            logger.error("Cancel order error: %s", e)
            await query.edit_message_text(f"Failed to cancel order: {str(e)[:180]}", reply_markup=back_keyboard())
        return

    if data == "cancel_all_orders":
        slug = session.get("selected_market")
        if not slug:
            await query.edit_message_text(
                "Open a market first, then cancel all open orders on that market.",
                reply_markup=back_keyboard("menu_market"),
            )
            return
        await query.edit_message_text(f"Cancelling all orders on {slug}...")
        try:
            await client.cancel_all_orders(slug)
            await query.edit_message_text(
                f"All open orders cancelled on\n<code>{slug}</code>",
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard(),
            )
        except Exception as e:
            logger.error("Cancel all error: %s", e)
            await query.edit_message_text(f"Failed to cancel orders: {str(e)[:180]}", reply_markup=back_keyboard())
        return


async def _open_category(query, context, session: dict, slug: str):
    client = get_client(context)
    await query.edit_message_text("Loading category...")
    try:
        session["category_slug"] = slug
        session["active_filters"] = {}
        session["filter_options"] = []
        session["market_page"] = 1

        if slug == "all":
            session["page_id"] = None
            session["category_path"] = None
            session["category_name"] = "All Markets"
            await _load_markets_page(query, context, session, 1)
            return

        path = f"/{slug}" if not slug.startswith("/") else slug
        page = await client.get_market_page_by_path(path)
        session["page_id"] = page.get("id")
        session["category_path"] = path
        session["category_name"] = page.get("name") or slug

        options = _extract_filter_options(page)
        session["filter_options"] = options
        if options:
            await query.edit_message_text(
                f"<b>{session['category_name']}</b>\n\n"
                f"Total markets: <b>{page.get('totalCount', '—')}</b>\n\n"
                "Select a subcategory or show all:",
                parse_mode=ParseMode.HTML,
                reply_markup=filters_keyboard(options, back_callback="menu_market"),
            )
        else:
            await _load_markets_page(query, context, session, 1)
    except Exception as e:
        logger.error("Open category error: %s", e)
        await query.edit_message_text(f"Failed to load category: {str(e)[:180]}", reply_markup=back_keyboard("menu_market"))


def _extract_filter_options(page: dict) -> list:
    options = []
    for group in page.get("filterGroups") or []:
        source = group.get("source") or {}
        source_type = source.get("type")
        property_slug = None
        if source_type == "property":
            property_slug = source.get("propertySlug")
        elif source_type == "custom":
            continue
        group_name = group.get("name") or group.get("slug") or ""
        for option in group.get("options") or []:
            count = option.get("count")
            if count is not None and int(count) <= 0:
                continue
            value = option.get("value")
            if not value:
                continue
            label = option.get("label") or value
            if group_name:
                label = f"{group_name}: {label}"
            prop = property_slug or group.get("slug")
            if not prop:
                continue
            options.append({
                "label": label,
                "value": value,
                "count": count,
                "property_slug": prop,
                "group_slug": group.get("slug"),
            })
        for tab in ((group.get("tabs") or {}).get("options") or []):
            count = tab.get("count")
            if count is not None and int(count) <= 0:
                continue
            value = tab.get("value")
            if not value:
                continue
            prop = property_slug or group.get("slug")
            if not prop:
                continue
            label = tab.get("label") or value
            options.append({
                "label": label,
                "value": value,
                "count": count,
                "property_slug": prop,
                "group_slug": group.get("slug"),
            })
    return options


async def _apply_filter(query, context, session: dict, token: str):
    if token == "all":
        session["active_filters"] = {}
        session["filter_label"] = "All"
    else:
        try:
            idx = int(token)
        except ValueError:
            await query.edit_message_text("Invalid filter.", reply_markup=back_keyboard("menu_market"))
            return
        options = session.get("filter_options") or []
        if idx < 0 or idx >= len(options):
            await query.edit_message_text("Filter expired. Open the category again.", reply_markup=back_keyboard("menu_market"))
            return
        option = options[idx]
        prop = option.get("property_slug")
        if not prop:
            await query.edit_message_text("Filter is missing a property key.", reply_markup=back_keyboard("menu_market"))
            return
        session["active_filters"] = {prop: option["value"]}
        session["filter_label"] = option.get("label") or option["value"]
    await _load_markets_page(query, context, session, 1)


async def _load_markets_page(query, context, session: dict, page: int):
    client = get_client(context)
    await query.edit_message_text("Loading markets...")
    try:
        page_id = session.get("page_id")
        filters = session.get("active_filters") or {}
        if page_id:
            result = await client.get_page_markets(
                page_id,
                page=page,
                limit=15,
                filters=filters or None,
            )
            markets = result.get("data") or []
            pagination = result.get("pagination") or {}
            total_pages = int(pagination.get("totalPages") or 1)
            total = pagination.get("total") or len(markets)
        else:
            result = await client.get_active_markets(page=page, limit=15)
            markets = result.get("data") or []
            total = int(result.get("totalMarketsCount") or len(markets))
            total_pages = max(1, (total + 14) // 15)

        session["market_list"] = markets
        session["market_page"] = page
        session["market_total_pages"] = total_pages

        name = session.get("category_name") or "Markets"
        filter_label = session.get("filter_label")
        title = f"<b>{name}</b>"
        if filter_label:
            title += f"\nFilter: <b>{filter_label}</b>"
        title += f"\n\nPage {page}/{total_pages} · {total} markets\nSelect a market:"

        back_cb = "menu_market"
        if session.get("filter_options") and page_id:
            back_cb = f"cat_{session.get('category_slug', '')}"

        if not markets:
            await query.edit_message_text(
                f"{title}\n\nNo markets found.",
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard(back_cb),
            )
            return

        await query.edit_message_text(
            title,
            parse_mode=ParseMode.HTML,
            reply_markup=market_list_keyboard(
                markets,
                back_callback=back_cb,
                page=page,
                total_pages=total_pages,
            ),
        )
    except Exception as e:
        logger.error("Load markets error: %s", e)
        await query.edit_message_text(
            f"Failed to load markets: {str(e)[:180]}",
            reply_markup=back_keyboard("menu_market"),
        )


async def _open_group(query, context, session: dict, slug: str):
    client = get_client(context)
    await query.edit_message_text("Loading group market...")
    try:
        group_market = await client.get_market(slug)
        session["group_data"] = group_market
        session["selected_group"] = slug
        title = group_market.get("title") or slug
        await query.edit_message_text(
            f"<b>{title}</b>\n\nSelect an outcome market:",
            parse_mode=ParseMode.HTML,
            reply_markup=group_markets_keyboard(group_market, _back_to_markets(session)),
        )
    except Exception as e:
        logger.error("Group market error: %s", e)
        await query.edit_message_text(
            f"Failed to load group: {str(e)[:180]}",
            reply_markup=back_keyboard("menu_market"),
        )


async def _open_market(query, context, session: dict, slug: str):
    client = get_client(context)
    if not slug:
        await query.edit_message_text("Invalid market.", reply_markup=back_keyboard("menu_market"))
        return
    await query.edit_message_text("Loading market details...")
    try:
        market = await client.get_market(slug)
        orderbook = {}
        try:
            orderbook = await client.get_orderbook(slug)
        except Exception as e:
            logger.warning("Orderbook unavailable for %s: %s", slug, e)
        session["selected_market"] = slug
        session["market_data"] = market
        text = format_market_info(market, orderbook)
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=market_actions_keyboard(_back_to_markets(session)),
        )
    except Exception as e:
        logger.error("Market detail error: %s", e)
        await query.edit_message_text(
            f"Failed to load market: {str(e)[:180]}",
            reply_markup=back_keyboard("menu_market"),
        )


async def _show_order_type(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    query = update.callback_query if edit else None
    user_id = update.effective_user.id
    session = get_session(context, user_id)
    slug = session.get("selected_market", "unknown")
    outcome = session.get("trade_outcome", "YES")
    side = session.get("trade_side", "BUY")
    text = (
        f"<b>Place Order</b>\n\n"
        f"Market: <code>{slug}</code>\n"
        f"Side: <b>{side} {outcome}</b>\n\n"
        f"Select order type:"
    )
    if edit and query:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=order_type_keyboard())
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=order_type_keyboard())


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return
    user_id = update.effective_user.id
    session = get_session(context, user_id)
    awaiting = session.get("awaiting_input")

    if not awaiting:
        await update.message.reply_text("Use /menu to open the main menu.", reply_markup=main_menu_keyboard())
        return

    text = (update.message.text or "").strip()

    if awaiting == "price":
        try:
            price = float(text)
            if not (0.01 <= price <= 0.99):
                raise ValueError()
            session["trade_price"] = price
            session["awaiting_input"] = "size"
            await update.message.reply_text(
                f"Price set to <b>{price}</b>\n\nNow enter the number of contracts (e.g. <code>10</code>):",
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard("menu_market"),
            )
        except ValueError:
            await update.message.reply_text("Invalid price. Enter a number between 0.01 and 0.99.")
        return

    if awaiting == "size":
        try:
            size = float(text)
            if size <= 0:
                raise ValueError()
            session["trade_size"] = size
            session["awaiting_input"] = None
            await _show_order_confirmation(update, context)
        except ValueError:
            await update.message.reply_text("Invalid size. Enter a positive number.")
        return

    if awaiting == "maker_amount":
        try:
            amount = float(text)
            if amount <= 0:
                raise ValueError()
            session["trade_maker_amount"] = amount
            session["awaiting_input"] = None
            await _show_order_confirmation(update, context)
        except ValueError:
            await update.message.reply_text("Invalid amount. Enter a positive number.")
        return


async def _show_order_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = get_session(context, user_id)
    slug = session.get("selected_market")
    outcome = session.get("trade_outcome", "YES")
    order_type = session.get("order_type", "GTC")
    side = session.get("trade_side", "BUY")
    if order_type == "FOK":
        amount = session.get("trade_maker_amount", 0)
        unit = "USDC" if side == "BUY" else "shares"
        details = f"Amount: <b>{amount} {unit}</b>"
    else:
        price = session.get("trade_price", 0)
        size = session.get("trade_size", 0)
        details = f"Price: <b>{price}</b>\nSize: <b>{size} contracts</b>"
    text = (
        f"<b>Confirm Order</b>\n\n"
        f"Market: <code>{slug}</code>\n"
        f"Side: <b>{side} {outcome}</b>\n"
        f"Type: <b>{order_type}</b>\n"
        f"{details}\n\n"
        f"Place this order?"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=confirm_keyboard())


async def _execute_order(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
    user_id = update.effective_user.id
    session = get_session(context, user_id)
    client = get_client(context)
    slug = session.get("selected_market")
    outcome = session.get("trade_outcome", "YES")
    order_type = session.get("order_type", "GTC")
    side = session.get("trade_side", "BUY")

    if not slug:
        text = "No market selected."
        if query:
            await query.edit_message_text(text, reply_markup=back_keyboard())
        return

    if query:
        await query.edit_message_text("Signing and placing order...")

    try:
        market_data = session.get("market_data")
        if not market_data or market_data.get("slug") != slug:
            market_data = await client.get_market(slug)
            session["market_data"] = market_data

        kwargs = {
            "market_slug": slug,
            "outcome": outcome,
            "side": side,
            "order_type": order_type,
            "market": market_data,
        }
        if order_type == "FOK":
            kwargs["maker_amount"] = session.get("trade_maker_amount")
        else:
            kwargs["price"] = session.get("trade_price")
            kwargs["size"] = session.get("trade_size")

        result = await client.place_order(**kwargs)
        text = format_order_result(result, slug, outcome, order_type, side)
        if query:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error("Order execution error: %s", e, exc_info=True)
        error_text = f"Order failed:\n<code>{str(e)[:350]}</code>"
        if query:
            await query.edit_message_text(error_text, parse_mode=ParseMode.HTML, reply_markup=back_keyboard())
        else:
            await update.message.reply_text(error_text, parse_mode=ParseMode.HTML, reply_markup=back_keyboard())
