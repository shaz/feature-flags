"use strict";
// fubo-flags admin console. Framework-free; talks to /api/v1 (dogfoods the API).

const API = "/api/v1";
const $ = (s, el = document) => el.querySelector(s);
const state = { projects: [], projectKey: null, envs: [], envKey: null, tab: "flags" };

// ---- API client ----
async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["content-type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch (_) {}
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return (res.headers.get("content-type") || "").includes("json") ? res.json() : res.text();
}

function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (isErr ? " err" : "");
  setTimeout(() => (t.className = "toast hidden"), isErr ? 4000 : 2200);
}

const pk = () => state.projectKey;
const ek = () => state.envKey;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString() : "—");
const parseValue = (s) => { try { return JSON.parse(s); } catch { return s; } };

// ---- bootstrap ----
async function init() {
  bindChrome();
  try {
    state.projects = await api("GET", "/projects");
  } catch (e) { toast(e.message, true); return; }

  if (state.projects.length === 0) { renderNoProject(); return; }
  fillSelect($("#project-select"), state.projects.map((p) => [p.key, p.name]));
  state.projectKey = state.projects[0].key;
  await loadEnvs();
  render();
}

async function loadEnvs() {
  state.envs = await api("GET", `/projects/${pk()}/environments`);
  fillSelect($("#env-select"), state.envs.map((e) => [e.key, e.name]));
  state.envKey = state.envs[0] ? state.envs[0].key : null;
}

function fillSelect(sel, pairs) {
  sel.innerHTML = pairs.map(([v, label]) => `<option value="${esc(v)}">${esc(label)}</option>`).join("");
}

function bindChrome() {
  $("#project-select").onchange = async (e) => { state.projectKey = e.target.value; await loadEnvs(); render(); };
  $("#env-select").onchange = (e) => { state.envKey = e.target.value; render(); };
  $("#new-project-btn").onclick = newProject;
  document.querySelectorAll("#tabs button").forEach((b) => {
    b.onclick = () => {
      state.tab = b.dataset.tab;
      document.querySelectorAll("#tabs button").forEach((x) => x.classList.toggle("active", x === b));
      render();
    };
  });
}

function render() {
  if (!pk()) { renderNoProject(); return; }
  ({ flags: renderFlags, segments: renderSegments, keys: renderKeys, audit: renderAudit }[state.tab])();
}

// ---- empty / project creation ----
function renderNoProject() {
  $("#view").innerHTML = `<div class="empty">No projects yet.<br><br>
    <button class="primary" id="first-project">Create your first project</button></div>`;
  $("#first-project").onclick = newProject;
}
async function newProject() {
  const key = prompt("Project key (lowercase, e.g. streaming):");
  if (!key) return;
  const name = prompt("Project name:", key) || key;
  try {
    await api("POST", "/projects", { key, name });
    state.projects = await api("GET", "/projects");
    fillSelect($("#project-select"), state.projects.map((p) => [p.key, p.name]));
    state.projectKey = key;
    $("#project-select").value = key;
    if ((await api("GET", `/projects/${key}/environments`)).length === 0) {
      const ekey = prompt("First environment key:", "production") || "production";
      await api("POST", `/projects/${key}/environments`, { key: ekey, name: ekey });
    }
    await loadEnvs();
    render();
    toast("Project created");
  } catch (e) { toast(e.message, true); }
}

