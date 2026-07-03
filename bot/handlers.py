import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from .keyboards import (
    main_menu_keyboard,
    timeframe_keyboard,
    football_league_keyboard,
    football_group_keyboard,
    market_list_keyboard,
    order_type_keyboard,
    confirm_keyboard,
    portfolio_keyboard,
    back_keyboard,
)
from .formatters import (
    format_market_info,
    format_orderbook,
    format_portfolio,
    format_positions,
    format_history,
    format_order_result,
)

logger = logging.getLogger(__name__)


def _derive_address(private_key: str) -> str:
    try:
        from eth_account import Account
        return Account.from_key(private_key).address
    except Exception:
        return ""


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
        f"Unauthorized access attempt from user_id={update.effective_user.id if update.effective_user else 'unknown'}"
    )
    if update.message:
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
    elif update.callback_query:
        await update.callback_query.answer("⛔ Unauthorized.", show_alert=True)


def get_session(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> dict:
    sessions = context.application.bot_data.setdefault("user_sessions", {})
    if user_id not in sessions:
        sessions[user_id] = {}
    return sessions[user_id]


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return
    user = update.effective_user
    text = (
        f"👋 Welcome, <b>{user.first_name}</b>!\n\n"
        "🏦 <b>Limitless Exchange Trading Bot</b>\n\n"
        "Trade prediction markets on Limitless Exchange directly from Telegram.\n\n"
        "Use the menu below to get started:"
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
        "📋 <b>Main Menu</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(),
    )


async def market_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return
    await update.message.reply_text(
        "📊 <b>Market Browser</b>\n\nSelect a timeframe to browse active markets:",
        parse_mode=ParseMode.HTML,
        reply_markup=timeframe_keyboard(),
    )


async def order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return
    user_id = update.effective_user.id
    session = get_session(context, user_id)
    if not session.get("selected_market"):
        await update.message.reply_text(
            "⚠️ Please select a market first.\n\nUse /market to browse markets.",
            reply_markup=back_keyboard(),
        )
        return
    await _show_order_type(update, context, edit=False)


async def portfolio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return
    client = get_client(context)
    config = context.application.bot_data["config"]
    msg = await update.message.reply_text("⏳ Loading portfolio...")
    try:
        wallet = _derive_address(config.get("wallet_private_key", ""))
        positions = await client.get_portfolio_positions()
        profile = await client.get_profile(wallet) if wallet else {}
        pnl = await client.get_pnl_chart()
        points = await client.get_points()
        text = format_portfolio(profile, positions, pnl, points)
        await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
    except Exception as e:
        logger.error(f"Portfolio error: {e}")
        await msg.edit_text("❌ Failed to load portfolio. Please try again.", reply_markup=back_keyboard())


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        await reject(update)
        return
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    session = get_session(context, user_id)

    if data == "menu_main":
        await query.edit_message_text(
            "📋 <b>Main Menu</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(),
        )

    elif data == "menu_market":
        await query.edit_message_text(
            "📊 <b>Market Browser</b>\n\nSelect a timeframe:",
            parse_mode=ParseMode.HTML,
            reply_markup=timeframe_keyboard(),
        )

    elif data == "menu_portfolio":
        await query.edit_message_text("⏳ Loading portfolio...")
        client = get_client(context)
        config = context.application.bot_data["config"]
        try:
            wallet = _derive_address(config.get("wallet_private_key", ""))
            positions = await client.get_portfolio_positions()
            profile = await client.get_profile(wallet) if wallet else {}
            pnl = await client.get_pnl_chart()
            points = await client.get_points()
            text = format_portfolio(profile, positions, pnl, points)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
        except Exception as e:
            logger.error(f"Portfolio callback error: {e}")
            await query.edit_message_text("❌ Failed to load portfolio.", reply_markup=back_keyboard())

    elif data == "menu_positions":
        await query.edit_message_text("⏳ Loading positions...")
        client = get_client(context)
        try:
            positions = await client.get_portfolio_positions()
            text = format_positions(positions)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
        except Exception as e:
            logger.error(f"Positions error: {e}")
            await query.edit_message_text("❌ Failed to load positions.", reply_markup=back_keyboard())

    elif data == "menu_history":
        await query.edit_message_text("⏳ Loading trade history...")
        client = get_client(context)
        try:
            history = await client.get_portfolio_history()
            text = format_history(history)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
        except Exception as e:
            logger.error(f"History error: {e}")
            await query.edit_message_text("❌ Failed to load history.", reply_markup=back_keyboard())

    elif data == "noop":
        await query.answer()

    elif data == "tf_football":
        session["market_source"] = "football"
        await query.edit_message_text("⏳ Loading football categories...")
        client = get_client(context)
        try:
            sport_page = await client.get_market_page_by_path("/sport")
            football_group = next(
                (g for g in sport_page.get("filterGroups", []) if g.get("slug") == "football"),
                None,
            )
            options = []
            if football_group:
                options.extend(football_group.get("options", []))
                tabs = football_group.get("tabs", {})
                for tab in tabs.get("options", []):
                    if tab.get("count", 0) > 0:
                        options.append(tab)
            if not options:
                options = [{"label": "FIFA World Cup", "value": "fifa-world-cup", "count": 1}]
            await query.edit_message_text(
                "⚽ <b>Football Markets</b>\n\nSelect a league or category:",
                parse_mode=ParseMode.HTML,
                reply_markup=football_league_keyboard(options),
            )
        except Exception as e:
            logger.error(f"Football menu error: {e}")
            await query.edit_message_text("❌ Failed to load football categories.", reply_markup=back_keyboard())

    elif data.startswith("fbpage_"):
        parts = data[8:].rsplit("_", 1)
        if len(parts) != 2:
            await query.edit_message_text("❌ Invalid page.", reply_markup=back_keyboard())
            return
        filter_key, page_str = parts
        await _show_football_markets(query, context, session, filter_key, int(page_str))

    elif data.startswith("fb_"):
        filter_key = data[3:]
        session["football_filter"] = filter_key
        session["market_source"] = "football"
        await _show_football_markets(query, context, session, filter_key, 1)

    elif data.startswith("fbgroup_"):
        slug = data[8:]
        session["market_source"] = "football"
        await query.edit_message_text("⏳ Loading match outcomes...")
        client = get_client(context)
        try:
            group_market = await client.get_market(slug)
            session["selected_group"] = slug
            title = group_market.get("title", slug)
            back_callback = f"fb_{session.get('football_filter', 'fifa-world-cup')}"
            await query.edit_message_text(
                f"⚽ <b>{title}</b>\n\nSelect an outcome to trade:",
                parse_mode=ParseMode.HTML,
                reply_markup=football_group_keyboard(group_market, back_callback),
            )
        except Exception as e:
            logger.error(f"Football group error: {e}")
            await query.edit_message_text("❌ Failed to load match outcomes.", reply_markup=back_keyboard())

    elif data.startswith("tf_"):
        timeframe = data[3:]
        session["timeframe"] = timeframe
        session["market_source"] = "crypto"
        await query.edit_message_text("⏳ Loading markets...")
        client = get_client(context)
        try:
            markets_data = await client.get_active_markets(limit=20)
            markets = markets_data.get("data", [])
            category_filter = {"5m": "5 min", "15m": "15 min", "1h": "hourly", "1d": "daily"}
            target_label = category_filter.get(timeframe, "").lower()
            if target_label:
                filtered = [
                    m for m in markets
                    if any(target_label in str(c).lower() for c in m.get("categories", []) + m.get("tags", []))
                ]
                if not filtered:
                    filtered = markets
            else:
                filtered = markets
            filtered = filtered[:20]
            session["market_list"] = filtered
            tf_labels = {"5m": "5 Min", "15m": "15 Min", "1h": "Hourly", "1d": "Daily"}
            tf_label = tf_labels.get(timeframe, timeframe)
            await query.edit_message_text(
                f"📊 <b>Active Markets — {tf_label}</b>\n\nSelect a market:",
                parse_mode=ParseMode.HTML,
                reply_markup=market_list_keyboard(filtered),
            )
        except Exception as e:
            logger.error(f"Market list error: {e}")
            await query.edit_message_text("❌ Failed to load markets.", reply_markup=back_keyboard())

    elif data.startswith("market_"):
        slug = data[7:]
        session["selected_market"] = slug
        await query.edit_message_text("⏳ Loading market details...")
        client = get_client(context)
        try:
            market = await client.get_market(slug)
            orderbook = await client.get_orderbook(slug)
            session["market_data"] = market
            text = format_market_info(market, orderbook)
            back_callback = _market_back_callback(session)
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🟢 Buy YES", callback_data=f"trade_buy_yes_{slug}"),
                    InlineKeyboardButton("🔴 Buy NO", callback_data=f"trade_buy_no_{slug}"),
                ],
                [InlineKeyboardButton("📖 Full Orderbook", callback_data=f"orderbook_{slug}")],
                [InlineKeyboardButton("◀️ Back to Markets", callback_data=back_callback)],
            ])
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Market detail error: {e}")
            await query.edit_message_text("❌ Failed to load market.", reply_markup=back_keyboard())

    elif data.startswith("orderbook_"):
        slug = data[10:]
        await query.edit_message_text("⏳ Loading orderbook...")
        client = get_client(context)
        try:
            orderbook = await client.get_orderbook(slug)
            text = format_orderbook(orderbook, slug)
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🟢 Buy YES", callback_data=f"trade_buy_yes_{slug}"),
                    InlineKeyboardButton("🔴 Buy NO", callback_data=f"trade_buy_no_{slug}"),
                ],
                [InlineKeyboardButton("◀️ Back", callback_data=f"market_{slug}")],
            ])
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Orderbook error: {e}")
            await query.edit_message_text("❌ Failed to load orderbook.", reply_markup=back_keyboard())

    elif data.startswith("trade_"):
        parts = data.split("_")
        outcome = parts[2]
        slug = "_".join(parts[3:])
        session["trade_side"] = "BUY"
        session["trade_outcome"] = outcome.upper()
        session["selected_market"] = slug
        await _show_order_type(update, context, edit=True)

    elif data.startswith("ordertype_"):
        order_type = data[10:]
        session["order_type"] = order_type
        slug = session.get("selected_market", "")
        outcome = session.get("trade_outcome", "YES")
        if order_type == "FOK":
            session["awaiting_input"] = "maker_amount"
            await query.edit_message_text(
                f"💰 <b>Market Order (FOK)</b>\n\n"
                f"Market: <code>{slug}</code>\n"
                f"Outcome: <b>{outcome}</b>\n\n"
                f"Enter the USDC amount to spend (e.g. <code>10</code>):",
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard(),
            )
        else:
            session["awaiting_input"] = "price"
            await query.edit_message_text(
                f"💲 <b>{order_type} Order</b>\n\n"
                f"Market: <code>{slug}</code>\n"
                f"Outcome: <b>{outcome}</b>\n\n"
                f"Enter the price (0.01 – 0.99):",
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard(),
            )

    elif data == "confirm_order":
        await _execute_order(update, context, query=query)

    elif data == "cancel_order":
        session.pop("pending_order", None)
        session.pop("awaiting_input", None)
        await query.edit_message_text("❌ Order cancelled.", reply_markup=main_menu_keyboard())

    elif data.startswith("cancel_order_id_"):
        order_id = data[16:]
        await query.edit_message_text("⏳ Cancelling order...")
        client = get_client(context)
        try:
            await client.cancel_order(order_id)
            await query.edit_message_text("✅ Order cancelled successfully.", reply_markup=back_keyboard())
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            await query.edit_message_text("❌ Failed to cancel order.", reply_markup=back_keyboard())

    elif data == "cancel_all_orders":
        await query.edit_message_text("⏳ Cancelling all orders...")
        client = get_client(context)
        try:
            await client.cancel_all_orders()
            await query.edit_message_text("✅ All orders cancelled.", reply_markup=back_keyboard())
        except Exception as e:
            logger.error(f"Cancel all error: {e}")
            await query.edit_message_text("❌ Failed to cancel orders.", reply_markup=back_keyboard())

    elif data == "back":
        await query.edit_message_text(
            "📋 <b>Main Menu</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(),
        )


