"use strict";
// The same-route UI: runs on the left; a map that replays a run (or follows a live one); results; figures.
// World coordinates are metres east (x) and north (y) of HKU, as in sameroute/world/world.py.

const GROUP_COLOURS = ["#2a78d6", "#1baf7a", "#6250d6", "#eda100", "#e34948", "#e87ba4", "#8a8f9c"];
const KIND_COLOURS = { go: "#2a78d6", stroll: "#eda100", live: "#1baf7a" };
const KIND_LABELS = { go: "Planned walk (go to)", stroll: "Stroll", live: "Live-world walk" };
const STATUS_TEXT = { running: "running", finished: "finished", partial: "partial", stopped: "stopped",
                      failed: "failed", "no output": "empty" };

const $ = (s) => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hhmm = (t) => { t = Math.max(0, Math.round(t)); return `${String(Math.floor(t / 3600) % 24).padStart(2, "0")}:${String(Math.floor(t / 60) % 60).padStart(2, "0")}`; };
const fmt = (n) => (n == null ? "–" : Number(n).toLocaleString("en-GB"));
const usd = (n) => (n == null ? "–" : "US$" + Number(n).toFixed(n < 1 ? 3 : 2));
async function api(path, opts) {
  const r = await fetch(path, opts);
  const ct = r.headers.get("content-type") || "";
  const body = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error(body.error || body || r.statusText);
  return body;
}
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// ------------------------------------------------------------------ state
const S = {
  runs: [], run: null, info: null, tab: "map",
  map: null, view: null,
  mode: "none",            // "replay" | "live" | "none"
  replay: null, t: 8 * 3600, playing: false, lastFrame: 0,
  active: [], ptr: 0, lastT: null,
  live: { prev: new Map(), next: new Map(), clockPrev: null, clockNext: null, at: 0, groups: [] },
  dots: [],                // what was drawn last frame, for clicking: [x, y, personId]
  selected: null, selectedTrips: [],
  sample: 3000,
};

// ------------------------------------------------------------------ canvas and view
const canvas = $("#map");
const ctx = canvas.getContext("2d");
const base = document.createElement("canvas");   // roads, redrawn when the view changes
const trail = document.createElement("canvas");  // fading trails
let dpr = 1, W = 0, H = 0, baseDirty = true;

function resize() {
  const r = canvas.getBoundingClientRect();
  dpr = window.devicePixelRatio || 1;
  W = r.width; H = r.height;
  for (const c of [canvas, base, trail]) { c.width = Math.max(1, Math.round(W * dpr)); c.height = Math.max(1, Math.round(H * dpr)); }
  if (S.map && !S.view) fitView();
  baseDirty = true;
}
function fitView() {
  const [x0, y0, x1, y1] = S.map.bounds;
  const pad = 40;
  const scale = Math.min((W - 2 * pad) / (x1 - x0), (H - 2 * pad) / (y1 - y0));
  S.view = { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, scale: Math.max(0.05, scale) };
  baseDirty = true;
}
const sx = (x) => (x - S.view.cx) * S.view.scale + W / 2;
const sy = (y) => H / 2 - (y - S.view.cy) * S.view.scale;

function drawBase() {
  const b = base.getContext("2d");
  b.setTransform(dpr, 0, 0, dpr, 0, 0);
  b.fillStyle = css("--map-bg"); b.fillRect(0, 0, W, H);
  if (!S.map) return;
  const road = css("--road"), steps = css("--road-steps");
  b.lineCap = "round"; b.lineJoin = "round";
  const lw = Math.max(0.6, Math.min(3, S.view.scale * 2.2));
  for (const pass of [0, 1]) {
    b.strokeStyle = pass ? steps : road; b.lineWidth = pass ? lw * 0.9 : lw;
    b.beginPath();
    for (const e of S.map.edges) {
      if ((e.s === 1) !== (pass === 1)) continue;
      const p = e.p;
      b.moveTo(sx(p[0]), sy(p[1]));
      for (let i = 2; i < p.length; i += 2) b.lineTo(sx(p[i]), sy(p[i + 1]));
    }
    b.stroke();
  }
  if (S.view.scale > 0.9) {   // places, once zoomed in
    b.fillStyle = css("--place");
    for (const p of S.map.places) { b.beginPath(); b.arc(sx(p[3]), sy(p[4]), 1.6, 0, 7); b.fill(); }
  }
  // area names
  b.font = "600 12px system-ui, sans-serif"; b.textAlign = "center";
  b.fillStyle = css("--muted");
  if (S.view.scale > 0.3) for (const [name, x, y] of S.map.areas || []) b.fillText(name, sx(x), sy(y) - 10);
  baseDirty = false;
}