// ---- Flags ----
async function renderFlags() {
  const view = $("#view");
  view.innerHTML = `<div class="view-head">
      <div><h1>Feature flags</h1><div class="sub">Status shown for <b>${esc(ek() || "—")}</b></div></div>
      <button class="primary" id="new-flag">Create flag</button>
    </div><div class="list" id="flag-list"><div class="empty">Loading…</div></div>`;
  $("#new-flag").onclick = openCreateFlag;

  let flags;
  try { flags = await api("GET", `/projects/${pk()}/flags`); }
  catch (e) { return toast(e.message, true); }
  if (!flags.length) { $("#flag-list").innerHTML = `<div class="empty">No flags yet.</div>`; return; }

  // N+1: fetch each flag's config for the selected env (dogfood: a combined
  // list endpoint would avoid this).
  const cfgs = await Promise.all(flags.map((f) =>
    api("GET", `/projects/${pk()}/flags/${f.key}/environments/${ek()}`).catch(() => null)));

  $("#flag-list").innerHTML = flags.map((f, i) => {
    const c = cfgs[i];
    const on = c && c.enabled;
    return `<div class="row" data-flag="${esc(f.key)}">
      <label class="switch" onclick="event.stopPropagation()">
        <input type="checkbox" data-toggle="${esc(f.key)}" ${on ? "checked" : ""} ${c ? "" : "disabled"}>
        <span class="slider"></span>
      </label>
      <div class="grow">
        <div class="name">${esc(f.name)}</div>
        <div class="key">${esc(f.key)}</div>
      </div>
      <span class="tag">${esc(f.kind)}</span>
      <span class="pill"><span class="dot ${on ? "on" : "off"}"></span>${on ? "Targeting on" : "Off"}</span>
    </div>`;
  }).join("");

  $("#flag-list").querySelectorAll(".row").forEach((row) => {
    row.onclick = () => openFlagDrawer(row.dataset.flag);
  });
  $("#flag-list").querySelectorAll("[data-toggle]").forEach((cb) => {
    cb.onchange = (e) => { e.stopPropagation(); quickToggle(cb.dataset.toggle, cb.checked); };
  });
}

async function quickToggle(flagKey, enabled) {
  try {
    const c = await api("GET", `/projects/${pk()}/flags/${flagKey}/environments/${ek()}`);
    await api("PUT", `/projects/${pk()}/flags/${flagKey}/environments/${ek()}`, configBody(c, { enabled }));
    toast(`${flagKey} ${enabled ? "enabled" : "disabled"} in ${ek()}`);
  } catch (e) { toast(e.message, true); render(); }
}

// Build a FlagConfigUpdate, preserving fields the UI didn't touch.
function configBody(cfg, overrides = {}) {
  return {
    enabled: cfg.enabled,
    targets: cfg.targets || [],
    rules: cfg.rules || [],
    fallthrough: cfg.fallthrough,
    offVariation: cfg.off_variation,
    prerequisites: cfg.prerequisites || [],
    ...overrides,
  };
}

