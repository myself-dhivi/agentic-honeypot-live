async function post(url, body){
  const res = await fetch(url, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body || {})
  });
  return res.json();
}

function addBubble(msg){
  const chat = document.getElementById("chat");
  const div = document.createElement("div");
  div.className = "bubble " + (msg.speaker === "AGENT" ? "right" : "left");

  const head = document.createElement("div");
  head.className = "head";
  head.innerHTML = `<span><b>${msg.speaker}</b> • #${msg.turn_id}</span><span>${msg.ts || ""}</span>`;

  const text = document.createElement("div");
  text.textContent = msg.text;

  div.appendChild(head);
  div.appendChild(text);
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function renderArtifacts(list){
  const el = document.getElementById("artifacts");
  el.innerHTML = "";
  if (!list || list.length === 0){
    el.innerHTML = `<div class="item">None yet.</div>`;
    return;
  }
  for (const a of list){
    const d = document.createElement("div");
    d.className = "item mono";
    d.textContent = `${a.type.toUpperCase()} → ${a.value}  (conf=${a.confidence}, turn=${a.turn_id})`;
    el.appendChild(d);
  }
}

function renderReasoning(list){
  const el = document.getElementById("reasoning");
  el.innerHTML = "";
  if (!list || list.length === 0){
    el.innerHTML = `<div class="item">Waiting…</div>`;
    return;
  }
  // show latest first
  const latest = [...list].slice(-6).reverse();
  for (const r of latest){
    const d = document.createElement("div");
    d.className = "item";
    const inds = (r.detected_indicators || []).join(",") || "none";
    const arts = (r.artifacts_extracted || []).map(x => x.type).join(",") || "none";
    d.innerHTML = `<b>Turn ${r.turn_id}</b> • indicators=[${inds}] • extracted=[${arts}]<br/>
      risk: ${r.risk_before} → ${r.risk_after}<br/>
      next: <b>${r.next_goal || "-"}</b> (intent=${r.intent || "-"})<br/>
      gap: ${r.intel_gap || "-"}<br/>
      note: ${r.strategy_note || "-"}<br/>
      why: ${r.why_next || "-"}`;
    el.appendChild(d);
  }
}

function renderGraph(graph){
  const el = document.getElementById("graph");
  el.innerHTML = "";
  if (!graph || !graph.nodes) {
    el.innerHTML = `<div class="item">No graph yet.</div>`;
    return;
  }
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const turns = graph.turns || [];

  const n = nodes.length, e = edges.length, t = turns.length;
  el.innerHTML += `<div class="item"><b>Nodes:</b> ${n} • <b>Edges:</b> ${e} • <b>Turns:</b> ${t}</div>`;

  // show last few turn summaries (compact)
  const recent = [...turns].slice(-5).reverse();
  for (const tr of recent){
    const d = document.createElement("div");
    d.className = "item mono";
    d.textContent = `T${tr.turn_id}: risk ${tr.risk_before}→${tr.risk_after} | next=${tr.next_goal || "-"} | intent=${tr.intent || "-"}`;
    el.appendChild(d);
  }
}

async function downloadReport(){
  const res = await fetch("/api/report");
  const data = await res.json();
  const blob = new Blob([JSON.stringify(data, null, 2)], {type:"application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "honeypot_report.json";
  a.click();
  URL.revokeObjectURL(url);
}

document.getElementById("sendBtn").addEventListener("click", async () => {
  const text = document.getElementById("msg").value.trim();
  if (!text) return;
  document.getElementById("msg").value = "";
  await post("/api/scammer_message", {text});
});

document.getElementById("msg").addEventListener("keydown", async (e) => {
  if (e.key === "Enter") document.getElementById("sendBtn").click();
});

document.getElementById("resetBtn").addEventListener("click", async () => {
  await post("/api/reset", {});
  location.reload();
});

document.getElementById("reportBtn").addEventListener("click", downloadReport);

document.getElementById("modeSel").addEventListener("change", async (e) => {
  await post("/api/mode", {mode: e.target.value});
});

// SSE live stream
const es = new EventSource("/api/stream");
es.onmessage = async (ev) => {
  const data = JSON.parse(ev.data);
  const t = data.type;
  const p = data.payload;

  if (t === "message") addBubble(p);

  // refresh dashboard panels on key events
  if (["artifact","risk","reasoning","graph","reset","finished","mode"].includes(t)) {
    const st = await (await fetch("/api/state")).json();
    document.getElementById("case").textContent = `Case: ${st.case_id}`;
    document.getElementById("status").textContent = st.finished ? "FINISHED" : (st.scam_detected ? "SCAM DETECTED" : "WAITING");
    document.getElementById("score").textContent = st.risk_score;
    document.getElementById("level").textContent = st.risk_level;
    document.getElementById("verdict").textContent = st.verdict;
    document.getElementById("detected").textContent = String(st.scam_detected);
    renderArtifacts(st.artifacts);
    renderReasoning(st.turn_reasoning);
    renderGraph(st.intel_graph);
  }
};
