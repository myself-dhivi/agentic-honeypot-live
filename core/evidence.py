RULES = {
    "urgency": ("URG_01","MEDIUM","Urgency reduces victim thinking time and increases compliance."),
    "payment_request": ("PAY_01","HIGH","Payment requests are a strong fraud indicator."),
    "threat_pressure": ("THR_01","HIGH","Threats/pressure are commonly used to coerce victims."),
    "link_shared": ("LNK_01","HIGH","Links are often used for phishing and credential theft."),
    "contact_request": ("CNT_01","MEDIUM","Moving off-platform reduces traceability and increases risk.")
}

def evidence_items(turn_id: int, text: str, indicators: dict):
    out = []
    for k, detected in indicators.items():
        if not detected: 
            continue
        rule_id, sev, why = RULES.get(k, ("GEN_00","LOW","Heuristic rule."))
        out.append((k, rule_id, sev, why))
    return out
