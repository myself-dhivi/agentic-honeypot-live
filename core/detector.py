def detect_indicators(text: str) -> dict:
    t = text.lower()
    return {
        "urgency": any(k in t for k in ["urgent","immediately","act now","today","fast","don’t wait","don't wait"]),
        "payment_request": any(k in t for k in ["pay","payment","fee","processing","transfer","send money","upi"]),
        "threat_pressure": any(k in t for k in ["cancelled","blocked","lose","suspended","legal action","police"]),
        "link_shared": any(k in t for k in ["http://","https://","www."]),
        "contact_request": any(k in t for k in ["phone","number","call","whatsapp","contact"])
    }
