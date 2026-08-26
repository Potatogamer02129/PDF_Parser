import pdfplumber
import re


def _parse_amount(cell) -> float:
    s = str(cell or "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_pdf(path: str):
    """Parse a Khatabook account statement PDF.

    Returns (transactions, metadata).
    transactions: list of dicts with keys date, party_name, area_code, details, debit, credit.
    metadata: dict with keys account, date_range.
    """
    transactions = []
    current_year = None
    prev_month_idx = -1
    _MONTH_IDX = {'Jan':0,'Feb':1,'Mar':2,'Apr':3,'May':4,'Jun':5,
                  'Jul':6,'Aug':7,'Sep':8,'Oct':9,'Nov':10,'Dec':11}
    metadata = {"account": "", "date_range": ""}

    with pdfplumber.open(path) as pdf:
        # Metadata from first page text
        first_text = pdf.pages[0].extract_text() or ""
        acc_match = re.search(r"(\+\d{10,13})", first_text)
        if acc_match:
            metadata["account"] = acc_match.group(1)
        dr_match = re.search(
            r"\((\d{2} \w+ \d{4}) - (\d{2} \w+ \d{4})\)", first_text
        )
        if dr_match:
            metadata["date_range"] = f"{dr_match.group(1)} - {dr_match.group(2)}"

        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cell0 = str(row[0] or "").strip()
                    if not cell0:
                        continue

                    # Month/year header e.g. "April 2023", "Februrary 2024"
                    month_match = re.match(r"[A-Za-z]+\s+(\d{4})$", cell0)
                    if month_match:
                        current_year = int(month_match.group(1))
                        prev_month_idx = -1
                        continue

                    # Skip column headers and total rows
                    if "Total" in cell0 or cell0 in ("Date", "Name", "Details"):
                        continue

                    # Transaction date e.g. "08 Apr"
                    date_match = re.match(r"(\d{2}) ([A-Z][a-z]{2})$", cell0)
                    if not date_match:
                        continue

                    day = date_match.group(1)
                    month_abbr = date_match.group(2)

                    # Auto-increment year when months roll backward (e.g. Dec → Jan)
                    mi = _MONTH_IDX.get(month_abbr, -1)
                    if current_year and mi >= 0 and prev_month_idx >= 0 and mi < prev_month_idx:
                        current_year += 1
                    if mi >= 0:
                        prev_month_idx = mi

                    date_str = f"{day} {month_abbr} {current_year or ''}"

                    # Parse name cell: "PARTY NAME | CITY | CODE" (newlines act as delimiters)
                    name_raw = str(row[1] or "")
                    parts = [p.replace("\n", " ").strip() for p in name_raw.split("|")]
                    non_empty = [p for p in parts if p]

                    if not non_empty:
                        continue

                    # Area code is always the last pipe-delimited segment (3 uppercase letters)
                    last_part = non_empty[-1].strip()
                    if re.match(r"^[A-Z]{3}$", last_part):
                        code = last_part
                    else:
                        # Fallback: last 3-letter uppercase word in the name
                        matches = re.findall(r"\b[A-Z]{3}\b", name_raw.replace("\n", " "))
                        code = matches[-1] if matches else "UNK"

                    # Party name and city from segments before the code
                    if len(non_empty) >= 3:
                        party_name = " ".join(non_empty[:-2])
                        city = non_empty[-2]
                    elif len(non_empty) == 2:
                        party_name = non_empty[0]
                        city = non_empty[1]
                    else:
                        party_name = code
                        city = ""

                    transactions.append(
                        {
                            "date": date_str,
                            "party_name": party_name,
                            "city": city,
                            "area_code": code,
                            "details": str(row[2] or "").replace("\n", " ").strip(),
                            "debit": _parse_amount(row[3]),
                            "credit": _parse_amount(row[4]),
                        }
                    )

    return transactions, metadata


def get_available_codes(transactions: list) -> list:
    return sorted(set(t["area_code"] for t in transactions))
