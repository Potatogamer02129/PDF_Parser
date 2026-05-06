import io
import logging
import os
import tempfile

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from parser import get_available_codes, parse_pdf
from report import generate_detailed_pdf, generate_grouped_pdf

load_dotenv()
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

WAIT_CODE, WAIT_MODE = range(2)

_TRANSACTIONS = "transactions"
_METADATA     = "metadata"
_CODE         = "area_code"
_PDF_PATH     = "pdf_path"

# Fixed area codes — update this list if new codes are added
KNOWN_AREA_CODES = ["ARJ", "BSR", "PGT", "PNG", "POD", "SLF", "SLI", "VDR", "VPI", "WSL"]
_CODES_DISPLAY   = "  •  ".join(KNOWN_AREA_CODES)

_MODE_KEYBOARD = [[
    InlineKeyboardButton("📊 Grouped Summary",       callback_data="grouped"),
    InlineKeyboardButton("📋 Detailed Transactions", callback_data="detailed"),
]]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "👋 *Khatabook Report Bot*\n\nSend me a Khatabook account statement PDF and I'll generate a filtered area-code report.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def receive_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doc = update.message.document
    if not doc or doc.mime_type != "application/pdf":
        await update.message.reply_text("⚠️ Please send a *PDF* file.", parse_mode="Markdown")
        return ConversationHandler.END

    # Clean up state from any previous session
    old_path = context.user_data.pop(_PDF_PATH, None)
    if old_path and os.path.exists(old_path):
        try:
            os.unlink(old_path)
        except OSError:
            pass
    context.user_data.pop(_TRANSACTIONS, None)
    context.user_data.pop(_METADATA, None)

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(tmp_path)
    except Exception:
        logger.exception("PDF download error")
        await update.message.reply_text("❌ Failed to download the file. Please try again.")
        return ConversationHandler.END

    context.user_data[_PDF_PATH] = tmp_path

    await update.message.reply_text(
        "📥 *PDF received!*\n\n"
        f"📋 *Available Area Codes:*\n`{_CODES_DISPLAY}`\n\n"
        "Reply with a *3-letter area code* (e.g. `WSL`) or `ALL` to generate reports for every code:",
        parse_mode="Markdown",
    )
    return WAIT_CODE


async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw      = update.message.text.strip().upper()
    pdf_path = context.user_data.get(_PDF_PATH)

    if not pdf_path or not os.path.exists(pdf_path):
        await update.message.reply_text("⚠️ No PDF on file. Please send a PDF first.")
        return ConversationHandler.END

    if raw != "ALL" and (len(raw) != 3 or not raw.isalpha()):
        await update.message.reply_text(
            f"⚠️ Enter a valid 3-letter code or `ALL`.\n\nAvailable: `{_CODES_DISPLAY}`",
            parse_mode="Markdown",
        )
        return WAIT_CODE

    # Parse the PDF lazily — only now that we have the code
    transactions = context.user_data.get(_TRANSACTIONS)
    metadata     = context.user_data.get(_METADATA)
    if transactions is None:
        await update.message.reply_text("⚙️ Parsing PDF…")
        try:
            transactions, metadata = parse_pdf(pdf_path)
        except Exception:
            logger.exception("PDF parse error")
            await update.message.reply_text(
                "❌ Could not read this PDF. Make sure it's a Khatabook account statement."
            )
            return ConversationHandler.END
        if not transactions:
            await update.message.reply_text("❌ No transactions found in this PDF.")
            return ConversationHandler.END
        context.user_data[_TRANSACTIONS] = transactions
        context.user_data[_METADATA]     = metadata

    if raw == "ALL":
        codes = get_available_codes(transactions)
        context.user_data[_CODE] = "ALL"
        await update.message.reply_text(
            f"Will generate *{len(codes)}* separate PDFs — one per area code.\n\nChoose report type:",
            reply_markup=InlineKeyboardMarkup(_MODE_KEYBOARD),
            parse_mode="Markdown",
        )
        return WAIT_MODE

    matching = [t for t in transactions if t["area_code"] == raw]
    if not matching:
        codes = get_available_codes(transactions)
        await update.message.reply_text(
            f"❌ No transactions found for code *{raw}*.\n\nCodes present in this file: `{'  '.join(codes)}`",
            parse_mode="Markdown",
        )
        return WAIT_CODE

    context.user_data[_CODE] = raw
    await update.message.reply_text(
        f"✅ Found *{len(matching)}* transaction(s) for area code *{raw}*.\n\nChoose report type:",
        reply_markup=InlineKeyboardMarkup(_MODE_KEYBOARD),
        parse_mode="Markdown",
    )
    return WAIT_MODE