def _market_back_callback(session: dict) -> str:
    if session.get("market_source") == "football":
        return f"fb_{session.get('football_filter', 'fifa-world-cup')}"
    return f"tf_{session.get('timeframe', '1h')}"


def _football_filter_label(filter_key: str) -> str:
    labels = {
        "all": "All Football",
        "fifa-world-cup": "FIFA World Cup",
        "matches": "Matches",
        "props": "Props",
        "player-props": "Player Props",
        "off-the-pitch": "Off the Pitch",
        "england-premier-league": "Premier League",
        "uefa-champions-league": "Champions League",
        "spain-laliga": "La Liga",
        "italy-serie-a": "Serie A",
        "bundesliga": "Bundesliga",
    }
    return labels.get(filter_key, filter_key.replace("-", " ").title())


async def _show_football_markets(query, context, session, filter_key: str, page: int):
    await query.edit_message_text("⏳ Loading football markets...")
    client = get_client(context)
    try:
        result = await client.get_football_markets(filter_key=filter_key, page=page, limit=15)
        markets = result.get("data", [])
        pagination = result.get("pagination", {})
        total_pages = pagination.get("totalPages", 1)
        session["market_list"] = markets
        session["football_filter"] = filter_key
        session["football_page"] = page
        session["market_source"] = "football"
        label = _football_filter_label(filter_key)
        if not markets:
            await query.edit_message_text(
                f"⚽ <b>{label}</b>\n\nNo active football markets found.",
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard(),
            )
            return
        await query.edit_message_text(
            f"⚽ <b>Football — {label}</b>\n\nSelect a market:",
            parse_mode=ParseMode.HTML,
            reply_markup=market_list_keyboard(
                markets,
                back_callback="tf_football",
                page=page,
                total_pages=total_pages,
                page_callback_prefix=f"fbpage_{filter_key}_",
            ),
        )
    except Exception as e:
        logger.error(f"Football market list error: {e}")
        await query.edit_message_text("❌ Failed to load football markets.", reply_markup=back_keyboard())


