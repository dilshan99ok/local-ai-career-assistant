"""Interactive skill-demand visualizations for the Streamlit workspace."""

from __future__ import annotations

import json

import pandas as pd


def _clean(value) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.lower() in {"none", "nan"} else value


def _json_payload(value) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _skill_payload(skill_summary: pd.DataFrame, canonical_rows: pd.DataFrame) -> list[dict]:
    if skill_summary.empty:
        return []

    rows = []
    for _, row in skill_summary.iterrows():
        skill = _clean(row.get("Skill"))
        if not skill:
            continue
        evidence = canonical_rows[canonical_rows["canonical_skill"] == skill].copy()
        evidence_rows = []
        for _, evidence_row in evidence.head(8).iterrows():
            evidence_rows.append(
                {
                    "company": _clean(evidence_row.get("company")) or "Unknown company",
                    "job_title": _clean(evidence_row.get("job_title")) or "Untitled role",
                    "domain": _clean(evidence_row.get("domain")) or "Unclassified",
                    "requirement": _clean(evidence_row.get("requirement_level")) or "Not specified",
                }
            )
        rows.append(
            {
                "skill": skill,
                "category": _clean(row.get("Category")) or "Other",
                "jobs": int(row.get("Jobs", 0) or 0),
                "occurrences": int(row.get("Occurrences", 0) or 0),
                "share": float(row.get("Job Share", 0) or 0),
                "last_seen": _clean(row.get("Last Seen"))[:10] or "—",
                "evidence": evidence_rows,
            }
        )
    return rows


