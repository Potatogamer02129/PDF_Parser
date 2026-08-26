import io
import logging
import os
import tempfile
from datetime import datetime

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
from report import (
    generate_analysis_pdf,
    generate_detailed_pdf,
    generate_full_sales_pdf,
    generate_grouped_pdf,
    generate_outstanding_analysis_pdf,
    generate_outstanding_pdf,
    generate_payment_analysis_pdf,
    generate_payment_only_pdf,
    generate_sales_only_pdf,
)

load_dotenv()
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

WAIT_CODE, WAIT_MODE, WAIT_DATE = range(3)

_TRANSACTIONS = "transactions"
_METADATA     = "metadata"
_CODE         = "area_code"
_PDF_PATH     = "pdf_path"

# Fixed area codes — update this list if new codes are added
KNOWN_AREA_CODES = ["ARJ", "BSR", "PGT", "PNG", "POD", "SLF", "SLI", "VDR", "VPI", "WSL"]
_CODES_DISPLAY   = "  •  ".join(KNOWN_AREA_CODES)

# Buttons shown immediately after PDF upload (whole-PDF, no area code needed)
_PDF_ACTION_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔍 Full PDF Sale Filter", callback_data="fullsales"),
        InlineKeyboardButton("📈 Analyse All Codes",    callback_data="analyse"),
    ]
])

# Buttons shown after area code is selected
_MODE_KEYBOARD = [
    [
        InlineKeyboardButton("📊 Grouped Summary",        callback_data="grouped"),
        InlineKeyboardButton("📋 Detailed Transactions",  callback_data="detailed"),
    ],
    [
        InlineKeyboardButton("💰 Sales Only",             callback_data="sales"),
        InlineKeyboardButton("💳 Payment Only",           callback_data="payment"),
    ],
    [
        InlineKeyboardButton("🪔 Pre-Diwali Outstanding", callback_data="outstanding"),
    ],
]


def _parse_user_date(text: str) -> datetime | None:
    for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


async def _ensure_parsed(context: ContextTypes.DEFAULT_TYPE) -> tuple[list, dict] | None:
    """Parse the PDF if not already done. Returns (transactions, metadata) or None on failure."""
    transactions = context.user_data.get(_TRANSACTIONS)
    metadata     = context.user_data.get(_METADATA)
    if transactions is not None:
        return transactions, metadata
    pdf_path = context.user_data.get(_PDF_PATH)
    if not pdf_path or not os.path.exists(pdf_path):
        return None
    try:
        transactions, metadata = parse_pdf(pdf_path)
    except Exception:
        logger.exception("PDF parse error")
        return None
    if not transactions:
        return None
    context.user_data[_TRANSACTIONS] = transactions
    context.user_data[_METADATA]     = metadata
    return transactions, metadata


def _cleanup_pdf(context: ContextTypes.DEFAULT_TYPE) -> None:
    pdf_path = context.user_data.pop(_PDF_PATH, None)
    if pdf_path and os.path.exists(pdf_path):
        try:
            os.unlink(pdf_path)
        except OSError:
            pass


def _done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔄 Different code / report type", callback_data="restart")]]
    )


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
    _cleanup_pdf(context)
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
        "Reply with a *3-letter area code* (e.g. `WSL`) or `ALL` for area-wise reports.\n\n"
        "Or tap a button below for a whole-PDF report:",
        parse_mode="Markdown",
        reply_markup=_PDF_ACTION_KEYBOARD,
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

    # Outstanding needs a date — ask for it before generating
    if mode == "outstanding":
        await query.edit_message_text(
            f"📅 *Pre-Diwali Outstanding* — Area Code: *{code}*\n\n"
            "Enter the cutoff date (e.g. `15 Oct 2024` or `15/10/2024`):\n\n"
            "All sales *before* this date, minus *all* payments received, will show the remaining balance.",
            parse_mode="Markdown",
        )
        return WAIT_DATE

    if code == "ALL":
        await _send_all_reports(query, transactions, metadata, mode)
    else:
        await _send_single_report(query, transactions, metadata, code, mode)

    _cleanup_pdf(context)

    await query.message.reply_text(
        "Done! Send another PDF or tap below to generate a different report from the same data.",
        reply_markup=_done_keyboard(),
    )
    return ConversationHandler.END


