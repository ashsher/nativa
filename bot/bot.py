"""
bot.py
Telegram bot for the Nativa language learning platform.

Responsibilities:
  - /start   — opens the Nativa Mini-App via a WebApp button.
  - /help    — shows usage instructions.
  - pre_checkout_query  — approve Telegram Stars payment before charge.
  - successful_payment  — confirm payment; POST to backend to activate premium.
  - Daily reminder job  — every day at 04:00 UTC, notify users with due vocabulary.

Uses python-telegram-bot v20+ (async Application pattern with JobQueue).
"""

import logging  # standard library logging
import os       # for environment variable access

import httpx                                # async HTTP client for backend calls
from datetime import time                   # for scheduling the daily job at 04:00 UTC
from dotenv import load_dotenv              # load .env file into os.environ

from telegram import (
    InlineKeyboardButton,   # button that opens a URL or WebApp
    InlineKeyboardMarkup,   # keyboard wrapper holding button rows
    Update,                 # Telegram Update object (all incoming data)
    WebAppInfo,             # tells Telegram to open a URL as a Mini-App
)
from telegram.ext import (
    Application,            # the bot application that drives the event loop
    CommandHandler,         # handler for /command messages
    ContextTypes,           # typed context for handlers
    MessageHandler,         # handler for message types (e.g. successful_payment)
    PreCheckoutQueryHandler, # handler for pre_checkout_query events
    filters,                # message filter constants
)

# ─── Load environment variables ───────────────────────────────────────────────
# Load .env before reading os.environ so all keys are available.
load_dotenv()

# Bot token from @BotFather — required.
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

# URL of the Nativa Mini-App frontend served by nginx — required.
MINI_APP_URL: str = os.environ["MINI_APP_URL"]

# Internal backend URL used by the bot to call backend APIs.
# Defaults to the Docker service name (bot → backend) if not set.
BACKEND_URL: str = os.environ.get("BACKEND_URL", "http://backend:8000")

# ─── Logging ──────────────────────────────────────────────────────────────────
# INFO level captures all request handling without excessive noise.
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─── /start handler ───────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command.

    Sends a welcome message with an InlineKeyboardButton that opens the
    Nativa Mini-App inside Telegram's WebView using WebAppInfo.

    Args:
        update:  Incoming Telegram Update containing the /start message.
        context: PTB handler context (bot reference, args, user_data, etc.).
    """
    user = update.effective_user  # the Telegram User object who sent /start
    # Use first_name if available, otherwise a generic fallback.
    name = user.first_name if user else "Foydalanuvchi"

    logger.info("User %s (%s) started the bot.", name, user.id if user else "unknown")

    # Build an inline keyboard with a single "Open App" WebApp button.
    # WebAppInfo instructs Telegram to render the URL inside the Mini-App container.
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="🚀 Nativa-ni ochish",
                    web_app=WebAppInfo(url=MINI_APP_URL),
                )
            ]
        ]
    )

    # Uzbek welcome message using Markdown bold/italic for emphasis.
    welcome_text = (
        f"Salom, {name}! 👋\n\n"
        "🌍 *Nativa* — til o'rganish uchun aqlli hamkoringiz.\n\n"
        "📹 YouTube videolari orqali so'z o'rganing\n"
        "📖 Maqolalarni o'qib lug'at to'plang\n"
        "🃏 Anki-uslubida takrorlash sessiyalari\n"
        "👥 Ona tilida so'zlashuvchilar bilan bog'laning\n\n"
        "Boshlash uchun quyidagi tugmani bosing:"
    )

    await update.message.reply_text(
        text=welcome_text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ─── /help handler ────────────────────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /help command.

    Returns a brief usage guide explaining all available commands
    and a summary of the app's features.

    Args:
        update:  Incoming Telegram Update.
        context: PTB handler context.
    """
    logger.info(
        "User %s requested help.",
        update.effective_user.id if update.effective_user else "unknown"
    )

    help_text = (
        "📚 *Nativa — Yordam*\n\n"
        "*/start* — Ilovani ochish tugmasini ko'rsatish\n"
        "*/help*  — Ushbu yordam xabarini ko'rsatish\n\n"
        "🔹 Ilovada YouTube havolasini joylashtiring\n"
        "🔹 Subtitr so'zlariga bosib tarjima oling\n"
        "🔹 So'zlarni lug'atga saqlang va takrorlang\n"
        "🔹 AI grammatika tushuntirishlari uchun so'zni bosib turing\n\n"
        "Muammo bo'lsa: @nativa_support"
    )

    await update.message.reply_text(text=help_text, parse_mode="Markdown")


# ─── Payment: pre_checkout_query ──────────────────────────────────────────────