// pan and zoom
let drag = null;
canvas.addEventListener("pointerdown", (e) => {
  drag = { x: e.clientX, y: e.clientY, cx: S.view.cx, cy: S.view.cy, moved: false };
  canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener("pointermove", (e) => {
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (Math.abs(dx) + Math.abs(dy) > 3) { drag.moved = true; canvas.classList.add("dragging"); }
  if (drag.moved) {
    S.view.cx = drag.cx - dx / S.view.scale; S.view.cy = drag.cy + dy / S.view.scale;
    baseDirty = true; clearTrail();
  }
});
canvas.addEventListener("pointerup", (e) => {
  canvas.classList.remove("dragging");
  if (drag && !drag.moved) pick(e);
  drag = null;
});
canvas.addEventListener("wheel", (e) => {
  e.preventDefault();
  const r = canvas.getBoundingClientRect();
  const mx = e.clientX - r.left, my = e.clientY - r.top;
  const wx = (mx - W / 2) / S.view.scale + S.view.cx, wy = S.view.cy - (my - H / 2) / S.view.scale;
  const f = Math.exp(-e.deltaY * 0.0015);
  S.view.scale = Math.min(40, Math.max(0.05, S.view.scale * f));
  S.view.cx = wx - (mx - W / 2) / S.view.scale; S.view.cy = wy + (my - H / 2) / S.view.scale;
  baseDirty = true; clearTrail();
}, { passive: false });
canvas.addEventListener("dblclick", fitView);

function clearTrail() { trail.getContext("2d").clearRect(0, 0, trail.width, trail.height); }

// ------------------------------------------------------------------ replay
function nodeXY(n) { return S.map.nodes[n]; }

function posAt(trip, t) {
  const p = trip[5], n = p.length / 2;
  let lo = 0, hi = n - 1;
  if (t <= p[1]) { const a = nodeXY(p[0]); return [a[0], a[1]]; }
  if (t >= p[2 * hi + 1]) { const a = nodeXY(p[2 * hi]); return [a[0], a[1]]; }
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (p[2 * m + 1] <= t) lo = m; else hi = m; }
  const a = nodeXY(p[2 * lo]), b = nodeXY(p[2 * hi]);
  const t0 = p[2 * lo + 1], t1 = p[2 * hi + 1];
  const f = t1 > t0 ? (t - t0) / (t1 - t0) : 0;
  return [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])];
}

function lowerBound(arr, v) { let lo = 0, hi = arr.length; while (lo < hi) { const m = (lo + hi) >> 1; if (arr[m] < v) lo = m + 1; else hi = m; } return lo; }
function upperBound(arr, v) { let lo = 0, hi = arr.length; while (lo < hi) { const m = (lo + hi) >> 1; if (arr[m] <= v) lo = m + 1; else hi = m; } return lo; }

function updateActive(t) {
  const R = S.replay;
  if (!R) return;
  if (S.lastT == null || t < S.lastT || t - S.lastT > 1800) {
    S.ptr = upperBound(R.deps, t);
    S.active = [];
    for (let i = 0; i < S.ptr; i++) if (R.trips[i][2] > t) S.active.push(R.trips[i]);
  } else {
    while (S.ptr < R.trips.length && R.trips[S.ptr][1] <= t) { S.active.push(R.trips[S.ptr]); S.ptr++; }
    S.active = S.active.filter((tr) => tr[2] > t);
  }
  S.lastT = t;
}

function colourOf(group, kind) {
  if ($("#colour").value === "kind") return KIND_COLOURS[kind] || "#8a8f9c";
  return GROUP_COLOURS[group] ?? GROUP_COLOURS[6];
}