async def receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cutoff = _parse_user_date(update.message.text.strip())
    if cutoff is None:
        await update.message.reply_text(
            "⚠️ Couldn't parse that date. Try formats like `15 Oct 2024` or `15/10/2024`.",
            parse_mode="Markdown",
        )
        return WAIT_DATE

    if cutoff >= datetime.now():
        await update.message.reply_text(
            f"⚠️ That date (`{cutoff.strftime('%d %b %Y')}`) is today or in the future — "
            "so *all* sales will be counted, which gives you the full total.\n\n"
            "Please enter a *past* date, e.g. `20 Oct 2025` for Diwali 2025.",
            parse_mode="Markdown",
        )
        return WAIT_DATE

    transactions = context.user_data.get(_TRANSACTIONS, [])
    metadata     = context.user_data.get(_METADATA, {})
    code         = context.user_data.get(_CODE, "")
    cutoff_label = cutoff.strftime("%d %b %Y")

    await update.message.reply_text(
        f"⚙️ Calculating outstanding before *{cutoff_label}*…",
        parse_mode="Markdown",
    )

    if code == "ALL":
        codes  = get_available_codes(transactions)
        errors = []
        sent   = 0
        for c in codes:
            try:
                pdf_bytes = generate_outstanding_pdf(transactions, c, cutoff, metadata)
                await update.message.reply_document(
                    document=io.BytesIO(pdf_bytes),
                    filename=f"report_{c}_outstanding_{cutoff.strftime('%d%b%Y')}.pdf",
                    caption=f"🪔 *Pre-Diwali Outstanding* — Code: *{c}* — Before: *{cutoff_label}*",
                    parse_mode="Markdown",
                )
                sent += 1
            except ValueError:
                pass
            except Exception:
                logger.exception("Outstanding report error for %s", c)
                errors.append(c)
        if sent == 0:
            await update.message.reply_text(
                f"ℹ️ No outstanding payments found for any area code before *{cutoff_label}*.",
                parse_mode="Markdown",
            )
        if errors:
            await update.message.reply_text(
                f"⚠️ Failed to generate for: `{'  '.join(errors)}`",
                parse_mode="Markdown",
            )
    else:
        try:
            pdf_bytes = generate_outstanding_pdf(transactions, code, cutoff, metadata)
            await update.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename=f"report_{code}_outstanding_{cutoff.strftime('%d%b%Y')}.pdf",
                caption=f"🪔 *Pre-Diwali Outstanding* — Area Code: *{code}* — Before: *{cutoff_label}*",
                parse_mode="Markdown",
            )
        except ValueError as e:
            await update.message.reply_text(f"ℹ️ {e}")
            return ConversationHandler.END
        except Exception:
            logger.exception("Outstanding report error")
            await update.message.reply_text("❌ Failed to generate the report. Please try again.")
            return ConversationHandler.END

    _cleanup_pdf(context)

    await update.message.reply_text(
        "Done! Send another PDF or tap below to generate a different report from the same data.",
        reply_markup=_done_keyboard(),
    )
    return ConversationHandler.END


