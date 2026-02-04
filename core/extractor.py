import re

UPI_RE  = re.compile(r"\b[a-zA-Z0-9.\-_]{2,}@[a-zA-Z]{2,}\b")
URL_RE  = re.compile(r"https?://[^\s]+")
PHONE_RE= re.compile(r"\b\d{10}\b")
IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
ACC_RE  = re.compile(r"\b\d{9,18}\b")

BANK_HINTS = ["account","ifsc","bank","branch","beneficiary","a/c","acc","account no","ifsc code","name"]

def extract_all(turn_id: int, text: str):
    found = []
    for upi in UPI_RE.findall(text):
        found.append(("upi", upi, 0.90, text))
    for url in URL_RE.findall(text):
        found.append(("url", url, 0.90, text))
    for ph in PHONE_RE.findall(text):
        found.append(("phone", ph, 0.80, text))
    for ifsc in IFSC_RE.findall(text):
        found.append(("ifsc", ifsc, 0.85, text))

    lower = text.lower()
    if any(h in lower for h in BANK_HINTS):
        for acc in ACC_RE.findall(text):
            found.append(("bank_account", acc, 0.70, text))

    if "name" in lower and ":" in text:
        k, v = text.split(":", 1)
        if "name" in k.lower() and len(v.strip()) >= 3:
            found.append(("account_name", v.strip(), 0.60, text))

    return found
