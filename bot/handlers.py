import asyncio
import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from .keyboards import (
    main_menu_keyboard,
    timeframe_keyboard,
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
from .errors import format_api_error, reply_error

logger = logging.getLogger(__name__)


def get_client(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["client"]


async def _show_query_error(query, error: Exception, *, action: str) -> None:
    await query.edit_message_text(
        format_api_error(error, action=action),
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard(),
    )


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
        positions = await client.get_portfolio_positions()
        profile = await client.get_current_profile()
        pnl = await client.get_pnl_chart()
        points = await client.get_points()
        text = format_portfolio(profile, positions, pnl, points)
        await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
    except Exception as e:
        logger.error(f"Portfolio error: {e}", exc_info=True)
        await msg.edit_text(
            format_api_error(e, action="load your portfolio"),
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard(),
        )


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
            positions = await client.get_portfolio_positions()
            profile = await client.get_current_profile()
            pnl = await client.get_pnl_chart()
            points = await client.get_points()
            text = format_portfolio(profile, positions, pnl, points)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
        except Exception as e:
            logger.error(f"Portfolio callback error: {e}", exc_info=True)
            await _show_query_error(query, e, action="load your portfolio")

    elif data == "menu_positions":
        await query.edit_message_text("⏳ Loading positions...")
        client = get_client(context)
        try:
            positions = await client.get_portfolio_positions()
            text = format_positions(positions)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
        except Exception as e:
            logger.error(f"Positions error: {e}", exc_info=True)
            await _show_query_error(query, e, action="load your positions")

    elif data == "menu_history":
        await query.edit_message_text("⏳ Loading trade history...")
        client = get_client(context)
        try:
            history = await client.get_portfolio_history()
            text = format_history(history)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=portfolio_keyboard())
        except Exception as e:
            logger.error(f"History error: {e}", exc_info=True)
            await _show_query_error(query, e, action="load trade history")

    elif data.startswith("tf_"):
        timeframe = data[3:]
        session["timeframe"] = timeframe
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
            logger.error(f"Market list error: {e}", exc_info=True)
            await _show_query_error(query, e, action="load markets")

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
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🟢 Buy YES", callback_data=f"trade_buy_yes_{slug}"),
                    InlineKeyboardButton("🔴 Buy NO", callback_data=f"trade_buy_no_{slug}"),
                ],
                [InlineKeyboardButton("📖 Full Orderbook", callback_data=f"orderbook_{slug}")],
                [InlineKeyboardButton("◀️ Back to Markets", callback_data=f"tf_{session.get('timeframe', '1h')}")],
            ])
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Market detail error: {e}", exc_info=True)
            await _show_query_error(query, e, action="load market details")

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
            logger.error(f"Orderbook error: {e}", exc_info=True)
            await _show_query_error(query, e, action="load the orderbook")

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
            logger.error(f"Cancel order error: {e}", exc_info=True)
            await _show_query_error(query, e, action="cancel the order")

    elif data == "cancel_all_orders":
        await query.edit_message_text("⏳ Cancelling all orders...")
        client = get_client(context)
        try:
            await client.cancel_all_orders()
            await query.edit_message_text("✅ All orders cancelled.", reply_markup=back_keyboard())
        except Exception as e:
            logger.error(f"Cancel all error: {e}", exc_info=True)
            await _show_query_error(query, e, action="cancel all orders")

    elif data == "back":
        await query.edit_message_text(
            "📋 <b>Main Menu</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(),
        )


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

    if not slug:
        await reply_error(
            update,
            query,
            ValueError("No market selected. Browse markets and try again."),
            action="place the order",
        )
        return

    if query:
        await query.edit_message_text("⏳ Placing order...")

    try:
        market_data = session.get("market_data")
        if not market_data:
            market_data = await asyncio.wait_for(client.get_market(slug), timeout=30)
            session["market_data"] = market_data

        result = await client.create_order(
            market_slug=slug,
            order_type=order_type,
            outcome=outcome,
            side=0 if side == "BUY" else 1,
            price=session.get("trade_price") if order_type != "FOK" else None,
            size=session.get("trade_size") if order_type != "FOK" else None,
            usdc_amount=session.get("trade_maker_amount") if order_type == "FOK" else None,
            market_data=market_data,
        )
        text = format_order_result(result, slug, outcome, order_type)
        if query:
            await query.edit_message_text(
                text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard()
            )
    except Exception as e:
        logger.error(f"Order execution error: {e}", exc_info=True)
        await reply_error(update, query, e, action="place the order")