async def receive_full_sales(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⚙️ Parsing PDF and building full sale filter…")

    result = await _ensure_parsed(context)
    if result is None:
        await query.edit_message_text("❌ Could not read the PDF. Please send it again.")
        return ConversationHandler.END
    transactions, metadata = result

    try:
        pdf_bytes = generate_full_sales_pdf(transactions, metadata)
    except Exception:
        logger.exception("Full sales report error")
        await query.edit_message_text("❌ Failed to generate the report. Please try again.")
        return ConversationHandler.END

    await query.message.reply_document(
        document=io.BytesIO(pdf_bytes),
        filename="report_full_sale_filter.pdf",
        caption="🔍 *Full PDF Sale Filter* — All debit entries across all area codes",
        parse_mode="Markdown",
    )

    _cleanup_pdf(context)

    await query.message.reply_text(
        "Done! Send another PDF or tap below to generate a different report from the same data.",
        reply_markup=_done_keyboard(),
    )
    return ConversationHandler.END


async def receive_analyse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⚙️ Parsing PDF and building analysis…")

    result = await _ensure_parsed(context)
    if result is None:
        await query.edit_message_text("❌ Could not read the PDF. Please send it again.")
        return ConversationHandler.END
    transactions, metadata = result

    errors = []

    try:
        pdf_bytes = generate_analysis_pdf(transactions, metadata)
        await query.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename="report_sales_analysis.pdf",
            caption="📈 *Sales Analysis* — Total sales grouped by area code",
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Sales analysis report error")
        errors.append("sales analysis")

    try:
        pdf_bytes = generate_payment_analysis_pdf(transactions, metadata)
        await query.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename="report_payment_analysis.pdf",
            caption="📈 *Payment Analysis* — Total payments grouped by area code",
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Payment analysis report error")
        errors.append("payment analysis")

    try:
        pdf_bytes = generate_outstanding_analysis_pdf(transactions, metadata)
        await query.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename="report_outstanding_analysis.pdf",
            caption="📈 *Outstanding Analysis* — Net outstanding (Sales − Payments) by area code",
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Outstanding analysis report error")
        errors.append("outstanding analysis")

    if errors:
        await query.message.reply_text(
            f"⚠️ Failed to generate: {', '.join(errors)}",
            parse_mode="Markdown",
        )

    _cleanup_pdf(context)

    await query.message.reply_text(
        "Done! Send another PDF or tap below to generate a different report from the same data.",
        reply_markup=_done_keyboard(),
    )
    return ConversationHandler.END


async def _send_single_report(query, transactions, metadata, code, mode):
    await query.edit_message_text(f"⚙️ Generating *{mode}* report for `{code}`…", parse_mode="Markdown")
    try:
        if mode == "grouped":
            pdf_bytes = generate_grouped_pdf(transactions, code, metadata)
            filename  = f"report_{code}_grouped.pdf"
            caption   = f"📊 *Grouped Summary* — Area Code: *{code}*"
        elif mode == "sales":
            pdf_bytes = generate_sales_only_pdf(transactions, code, metadata)
            filename  = f"report_{code}_sales.pdf"
            caption   = f"💰 *Sales Only* — Area Code: *{code}*"
        elif mode == "payment":
            pdf_bytes = generate_payment_only_pdf(transactions, code, metadata)
            filename  = f"report_{code}_payments.pdf"
            caption   = f"💳 *Payment Only* — Area Code: *{code}*"
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
            elif mode == "sales":
                pdf_bytes = generate_sales_only_pdf(transactions, code, metadata)
                filename  = f"report_{code}_sales.pdf"
                caption   = f"💰 *Sales Only* — Area Code: *{code}*"
            elif mode == "payment":
                pdf_bytes = generate_payment_only_pdf(transactions, code, metadata)
                filename  = f"report_{code}_payments.pdf"
                caption   = f"💳 *Payment Only* — Area Code: *{code}*"
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
        f"📋 *Available Area Codes:*\n`{_CODES_DISPLAY}`\n\n"
        "Reply with an area code or `ALL` for area-wise reports.\n\n"
        "Or tap a button below for a whole-PDF report:",
        parse_mode="Markdown",
        reply_markup=_PDF_ACTION_KEYBOARD,
    )
    return WAIT_CODE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _cleanup_pdf(context)
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
                CallbackQueryHandler(receive_full_sales, pattern="^fullsales$"),
                CallbackQueryHandler(receive_analyse,    pattern="^analyse$"),
            ],
            WAIT_MODE: [
                CallbackQueryHandler(receive_mode, pattern="^(grouped|detailed|sales|payment|outstanding)$"),
            ],
            WAIT_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_date),
            ],
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