async def _show_order_type(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    query = update.callback_query if edit else None
    user_id = update.effective_user.id
    session = get_session(context, user_id)
    slug = session.get("selected_market", "unknown")
    outcome = session.get("trade_outcome", "YES")
    text = (
        f"📋 <b>Place Order</b>\n\n"
        f"Market: <code>{slug}</code>\n"
        f"Outcome: <b>{outcome}</b>\n\n"
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

    text = update.message.text.strip()

    if awaiting == "price":
        try:
            price = float(text)
            if not (0.01 <= price <= 0.99):
                raise ValueError()
            session["trade_price"] = price
            session["awaiting_input"] = "size"
            await update.message.reply_text(
                f"📦 Price set to <b>{price}</b>\n\nNow enter the number of contracts (e.g. <code>10</code>):",
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard(),
            )
        except ValueError:
            await update.message.reply_text("⚠️ Invalid price. Enter a number between 0.01 and 0.99.")

    elif awaiting == "size":
        try:
            size = float(text)
            if size <= 0:
                raise ValueError()
            session["trade_size"] = size
            session["awaiting_input"] = None
            await _show_order_confirmation(update, context)
        except ValueError:
            await update.message.reply_text("⚠️ Invalid size. Enter a positive number.")

    elif awaiting == "maker_amount":
        try:
            amount = float(text)
            if amount <= 0:
                raise ValueError()
            session["trade_maker_amount"] = amount
            session["awaiting_input"] = None
            await _show_order_confirmation(update, context)
        except ValueError:
            await update.message.reply_text("⚠️ Invalid amount. Enter a positive number.")


async def _show_order_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = get_session(context, user_id)
    slug = session.get("selected_market")
    outcome = session.get("trade_outcome", "YES")
    order_type = session.get("order_type", "GTC")
    side = session.get("trade_side", "BUY")
    if order_type == "FOK":
        amount = session.get("trade_maker_amount", 0)
        details = f"Amount: <b>{amount} USDC</b>"
    else:
        price = session.get("trade_price", 0)
        size = session.get("trade_size", 0)
        details = f"Price: <b>{price}</b>\nSize: <b>{size} contracts</b>"
    text = (
        f"✅ <b>Confirm Order</b>\n\n"
        f"Market: <code>{slug}</code>\n"
        f"Outcome: <b>{outcome}</b>\n"
        f"Type: <b>{order_type}</b>\n"
        f"Side: <b>{side}</b>\n"
        f"{details}\n\n"
        f"Do you want to place this order?"
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
    if query:
        await query.edit_message_text("⏳ Placing order...")
    try:
        market_data = session.get("market_data")
        if not market_data:
            market_data = await client.get_market(slug)
            session["market_data"] = market_data
        tokens = market_data.get("tokens", market_data.get("positionIds", {}))
        if isinstance(tokens, dict):
            token_id = tokens.get("yes" if outcome == "YES" else "no", "")
        elif isinstance(tokens, list):
            token_id = tokens[0] if outcome == "YES" else (tokens[1] if len(tokens) > 1 else tokens[0])
        else:
            token_id = str(tokens)
        payload = {
            "marketSlug": slug,
            "orderType": order_type,
            "args": {"tokenId": token_id, "side": side},
        }
        if order_type == "FOK":
            payload["args"]["makerAmount"] = session.get("trade_maker_amount")
        else:
            payload["args"]["price"] = session.get("trade_price")
            payload["args"]["size"] = session.get("trade_size")
        result = await client.create_order(payload)
        text = format_order_result(result, slug, outcome, order_type)
        if query:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error(f"Order execution error: {e}")
        error_text = f"❌ Order failed: {str(e)[:200]}"
        if query:
            await query.edit_message_text(error_text, reply_markup=back_keyboard())
        else:
            await update.message.reply_text(error_text, reply_markup=back_keyboard())