// ------------------------------------------------------------------ the frame
function frame(now) {
  requestAnimationFrame(frame);
  if (S.tab !== "map" || !S.map) { S.lastFrame = now; return; }
  const dt = S.lastFrame ? Math.min(0.25, (now - S.lastFrame) / 1000) : 0;
  S.lastFrame = now;
  if (baseDirty) drawBase();

  const trails = $("#trails").checked;
  const tc = trail.getContext("2d");
  tc.setTransform(dpr, 0, 0, dpr, 0, 0);
  tc.globalCompositeOperation = "destination-out";
  tc.fillStyle = `rgba(0,0,0,${trails ? 0.06 : 1})`;
  tc.fillRect(0, 0, W, H);
  tc.globalCompositeOperation = "source-over";

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.drawImage(base, 0, 0, W, H);
  S.dots = [];
  const counts = new Array(GROUP_COLOURS.length).fill(0);
  const kindCounts = {};
  const r = Math.max(2, Math.min(5, S.view.scale * 3));

  if (S.mode === "replay" && S.replay) {
    if (S.playing) {
      S.t += dt * Number($("#speed").value);
      if (S.t >= S.replay.t_max) { S.t = S.replay.t_max; setPlaying(false); }
      $("#time").value = S.t;
    }
    updateActive(S.t);
    const R = S.replay;
    drawSelected();
    for (const tr of S.active) {
      const [x, y] = posAt(tr, S.t);
      const X = sx(x), Y = sy(y);
      const g = R.people[tr[0]][1];
      const kind = R.kinds[tr[4]];
      counts[g]++; kindCounts[kind] = (kindCounts[kind] || 0) + 1;
      if (X < -10 || Y < -10 || X > W + 10 || Y > H + 10) continue;
      const col = colourOf(g, kind);
      if (trails) { tc.fillStyle = col; tc.globalAlpha = 0.5; tc.beginPath(); tc.arc(X, Y, r * 0.55, 0, 7); tc.fill(); tc.globalAlpha = 1; }
      S.dots.push([X, Y, R.people[tr[0]][0], col, tr[3]]);
    }
    ctx.drawImage(trail, 0, 0, W, H);
    for (const [X, Y, pid, col, auto] of S.dots) {
      ctx.fillStyle = col; ctx.beginPath(); ctx.arc(X, Y, r, 0, 7); ctx.fill();
      if (auto) { ctx.strokeStyle = "#d13b3b"; ctx.lineWidth = 1.5; ctx.stroke(); }
      if (pid === S.selected) ring(X, Y, r);
    }
    const done = upperBound(R.arrs, S.t);
    $("#clock").textContent = hhmm(S.t);
    $("#stats").innerHTML = `<b>${fmt(S.active.length)}</b> walking now · <b>${fmt(done)}</b> of ${fmt(R.trips.length)} walks done` +
      (R.people.length < R.people_total ? `<br>${fmt(R.people.length)} of ${fmt(R.people_total)} people shown` : `<br>${fmt(R.people.length)} people`);
  } else if (S.mode === "live") {
    const L = S.live;
    const f = L.clockPrev == null ? 1 : Math.min(1, (performance.now() - L.at) / 1000);
    const clock = L.clockNext == null ? null : (L.clockPrev == null ? L.clockNext : L.clockPrev + f * (L.clockNext - L.clockPrev));
    let walking = 0, still = 0;
    for (const [pid, n] of L.next) {
      const p = L.prev.get(pid) || n;
      const x = p[0] + f * (n[0] - p[0]), y = p[1] + f * (n[1] - p[1]);
      const X = sx(x), Y = sy(y);
      const moving = n[2], visible = n[3], g = n[5];
      if (moving) { walking++; counts[g]++; } else still++;
      if (X < -10 || Y < -10 || X > W + 10 || Y > H + 10) continue;
      const col = colourOf(g, "live");
      if (moving && trails) { tc.fillStyle = col; tc.globalAlpha = 0.5; tc.beginPath(); tc.arc(X, Y, r * 0.55, 0, 7); tc.fill(); tc.globalAlpha = 1; }
      S.dots.push([X, Y, pid, col, 0, moving, visible]);
    }
    ctx.drawImage(trail, 0, 0, W, H);
    for (const [X, Y, pid, col, , moving, visible] of S.dots) {
      ctx.beginPath(); ctx.arc(X, Y, moving ? r : r * 0.7, 0, 7);
      if (moving) { ctx.fillStyle = col; ctx.fill(); }
      else { ctx.globalAlpha = visible ? 0.8 : 0.35; ctx.strokeStyle = col; ctx.lineWidth = 1.2; ctx.stroke(); ctx.globalAlpha = 1; }
      if (pid === S.selected) ring(X, Y, r);
    }
    $("#clock").textContent = clock == null ? "--:--" : hhmm(clock);
    $("#stats").innerHTML = `<b>${fmt(walking)}</b> walking · <b>${fmt(still)}</b> at a place` +
      `<br><span class="small">filled dot: walking · ring: at a place (faint: indoors)</span>`;
  } else {
    ctx.drawImage(trail, 0, 0, W, H);
  }
  drawLegend(counts, kindCounts);
}

function ring(X, Y, r) {
  ctx.strokeStyle = css("--ink"); ctx.lineWidth = 2;
  ctx.beginPath(); ctx.arc(X, Y, r + 4, 0, 7); ctx.stroke();
}

function drawSelected() {
  if (!S.selectedTrips.length) return;
  ctx.strokeStyle = css("--ink"); ctx.globalAlpha = 0.55; ctx.lineWidth = 2.5; ctx.setLineDash([5, 4]);
  for (const tr of S.selectedTrips) {
    const p = tr[5];
    ctx.beginPath();
    for (let i = 0; i < p.length; i += 2) { const [x, y] = nodeXY(p[i]); i ? ctx.lineTo(sx(x), sy(y)) : ctx.moveTo(sx(x), sy(y)); }
    ctx.stroke();
  }
  ctx.setLineDash([]); ctx.globalAlpha = 1;
}

