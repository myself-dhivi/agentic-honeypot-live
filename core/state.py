import time, uuid, queue, threading, hashlib

def ts(): return time.strftime("%Y-%m-%d %H:%M:%S")

LOCK = threading.Lock()
EVENTS = queue.Queue()  # SSE events

def _id(prefix: str, content: str) -> str:
    h = hashlib.md5(content.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{h}"

STATE = {
    "case_id": f"CASE-{uuid.uuid4().hex[:8].upper()}",
    "session_id": uuid.uuid4().hex,
    "finished": False,
    "mode": "HUMAN",  # HUMAN or SIMULATED

    "risk_score": 0,
    "risk_level": "LOW",
    "verdict": "SAFE",
    "scam_detected": False,

    "transcript": [],

    "evidence_ledger": [],
    "artifacts": [],
    "agent_actions": [],

    "asked_intents": [],
    "step": 0,
    "max_turns": 20,

    # NEW: per-turn explicit reasoning (judge-visible)
    "turn_reasoning": [],

    # NEW: evolving intelligence graph (indicator -> evidence -> artifact -> decision)
    "intel_graph": {
        "nodes": [],   # {id,type,label,turn_id,meta}
        "edges": [],   # {src,dst,rel,turn_id,meta}
        "turns": []    # {turn_id, indicators, evidence_ids, artifact_ids, risk_before, risk_after, next_goal, intent}
    },

    "final_report": None,
}

def push_event(event_type: str, payload: dict):
    EVENTS.put({"type": event_type, "payload": payload, "ts": ts()})

def reset_state():
    with LOCK:
        STATE["case_id"] = f"CASE-{uuid.uuid4().hex[:8].upper()}"
        STATE["session_id"] = uuid.uuid4().hex
        STATE["finished"] = False
        STATE["mode"] = "HUMAN"

        STATE["risk_score"] = 0
        STATE["risk_level"] = "LOW"
        STATE["verdict"] = "SAFE"
        STATE["scam_detected"] = False

        STATE["transcript"] = []
        STATE["evidence_ledger"] = []
        STATE["artifacts"] = []
        STATE["agent_actions"] = []
        STATE["asked_intents"] = []
        STATE["step"] = 0
        STATE["max_turns"] = 20
        STATE["turn_reasoning"] = []

        STATE["intel_graph"] = {"nodes": [], "edges": [], "turns": []}
        STATE["final_report"] = None

def snapshot():
    with LOCK:
        out = {}
        for k, v in STATE.items():
            if isinstance(v, list):
                out[k] = list(v)
            elif isinstance(v, dict):
                out[k] = v.copy()
            else:
                out[k] = v
        # deep copy nested graph
        out["intel_graph"] = {
            "nodes": list(STATE["intel_graph"]["nodes"]),
            "edges": list(STATE["intel_graph"]["edges"]),
            "turns": list(STATE["intel_graph"]["turns"]),
        }
        return out

def add_msg(speaker: str, text: str) -> int:
    with LOCK:
        turn_id = len(STATE["transcript"]) + 1
        item = {"turn_id": turn_id, "speaker": speaker, "text": text, "ts": ts()}
        STATE["transcript"].append(item)
    push_event("message", item)
    return turn_id

def add_evidence(indicator, rule_id, severity, turn_id, text, why):
    item = {
        "indicator": indicator, "rule_id": rule_id, "severity": severity,
        "turn_id": turn_id, "text": text, "why": why, "ts": ts()
    }
    with LOCK:
        STATE["evidence_ledger"].append(item)
    push_event("evidence", item)
    return item

def add_artifact(a_type, value, confidence, turn_id, evidence):
    with LOCK:
        for a in STATE["artifacts"]:
            if a["type"] == a_type and a["value"] == value:
                return None
        item = {
            "type": a_type, "value": value, "confidence": float(confidence),
            "turn_id": turn_id, "evidence": evidence, "ts": ts()
        }
        STATE["artifacts"].append(item)
    push_event("artifact", item)
    return item

def add_action(step, goal, intent, reasoning, message):
    item = {"step": step, "goal": goal, "intent": intent, "reasoning": reasoning, "message": message, "ts": ts()}
    with LOCK:
        STATE["agent_actions"].append(item)
    push_event("action", item)
    return item

def set_risk(score, level, verdict, scam_detected=None):
    with LOCK:
        STATE["risk_score"] = int(score)
        STATE["risk_level"] = level
        STATE["verdict"] = verdict
        if scam_detected is not None:
            STATE["scam_detected"] = bool(scam_detected)
        payload = {"risk_score": int(score), "risk_level": level, "verdict": verdict, "scam_detected": STATE["scam_detected"]}
    push_event("risk", payload)

def add_turn_reasoning(turn_id: int, item: dict):
    item2 = {"turn_id": turn_id, "ts": ts(), **item}
    with LOCK:
        STATE["turn_reasoning"].append(item2)
    push_event("reasoning", item2)

# -------- INTEL GRAPH HELPERS --------
def _ensure_node(node):
    with LOCK:
        exists = any(n["id"] == node["id"] for n in STATE["intel_graph"]["nodes"])
        if not exists:
            STATE["intel_graph"]["nodes"].append(node)

def _ensure_edge(edge):
    with LOCK:
        exists = any((e["src"], e["dst"], e["rel"], e["turn_id"]) == (edge["src"], edge["dst"], edge["rel"], edge["turn_id"])
                     for e in STATE["intel_graph"]["edges"])
        if not exists:
            STATE["intel_graph"]["edges"].append(edge)

def graph_add_indicator(turn_id: int, indicator: str, meta=None):
    nid = _id("IND", f"{turn_id}:{indicator}")
    _ensure_node({"id": nid, "type": "indicator", "label": indicator, "turn_id": turn_id, "meta": meta or {}})
    push_event("graph", {"op": "node", "node_id": nid})
    return nid

def graph_add_evidence(turn_id: int, rule_id: str, severity: str, text: str, meta=None):
    label = f"{rule_id}:{severity}"
    nid = _id("EVD", f"{turn_id}:{label}:{text[:50]}")
    _ensure_node({"id": nid, "type": "evidence", "label": label, "turn_id": turn_id, "meta": {"snippet": text[:120], **(meta or {})}})
    push_event("graph", {"op": "node", "node_id": nid})
    return nid

def graph_add_artifact(turn_id: int, a_type: str, value: str, conf: float, meta=None):
    label = f"{a_type}:{value}"
    nid = _id("ART", f"{turn_id}:{label}")
    _ensure_node({"id": nid, "type": "artifact", "label": label, "turn_id": turn_id, "meta": {"confidence": conf, **(meta or {})}})
    push_event("graph", {"op": "node", "node_id": nid})
    return nid

def graph_add_decision(turn_id: int, risk_score: int, risk_level: str, verdict: str):
    label = f"{verdict}:{risk_level}:{risk_score}"
    nid = _id("DEC", f"{turn_id}:{label}")
    _ensure_node({"id": nid, "type": "decision", "label": label, "turn_id": turn_id, "meta": {"risk_score": risk_score, "risk_level": risk_level, "verdict": verdict}})
    push_event("graph", {"op": "node", "node_id": nid})
    return nid

def graph_link(turn_id: int, src: str, dst: str, rel: str, meta=None):
    edge = {"src": src, "dst": dst, "rel": rel, "turn_id": turn_id, "meta": meta or {}}
    _ensure_edge(edge)
    push_event("graph", {"op": "edge", "rel": rel})

def graph_add_turn_summary(summary: dict):
    with LOCK:
        STATE["intel_graph"]["turns"].append(summary)
    push_event("graph", {"op": "turn", "turn_id": summary.get("turn_id")})

def mark_finished(final_report: dict):
    with LOCK:
        STATE["finished"] = True
        STATE["final_report"] = final_report
    push_event("finished", {"ok": True})