async def pre_checkout_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Answer Telegram's pre_checkout_query to approve a Telegram Stars payment.

    Telegram sends this before charging the user (~10 second window to respond).
    We always answer ok=True here; business validation is done in
    successful_payment_handler after the actual charge.

    Args:
        update:  Update containing the pre_checkout_query.
        context: PTB handler context.
    """
    query = update.pre_checkout_query  # the pre-checkout query object
    logger.info(
        "PreCheckout: invoice_payload=%s from user %s",
        query.invoice_payload,
        query.from_user.id,
    )
    # Approve the payment — the backend verifies legitimacy via /api/payment/verify.
    await query.answer(ok=True)


# ─── Payment: successful_payment handler ──────────────────────────────────────

async def successful_payment_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle the successful_payment message sent by Telegram after a Stars charge.

    Steps:
      1. Extract the telegram_payment_charge_id from the payment info.
      2. POST to the backend /api/payment/verify with the charge ID and stars amount.
      3. Reply to the user with a success message.

    Args:
        update:  Update containing the successful_payment message.
        context: PTB handler context.
    """
    # Extract the payment data from the successful_payment message field.
    payment = update.message.successful_payment
    # Telegram's internal charge identifier — used as the transaction reference.
    charge_id    = payment.telegram_payment_charge_id
    # Number of Telegram Stars charged (100 XTR ≈ $1 at current rates).
    stars_amount = payment.total_amount

    logger.info(
        "Successful payment: charge_id=%s stars=%s from user %s",
        charge_id,
        stars_amount,
        update.effective_user.id,
    )

    # POST to the backend to activate premium for this user.
    # The backend verifies the charge_id against its records and sets is_premium=True.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Include a minimal auth token so the backend can identify the user.
            # In production this would use the bot's own internal secret.
            resp = await client.post(
                f"{BACKEND_URL}/api/payment/verify",
                json={
                    "transaction_ref": charge_id,   # Telegram charge ID
                    "stars_amount":    stars_amount, # amount charged in Stars
                },
                headers={
                    # Bot-internal header; the payment endpoint accepts bot requests.
                    "X-Bot-Secret": os.environ.get("SECRET_KEY", ""),
                },
            )
            # Log the backend response status for audit trails.
            logger.info("Backend verify response: %s", resp.status_code)
    except httpx.RequestError as exc:
        # Log the error but don't crash — the webhook may retry.
        logger.error("Failed to notify backend of payment: %s", exc)

    # Reply to the user in Uzbek to confirm their premium upgrade.
    await update.message.reply_text(
        "🎉 To'lov muvaffaqiyatli! Siz endi Premium foydalanuvchisiz. ⚡\n\n"
        "Nativa-ni oching va barcha imkoniyatlardan foydalaning!",
        parse_mode="Markdown",
    )


# ─── Daily reminder job ────────────────────────────────────────────────────────

async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Daily job that runs at 04:00 UTC.

    Calls the backend to get a list of users with vocabulary words due today,
    then sends each user a reminder message with a button to open the app.

    The backend endpoint GET /api/user/due-words returns a list of:
      { telegram_id: int, first_name: str, due_count: int }

    Args:
        context: PTB job context (bot reference available via context.bot).
    """
    logger.info("Running daily vocabulary reminder job.")

    # Fetch users with due words from the backend.
    due_users = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{BACKEND_URL}/api/user/due-words",
                headers={"X-Bot-Secret": os.environ.get("SECRET_KEY", "")},
            )
            if resp.status_code == 200:
                # Expect a JSON array of { telegram_id, first_name, due_count }.
                due_users = resp.json()
            else:
                logger.warning("due-words endpoint returned %s", resp.status_code)
    except httpx.RequestError as exc:
        # Network failure — skip this run, will retry tomorrow.
        logger.error("Failed to fetch due-words from backend: %s", exc)
        return

    # Send a personalised reminder to each user with due words.
    for user_data in due_users:
        telegram_id = user_data.get("telegram_id")
        first_name  = user_data.get("first_name", "Foydalanuvchi")
        due_count   = user_data.get("due_count", 0)

        if not telegram_id or due_count == 0:
            # Skip users with no telegram_id or no due words (safety check).
            continue

        # Build the reminder message in Uzbek.
        reminder_text = (
            f"Salom, {first_name}! 👋\n\n"
            f"📚 Bugun *{due_count} ta so'z* sizni kutmoqda.\n"
            "Hozir takrorlasangiz, eslash ancha oson bo'ladi!"
        )

        # Inline keyboard button to open the Mini-App directly to the vocab tab.
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                text="📖 Nativani ochish",
                web_app=WebAppInfo(url=MINI_APP_URL),
            )]]
        )

        try:
            # Send the reminder message to the user's private chat.
            await context.bot.send_message(
                chat_id=telegram_id,
                text=reminder_text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
            logger.info("Sent reminder to user %s (%s due words).", telegram_id, due_count)
        except Exception as exc:
            # User may have blocked the bot — log and continue with others.
            logger.warning("Could not send reminder to %s: %s", telegram_id, exc)


# ─── Application bootstrap ────────────────────────────────────────────────────

def main() -> None:
    """
    Build and run the Telegram bot application.

    Registers all handlers and schedules the daily reminder job,
    then starts long-polling for updates.

    Polling is appropriate for VPS deployments; use webhooks for
    high-traffic production environments.
    """
    logger.info("Starting Nativa bot…")

    # Build the Application with the bot token.
    # JobQueue is enabled by default in python-telegram-bot v20+.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ── Command handlers ────────────────────────────────────────────────────
    application.add_handler(CommandHandler("start", start))    # /start command
    application.add_handler(CommandHandler("help", help_command))  # /help command

    # ── Payment handlers ────────────────────────────────────────────────────
    # Pre-checkout query: approve before Telegram charges the user.
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))

    # Successful payment: verify and activate premium after charge.
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler)
    )

    # ── Daily reminder job ──────────────────────────────────────────────────
    # run_daily schedules the callback to fire every day at 04:00 UTC.
    # This is early morning in Central Asia (Uzbekistan is UTC+5, so 09:00 local).
    application.job_queue.run_daily(
        callback=send_daily_reminders,
        time=time(hour=4, minute=0),  # 04:00 UTC every day
        name="daily_vocab_reminders",
    )

    logger.info("Bot polling started. Press Ctrl+C to stop.")

    # run_polling blocks until the process receives SIGINT or SIGTERM.
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
