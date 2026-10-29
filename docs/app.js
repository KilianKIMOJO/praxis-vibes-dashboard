/* Praxis Vibes Reichweiten-Dashboard – liest window.PV_DATA (data.js) und zeichnet alles als SVG. */
(function () {
  "use strict";
  const D = window.PV_DATA;
  if (!D) { document.querySelector("main").innerHTML = "<p>Keine Daten gefunden (data.js fehlt).</p>"; return; }

  // ── Formatierung ──────────────────────────────────────────────────────────
  const nf = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 });
  const MON = ["Jan", "Feb", "März", "Apr", "Mai", "Juni", "Juli", "Aug", "Sep", "Okt", "Nov", "Dez"];
  const fnum = (v) => (v == null ? "–" : nf.format(v));
  const fpct = (p) => (p == null ? "–" : (p > 0 ? "+" : p < 0 ? "−" : "±") + nf.format(Math.abs(p * 100)) + " %");
  const pd = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
  const fdate = (s) => { const d = pd(s); return `${d.getDate()}. ${MON[d.getMonth()]}`; };
  const kw = (wid) => +wid.split("-W")[1];
  const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  // ── Wochen ────────────────────────────────────────────────────────────────
  const byWeek = Object.fromEntries(D.weeks.map((w) => [w.week, w]));
  function isoWeekId(d) {
    const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    const day = t.getUTCDay() || 7; t.setUTCDate(t.getUTCDate() + 4 - day);
    const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    const w = Math.ceil(((t - y0) / 86400000 + 1) / 7);
    return `${t.getUTCFullYear()}-W${String(w).padStart(2, "0")}`;
  }
  // Lückenlose Wochenfolge vom ersten Datensatz bis zum Ende des Berichtszeitraums
  const allWeeks = [];
  for (let d = pd(D.weeks[0].start), end = pd(D.period.end); d <= end; d.setDate(d.getDate() + 7)) {
    const wid = isoWeekId(d);
    allWeeks.push({ week: wid, start: ymd(d), rec: byWeek[wid] || null });
  }
  const val = (w, sec, key) => (w.rec && w.rec[sec] && w.rec[sec][key] != null ? w.rec[sec][key] : null);
  const epByWeek = {};
  (D.episodes || []).forEach((e) => { const wid = isoWeekId(pd(e.date)); (epByWeek[wid] = epByWeek[wid] || []).push(e); });

  // ── Kopf ──────────────────────────────────────────────────────────────────
  const gen = new Date(D.generated);
  document.getElementById("stand").textContent =
    `Daten bis KW ${kw(D.period.weeks[1])} · erzeugt am ${gen.toLocaleDateString("de-DE")}, ${gen.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })} Uhr`;
  document.getElementById("period-label").textContent = D.period.label;
  document.getElementById("period-dates").textContent = `${fdate(D.period.start)} bis ${fdate(D.period.end)} ${pd(D.period.end).getFullYear()} · Summe aus zwei Wochen`;
  const st = D.status || {};
  document.getElementById("sources").innerHTML = [["Instagram", "instagram"], ["Spotify", "spotify"], ["Feed", "feed"]].map(([n, k]) => {
    const s = st[k] || {}; const ok = !!s.ok;
    const txt = k === "feed" ? (ok ? "aktuell" : "offline") : ok ? "automatisch" : "aus Excel";
    return `<span class="chip" title="${esc(s.message || "noch nicht abgerufen")}"><span class="dot ${ok ? "ok" : "no"}"></span><b>${n}</b> ${txt}</span>`;
  }).join("");

  // ── Nordsterne ────────────────────────────────────────────────────────────
  function deltaHtml(p, word) {
    if (p == null) return `<span class="delta flat">kein Vergleich</span>`;
    const cls = p > 0 ? "up" : p < 0 ? "down" : "flat";
    const arrow = p > 0 ? "▲" : p < 0 ? "▼" : "■";
    return `<span class="delta ${cls}">${arrow} ${fpct(p)}</span> <span>${word}</span>`;
  }
  function northTile(x, color, unit) {
    const useAvg = x.vs_prev == null;
    const goal = x.goal
      ? `<div class="goal">Ziel ${fnum(x.goal.target)} · ${nf.format(x.goal.ratio * 100)} % erreicht <span class="badge ${x.goal.level.split(" ")[0]}">${x.goal.level}</span>
           <div class="bar"><i style="width:${Math.min(100, x.goal.ratio * 100)}%"></i></div></div>`
      : `<div class="goal">Noch kein Ziel hinterlegt. Zielwert aus dem Workshop in <code>config/ziele.json</code> eintragen.</div>`;
    return `<div class="card ns" style="--c:var(${color})">
      <div class="ns-lbl">${esc(x.label)}</div>
      <div class="ns-val">${fnum(x.value)}</div>
      <div class="ns-row">${deltaHtml(useAvg ? x.vs_avg12 : x.vs_prev, useAvg ? "zum 12-Wochen-Schnitt" : "zur Vorperiode")}
        <span>Ø 12 Wochen: ${fnum(x.avg12)} ${unit}</span></div>
      ${x.complete ? "" : `<div class="note">Nur ${x.weeks_with_data} von 2 Wochen mit Daten.</div>`}
      ${useAvg && x.prev == null ? `<div class="note" style="color:var(--muted)">Vorperiode ohne vollständige Daten, daher Vergleich mit dem Schnitt.</div>` : ""}
      ${goal}</div>`;
  }
  document.getElementById("north").innerHTML =
    northTile(D.kpis.plays, "--pod", "je 14 Tage") + northTile(D.kpis.reach, "--ig", "je 14 Tage");

  // ── Treiber ───────────────────────────────────────────────────────────────
  const K = D.kpis;
  const tile = (lbl, v, sub) => `<div class="card tile"><div class="t-lbl">${lbl}</div><div class="t-val">${v}</div><div class="t-sub">${sub}</div></div>`;
  const cmp = (x) => (x.vs_prev != null ? `${fpct(x.vs_prev)} zur Vorperiode` : x.vs_avg12 != null ? `${fpct(x.vs_avg12)} zum Ø` : "kein Vergleich");
  const signed = (v) => (v == null ? "–" : (v > 0 ? "+" : "") + nf.format(v));
  document.getElementById("drivers").innerHTML = [
    tile("Instagram-Follower", fnum(K.ig_followers.value), `${signed(K.ig_net.value)} netto in 14 Tagen`),
    tile("Spotify-Follower netto", signed(K.pod_followers_net.value), K.pod_followers.value != null ? `Stand ${fnum(K.pod_followers.value)}` : "in 14 Tagen"),
    tile("Instagram-Views", fnum(K.views.value), cmp(K.views)),
    tile("Profilaufrufe", fnum(K.profile_views.value), cmp(K.profile_views)),
    tile("Link-Klicks", fnum(K.link_clicks.value), cmp(K.link_clicks)),
    tile("Wiedergaben je 1.000 Reichweite", K.plays_per_1000_reach != null ? nf1.format(K.plays_per_1000_reach) : "–", "Brücke Instagram → Podcast"),
  ].join("");

  // ── Hinweise und Folgen ───────────────────────────────────────────────────
  document.getElementById("hints").innerHTML = (D.hints.length ? D.hints : ["Keine Auffälligkeiten."])
    .map((h) => `<li class="${/^Datencheck|läuft/.test(h) ? "warn" : ""}">${esc(h)}</li>`).join("");
  document.querySelector("#eps tbody").innerHTML = (D.episodes || []).slice(0, 8).map((e) =>
    `<tr><td>${e.number != null ? "#" + e.number : ""}</td><td><a href="${esc(e.link)}" target="_blank" rel="noopener">${esc(e.title)}</a></td>
     <td>${fdate(e.date)}</td><td class="r">${e.plays_total != null ? fnum(e.plays_total) : "–"}</td></tr>`).join("");

  // ── Wochentabelle ─────────────────────────────────────────────────────────
  const cols = [["Wiedergaben", "pod", "plays"], ["Spotify-Foll. netto", "pod", "followers_net"], ["Erreichte Konten", "ig", "reach"],
    ["Views", "ig", "views"], ["Profilaufrufe", "ig", "profile_views"], ["Link-Klicks", "ig", "link_clicks"],
    ["IG-Follower", "ig", "followers"], ["IG netto", "ig", "net"]];
  document.getElementById("weeks").innerHTML =
    `<thead><tr><th>Woche</th>${cols.map((c) => `<th>${c[0]}</th>`).join("")}<th>Quelle</th></tr></thead><tbody>` +
    allWeeks.slice().reverse().map((w) => `<tr><td>KW ${kw(w.week)} <span class="src">${w.week.slice(0, 4)}</span></td>${cols.map((c) => `<td>${fnum(val(w, c[1], c[2]))}</td>`).join("")}
      <td class="src">${w.rec ? [...new Set(Object.values(w.rec.sources || {}))].join(", ") || "–" : "keine Daten"}</td></tr>`).join("") + "</tbody>";

  // ── Diagramme ─────────────────────────────────────────────────────────────
  const tip = document.getElementById("tip");
  function showTip(evt, htmlStr) {
    tip.innerHTML = htmlStr; tip.style.opacity = 1;
    const r = tip.getBoundingClientRect();
    let x = evt.clientX + 14, y = evt.clientY - r.height - 10;
    if (x + r.width > innerWidth - 8) x = evt.clientX - r.width - 14;
    if (y < 8) y = evt.clientY + 16;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  const hideTip = () => { tip.style.opacity = 0; };

  function nice(max) {
    if (max <= 0) return 1;
    const e = Math.pow(10, Math.floor(Math.log10(max))), f = max / e;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * e;
  }
  const compact = (v) => (Math.abs(v) >= 10000 ? nf.format(v / 1000) + " Tsd." : nf.format(v));
  const svgEl = (tag, attrs) => `<${tag} ${Object.entries(attrs).map(([k, v]) => `${k}="${v}"`).join(" ")}/>`;

  function barPath(x, y0, y1, w) { // Rundung 4px am Datenende, flach an der Nulllinie
    const h = Math.abs(y1 - y0), r = Math.min(4, h, w / 2), up = y1 < y0;
    if (h < 0.5) return "";
    if (up) return `M${x},${y0}V${y1 + r}Q${x},${y1} ${x + r},${y1}H${x + w - r}Q${x + w},${y1} ${x + w},${y1 + r}V${y0}Z`;
    return `M${x},${y0}V${y1 - r}Q${x},${y1} ${x + r},${y1}H${x + w - r}Q${x + w},${y1} ${x + w},${y1 - r}V${y0}Z`;
  }

  function weekTitle(w) {
    const e = new Date(pd(w.start)); e.setDate(e.getDate() + 6);
    return `KW ${kw(w.week)} · ${fdate(w.start)} – ${fdate(ymd(e))}`;
  }

  function chart(id, weeks, opt) {
    const plot = document.querySelector(`#${id} .plot`);
    const W = plot.clientWidth, H = plot.clientHeight;
    const m = { l: 52, r: 10, t: 14, b: 26 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const vals = weeks.map((w) => opt.get(w));
    const have = vals.filter((v) => v != null);
    if (!have.length) { plot.innerHTML = `<p class="sub" style="padding-top:80px;text-align:center">Für diesen Zeitraum noch keine Daten.</p>`; return; }
    let lo = opt.type === "line" ? Math.min(...have) : Math.min(0, ...have);
    let hi = Math.max(...have);
    if (opt.type === "line") { const pad = (hi - lo) * 0.1 || 10; lo = Math.max(0, lo - pad); hi = hi + pad; }
    const step = nice((hi - lo) / 4);
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step || step;
    const y = (v) => m.t + ih - ((v - lo) / (hi - lo)) * ih;
    const bw = iw / weeks.length;
    const x = (i) => m.l + i * bw;
    const color = css(opt.color);
    let s = "";
    for (let g = lo; g <= hi + step / 2; g += step) {
      s += svgEl("line", { class: "gl", x1: m.l, x2: W - m.r, y1: y(g), y2: y(g) });
      s += `<text class="ax" x="${m.l - 8}" y="${y(g) + 4}" text-anchor="end">${compact(g)}</text>`;
    }
    // X-Beschriftung: Abstand mindestens 56px
    const every = Math.max(1, Math.ceil(56 / bw));
    weeks.forEach((w, i) => {
      if ((weeks.length - 1 - i) % every) return;
      const lbl = kw(w.week) === 1 || i === 0 ? `KW ${kw(w.week)} ’${w.week.slice(2, 4)}` : `KW ${kw(w.week)}`;
      s += `<text class="ax" x="${x(i) + bw / 2}" y="${H - 6}" text-anchor="middle">${lbl}</text>`;
    });
    s += `<g class="hls"></g>`;
    if (opt.type === "bar") {
      const w = Math.max(2, Math.min(bw - 2, bw * 0.72));
      weeks.forEach((wk, i) => {
        const v = vals[i];
        if (v == null) { s += `<circle cx="${x(i) + bw / 2}" cy="${y(0)}" r="1.5" fill="${css("--muted")}"/>`; return; }
        s += `<path d="${barPath(x(i) + (bw - w) / 2, y(0), y(v), w)}" fill="${color}"/>`;
      });
      if (lo < 0) s += svgEl("line", { x1: m.l, x2: W - m.r, y1: y(0), y2: y(0), stroke: css("--muted"), "stroke-width": 1 });
    } else {
      let d = "", started = false;
      weeks.forEach((wk, i) => {
        const v = vals[i]; if (v == null) return;
        d += `${started ? "L" : "M"}${x(i) + bw / 2},${y(v)}`; started = true;
      });
      s += `<path d="${d}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
      const li = vals.map((v, i) => [v, i]).filter((t) => t[0] != null).pop();
      s += `<circle cx="${x(li[1]) + bw / 2}" cy="${y(li[0])}" r="4" fill="${color}" stroke="${css("--card")}" stroke-width="2"/>`;
      s += `<text class="avg-lbl" x="${Math.min(x(li[1]) + bw / 2, W - m.r)}" y="${y(li[0]) - 10}" text-anchor="end">${fnum(li[0])}</text>`;
    }
    if (opt.avg) {
      const avg = have.reduce((a, b) => a + b, 0) / have.length;
      s += svgEl("line", { class: "avg", x1: m.l, x2: W - m.r, y1: y(avg), y2: y(avg) });
      s += `<text class="avg-lbl" x="${W - m.r}" y="${y(avg) - 6}" text-anchor="end">Ø ${fnum(avg)}</text>`;
    }
    if (opt.episodes) {
      weeks.forEach((wk, i) => {
        if (!epByWeek[wk.week]) return;
        const cx = x(i) + bw / 2, cy = y(0);
        s += `<path class="ep" d="M${cx},${cy - 6}L${cx + 6},${cy}L${cx},${cy + 6}L${cx - 6},${cy}Z"/>`;
      });
    }
    weeks.forEach((wk, i) => { s += `<rect class="hit" data-i="${i}" x="${x(i)}" y="${m.t}" width="${bw}" height="${ih}"/>`; });
    plot.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opt.label)}">${s}</svg>`;
    const svg = plot.querySelector("svg"), hls = svg.querySelector(".hls");
    svg.querySelectorAll(".hit").forEach((r) => {
      const i = +r.dataset.i, wk = weeks[i];
      r.addEventListener("mousemove", (evt) => {
        hls.innerHTML = `<rect class="hl" x="${x(i)}" y="${m.t}" width="${bw}" height="${ih}"/>`;
        const v = vals[i];
        const eps = (epByWeek[wk.week] || []).map((e) => `<div class="t-sub">Neue Folge #${e.number ?? ""}: ${esc(e.title.slice(0, 60))}</div>`).join("");
        const srcs = wk.rec ? [...new Set(Object.values(wk.rec.sources || {}))].join(", ") : "";
        showTip(evt, `<div class="t-sub">${weekTitle(wk)}</div><b>${v == null ? "keine Daten" : fnum(v)}</b> ${v == null ? "" : opt.unit}${eps}${srcs ? `<div class="t-sub">Quelle: ${srcs}</div>` : ""}`);
      });
      r.addEventListener("mouseleave", () => { hls.innerHTML = ""; hideTip(); });
    });
  }

  let range = 26;
  try { range = +localStorage.getItem("pv-range") || 26; } catch (e) { /* ohne Speicher */ }
  function render() {
    const weeks = allWeeks.slice(-range);
    chart("c-plays", weeks, { type: "bar", color: "--pod", get: (w) => val(w, "pod", "plays"), unit: "Wiedergaben", avg: true, episodes: true, label: "Podcast-Wiedergaben je Woche" });
    chart("c-reach", weeks, { type: "bar", color: "--ig", get: (w) => val(w, "ig", "reach"), unit: "erreichte Konten", avg: true, label: "Instagram erreichte Konten je Woche" });
    chart("c-igf", weeks, { type: "line", color: "--ig", get: (w) => val(w, "ig", "followers"), unit: "Follower", label: "Instagram-Follower gesamt" });
    chart("c-igz", weeks, { type: "bar", color: "--ig", get: (w) => val(w, "ig", "net"), unit: "Follower netto", avg: true, label: "Instagram-Follower netto je Woche" });
    document.querySelectorAll("#range button").forEach((b) => b.classList.toggle("on", +b.dataset.r === range));
  }
  document.querySelectorAll("#range button").forEach((b) => b.addEventListener("click", () => {
    range = +b.dataset.r; try { localStorage.setItem("pv-range", range); } catch (e) { /* egal */ }
    render();
  }));
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(render, 120); });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
  render();
})();