async def receive_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    mode         = query.data
    transactions = context.user_data.get(_TRANSACTIONS, [])
    metadata     = context.user_data.get(_METADATA, {})
    code         = context.user_data.get(_CODE, "")

    if code == "ALL":
        await _send_all_reports(query, transactions, metadata, mode)
    else:
        await _send_single_report(query, transactions, metadata, code, mode)

    # Release the temp PDF — transactions are still cached for restart
    pdf_path = context.user_data.pop(_PDF_PATH, None)
    if pdf_path and os.path.exists(pdf_path):
        try:
            os.unlink(pdf_path)
        except OSError:
            pass

    await query.message.reply_text(
        "Done! Send another PDF or tap below to generate a different report from the same data.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔄 Different code / report type", callback_data="restart")]]
        ),
    )
    return ConversationHandler.END


async def _send_single_report(query, transactions, metadata, code, mode):
    await query.edit_message_text(f"⚙️ Generating *{mode}* report for `{code}`…", parse_mode="Markdown")
    try:
        if mode == "grouped":
            pdf_bytes = generate_grouped_pdf(transactions, code, metadata)
            filename  = f"report_{code}_grouped.pdf"
            caption   = f"📊 *Grouped Summary* — Area Code: *{code}*"
        else:
            pdf_bytes = generate_detailed_pdf(transactions, code, metadata)
            filename  = f"report_{code}_detailed.pdf"
            caption   = f"📋 *Detailed Transactions* — Area Code: *{code}*"
    except Exception:
        logger.exception("Report generation error")
        await query.edit_message_text("❌ Failed to generate the report. Please try again.")
        return

    await query.message.reply_document(
        document=io.BytesIO(pdf_bytes),
        filename=filename,
        caption=caption,
        parse_mode="Markdown",
    )


async def _send_all_reports(query, transactions, metadata, mode):
    codes = get_available_codes(transactions)
    await query.edit_message_text(
        f"⚙️ Generating *{mode}* reports for all *{len(codes)}* area codes…",
        parse_mode="Markdown",
    )
    errors = []
    for code in codes:
        try:
            if mode == "grouped":
                pdf_bytes = generate_grouped_pdf(transactions, code, metadata)
                filename  = f"report_{code}_grouped.pdf"
                caption   = f"📊 *Grouped Summary* — Area Code: *{code}*"
            else:
                pdf_bytes = generate_detailed_pdf(transactions, code, metadata)
                filename  = f"report_{code}_detailed.pdf"
                caption   = f"📋 *Detailed Transactions* — Area Code: *{code}*"
            await query.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename=filename,
                caption=caption,
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception("Report generation error for code %s", code)
            errors.append(code)

    if errors:
        await query.message.reply_text(
            f"⚠️ Failed to generate reports for: `{'  '.join(errors)}`",
            parse_mode="Markdown",
        )


async def restart_same_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not context.user_data.get(_TRANSACTIONS):
        await query.edit_message_text("No data loaded. Please send a new PDF.")
        return ConversationHandler.END

    await query.edit_message_text(
        f"📋 *Available Area Codes:*\n`{_CODES_DISPLAY}`\n\nReply with an area code or `ALL`:",
        parse_mode="Markdown",
    )
    return WAIT_CODE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pdf_path = context.user_data.pop(_PDF_PATH, None)
    if pdf_path and os.path.exists(pdf_path):
        try:
            os.unlink(pdf_path)
        except OSError:
            pass
    await update.message.reply_text("Cancelled. Send a PDF whenever you're ready.")
    return ConversationHandler.END


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")

    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.PDF, receive_pdf)],
        states={
            WAIT_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code),
                CallbackQueryHandler(restart_same_pdf, pattern="^restart$"),
            ],
            WAIT_MODE: [CallbackQueryHandler(receive_mode, pattern="^(grouped|detailed)$")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(restart_same_pdf, pattern="^restart$"))

    logger.info("Bot started. Waiting for messages…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
