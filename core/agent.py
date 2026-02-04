import json
import urllib.request

from core.state import (
    STATE, snapshot, add_msg, add_evidence, add_artifact, add_action, set_risk,
    add_turn_reasoning,
    graph_add_indicator, graph_add_evidence, graph_add_artifact, graph_add_decision, graph_link, graph_add_turn_summary,
    mark_finished
)
from core.detector import detect_indicators
from core.evidence import evidence_items
from core.extractor import extract_all
from core.scorer import compute_score, map_verdict
from core.persona import Persona
from core.planner import next_goal

def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))

def _stop_condition(artifacts: list) -> bool:
    t = {a["type"] for a in artifacts}
    return ("url" in t) and ("upi" in t) and (("bank_account" in t) or ("ifsc" in t))

class AgentRuntime:
    def __init__(self):
        self.persona = Persona()

    def on_scammer_message(self, scammer_text: str):
        if STATE["finished"]:
            return

        # --- TURN START SNAPSHOT ---
        before = snapshot()
        risk_before = before["risk_score"]

        # 1) Add scammer message
        scam_turn = add_msg("SCAMMER", scammer_text)

        # 2) Detect indicators
        ind = detect_indicators(scammer_text)

        # 3) Evidence ledger updates + intel graph indicator/evidence nodes
        indicator_nodes = []
        evidence_nodes = []
        evidence_ids = []
        indicators_fired = [k for k, v in ind.items() if v]

        for name in indicators_fired:
            indicator_nodes.append(graph_add_indicator(scam_turn, name, meta={"source": "detector"}))

        for (name, rule_id, sev, why) in evidence_items(scam_turn, scammer_text, ind):
            ev_item = add_evidence(name, rule_id, sev, scam_turn, scammer_text, why)
            ev_node = graph_add_evidence(scam_turn, rule_id, sev, scammer_text, meta={"indicator": name})
            evidence_nodes.append(ev_node)
            evidence_ids.append(ev_node)

        # Link indicator -> evidence
        for i_node in indicator_nodes:
            for e_node in evidence_nodes:
                graph_link(scam_turn, i_node, e_node, "supports")

        # 4) Scam detection latch
        if any(ind.values()):
            STATE["scam_detected"] = True

        # 5) Extract artifacts from scammer message; update intel graph
        artifact_nodes = []
        artifact_ids = []
        extracted_now = []

        for (a_type, val, conf, ev) in extract_all(scam_turn, scammer_text):
            item = add_artifact(a_type, val, conf, scam_turn, ev)
            if item:
                extracted_now.append(item)
                a_node = graph_add_artifact(scam_turn, a_type, val, conf, meta={})
                artifact_nodes.append(a_node)
                artifact_ids.append(a_node)

                # evidence -> artifact linkage (same turn)
                for e_node in evidence_nodes:
                    graph_link(scam_turn, e_node, a_node, "extracts")

        # 6) Persona evolves based on latest scammer message
        self.persona.evolve(ind, scammer_text)

        # 7) Recompute risk + decision graph
        mid = snapshot()
        score = compute_score(mid["evidence_ledger"], mid["artifacts"])
        level, verdict = map_verdict(score, mid["artifacts"])
        set_risk(score, level, verdict, scam_detected=mid["scam_detected"])

        dec_node = graph_add_decision(scam_turn, score, level, verdict)
        # evidence/artifacts -> decision
        for e_node in evidence_nodes:
            graph_link(scam_turn, e_node, dec_node, "influences")
        for a_node in artifact_nodes:
            graph_link(scam_turn, a_node, dec_node, "escalates")

        # 8) If scam not detected yet, do not engage (honeypot engages after detection)
        if not mid["scam_detected"]:
            add_turn_reasoning(scam_turn, {
                "detected_indicators": indicators_fired,
                "evidence_added": len(evidence_nodes),
                "artifacts_extracted": [a["type"] for a in extracted_now],
                "risk_before": risk_before,
                "risk_after": score,
                "next_goal": None,
                "why_next": "Scam not detected yet; agent holds engagement."
            })
            graph_add_turn_summary({
                "turn_id": scam_turn,
                "indicators": indicators_fired,
                "evidence_ids": evidence_ids,
                "artifact_ids": artifact_ids,
                "risk_before": risk_before,
                "risk_after": score,
                "next_goal": None,
                "intent": None
            })
            return

        # 9) Stop if goals already satisfied (avoid repeating questions)
        if _stop_condition(mid["artifacts"]):
            self.finish("All required artifacts already collected.")
            return

        # 10) Goal replanning EVERY TURN
        goal, intent, why_next = next_goal(mid["artifacts"], ind, scammer_text)

        # Avoid repeating intent if already asked; force actual replanning
        if intent in mid["asked_intents"]:
            # hard pivot: if repeated, shift down the funnel
            if intent in ("ASK_LINK", "ASK_OFFICIAL_LINK"):
                goal, intent, why_next = ("GET_UPI_ID", "ASK_UPI", "Avoid repetition: pivot to UPI extraction.")
            elif intent in ("ASK_UPI", "ASK_UPI_FOR_FEE"):
                goal, intent, why_next = ("GET_BANK_DETAILS", "ASK_BANK", "Avoid repetition: pivot to bank/IFSC extraction.")

        if intent != "STOP" and intent not in STATE["asked_intents"]:
            STATE["asked_intents"].append(intent)

        # 11) Dynamic response generation (depends on last message + goals + artifacts + risk stage)
        agent_text = self.persona.compose(intent=intent, last_scammer_text=scammer_text, artifacts=mid["artifacts"], indicators=ind)

        # 12) Log per-turn reasoning trace (judge-visible)
        add_turn_reasoning(scam_turn, {
            "detected_indicators": indicators_fired,
            "evidence_added": len(evidence_nodes),
            "artifacts_extracted": [{"type": a["type"], "value": a["value"], "conf": a["confidence"]} for a in extracted_now],
            "risk_before": risk_before,
            "risk_after": score,
            "next_goal": goal,
            "intent": intent,
            "why_next": why_next,
            "intel_gap": self._intel_gap(mid["artifacts"]),
            "strategy_note": self._strategy_note(ind, mid["artifacts"])
        })

        # 13) Save turn summary in intel graph
        graph_add_turn_summary({
            "turn_id": scam_turn,
            "indicators": indicators_fired,
            "evidence_ids": evidence_ids,
            "artifact_ids": artifact_ids,
            "risk_before": risk_before,
            "risk_after": score,
            "next_goal": goal,
            "intent": intent
        })

        # 14) Emit agent action + message immediately (LIVE)
        STATE["step"] += 1
        add_action(STATE["step"], goal, intent, why_next, agent_text)
        add_msg("AGENT", agent_text)

        # 15) Optional: fully autonomous continuation when SIMULATED
        if STATE["mode"] == "SIMULATED":
            self.autonomous_step()

    def autonomous_step(self):
        # one-step simulated tick (agent -> scammer -> agent) to keep UI responsive
        if STATE["finished"]:
            return

        s = snapshot()
        if _stop_condition(s["artifacts"]):
            self.finish("Stop condition met.")
            return

        # last agent message
        last_agent = ""
        for m in reversed(s["transcript"]):
            if m["speaker"] == "AGENT":
                last_agent = m["text"]
                break

        resp = _post("http://127.0.0.1:5000/api/mock_scammer", {
            "session_id": s["session_id"],
            "mode": "SIMULATED",
            "agent_message": last_agent
        })
        scammer_text = resp.get("reply", "Proceed.")
        self.on_scammer_message(scammer_text)

    def _intel_gap(self, artifacts: list) -> str:
        t = {a["type"] for a in artifacts}
        missing = []
        if "url" not in t: missing.append("phishing_link")
        if "upi" not in t: missing.append("upi_id")
        if ("bank_account" not in t) and ("ifsc" not in t): missing.append("bank_ifsc")
        return "missing=" + ",".join(missing) if missing else "none"

    def _strategy_note(self, indicators: dict, artifacts: list) -> str:
        t = {a["type"] for a in artifacts}
        if indicators.get("threat_pressure") and "url" not in t:
            return "Threat spike → request official portal URL (lure) and calm tone."
        if "url" in t and "upi" not in t:
            return "Link obtained → pivot to payment rail (UPI)."
        if "upi" in t and (("bank_account" not in t) and ("ifsc" not in t)):
            return "Payment rail obtained → pivot to bank/IFSC via beneficiary lure."
        return "Maintain compliance tone; extract next missing artifact."

    def finish(self, reason: str):
        s = snapshot()
        final = {
            "case_id": s["case_id"],
            "session_id": s["session_id"],
            "final_assessment": {
                "scam_detected": s["scam_detected"],
                "risk_score": s["risk_score"],
                "risk_level": s["risk_level"],
                "verdict": s["verdict"],
            },
            "conversation_transcript": s["transcript"],
            "extracted_artifacts": s["artifacts"],
            "evidence_ledger": s["evidence_ledger"],
            "agent_actions": s["agent_actions"],
            "turn_reasoning": s["turn_reasoning"],
            "intel_graph": s["intel_graph"],
            "stopped_reason": reason
        }
        mark_finished(final)

RUNTIME = AgentRuntime()