let legendKey = "";
function drawLegend(counts, kindCounts) {
  const byKind = $("#colour").value === "kind";
  const groups = (S.replay && S.replay.groups) || S.live.groups || [];
  let items;
  if (byKind) {
    const kinds = S.mode === "live" ? ["live"] : (S.replay ? S.replay.kinds : []);
    items = kinds.map((k) => [KIND_COLOURS[k] || "#8a8f9c", KIND_LABELS[k] || k, kindCounts[k] || 0]);
  } else {
    items = groups.map((g, i) => [GROUP_COLOURS[i], g, counts[i] || 0]).filter((it, i) => i < 6 || it[2]);
  }
  const key = JSON.stringify(items) + S.mode;
  if (key === legendKey) return;
  legendKey = key;
  const box = $("#legend");
  box.classList.toggle("hidden", !items.length || S.mode === "none");
  box.replaceChildren(el("div", { class: "small muted" }, "walking now"),
    ...items.map(([c, label, n]) => el("div", { class: "item" }, el("span", { class: "sw", style: `background:${c}` }), label, el("span", { class: "n" }, fmt(n)))),
    ...(S.mode === "replay" ? [el("div", { class: "small muted", style: "margin-top:6px" }, "red edge: walked home by the simulator")] : []));
}

// ------------------------------------------------------------------ picking a person
function pick(e) {
  const r = canvas.getBoundingClientRect();
  const mx = e.clientX - r.left, my = e.clientY - r.top;
  let best = null, bd = 12 * 12;
  for (const d of S.dots) { const dd = (d[0] - mx) ** 2 + (d[1] - my) ** 2; if (dd < bd) { bd = dd; best = d; } }
  if (best) showPerson(best[2]); else closePerson();
}

function closePerson() { S.selected = null; S.selectedTrips = []; $("#person").classList.add("hidden"); }

async function showPerson(pid) {
  S.selected = pid;
  S.selectedTrips = [];
  if (S.replay) {
    const pi = S.replay.people.findIndex((p) => p[0] === pid);
    S.selectedTrips = S.replay.trips.filter((t) => t[0] === pi);
  }
  const box = $("#person-body");
  $("#person").classList.remove("hidden");
  box.replaceChildren(el("h3", {}, pid), el("p", { class: "muted small" }, "Loading this person's day…"));
  let rec;
  try { rec = await api(`/api/runs/${encodeURIComponent(S.run)}/person/${pid}`); }
  catch (err) { box.replaceChildren(el("h3", {}, pid), el("p", { class: "muted small" }, String(err.message || err))); return; }
  if (S.selected !== pid) return;
  const a = rec.agent || {};
  const place = (c) => (S.map.placeByCode[c] ? S.map.placeByCode[c][1] : c);
  const tags = [a.kind, a.age && `age ${a.age}`, a.faculty, a.personality].filter(Boolean);
  const kids = [
    el("h3", {}, a.name || pid),
    el("div", { class: "muted small" }, `${pid} · lives at ${place(a.home)}`),
    el("div", { class: "tags" }, tags.map((t) => el("span", { class: "tag" }, t))),
  ];
  const facts = [...(a.habits || []), ...(a.interests || []).map((i) => "likes " + i), ...((a.today || {}).notes || [])];
  if (a.today && a.today.feeling) facts.unshift("feels " + a.today.feeling);
  if (facts.length) kids.push(el("h4", {}, "Today"), el("div", { class: "tags" }, facts.map((t) => el("span", { class: "tag" }, t))));
  if ((a.commitments || []).length) {
    kids.push(el("h4", {}, "Commitments"), el("ul", { class: "timeline" },
      a.commitments.map((c) => el("li", {}, el("span", { class: "t" }, c.start), `${c.what} at ${place(c.place)}${c.end ? " until " + c.end : ""}`))));
  }
  kids.push(el("h4", {}, `Walks (${(rec.trips || []).length})`), el("ul", { class: "timeline" },
    (rec.trips || []).map((t) => el("li", { class: "trip", title: "Jump to this walk", onclick: () => { S.t = t.depart; $("#time").value = t.depart; S.lastT = null; clearTrail(); } },
      el("span", { class: "t" }, hhmm(t.depart)),
      el("span", {}, `${place(t.from)} → ${place(t.to)} `, el("span", { class: "muted" }, `${fmt(t.metres)} m, ${Math.round(((t.arrive ?? t.depart) - t.depart) / 60)} min${t.reason ? " · " + t.reason : ""}${t.auto ? " · walked home by the simulator" : ""}`))))));
  if ((rec.log || []).length) {
    kids.push(el("h4", {}, `What they did (${rec.log.length} tool calls)`), el("ul", { class: "timeline" },
      rec.log.slice(0, 400).map((l) => el("li", {}, el("span", { class: "t" }, l.t),
        el("span", { class: l.error ? "err" : "" }, el("b", {}, l.tool), " ", el("span", { class: "muted" }, JSON.stringify(l.input || {}).slice(0, 140)))))));
  }
  kids.push(el("p", { class: "small muted" }, `Day ended: ${rec.stop || "–"}${rec.summary ? " · “" + rec.summary + "”" : ""} · ${rec.calls ?? 0} calls · ${usd(rec.cost_usd)}`));
  box.replaceChildren(...kids);
}
$("#person-close").addEventListener("click", closePerson);

