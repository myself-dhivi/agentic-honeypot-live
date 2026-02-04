import random, secrets

def _pick(options):
    # secrets for better variability
    return secrets.choice(options)

class Persona:
    """
    Persona state persists across turns and affects message style.
    """
    def __init__(self):
        self.name = "Ravi"
        self.role = "Small business owner"
        self.anxiety = 0.2
        self.confusion = 0.3
        self.trust = 0.2
        self.last_topic = "general"

    def evolve(self, indicators: dict, last_scammer_text: str):
        t = (last_scammer_text or "").lower()

        if "kyc" in t: self.last_topic = "kyc"
        elif any(k in t for k in ["reward","prize","won","gift"]): self.last_topic = "reward"
        elif any(k in t for k in ["delivery","courier","parcel"]): self.last_topic = "delivery"
        else: self.last_topic = "general"

        if indicators.get("threat_pressure"): self.anxiety = min(1.0, self.anxiety + 0.25)
        if indicators.get("urgency"): self.anxiety = min(1.0, self.anxiety + 0.10)
        if indicators.get("payment_request"): self.confusion = min(1.0, self.confusion + 0.10)

        # crude trust heuristic: if scammer provided link/upi/bank, trust rises slightly (victim compliance)
        if indicators.get("link_shared") or indicators.get("payment_request"):
            self.trust = min(1.0, self.trust + 0.05)

    def tone(self):
        if self.anxiety > 0.70: return "panicked"
        if self.confusion > 0.55: return "confused"
        return "neutral"

    def opener(self):
        t = self.tone()
        if t == "panicked":
            return _pick([
                "Please don't block it, I'm trying.",
                "I don't want any problem, I'm doing it now.",
                "Okay okay, please wait—I'm trying to do it."
            ]) + " "
        if t == "confused":
            return _pick([
                "Sorry, I'm a bit confused.",
                "I don't understand fully.",
                "I'm not very familiar with this."
            ]) + " "
        return _pick(["Okay.", "Alright.", "Sure."]) + " "

    def compose(self, intent: str, last_scammer_text: str, artifacts: list, indicators: dict) -> str:
        """
        Dynamic response generation:
        - references last message topic (KYC/reward/delivery)
        - changes tone with threat/urgency
        - uses 'lures' to force scammer to reveal intel
        - avoids repeating already collected artifacts
        """
        topic = self.last_topic
        pre = self.opener()

        have = {a["type"] for a in artifacts}
        mention = ""

        if topic == "kyc":
            mention = _pick([
                "About the KYC update you said, ",
                "Regarding KYC, ",
                "For the KYC thing, "
            ])
        elif topic == "reward":
            mention = _pick([
                "About the reward, ",
                "For the prize claim, ",
                "Regarding the reward message, "
            ])
        elif topic == "delivery":
            mention = _pick([
                "About the delivery, ",
                "For the parcel, ",
                "Regarding the courier, "
            ])

        # Intent-driven, but text is dynamic using last scammer msg and state
        if intent == "ASK_OFFICIAL_LINK":
            # lure: insist on "official" portal and full URL
            return pre + mention + _pick([
                "my phone shows a warning. Can you send the exact official link again (full URL)?",
                "I need the official portal link. Please share the complete URL in one message.",
                "It says 'unsafe site'. Please send the correct official verification link."
            ])

        if intent == "ASK_LINK":
            return pre + mention + _pick([
                "the link is not opening on my phone. Can you send the full link again?",
                "it opens blank. Please resend the complete link.",
                "I can’t see the full link here. Can you share it properly?"
            ])

        if intent == "ASK_UPI_FOR_FEE":
            # context: KYC scams often ask fee/fine
            if "upi" in have:
                # do not ask UPI again; pivot to bank
                return pre + "My bank app is asking beneficiary details. Is there an account number + IFSC option?"
            return pre + mention + _pick([
                "is there any fee/fine for this? If yes, please share the UPI ID clearly.",
                "you said update within hours—do I need to pay anything? Share the UPI handle please.",
                "if payment is required, please type the exact UPI ID (no short form)."
            ])

        if intent == "ASK_UPI":
            if "upi" in have:
                return pre + "I already noted the UPI. Is there a bank account + IFSC option also?"
            return pre + mention + _pick([
                "my UPI app needs the exact UPI ID. Please type it clearly once.",
                "I’m not familiar with UPI. Please send the UPI ID in text.",
                "please share the UPI handle clearly so I can proceed."
            ])

        if intent == "ASK_BANK":
            if ("bank_account" in have) or ("ifsc" in have):
                return pre + "I got the bank details. Can you confirm the beneficiary name as it should appear?"
            # lure: “beneficiary add” forces account+IFSC+name
            return pre + mention + _pick([
                "to add beneficiary, I need account number, IFSC, and beneficiary name. Please send all three.",
                "my bank app asks account number + IFSC + name. Please share it in one message.",
                "I can only do bank transfer. Send account number, IFSC and name."
            ])

        # fallback
        if indicators.get("threat_pressure"):
            return pre + _pick([
                "I'm doing it right now. Please guide step-by-step.",
                "Please wait—I'm trying. What should I do first?"
            ])

        return pre + "Please tell me what I should do next."