def build_skill_landscape_html(skill_summary: pd.DataFrame, canonical_rows: pd.DataFrame) -> str:
    """Return an iframe-ready interactive hierarchical skill demand map."""

    payload = _json_payload(_skill_payload(skill_summary, canonical_rows))
    template = r'''
<div id="skill-landscape" class="skill-landscape" role="application" aria-label="Interactive skill demand landscape">
  <div class="skill-landscape-toolbar">
    <div>
      <div class="skill-landscape-kicker">DEMAND MAP</div>
      <div class="skill-landscape-title">Your saved jobs, organised by skill family</div>
      <div class="skill-landscape-subtitle">Categories contain demand-weighted skills. Select a tile to inspect its market evidence.</div>
    </div>
    <button id="skill-reset" type="button" class="skill-reset">Show all</button>
  </div>
  <div id="skill-category-filter" class="skill-category-filter" aria-label="Skill categories"></div>
  <div class="skill-landscape-body">
    <main class="skill-treemap-wrap">
      <div class="skill-map-head"><span>SKILL DEMAND TREEMAP</span><span>Tile weight = jobs requiring the skill</span></div>
      <div id="skill-treemap" class="skill-treemap" aria-live="polite"></div>
      <div class="skill-map-foot"><span class="legend-swatch tone-blue"></span> Technical demand <span class="legend-swatch tone-purple"></span> Platform / systems <span class="legend-swatch tone-green"></span> Support / operations</div>
    </main>
    <aside id="skill-detail" class="skill-detail" aria-live="polite"></aside>
  </div>
</div>
<style>
  html, body { margin:0; background:#0f1218; }
  #skill-landscape {
    --surface: #0f1218;
    --surface-2: #151a23;
    --surface-3: #1c2430;
    --text: #f0f4f8;
    --muted: #9baabd;
    --line: rgba(160, 180, 205, 0.18);
    --blue: #8ec5f0;
    --green: #79e6a6;
    --purple: #c5a7ff;
    --orange: #f0bd75;
    color: var(--text);
    font-family:system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    margin: 0.75rem 0 1.2rem;
  }
  #skill-landscape * { box-sizing: border-box; }
  .skill-landscape-toolbar { display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; margin-bottom:0.8rem; }
  .skill-landscape-kicker { color:var(--blue); font-size:0.68rem; font-weight:750; letter-spacing:0.14em; }
  .skill-landscape-title { color:var(--text); font-size:1.22rem; font-weight:700; margin-top:0.22rem; }
  .skill-landscape-subtitle { color:var(--muted); font-size:0.83rem; margin-top:0.24rem; }
  .skill-reset { border:1px solid rgba(142,197,240,0.3); border-radius:0.45rem; color:var(--text); background:rgba(142,197,240,0.08); padding:0.48rem 0.75rem; font:inherit; font-size:0.78rem; cursor:pointer; transition:background 160ms ease, transform 160ms ease; }
  .skill-reset:hover { background:rgba(142,197,240,0.17); transform:translateY(-1px); }
  .skill-category-filter { display:flex; gap:0.38rem; flex-wrap:wrap; margin-bottom:0.65rem; }
  .skill-category-filter button { border:1px solid rgba(160,180,205,0.2); border-radius:999px; background:rgba(255,255,255,0.035); color:var(--muted); padding:0.36rem 0.6rem; font:inherit; font-size:0.73rem; cursor:pointer; transition:all 160ms ease; }
  .skill-category-filter button:hover, .skill-category-filter button.active { background:rgba(142,197,240,0.15); border-color:rgba(142,197,240,0.45); color:var(--text); }
  .skill-landscape-body { display:grid; grid-template-columns:minmax(0, 2.25fr) minmax(245px, 0.9fr); gap:0.8rem; align-items:start; }
  .skill-treemap-wrap { background:linear-gradient(145deg, rgba(21,26,35,0.9), rgba(15,18,24,0.96)); border:1px solid rgba(160,180,205,0.18); border-radius:0.65rem; overflow:hidden; min-width:0; }
  .skill-map-head { display:flex; justify-content:space-between; gap:1rem; color:var(--muted); font-size:0.68rem; font-weight:700; letter-spacing:0.1em; padding:0.7rem 0.8rem; border-bottom:1px solid rgba(160,180,205,0.12); }
  .skill-map-head span:last-child { font-weight:500; letter-spacing:0; }
  .skill-treemap { display:grid; grid-template-columns:repeat(12, minmax(0, 1fr)); gap:0.55rem; padding:0.7rem; min-height:450px; }
  .category-panel { grid-column:span 4; background:rgba(255,255,255,0.028); border:1px solid rgba(160,180,205,0.17); border-radius:0.55rem; padding:0.65rem; min-width:0; animation:skill-panel-in 260ms ease both; transition:background 180ms ease, border-color 180ms ease; }
  .category-panel:hover { background:rgba(255,255,255,0.044); border-color:rgba(142,197,240,0.33); }
  .category-panel.wide { grid-column:span 6; }
  .category-panel.full { grid-column:1 / -1; }
  .category-header { display:flex; justify-content:space-between; gap:0.5rem; align-items:baseline; margin-bottom:0.55rem; }
  .category-name { color:var(--text); font-size:0.86rem; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .category-meta { color:var(--muted); font-size:0.67rem; white-space:nowrap; }
  .category-skills { display:flex; flex-wrap:wrap; gap:0.42rem; align-items:stretch; }
  .skill-tile { position:relative; flex:var(--skill-weight) 1 112px; min-height:66px; border:1px solid rgba(255,255,255,0.12); border-radius:0.48rem; color:var(--text); padding:0.55rem 0.58rem; text-align:left; font:inherit; cursor:pointer; overflow:hidden; transition:transform 160ms ease, border-color 160ms ease, background 160ms ease, box-shadow 160ms ease; }
  .skill-tile::after { content:""; position:absolute; inset:0; background:linear-gradient(120deg, transparent 30%, rgba(255,255,255,0.08), transparent 70%); transform:translateX(-130%); transition:transform 380ms ease; pointer-events:none; }
  .skill-tile:hover::after, .skill-tile.selected::after { transform:translateX(130%); }
  .skill-tile:hover, .skill-tile.selected { transform:translateY(-2px); border-color:rgba(255,255,255,0.48); box-shadow:0 8px 20px rgba(0,0,0,0.18); }
  .skill-tile.selected { animation:skill-focus 420ms ease both; }
  .skill-tile.tone-blue { background:rgba(91,169,230,0.17); }
  .skill-tile.tone-purple { background:rgba(169,129,235,0.17); }
  .skill-tile.tone-green { background:rgba(76,190,128,0.17); }
  .skill-tile.tone-orange { background:rgba(220,163,87,0.17); }
  .skill-tile.tone-slate { background:rgba(140,160,185,0.14); }
  .skill-tile-name { display:block; font-size:0.83rem; font-weight:700; line-height:1.2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .skill-tile-value { display:block; color:rgba(240,244,248,0.66); font-size:0.7rem; margin-top:0.38rem; }
  .skill-tile-share { position:absolute; top:0.5rem; right:0.5rem; color:rgba(240,244,248,0.68); font-size:0.66rem; }
  .skill-map-foot { display:flex; align-items:center; gap:0.42rem; color:var(--muted); font-size:0.72rem; padding:0.55rem 0.8rem 0.7rem; border-top:1px solid rgba(160,180,205,0.12); }
  .legend-swatch { width:12px; height:12px; display:inline-block; border-radius:0.22rem; margin-left:0.2rem; }
  .legend-swatch.tone-blue { background:rgba(91,169,230,0.62); }
  .legend-swatch.tone-purple { background:rgba(169,129,235,0.62); }
  .legend-swatch.tone-green { background:rgba(76,190,128,0.62); }
  .skill-detail { background:var(--surface-2); border:1px solid rgba(160,180,205,0.18); border-radius:0.65rem; min-height:260px; padding:1rem; }
  .detail-empty { color:var(--muted); font-size:0.85rem; line-height:1.5; padding-top:1rem; }
  .detail-kicker { color:var(--blue); font-size:0.67rem; font-weight:750; letter-spacing:0.12em; }
  .detail-title { color:var(--text); font-size:1.25rem; font-weight:700; line-height:1.2; margin-top:0.3rem; }
  .detail-category { color:var(--muted); font-size:0.8rem; margin-top:0.25rem; }
  .detail-metrics { display:grid; grid-template-columns:1fr 1fr; gap:0.45rem; margin:1rem 0; }
  .detail-metric { background:rgba(255,255,255,0.04); border-radius:0.45rem; padding:0.55rem; }
  .detail-metric-label { color:var(--muted); font-size:0.68rem; }
  .detail-metric-value { color:var(--text); font-size:1.06rem; font-weight:700; margin-top:0.18rem; }
  .detail-section-label { color:var(--muted); font-size:0.68rem; font-weight:700; letter-spacing:0.1em; margin:0.9rem 0 0.45rem; }
  .detail-evidence { border-top:1px solid rgba(160,180,205,0.13); padding:0.48rem 0; }
  .detail-job { color:var(--text); font-size:0.78rem; font-weight:650; line-height:1.25; }
  .detail-company { color:var(--muted); font-size:0.7rem; margin-top:0.16rem; }
  .detail-requirement { color:var(--orange); font-size:0.68rem; margin-top:0.14rem; }
  @keyframes skill-panel-in { from { opacity:0; transform:translateY(5px); } to { opacity:1; transform:translateY(0); } }
  @keyframes skill-focus { 0% { transform:translateY(0) scale(1); } 55% { transform:translateY(-3px) scale(1.025); } 100% { transform:translateY(-2px) scale(1); } }
  @media (prefers-reduced-motion: reduce) { #skill-landscape *, #skill-landscape *::after { animation:none !important; transition:none !important; } }
  @media (max-width: 900px) { .skill-landscape-body { grid-template-columns:1fr; } .skill-detail { min-height:260px; } }
  @media (max-width: 700px) { .skill-treemap { grid-template-columns:1fr; } .category-panel, .category-panel.wide { grid-column:1 / -1; } .skill-map-head { align-items:flex-start; flex-direction:column; gap:0.2rem; } }
</style>
<script>
(() => {
  const data = __SKILL_DATA__;
  const root = document.getElementById("skill-landscape");
  if (!root) return;
  const map = document.getElementById("skill-treemap");
  const filters = document.getElementById("skill-category-filter");
  const detail = document.getElementById("skill-detail");
  const reset = document.getElementById("skill-reset");
  const categoryTotals = [...new Set(data.map(item => item.category))]
    .map(category => ({ category, total: data.filter(item => item.category === category).reduce((sum, item) => sum + item.jobs, 0) }))
    .sort((a, b) => b.total - a.total);
  let activeCategory = "All";

  const safe = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"}[char]));
  const short = (value, max = 18) => value.length > max ? `${value.slice(0, max - 1)}…` : value;

  function showDetail(item) {
    if (!item) {
      detail.innerHTML = '<div class="detail-empty">Select a skill tile to see where it appears, how often it is requested, and which roles supplied the evidence.</div>';
      return;
    }
    const evidence = item.evidence.length
      ? item.evidence.map(row => `<div class="detail-evidence"><div class="detail-job">${safe(row.job_title)}</div><div class="detail-company">${safe(row.company)} · ${safe(row.domain)}</div><div class="detail-requirement">${safe(row.requirement)}</div></div>`).join("")
      : '<div class="detail-empty">No source evidence was retained for this skill.</div>';
    detail.innerHTML = `<div class="detail-kicker">SELECTED SKILL</div><div class="detail-title">${safe(item.skill)}</div><div class="detail-category">${safe(item.category)}</div><div class="detail-metrics"><div class="detail-metric"><div class="detail-metric-label">Jobs requiring it</div><div class="detail-metric-value">${safe(item.jobs)}</div></div><div class="detail-metric"><div class="detail-metric-label">Job share</div><div class="detail-metric-value">${safe(item.share)}%</div></div><div class="detail-metric"><div class="detail-metric-label">Occurrences</div><div class="detail-metric-value">${safe(item.occurrences)}</div></div><div class="detail-metric"><div class="detail-metric-label">Last seen</div><div class="detail-metric-value">${safe(item.last_seen)}</div></div></div><div class="detail-section-label">SOURCE EVIDENCE</div>${evidence}`;
  }

  function selectSkill(item, button) {
    map.querySelectorAll(".skill-tile.selected").forEach(node => node.classList.remove("selected"));
    button.classList.add("selected");
    showDetail(item);
  }

  function renderFilters() {
    filters.innerHTML = "";
    ["All", ...categoryTotals.map(item => item.category)].forEach(category => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = category === "All" ? "All categories" : category;
      button.className = category === activeCategory ? "active" : "";
      button.setAttribute("aria-pressed", category === activeCategory ? "true" : "false");
      button.addEventListener("click", () => { activeCategory = category; renderFilters(); renderMap(); showDetail(null); });
      filters.appendChild(button);
    });
  }

  function renderMap() {
    map.innerHTML = "";
    const visibleCategories = activeCategory === "All"
      ? categoryTotals
      : [{ category: activeCategory, total: categoryTotals.find(item => item.category === activeCategory)?.total || 0 }];
    const maxTotal = Math.max(...visibleCategories.map(item => item.total), 1);
    visibleCategories.forEach((categoryData, categoryIndex) => {
      const category = categoryData.category;
      const categorySkills = data.filter(item => item.category === category).sort((a, b) => b.jobs - a.jobs);
      const panel = document.createElement("section");
      const spanClass = activeCategory !== "All" ? "full" : categoryData.total / maxTotal > 0.55 ? "wide" : "";
      panel.className = `category-panel ${spanClass}`;
      panel.style.animationDelay = `${categoryIndex * 35}ms`;
      const header = document.createElement("div");
      header.className = "category-header";
      header.innerHTML = `<div class="category-name" title="${safe(category)}">${safe(category)}</div><div class="category-meta">${categorySkills.length} skills · ${categoryData.total} jobs</div>`;
      panel.appendChild(header);
      const skillWrap = document.createElement("div");
      skillWrap.className = "category-skills";
      categorySkills.forEach(item => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `skill-tile tone-${["blue", "purple", "green", "orange", "slate"][categoryIndex % 5]}`;
        button.style.setProperty("--skill-weight", String(Math.max(1, item.jobs)));
        button.setAttribute("aria-label", `${item.skill}, requested by ${item.jobs} jobs`);
        button.title = `${item.skill} · ${item.jobs} jobs · ${item.share}% share`;
        button.innerHTML = `<span class="skill-tile-name">${safe(short(item.skill))}</span><span class="skill-tile-value">${safe(item.jobs)} jobs · ${safe(item.occurrences)} mentions</span><span class="skill-tile-share">${safe(item.share)}%</span>`;
        button.addEventListener("click", () => selectSkill(item, button));
        skillWrap.appendChild(button);
      });
      panel.appendChild(skillWrap);
      map.appendChild(panel);
    });
  }

  reset.addEventListener("click", () => { activeCategory = "All"; renderFilters(); renderMap(); showDetail(null); });
  renderFilters();
  renderMap();
  showDetail(null);
})();
</script>
'''
    return template.replace("__SKILL_DATA__", payload)