// ------------------------------------------------------------------ controls
function setPlaying(p) { S.playing = p; $("#play").textContent = p ? "❚❚" : "▶"; $("#play").setAttribute("aria-label", p ? "Pause" : "Play"); }
$("#play").addEventListener("click", () => {
  if (S.mode !== "replay" || !S.replay) return;
  if (!S.playing && S.t >= S.replay.t_max) { S.t = S.replay.t_min; S.lastT = null; clearTrail(); }
  setPlaying(!S.playing);
});
$("#time").addEventListener("input", (e) => { S.t = Number(e.target.value); clearTrail(); });
$("#colour").addEventListener("change", () => { legendKey = ""; clearTrail(); });
$("#trails").addEventListener("change", clearTrail);
$("#sample").addEventListener("change", (e) => { S.sample = Number(e.target.value); if (S.mode === "replay") loadReplay(); });
document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, select, textarea") || S.tab !== "map") return;
  if (e.code === "Space") { e.preventDefault(); $("#play").click(); }
  if (e.key === "Escape") closePerson();
});

function setTicks(t0, t1) {
  const box = $("#ticks");
  box.replaceChildren();
  for (let h = Math.ceil(t0 / 3600); h * 3600 <= t1; h += 2) {
    box.append(el("span", { style: `left:${(100 * (h * 3600 - t0)) / (t1 - t0)}%` }, String(h % 24).padStart(2, "0")));
  }
}

// ------------------------------------------------------------------ runs
const DAY_START = 6 * 3600, DAY_END = 24 * 3600;
function runFraction(r) {   // how far a running run is: the clock for the live world, people done for the Agent World
  const p = r.progress || {};
  if (r.kind === "live" && p.clock != null) return Math.max(0, Math.min(1, (p.clock - DAY_START) / (DAY_END - DAY_START)));
  return p.people ? (p.done || 0) / p.people : 0;
}
function runCard(r) {
  const s = r.summary || {}, p = r.progress || {};
  const trips = s.trips != null ? `${fmt(s.trips)} walks` : "";
  const cost = r.planner === "mock" ? "free" : s.usd != null ? usd(s.usd) : p.usd != null ? usd(p.usd) : "";
  const meta = [r.people ? `${fmt(r.people)} people` : "", trips, cost].filter(Boolean).join(" · ");
  const card = el("button", { class: "run-card" + (r.name === S.run ? " active" : ""), onclick: () => selectRun(r.name) },
    el("div", { class: "row1" }, el("span", { class: "name" }, r.name), el("span", { class: `pill ${r.status}` }, STATUS_TEXT[r.status] || r.status)),
    el("div", { class: "meta" }, (r.kind === "live" ? "Live world" : "Agent World") + (r.planner ? ` · ${r.planner === "mock" ? "rule-based" : "Claude"}` : "")),
    meta ? el("div", { class: "meta" }, meta) : null);
  if (r.status === "running" && p.people) {
    card.append(el("div", { class: "bar" }, el("div", { style: `width:${100 * runFraction(r)}%` })));
  }
  return card;
}

async function refreshRuns(prefer) {
  try { S.runs = await api("/api/runs"); } catch { return; }
  $("#runs-count").textContent = S.runs.length ? `${S.runs.length}` : "";
  const list = $("#runs-list");
  list.replaceChildren(...(S.runs.length ? S.runs.map(runCard)
    : [el("p", { class: "muted small", style: "padding:8px" }, "No runs yet. Start a free one with the button at the top.")]));
  const cur = S.runs.find((r) => r.name === S.run);
  if (cur) onInfo(cur);
  if (!S.run && S.runs.length) {
    const pick = S.runs.find((r) => r.name === prefer) || S.runs.find((r) => r.status === "running")
      || S.runs.find((r) => r.name === "census_run") || S.runs[0];
    selectRun(pick.name);
  }
}

function onInfo(info) {
  const prev = S.info;
  S.info = info;
  const p = info.progress || {};
  const running = info.status === "running";
  // switch between following a live run and replaying a finished one
  const wantLive = running && info.kind === "live";
  if (wantLive && S.mode !== "live") startLive();
  if (!wantLive && S.mode === "live") { stopLive(); loadReplay(); }
  if (running && info.kind === "agent-world" && prev && prev.name === info.name && (p.done || 0) !== ((prev.progress || {}).done || 0)
      && performance.now() - (S.replayLoadedAt || 0) > 8000) loadReplay(true);
  if (!running && prev && prev.name === info.name && prev.status === "running") loadReplay();
  // progress box
  const box = $("#progress-box");
  box.classList.toggle("hidden", !running);
  if (running) {
    $("#progress-bar").style.width = 100 * runFraction(info) + "%";
    const spend = info.planner === "claude" ? ` · ${usd(p.usd)} of ${usd(p.budget)} budget` : " · free";
    const what = info.kind === "live"
      ? `${fmt(p.started_people || 0)} of ${fmt(p.people)} out today, ${fmt(p.done || 0)} days over`
      : `${fmt(p.done || 0)} of ${fmt(p.people)} people done`;
    $("#progress-text").replaceChildren(what + spend + " ",
      el("button", { class: "small", style: "padding:1px 8px;margin-left:4px", onclick: stopRun }, "Stop"));
  }
  $("#live-badge").classList.toggle("hidden", !wantLive);
  const note = $("#map-notice");
  const msg = !running && p.message ? p.message : info.status === "partial" && info.summary ? (info.summary.note || "") : "";
  note.textContent = msg; note.classList.toggle("hidden", !msg);
  $("#controls").classList.toggle("hidden", S.mode === "live");
}

