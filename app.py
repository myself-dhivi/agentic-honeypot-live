from flask import Flask, request, jsonify, render_template, Response
import json, time

from core.state import snapshot, reset_state, EVENTS, push_event, STATE
from core.agent import RUNTIME
from mock.api import process_human_message, simulated_reply

app = Flask(__name__)

@app.get("/")
def home():
    return render_template("index.html")

# --- SSE stream for live updates (no refresh) ---
@app.get("/api/stream")
def stream():
    def event_gen():
        while True:
            ev = EVENTS.get()
            yield f"data: {json.dumps(ev)}\n\n"
    return Response(event_gen(), mimetype="text/event-stream")

@app.get("/api/state")
def api_state():
    return jsonify(snapshot())

@app.post("/api/reset")
def api_reset():
    reset_state()
    push_event("reset", {"ok": True})
    return jsonify({"ok": True})

@app.post("/api/mode")
def api_mode():
    payload = request.get_json(force=True)
    mode = (payload.get("mode") or "HUMAN").upper()
    STATE["mode"] = "SIMULATED" if mode == "SIMULATED" else "HUMAN"
    push_event("mode", {"mode": STATE["mode"]})
    return jsonify({"ok": True, "mode": STATE["mode"]})

# --- USER (scammer) sends message here ---
@app.post("/api/scammer_message")
def scammer_message():
    payload = request.get_json(force=True)
    text = payload.get("text", "")

    # Mandatory: route scammer message through Mock Scammer API (HUMAN mode)
    processed = process_human_message(session_id=STATE["session_id"], scammer_message=text)

    # Agent reacts immediately (receive->analyze->plan->respond->extract->update)
    RUNTIME.on_scammer_message(processed)

    return jsonify({"ok": True})

# --- Mock Scammer API endpoint (MANDATORY) ---
@app.post("/api/mock_scammer")
def mock_scammer():
    payload = request.get_json(force=True)
    session_id = payload.get("session_id")
    mode = (payload.get("mode") or "SIMULATED").upper()
    agent_message = payload.get("agent_message", "")

    if mode == "SIMULATED":
        reply = simulated_reply(session_id=session_id, agent_message=agent_message)
    else:
        # HUMAN mode handled via process_human_message (this endpoint exists for spec compliance)
        reply = ""

    return jsonify({"reply": reply})

@app.get("/api/report")
def report():
    s = snapshot()
    return jsonify(s["final_report"] or {"ok": False, "message": "Not finished yet."})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
