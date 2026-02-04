def compute_score(evidence_ledger: list, artifacts: list) -> int:
    score = 0
    for e in evidence_ledger:
        if e["severity"] == "HIGH": score += 30
        elif e["severity"] == "MEDIUM": score += 15
        else: score += 5

    types = {a["type"] for a in artifacts}
    if "url" in types: score += 15
    if "upi" in types: score += 20
    if "bank_account" in types or "ifsc" in types: score += 25

    return min(score, 100)

def map_verdict(score: int, artifacts: list):
    types = {a["type"] for a in artifacts}
    has_infra = any(t in types for t in ["url","upi","bank_account","ifsc"])

    if has_infra:
        if score >= 80: return ("CRITICAL", "SCAM")
        return ("HIGH", "SCAM")

    if score >= 80: return ("CRITICAL","SCAM")
    if score >= 60: return ("HIGH","SCAM")
    if score >= 40: return ("MEDIUM","SUSPICIOUS")
    return ("LOW","SAFE")
