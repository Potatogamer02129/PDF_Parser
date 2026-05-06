# Khatabook Report Bot

A Telegram bot that turns a Khatabook account-statement PDF into clean,
area-code-filtered reports. Send it a PDF, pick an area code (or `ALL`), choose
between a **Grouped Summary** or a **Detailed Statement**, and get a polished
PDF back — complete with a running balance, totals, and Indian-rupee formatting.

---

## Features

- **Two report styles**
  - *Grouped Summary* — one row per party with totals and net balance.
  - *Detailed Statement* — every transaction with a running Dr/Cr balance
    column, plus header summary cards (count, total debit, total credit, net).
- **Area-code filtering** — pick one of the 3-letter codes detected in the PDF,
  or `ALL` to generate a separate PDF per code in one shot.
- **Indian-rupee formatting** with lakh/crore comma grouping (`₹14,95,493`).
- **Robust parsing** — handles month-header rows, multi-line party names, and
  city/code splits via pdfplumber.
- **Stateless polling** — long-poll only, no public ports needed, fits the
  free tier of any worker host.

---

## Project layout

| File              | Purpose                                                       |
| ----------------- | ------------------------------------------------------------- |
| `bot.py`          | Telegram conversation handler (PDF in → reports out).         |
| `parser.py`       | `pdfplumber`-based Khatabook statement parser.                |
| `report.py`       | `reportlab`-based PDF generation (grouped + detailed).        |
| `requirements.txt`| Pinned Python dependencies.                                   |
| `Procfile`        | `worker: python bot.py` — for Koyeb / Heroku-style platforms. |
| `.env.example`    | Template for the one required secret.                         |
| `EXAMPLE_PDF.pdf` | Sample input for local testing.                               |

---

## Local setup

Requires **Python 3.10+**.

```bash
git clone <your-repo-url>
cd PDF_Final

python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and paste the token you get from @BotFather on Telegram

python bot.py
```

You should see:

```
Bot started. Waiting for messages…
```

Open Telegram, find your bot, and send it a Khatabook PDF.

---

## How to use the bot

1. **`/start`** — get a welcome message.
2. **Send a Khatabook PDF** — the bot extracts transactions and shows the
   available area codes.
3. **Reply with a 3-letter code** (e.g. `WSL`) **or `ALL`**.
4. **Tap a button**:
   - 📊 *Grouped Summary* — one row per party.
   - 📋 *Detailed Transactions* — every entry with running balance.
5. The bot replies with the generated PDF(s).

You can tap **🔄 Different code / report type** to re-run on the same data
without re-uploading.

---

## Environment variables

| Variable             | Required | Description                          |
| -------------------- | -------- | ------------------------------------ |
| `TELEGRAM_BOT_TOKEN` | Yes      | Token from [@BotFather](https://t.me/BotFather). |

Locally these come from `.env`. **Never commit `.env`** — `.gitignore` already
excludes it.

---

## Adding new area codes

`bot.py` ships with a fixed list shown to users when a PDF is uploaded:

```python
KNOWN_AREA_CODES = ["ARJ", "BSR", "PGT", "PNG", "POD",
                    "SLF", "SLI", "VDR", "VPI", "WSL"]
```

The parser auto-detects whatever codes are present in the uploaded PDF, so
this list only affects the help text shown in chat. Edit it when new codes
appear in your Khatabook account.

---

## Customising the PDF look

All styling lives at the top of `report.py`:

- **Colours** — palette constants like `C_NAVY`, `C_DEBIT`, `C_CREDIT`, etc.
- **Fonts** — Ubuntu (with Helvetica fallback if Ubuntu isn't installed).
- **Layout** — column widths in millimetres for both report types.

The detailed report's transaction table uses these column widths
(must sum to 180 mm / page body width):

```
S.No 8  | Date 19 | Party 38 | City 15 | Bill 24 | Debit 24 | Credit 24 | Balance 28
```

---

## Troubleshooting

| Symptom                                            | Likely cause / fix                                                   |
| -------------------------------------------------- | -------------------------------------------------------------------- |
| `RuntimeError: TELEGRAM_BOT_TOKEN not set in .env` | `.env` missing or env var not set on the host.                       |
| `❌ Could not read this PDF.`                       | The PDF isn't a Khatabook account statement (different layout).      |
| Grand-total amount wraps in the cell               | Increase the relevant column width in `report.py` (must total 180mm).|
| Bot replies once then stops on the host            | Make sure it's deployed as a **worker**, not a web service.          |

---

## Tech stack

- [`python-telegram-bot`](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram client (async, polling).
- [`pdfplumber`](https://github.com/jsvine/pdfplumber) — PDF parsing.
- [`reportlab`](https://www.reportlab.com/) — PDF generation.
- [`python-dotenv`](https://github.com/theskumar/python-dotenv) — local `.env` loading.