async function stopRun() {
  if (!confirm(`Stop ${S.run}? It saves, and the same command continues it later.`)) return;
  try { await api(`/api/runs/${encodeURIComponent(S.run)}/stop`, { method: "POST", body: "{}" }); } catch (e) { alert(e.message); }
}

async function selectRun(name) {
  if (S.run === name && S.info) return;
  S.run = name; S.info = null; closePerson();
  location.hash = "run=" + encodeURIComponent(name);
  document.querySelectorAll(".run-card").forEach((c) => c.classList.toggle("active", c.querySelector(".name").textContent === name));
  $("#run-title").textContent = name;
  $("#runs-panel").classList.remove("open");
  stopLive(); S.mode = "none"; S.replay = null; clearTrail();
  let info;
  try { info = await api(`/api/runs/${encodeURIComponent(name)}`); } catch (e) { return; }
  if (S.run !== name) return;
  if (info.status === "running" && info.kind === "live") { S.info = info; startLive(); onInfo(info); }
  else { onInfo(info); await loadReplay(); }
  renderResults();
}

async function loadReplay(keepTime = false) {
  const name = S.run;
  const empty = $("#map-empty");
  if (!S.replay) { empty.classList.remove("hidden"); empty.innerHTML = `<div>Loading the walks of <code>${esc(name)}</code>…</div>`; }
  let data;
  try { data = await api(`/api/runs/${encodeURIComponent(name)}/replay?people=${S.sample}`); }
  catch (e) { empty.innerHTML = `<div>${esc(e.message)}</div>`; return; }
  if (S.run !== name || S.mode === "live") return;
  S.replayLoadedAt = performance.now();
  data.deps = data.trips.map((t) => t[1]);
  data.arrs = data.trips.map((t) => t[2]).sort((a, b) => a - b);
  const first = !S.replay || !keepTime;
  S.replay = data; S.mode = "replay"; S.lastT = null; legendKey = "";
  if (S.selected) { const pi = data.people.findIndex((p) => p[0] === S.selected); S.selectedTrips = data.trips.filter((t) => t[0] === pi); }
  const t0 = Math.floor(data.t_min / 3600) * 3600, t1 = Math.min(86400, Math.ceil(data.t_max / 3600) * 3600);
  const slider = $("#time"); slider.min = t0; slider.max = t1;
  setTicks(t0, t1);
  if (first) { S.t = Math.max(data.t_min, Math.min(8 * 3600, data.t_max)); slider.value = S.t; }
  $("#controls").classList.remove("hidden");
  if (!data.trips.length) {
    empty.classList.remove("hidden");
    empty.innerHTML = S.info && S.info.status === "running"
      ? `<div>Nobody has finished their day yet. The map fills up as people finish.</div>`
      : `<div>No walks in <code>${esc(name)}</code> yet.</div>`;
  } else empty.classList.add("hidden");
}

// ------------------------------------------------------------------ following a live run
let liveTimer = null;
function startLive() {
  stopLive();
  S.mode = "live"; S.replay = null; legendKey = "";
  S.live = { prev: new Map(), next: new Map(), clockPrev: null, clockNext: null, at: performance.now(), groups: [] };
  $("#controls").classList.add("hidden");
  $("#map-empty").classList.add("hidden");
  const tick = async () => {
    const name = S.run;
    try {
      const snap = await api(`/api/runs/${encodeURIComponent(name)}/positions`);
      if (S.run !== name || S.mode !== "live") return;
      const L = S.live;
      const now = performance.now();
      const f = L.clockPrev == null ? 1 : Math.min(1, (now - L.at) / 1000);
      const cur = new Map();   // where each dot is drawn right now becomes the start of the next glide
      for (const [pid, n] of L.next) { const p = L.prev.get(pid) || n; cur.set(pid, [p[0] + f * (n[0] - p[0]), p[1] + f * (n[1] - p[1])]); }
      L.prev = cur;
      L.next = new Map(snap.people.map((p) => [p[0], [p[1], p[2], p[3], p[4], p[5], p[6]]]));
      L.clockPrev = L.clockNext; L.clockNext = snap.clock; L.at = now; L.groups = snap.groups || [];
    } catch { /* the file is being replaced; try again */ }
  };
  tick();
  liveTimer = setInterval(tick, 1000);
}
function stopLive() { if (liveTimer) clearInterval(liveTimer); liveTimer = null; if (S.mode === "live") S.mode = "none"; }