async function openFlagDrawer(flagKey) {
  let flag, cfg;
  try {
    flag = await api("GET", `/projects/${pk()}/flags/${flagKey}`);
    cfg = await api("GET", `/projects/${pk()}/flags/${flagKey}/environments/${ek()}`);
  } catch (e) { return toast(e.message, true); }

  const varOpts = flag.variations.map((v, i) => `<option value="${i}">${i}: ${esc(v.name)}</option>`).join("");
  const ft = cfg.fallthrough || { variation: 0 };
  const isRollout = !!ft.rollout;

  drawer(`
    <h2>${esc(flag.name)}</h2>
    <div class="key">${esc(flag.key)} · ${esc(flag.kind)}</div>

    <div class="section">
      <h3>Targeting · ${esc(ek())}</h3>
      <div class="rowflex">
        <label class="switch"><input type="checkbox" id="d-enabled" ${cfg.enabled ? "checked" : ""}><span class="slider"></span></label>
        <span id="d-enabled-label">${cfg.enabled ? "Targeting is ON" : "Targeting is OFF"}</span>
        <span class="spacer"></span><span class="meta">v${cfg.version}</span>
      </div>
    </div>

    <div class="section">
      <h3>Variations</h3>
      <div class="list">${flag.variations.map((v, i) =>
        `<div class="row" style="cursor:default"><div class="grow"><span class="meta">${i}</span> <b>${esc(v.name)}</b></div><span class="code" style="padding:2px 8px">${esc(JSON.stringify(v.value))}</span></div>`).join("")}</div>
    </div>

    <div class="section">
      <h3>Default rule (fallthrough)</h3>
      <div class="field">
        <label><input type="radio" name="ftmode" value="fixed" ${isRollout ? "" : "checked"}> Serve a variation</label>
        <select id="d-ft-var">${varOpts}</select>
      </div>
      <div class="field">
        <label><input type="radio" name="ftmode" value="rollout" ${isRollout ? "checked" : ""}> Percentage rollout (%)</label>
        <div id="d-rollout">${flag.variations.map((v, i) =>
          `<div class="rowflex"><span class="meta" style="width:120px">${esc(v.name)}</span>
           <input type="text" data-pct="${i}" value="${rolloutPct(ft, i, flag.variations.length)}" style="width:70px"> %</div>`).join("")}</div>
      </div>
    </div>

    <div class="section">
      <h3>When off, serve</h3>
      <select id="d-off">${varOpts}</select>
    </div>

    ${(cfg.rules && cfg.rules.length) ? `<div class="section"><h3>Targeting rules (read-only)</h3>
      <div class="code">${esc(JSON.stringify(cfg.rules, null, 2))}</div>
      <div class="meta" style="margin-top:6px">Rule editing in the UI is not built yet.</div></div>` : ""}
    ${(cfg.prerequisites && cfg.prerequisites.length) ? `<div class="section"><h3>Prerequisites</h3>
      <div class="code">${esc(JSON.stringify(cfg.prerequisites, null, 2))}</div></div>` : ""}

    <div class="section rowflex">
      <button class="primary" id="d-save">Save targeting</button>
      <span class="spacer"></span>
      <span class="meta">Last changed ${fmtDate(cfg.updated_at)} by ${esc(cfg.updated_by || "—")}</span>
    </div>
  `);

  $("#d-ft-var").value = isRollout ? 0 : (ft.variation ?? 0);
  $("#d-off").value = cfg.off_variation ?? 0;
  $("#d-enabled").onchange = (e) =>
    ($("#d-enabled-label").textContent = e.target.checked ? "Targeting is ON" : "Targeting is OFF");

  $("#d-save").onclick = async () => {
    const mode = $('input[name="ftmode"]:checked').value;
    let fallthrough;
    if (mode === "fixed") {
      fallthrough = { variation: Number($("#d-ft-var").value) };
    } else {
      const weights = [...document.querySelectorAll("[data-pct]")].map((inp) => Math.round(Number(inp.value) * 1000));
      const sum = weights.reduce((a, b) => a + b, 0);
      if (sum !== 100000) return toast(`Rollout must total 100% (got ${(sum / 1000).toFixed(1)}%)`, true);
      fallthrough = { rollout: { contextKind: "user", bucketBy: "key",
        variations: weights.map((w, i) => ({ variation: i, weight: w })) } };
    }
    try {
      await api("PUT", `/projects/${pk()}/flags/${flag.key}/environments/${ek()}`,
        configBody(cfg, { enabled: $("#d-enabled").checked, fallthrough, offVariation: Number($("#d-off").value) }));
      closeDrawer(); toast("Targeting saved"); render();
    } catch (e) { toast(e.message, true); }
  };
}

function rolloutPct(ft, i, n) {
  if (ft.rollout) {
    const wv = ft.rollout.variations.find((v) => v.variation === i);
    return wv ? (wv.weight / 1000) : 0;
  }
  return i === 0 ? 100 : 0; // default seed when switching to rollout
}

