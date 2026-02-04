def types(artifacts: list) -> set:
    return {a["type"] for a in artifacts}

def scenario_from_text(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["kyc", "aadhaar", "pan", "bank update", "verify kyc", "account will be blocked"]):
        return "KYC_THREAT"
    if any(k in t for k in ["reward", "prize", "won", "gift", "lottery"]):
        return "REWARD"
    if any(k in t for k in ["delivery", "courier", "shipment", "parcel"]):
        return "DELIVERY"
    return "GENERIC"

def next_goal(artifacts: list, indicators: dict, last_scammer_text: str):
    t = types(artifacts)
    scn = scenario_from_text(last_scammer_text)

    # Required intelligence: URL + UPI + (BANK/IFSC)
    need_url = "url" not in t
    need_upi = "upi" not in t
    need_bank = ("bank_account" not in t) and ("ifsc" not in t)

    # Pivot: if threat pressure spikes, first stabilize victim persona + request "official" link (lure)
    if indicators.get("threat_pressure") and need_url:
        return ("DEESCALATE_THREAT", "ASK_OFFICIAL_LINK",
                f"Threat detected in {scn}; stabilize tone and request official KYC/verification link.")

    # Standard replanning based on missing artifacts
    if need_url:
        if scn == "KYC_THREAT":
            return ("GET_PHISHING_LINK", "ASK_OFFICIAL_LINK", "KYC scenario: ask for official portal link/URL.")
        return ("GET_PHISHING_LINK", "ASK_LINK", "Need phishing link (delivery vector).")

    if need_upi:
        # After link, move to payment rail
        if scn == "KYC_THREAT":
            return ("GET_UPI_ID", "ASK_UPI_FOR_FEE", "KYC scenario: ask about any fee and UPI handle.")
        return ("GET_UPI_ID", "ASK_UPI", "Need UPI (payment rail).")

    if need_bank:
        return ("GET_BANK_DETAILS", "ASK_BANK", "Need bank account/IFSC (alternate rail).")

    return ("DONE", "STOP", "All required artifacts collected.")