// ------------------------------------------------------------------ results
function card(k, v, extra = "") { return el("div", { class: "card " + extra }, el("div", { class: "k" }, k), el("div", { class: "v" }, v)); }

function renderResults() {
  const info = S.info;
  if (!info) return;
  const s = info.summary || {}, p = info.progress || {};
  const cards = [
    card("Kind", info.kind === "live" ? "Live world" : "Agent World"),
    card("Status", STATUS_TEXT[info.status] || info.status),
    card("People", fmt(s.agents ?? info.people)),
    card("Walks", fmt(s.trips)),
    card("Model calls", fmt(s.calls ?? p.calls)),
    card("Cost", info.planner === "mock" ? "free" : usd(s.usd ?? p.usd)),
  ];
  if (s.usd_per_agent) cards.push(card("Cost per person", usd(s.usd_per_agent)));
  if (s.auto_trips != null) cards.push(card("Walks finished by the simulator", fmt(s.auto_trips)));
  if (s.clock_reached) cards.push(card("Clock reached", s.clock_reached));
  const ended = s.how_days_ended || {};
  const total = Object.values(ended).reduce((a, b) => a + b, 0);
  if (total) {
    cards.push(el("div", { class: "card wide" }, el("div", { class: "k" }, "How the days ended"),
      Object.entries(ended).sort((a, b) => b[1] - a[1]).map(([k, n]) =>
        el("div", { class: "hbar" }, el("span", {}, k), el("div", { class: "track" }, el("div", { class: "fill", style: `width:${(100 * n) / total}%` })), el("span", { class: "n" }, fmt(n))))));
  }
  if (!Object.keys(s).length && !Object.keys(p).length) cards.push(card("Results", "none yet", "wide"));
  $("#summary-cards").replaceChildren(...cards);

  const list = $("#files-list");
  const files = info.analysis || [];
  if (!files.length) {
    list.replaceChildren(el("p", { class: "muted small", style: "padding:0 14px" },
      info.has_trips ? `No analysis yet. Run python -m sameroute analyse following --run ${info.name}` : "No analysis yet."));
    $("#doc").innerHTML = `<p class="muted">Nothing to read yet.</p>`;
    return;
  }
  const order = (f) => [f.includes("/") ? 1 : 0, f.endsWith(".md") ? 0 : 1, f];
  const sorted = [...files].sort((a, b) => (JSON.stringify(order(a)) < JSON.stringify(order(b)) ? -1 : 1));
  const kids = []; let dir = null;
  for (const f of sorted) {
    const d = f.includes("/") ? f.slice(0, f.lastIndexOf("/")) : "";
    if (d !== dir) { dir = d; if (d) kids.push(el("div", { class: "dir" }, d + "/")); }
    kids.push(el("button", { "data-file": f, onclick: () => openFile(f) }, f.slice(d ? d.length + 1 : 0)));
  }
  list.replaceChildren(...kids);
  const main = ["following.md", "summary.md", "compare.md", "paper_tables.md"].find((f) => files.includes(f)) || sorted[0];
  openFile(main);
}

async function openFile(f) {
  document.querySelectorAll("#files-list button").forEach((b) => b.classList.toggle("active", b.dataset.file === f));
  const doc = $("#doc");
  doc.innerHTML = `<p class="muted">Loading ${esc(f)}…</p>`;
  let text;
  try { text = await api(`/api/runs/${encodeURIComponent(S.run)}/file?path=${encodeURIComponent(f)}`); }
  catch (e) { doc.innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; }
  if (f.endsWith(".md")) doc.innerHTML = markdown(text);
  else if (f.endsWith(".csv")) doc.innerHTML = `<h2>${esc(f)}</h2>` + csvTable(text);
  else doc.innerHTML = `<h2>${esc(f)}</h2><pre>${esc(text)}</pre>`;
}