function openCreateFlag() {
  drawer(`
    <h2>Create flag</h2>
    <div class="field"><label>Name</label><input type="text" id="f-name"></div>
    <div class="field"><label>Key (lowercase)</label><input type="text" id="f-key"></div>
    <div class="field"><label>Kind</label>
      <select id="f-kind"><option value="boolean">boolean</option><option value="multivariate">multivariate</option></select></div>
    <div class="section"><h3>Variations</h3><div id="f-vars"></div>
      <button class="ghost" id="f-addvar" style="margin-top:8px">+ variation</button></div>
    <div class="section rowflex"><button class="primary" id="f-create">Create</button></div>
  `);
  const varsBox = $("#f-vars");
  const addVar = (name = "", value = "") => {
    const d = document.createElement("div");
    d.className = "rowflex"; d.style.marginBottom = "6px";
    d.innerHTML = `<input type="text" placeholder="name" value="${esc(name)}" data-vn style="flex:1">
      <input type="text" placeholder="value (JSON)" value="${esc(value)}" data-vv style="flex:1">
      <button class="danger" data-rm>×</button>`;
    d.querySelector("[data-rm]").onclick = () => d.remove();
    varsBox.appendChild(d);
  };
  const seedBoolean = () => { varsBox.innerHTML = ""; addVar("On", "true"); addVar("Off", "false"); };
  seedBoolean();
  $("#f-kind").onchange = (e) => { if (e.target.value === "boolean") seedBoolean(); };
  $("#f-addvar").onclick = () => addVar();

  $("#f-create").onclick = async () => {
    const variations = [...varsBox.querySelectorAll(".rowflex")].map((r) => ({
      name: r.querySelector("[data-vn]").value,
      value: parseValue(r.querySelector("[data-vv]").value),
    }));
    const body = { name: $("#f-name").value, key: $("#f-key").value, kind: $("#f-kind").value, variations };
    try {
      await api("POST", `/projects/${pk()}/flags`, body);
      closeDrawer(); toast("Flag created"); render();
    } catch (e) { toast(e.message, true); }
  };
}

// ---- Segments ----
async function renderSegments() {
  $("#view").innerHTML = `<div class="view-head">
      <div><h1>Segments</h1><div class="sub">Reusable groups for targeting · ${esc(ek())}</div></div>
      <button class="primary" id="new-seg">New segment</button></div>
    <div class="list" id="seg-list"><div class="empty">Loading…</div></div>`;
  $("#new-seg").onclick = async () => {
    const key = prompt("Segment key:"); if (!key) return;
    const name = prompt("Segment name:", key) || key;
    try { await api("POST", `/projects/${pk()}/segments`, { key, name }); renderSegments(); toast("Segment created"); }
    catch (e) { toast(e.message, true); }
  };
  let segs;
  try { segs = await api("GET", `/projects/${pk()}/segments`); }
  catch (e) { return toast(e.message, true); }
  if (!segs.length) { $("#seg-list").innerHTML = `<div class="empty">No segments yet.</div>`; return; }
  $("#seg-list").innerHTML = segs.map((s) =>
    `<div class="row" data-seg="${esc(s.key)}"><div class="grow"><div class="name">${esc(s.name)}</div><div class="key">${esc(s.key)}</div></div></div>`).join("");
  $("#seg-list").querySelectorAll(".row").forEach((r) => (r.onclick = () => openSegmentDrawer(r.dataset.seg)));
}

async function openSegmentDrawer(segKey) {
  const cfg = await api("GET", `/projects/${pk()}/segments/${segKey}/environments/${ek()}`).catch(() => null);
  const inc = cfg ? cfg.included.join("\n") : "";
  const exc = cfg ? cfg.excluded.join("\n") : "";
  const kind = cfg ? cfg.context_kind : "user";
  drawer(`
    <h2>${esc(segKey)}</h2><div class="key">segment · ${esc(ek())}</div>
    <div class="field"><label>Context kind</label><input type="text" id="s-kind" value="${esc(kind)}"></div>
    <div class="field"><label>Included keys (one per line)</label><textarea id="s-inc" rows="5">${esc(inc)}</textarea></div>
    <div class="field"><label>Excluded keys (one per line)</label><textarea id="s-exc" rows="3">${esc(exc)}</textarea></div>
    ${cfg && cfg.rules.length ? `<div class="section"><h3>Rules (read-only)</h3><div class="code">${esc(JSON.stringify(cfg.rules, null, 2))}</div></div>` : ""}
    <div class="section"><button class="primary" id="s-save">Save segment</button></div>
  `);
  $("#s-save").onclick = async () => {
    const lines = (id) => $(id).value.split("\n").map((x) => x.trim()).filter(Boolean);
    try {
      await api("PUT", `/projects/${pk()}/segments/${segKey}/environments/${ek()}`,
        { contextKind: $("#s-kind").value, included: lines("#s-inc"), excluded: lines("#s-exc"), rules: cfg ? cfg.rules : [] });
      closeDrawer(); toast("Segment saved");
    } catch (e) { toast(e.message, true); }
  };
}

