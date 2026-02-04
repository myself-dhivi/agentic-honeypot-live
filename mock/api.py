import random

SESS = {}

def _get(session_id: str):
    if session_id not in SESS:
        SESS[session_id] = {
            "stage": "HOOK",
            "upi": "luckyprize@upi",
            "url": "http://verify-reward.example.com",
            "acc": "123456789012",
            "ifsc": "HDFC0AB1234",
            "name": "R Kumar",
        }
    return SESS[session_id]

def process_human_message(session_id: str, scammer_message: str) -> str:
    # HUMAN mode: treat user message as the scammer message, but still "API-processed"
    # This satisfies: "agent interacts via Mock Scammer API"
    return scammer_message or ""

def simulated_reply(session_id: str, agent_message: str) -> str:
    s = _get(session_id)
    m = (agent_message or "").lower()

    if random.random() < 0.12:
        return "Why so many questions? If you want reward, follow instructions fast."

    if "link" in m:
        s["stage"] = "VERIFY"
        return f"Here is the verification link: {s['url']} Open it and enter your details."
    if "upi" in m:
        s["stage"] = "PAY"
        return f"Send processing fee now. UPI: {s['upi']}. After payment you will receive reward."
    if "ifsc" in m or "account" in m or "beneficiary" in m:
        s["stage"] = "BANK"
        return f"Bank transfer possible. Account: {s['acc']}, IFSC: {s['ifsc']}, Name: {s['name']}."

    if s["stage"] == "HOOK":
        return "You are selected for reward. To confirm, complete verification today."
    if s["stage"] == "VERIFY":
        return "After verification, you must pay a small fee quickly."
    if s["stage"] == "PAY":
        return "Payment pending. If you delay, reward will be cancelled."
    return "Proceed fast."