function inline(s) {
  return esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>").replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}
function splitRow(line) { return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim()); }
function markdown(md) {
  const lines = md.replace(/\r/g, "").split("\n");
  let out = "", i = 0, para = [];
  const flush = () => { if (para.length) { out += `<p>${inline(para.join(" "))}</p>`; para = []; } };
  while (i < lines.length) {
    const l = lines[i];
    if (/^```/.test(l)) { flush(); let j = i + 1, code = []; while (j < lines.length && !/^```/.test(lines[j])) code.push(lines[j++]); out += `<pre><code>${esc(code.join("\n"))}</code></pre>`; i = j + 1; continue; }
    const h = l.match(/^(#{1,4})\s+(.*)/);
    if (h) { flush(); out += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`; i++; continue; }
    if (/^\s*\|/.test(l) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      flush(); const head = splitRow(l); i += 2; const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(splitRow(lines[i++]));
      out += `<table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>` +
        rows.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("") + "</tbody></table>";
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(l)) {
      flush(); const ordered = /^\s*\d+\./.test(l); const items = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        let item = lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, "");
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s+/.test(lines[i])) item += " " + lines[i++].trim();
        items.push(`<li>${inline(item)}</li>`);
      }
      out += ordered ? `<ol>${items.join("")}</ol>` : `<ul>${items.join("")}</ul>`; continue;
    }
    if (!l.trim()) { flush(); i++; continue; }
    para.push(l.trim()); i++;
  }
  flush();
  return out;
}
function parseCSV(text) {
  const rows = []; let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += c; }
    else if (c === '"') q = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n") { row.push(cell); rows.push(row); row = []; cell = ""; }
    else if (c !== "\r") cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}
function csvTable(text) {
  const rows = parseCSV(text);
  if (!rows.length) return "<p class='muted'>Empty.</p>";
  const max = 1000, body = rows.slice(1, max + 1);
  return `<table><thead><tr>${rows[0].map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>` +
    body.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("") + "</tbody></table>" +
    (rows.length - 1 > max ? `<p class="muted small">First ${fmt(max)} of ${fmt(rows.length - 1)} rows.</p>` : "");
}

// ------------------------------------------------------------------ figures
async function renderFigures() {
  let figs;
  try { figs = await api("/api/figures"); } catch { return; }
  $("#figure-grid").replaceChildren(...figs.map((f) => el("figure", { onclick: () => { $("#lightbox-img").src = "/graphs/" + f.png; $("#lightbox").showModal(); } },
    el("img", { src: "/graphs/" + f.png, loading: "lazy", alt: f.name }), el("figcaption", {}, f.name + (f.pdf ? "  (PDF too)" : "")))));
}

// ------------------------------------------------------------------ tabs
function setTab(tab) {
  S.tab = tab;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  document.querySelectorAll(".tab-page").forEach((p) => p.classList.toggle("active", p.id === "page-" + tab));
  if (tab === "map") { resize(); }
  if (tab === "figures") renderFigures();
  if (tab === "results") renderResults();
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
$("#toggle-runs").addEventListener("click", () => $("#runs-panel").classList.toggle("open"));

// ------------------------------------------------------------------ starting a free run
const dlg = $("#launch");
function slowText() {
  const kind = dlg.querySelector("input[name=kind]:checked").value, v = Number($("#slow").value);
  $("#slow-text").textContent = kind === "live"
    ? (v ? `${v} s per simulated hour (the day takes about ${Math.round((v * 18) / 60)} min)` : "as fast as it goes (a few seconds)")
    : (v ? `${(v / 100).toFixed(2)} s per person` : "as fast as it goes");
}
$("#new-run").addEventListener("click", () => {
  const d = new Date();
  const kind = dlg.querySelector("input[name=kind]:checked").value;
  $("#launch-name").value = `try-${kind === "live" ? "live" : "aw"}-${String(d.getHours()).padStart(2, "0")}${String(d.getMinutes()).padStart(2, "0")}`;
  $("#launch-error").classList.add("hidden");
  slowText(); dlg.showModal();
});
dlg.querySelectorAll("input[name=kind]").forEach((r) => r.addEventListener("change", () => {
  const live = r.value === "live" && r.checked;
  if (!r.checked) return;
  dlg.querySelector("input[name=people]").value = live ? 300 : 500;
  $("#launch-name").value = $("#launch-name").value.replace(/^try-(live|aw)-/, `try-${live ? "live" : "aw"}-`);
  slowText();
}));
$("#slow").addEventListener("input", slowText);
$("#launch-form").addEventListener("submit", async (e) => {
  if (e.submitter && e.submitter.value === "cancel") return;
  e.preventDefault();
  const fd = new FormData(e.target);
  const kind = fd.get("kind");
  const v = Number(fd.get("slow"));
  const body = { kind, run: fd.get("run"), people: Number(fd.get("people")), seed: Number(fd.get("seed")), slow: kind === "live" ? v : v / 100 };
  try {
    const r = await api("/api/launch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    dlg.close();
    S.run = null;
    for (let i = 0; i < 20; i++) {   // wait for the run to show up, then follow it
      await new Promise((res) => setTimeout(res, 500));
      await refreshRuns();
      if (S.runs.some((x) => x.name === r.run && x.progress)) { S.info = null; await selectRun(r.run); break; }
    }
    setTab("map");
  } catch (err) {
    const box = $("#launch-error"); box.textContent = err.message; box.classList.remove("hidden");
  }
});

// ------------------------------------------------------------------ start
async function init() {
  window.addEventListener("resize", resize);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { baseDirty = true; });
  resize();
  requestAnimationFrame(frame);
  const empty = $("#map-empty");
  empty.classList.remove("hidden"); empty.innerHTML = "<div>Loading the map…</div>";
  S.map = await api("/api/map");
  S.map.placeByCode = Object.fromEntries(S.map.places.map((p) => [p[0], p]));
  fitView(); empty.classList.add("hidden");
  const m = location.hash.match(/run=([^&]+)/);
  await refreshRuns(m ? decodeURIComponent(m[1]) : null);
  setInterval(() => refreshRuns(), 3000);
}
init();