// ---- SDK keys ----
async function renderKeys() {
  const base = `/projects/${pk()}/environments/${ek()}/credentials`;
  $("#view").innerHTML = `<div class="view-head">
      <div><h1>SDK keys</h1><div class="sub">${esc(ek())}</div></div>
      <div class="rowflex">
        <select id="k-kind"><option>server</option><option>client</option><option>mobile</option></select>
        <button class="primary" id="k-issue">Issue key</button></div></div>
    <div class="list" id="k-list"><div class="empty">Loading…</div></div>`;
  $("#k-issue").onclick = async () => {
    try {
      const c = await api("POST", base, { kind: $("#k-kind").value });
      drawer(`<h2>Key issued</h2><p class="meta">Copy it now — it is shown only once.</p>
        <div class="code" style="margin-top:12px">${esc(c.key)}</div>
        <div class="section"><button class="primary" id="k-done">Done</button></div>`);
      $("#k-done").onclick = () => { closeDrawer(); renderKeys(); };
    } catch (e) { toast(e.message, true); }
  };
  let keys;
  try { keys = await api("GET", base); } catch (e) { return toast(e.message, true); }
  if (!keys.length) { $("#k-list").innerHTML = `<div class="empty">No keys yet.</div>`; return; }
  $("#k-list").innerHTML = keys.map((k) =>
    `<div class="row" style="cursor:default"><div class="grow"><div class="name">${esc(k.kind)} <span class="key">${esc(k.key_prefix)}…</span></div>
       <div class="meta">created ${fmtDate(k.created_at)}${k.revoked_at ? " · revoked " + fmtDate(k.revoked_at) : ""}</div></div>
     ${k.revoked_at ? `<span class="tag">revoked</span>` : `<button class="danger" data-revoke="${esc(k.id)}">Revoke</button>`}</div>`).join("");
  $("#k-list").querySelectorAll("[data-revoke]").forEach((b) => {
    b.onclick = async () => {
      try { await api("POST", `${base}/${b.dataset.revoke}/revoke`); renderKeys(); toast("Key revoked"); }
      catch (e) { toast(e.message, true); }
    };
  });
}

// ---- Audit ----
async function renderAudit() {
  $("#view").innerHTML = `<div class="view-head"><div><h1>Audit log</h1>
      <div class="sub">Every change across ${esc(pk())}</div></div></div>
    <div class="list" id="a-list"><div class="empty">Loading…</div></div>`;
  let entries;
  try { entries = await api("GET", `/projects/${pk()}/audit?limit=100`); }
  catch (e) { return toast(e.message, true); }
  if (!entries.length) { $("#a-list").innerHTML = `<div class="empty">No activity yet.</div>`; return; }
  $("#a-list").innerHTML = entries.map((a) =>
    `<div class="row" style="cursor:default"><div class="grow"><div class="name">${esc(a.summary)}</div>
       <div class="meta">${esc(a.actor)} · ${esc(a.action)}</div></div>
     <span class="meta">${fmtDate(a.created_at)}</span></div>`).join("");
}

// ---- drawer ----
function drawer(html) {
  const d = $("#drawer");
  d.innerHTML = `<button class="drawer-close" id="drawer-x">×</button>` + html;
  d.classList.remove("hidden");
  $("#drawer-x").onclick = closeDrawer;
}
function closeDrawer() { $("#drawer").classList.add("hidden"); $("#drawer").innerHTML = ""; }

init();
