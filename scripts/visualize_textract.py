#!/usr/bin/env python3
"""
Parse a Textract AnalyzeDocument JSON file and produce an interactive HTML graph.
Rendered by @viz-js/viz (Graphviz WebAssembly) in the browser.

Features:
  - Pan (drag) and zoom (scroll wheel, +/- buttons)
  - Keyboard navigation: arrow keys traverse graph edges, Tab cycles all nodes
  - Live search: type to find nodes by content, Enter/n jumps between matches
  - Hover tooltip: full block detail on mouse-over

Usage:
    python3 scripts/visualize_textract.py input.json
    python3 scripts/visualize_textract.py input.json output.html

Also writes a .dot file for use in desktop Graphviz tools.
"""

import json
import sys
from pathlib import Path

# ── Appearance ────────────────────────────────────────────────────────────────

NODE_STYLE = {
    "PAGE":          {"bg": "#2563eb", "border": "#1d4ed8", "font": "white"},
    "LINE":          {"bg": "#16a34a", "border": "#15803d", "font": "white"},
    "WORD":          {"bg": "#86efac", "border": "#16a34a", "font": "#111111"},
    "TABLE":         {"bg": "#d97706", "border": "#b45309", "font": "white"},
    "TABLE_TITLE":   {"bg": "#7c3aed", "border": "#6d28d9", "font": "white"},
    "CELL":          {"bg": "#fde68a", "border": "#ca8a04", "font": "#111111"},
    "MERGED_CELL":   {"bg": "#fb923c", "border": "#ea580c", "font": "white"},
    "KEY_VALUE_SET": {"bg": "#e11d48", "border": "#be123c", "font": "white"},
}
DEFAULT_STYLE = {"bg": "#94a3b8", "border": "#64748b", "font": "#111111"}

EDGE_COLOR = {
    "CHILD":       "#6b7280",
    "VALUE":       "#d97706",
    "MERGED_CELL": "#fb923c",
    "TABLE_TITLE": "#7c3aed",
}


# ── DOT helpers ───────────────────────────────────────────────────────────────

def dot_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def node_label(block: dict) -> str:
    bt = block["BlockType"]
    parts = [bt]

    conf = block.get("Confidence")
    if conf is not None:
        parts[0] += f" {conf:.0f}%"

    text = block.get("Text", "")
    if text:
        parts.append(f'"{text[:30]}{"…" if len(text) > 30 else ""}"')

    if bt in ("CELL", "MERGED_CELL"):
        r, c = block.get("RowIndex", "?"), block.get("ColumnIndex", "?")
        rs, cs = block.get("RowSpan", 1), block.get("ColumnSpan", 1)
        parts.append(f"R{r} C{c}" + (f" {rs}×{cs}" if rs > 1 or cs > 1 else ""))

    if bt == "KEY_VALUE_SET" and block.get("EntityTypes"):
        parts.append(",".join(block["EntityTypes"]))

    if bt == "WORD" and block.get("TextType"):
        parts.append(block["TextType"])

    return "\\n".join(parts)


def node_tooltip(block: dict) -> str:
    bt = block["BlockType"]
    rows = [bt, f"id: {block['Id']}"]
    if block.get("Confidence") is not None:
        rows.append(f"confidence: {block['Confidence']:.2f}%")
    if "Text" in block:
        rows.append(f"text: {block['Text']}")
    if "TextType" in block:
        rows.append(f"textType: {block['TextType']}")
    if block.get("EntityTypes"):
        rows.append(f"entityTypes: {', '.join(block['EntityTypes'])}")
    if "RowIndex" in block:
        rows.append(
            f"row {block['RowIndex']}  col {block['ColumnIndex']}  "
            f"rowSpan {block.get('RowSpan',1)}  colSpan {block.get('ColumnSpan',1)}"
        )
    bb = block.get("Geometry", {}).get("BoundingBox", {})
    if bb:
        rows.append(f"bbox  L {bb['Left']:.3f}  T {bb['Top']:.3f}  "
                    f"W {bb['Width']:.3f}  H {bb['Height']:.3f}")
    for rel in block.get("Relationships", []):
        rows.append(f"{rel['Type']}: {len(rel['Ids'])} child(ren)")
    return "\\n".join(rows)


def node_search_text(block: dict) -> str:
    """Flat lowercased string used for JS search matching."""
    parts = [block["BlockType"]]
    if block.get("Text"):
        parts.append(block["Text"])
    if block.get("EntityTypes"):
        parts.extend(block["EntityTypes"])
    if "RowIndex" in block:
        parts.append(f"R{block['RowIndex']}C{block['ColumnIndex']}")
    return " ".join(parts).lower()


# ── Build DOT + graph metadata ────────────────────────────────────────────────

def build_dot_and_data(data: dict) -> tuple[str, dict]:
    """
    Returns (dot_string, graph_data) where graph_data is a dict ready to be
    JSON-embedded in the HTML:
      nodeOrder   - list of DOT IDs in block order (for Tab cycling)
      adjacency   - {id: {parents:[...], children:[...]}}
      nodeSearch  - [{id, text}] for live search
    """
    blocks = data["Blocks"]
    id_to_n = {b["Id"]: f"n{i}" for i, b in enumerate(blocks)}

    # ── DOT source ──
    dot_lines: list[str] = [
        "digraph textract {",
        '  graph [rankdir=TB, splines=polyline, bgcolor="#f8fafc",'
        '         pad="0.4,0.4", fontname=Helvetica];',
        '  node  [fontname=Helvetica, fontsize=9, style="filled,rounded",'
        '         margin="0.12,0.06", penwidth=1.5];',
        '  edge  [fontname=Helvetica, fontsize=7, arrowsize=0.6];',
        "",
    ]

    for block in blocks:
        nid = id_to_n[block["Id"]]
        bt  = block["BlockType"]
        s   = NODE_STYLE.get(bt, DEFAULT_STYLE)
        dot_lines.append(
            f'  {nid} [label="{dot_escape(node_label(block))}",'
            f' tooltip="{dot_escape(node_tooltip(block))}",'
            f' fillcolor="{s["bg"]}", color="{s["border"]}", fontcolor="{s["font"]}"];'
        )

    dot_lines.append("")

    for block in blocks:
        src = id_to_n[block["Id"]]
        for rel in block.get("Relationships", []):
            rt = rel["Type"]
            ec = EDGE_COLOR.get(rt, "#9ca3af")
            for cid in rel.get("Ids", []):
                if cid in id_to_n:
                    dot_lines.append(
                        f'  {src} -> {id_to_n[cid]}'
                        f' [label="{rt}", color="{ec}", fontcolor="{ec}"];'
                    )

    dot_lines.append("}")
    dot_src = "\n".join(dot_lines)

    # ── Graph metadata for JS ──
    node_order = [id_to_n[b["Id"]] for b in blocks]

    adjacency: dict[str, dict] = {id_to_n[b["Id"]]: {"parents": [], "children": []}
                                   for b in blocks}
    for block in blocks:
        src = id_to_n[block["Id"]]
        for rel in block.get("Relationships", []):
            for cid in rel.get("Ids", []):
                if cid in id_to_n:
                    dst = id_to_n[cid]
                    adjacency[src]["children"].append(dst)
                    adjacency[dst]["parents"].append(src)

    node_search = [
        {"id": id_to_n[b["Id"]], "text": node_search_text(b)}
        for b in blocks
    ]

    graph_data = {
        "nodeOrder":  node_order,
        "adjacency":  adjacency,
        "nodeSearch": node_search,
    }
    return dot_src, graph_data


# ── HTML template ─────────────────────────────────────────────────────────────

def build_html(dot_src: str, graph_data: dict, title: str, stats: str) -> str:
    dot_json   = json.dumps(dot_src)
    gdata_json = json.dumps(graph_data)

    legend_html = "".join(
        f'<span class="leg-item">'
        f'<span class="leg-box" style="background:{s["bg"]};border-color:{s["border"]}"></span>'
        f'{bt}</span>\n'
        for bt, s in NODE_STYLE.items()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/@viz-js/viz@3/lib/viz-standalone.js"></script>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #0f172a; color: #e2e8f0;
        height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}

/* ── toolbar ── */
#toolbar {{ padding: 0.45rem 0.9rem; background: #1e293b;
            border-bottom: 1px solid #334155;
            display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; flex-shrink: 0; }}
#toolbar h1 {{ font-size: 0.85rem; font-weight: 700; color: #f1f5f9; white-space: nowrap; }}
#stats      {{ font-size: 0.72rem; color: #94a3b8; white-space: nowrap; }}

.sep {{ width: 1px; height: 1.3rem; background: #475569; flex-shrink: 0; }}

.btn {{ padding: 0.25rem 0.6rem; border-radius: 4px; border: 1px solid #475569;
        background: #334155; color: #e2e8f0; cursor: pointer; font-size: 0.73rem;
        transition: background 0.1s; white-space: nowrap; line-height: 1; }}
.btn:hover  {{ background: #475569; }}
.btn.active {{ background: #2563eb; border-color: #1d4ed8; }}
.btn-group  {{ display: flex; gap: 0.2rem; align-items: center; }}

#btn-zoomin, #btn-zoomout {{ font-size: 0.95rem; padding: 0.1rem 0.5rem; font-weight: 700; }}
#zoom-label {{ font-size: 0.7rem; color: #94a3b8; min-width: 3rem; text-align: center; }}

/* search */
#search-wrap {{ display: flex; align-items: center; gap: 0.25rem; }}
#search-input {{ background: #0f172a; border: 1px solid #475569; border-radius: 4px;
                 color: #e2e8f0; font-size: 0.73rem; padding: 0.22rem 0.5rem;
                 width: 160px; outline: none; }}
#search-input:focus {{ border-color: #2563eb; }}
#search-count {{ font-size: 0.7rem; color: #94a3b8; white-space: nowrap; min-width: 4rem; }}

/* legend */
#legend {{ display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center;
           font-size: 0.68rem; color: #cbd5e1; }}
.leg-item {{ display: flex; align-items: center; gap: 0.2rem; }}
.leg-box  {{ width: 11px; height: 11px; border-radius: 2px; border: 2px solid; flex-shrink: 0; }}

/* ── canvas ── */
#viewport {{ flex: 1; overflow: hidden; position: relative; background: #f8fafc; }}
#svg-wrap  {{ position: absolute; top: 0; left: 0; transform-origin: 0 0; }}
#svg-wrap svg {{ display: block; max-width: none; max-height: none; }}

/* transparent overlay captures all pan/zoom mouse events */
#overlay {{ position: absolute; inset: 0; z-index: 10; cursor: grab; }}
#overlay.panning {{ cursor: grabbing; }}

#status {{ position: absolute; inset: 0; display: flex; align-items: center;
           justify-content: center; font-size: 1rem; color: #64748b;
           background: #f8fafc; z-index: 20; }}

/* selected / search-match node highlighting (applied to SVG groups) */
#svg-wrap g.node.selected polygon,
#svg-wrap g.node.selected ellipse,
#svg-wrap g.node.selected rect {{
  stroke: #f97316 !important;
  stroke-width: 4px !important;
  filter: drop-shadow(0 0 5px rgba(249,115,22,0.7));
}}
#svg-wrap g.node.search-match polygon,
#svg-wrap g.node.search-match ellipse,
#svg-wrap g.node.search-match rect {{
  stroke: #facc15 !important;
  stroke-width: 2.5px !important;
}}
#svg-wrap g.node.search-current polygon,
#svg-wrap g.node.search-current ellipse,
#svg-wrap g.node.search-current rect {{
  stroke: #f97316 !important;
  stroke-width: 4px !important;
  filter: drop-shadow(0 0 5px rgba(249,115,22,0.7));
}}

/* hover tooltip */
#tooltip {{ position: fixed; background: rgba(15,23,42,0.94); color: #e2e8f0;
            padding: 0.5rem 0.8rem; border-radius: 6px; font-size: 0.73rem;
            pointer-events: none; display: none; white-space: pre;
            max-width: 400px; line-height: 1.6; z-index: 500;
            border: 1px solid #334155; box-shadow: 0 4px 20px rgba(0,0,0,0.6); }}

/* selection info bar at bottom */
#sel-bar {{ position: absolute; bottom: 0; left: 0; right: 0; z-index: 15;
            background: rgba(30,41,59,0.92); border-top: 1px solid #334155;
            padding: 0.3rem 0.9rem; font-size: 0.72rem; color: #cbd5e1;
            display: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
#sel-bar b {{ color: #f8fafc; }}
</style>
</head>
<body>

<div id="toolbar">
  <h1>Textract Block Graph</h1>
  <span id="stats">{stats}</span>
  <div class="sep"></div>

  <!-- engine -->
  <div class="btn-group">
    <button class="btn active" onclick="render('dot')"   id="btn-dot">dot</button>
    <button class="btn"        onclick="render('fdp')"   id="btn-fdp">fdp</button>
    <button class="btn"        onclick="render('sfdp')"  id="btn-sfdp">sfdp</button>
    <button class="btn"        onclick="render('neato')" id="btn-neato">neato</button>
    <button class="btn"        onclick="render('circo')" id="btn-circo">circo</button>
  </div>
  <div class="sep"></div>

  <!-- zoom -->
  <div class="btn-group">
    <button class="btn" id="btn-zoomout" onclick="zoomStep(1/1.3)" title="Zoom out (-)">−</button>
    <span   id="zoom-label">100%</span>
    <button class="btn" id="btn-zoomin"  onclick="zoomStep(1.3)"   title="Zoom in (+)">+</button>
  </div>
  <button class="btn" onclick="resetView()" title="Fit graph to window (0)">Fit</button>
  <div class="sep"></div>

  <!-- search -->
  <div id="search-wrap">
    <input  id="search-input" type="text" placeholder="Search nodes…"
            oninput="onSearchInput()" onkeydown="onSearchKey(event)" />
    <button class="btn" onclick="searchStep(-1)" title="Previous match">◀</button>
    <button class="btn" onclick="searchStep(+1)" title="Next match (Enter)">▶</button>
    <button class="btn" onclick="clearSearch()" title="Clear">✕</button>
    <span   id="search-count"></span>
  </div>
  <div class="sep"></div>

  <div id="legend">{legend_html}</div>
</div>

<div id="viewport">
  <div id="svg-wrap"></div>
  <div id="overlay"></div>
  <div id="status">Rendering graph…</div>
  <div id="sel-bar"></div>
</div>
<div id="tooltip"></div>

<script>
const DOT_SRC   = {dot_json};
const GDATA     = {gdata_json};
const NODE_ORDER  = GDATA.nodeOrder;
const ADJACENCY   = GDATA.adjacency;
const NODE_SEARCH = GDATA.nodeSearch;  // {{id, text}}

// ── Viz rendering ─────────────────────────────────────────────────────────────
let vizInstance = null;

Viz.instance().then(v => {{
  vizInstance = v;
  render('dot');
}}).catch(err => {{
  document.getElementById('status').textContent = 'Viz.js load failed: ' + err;
}});

function render(engine) {{
  if (!vizInstance) return;
  ['dot','fdp','sfdp','neato','circo'].forEach(e =>
    document.getElementById('btn-' + e).classList.toggle('active', e === engine));

  const status = document.getElementById('status');
  status.textContent = `Rendering with ${{engine}}…`;
  status.style.display = 'flex';

  setTimeout(() => {{
    try {{
      const svg = vizInstance.renderSVGElement(DOT_SRC, {{ engine }});
      document.getElementById('svg-wrap').replaceChildren(svg);
      status.style.display = 'none';
      buildNodeMap();
      resetView();
      // re-apply current search highlights after re-render
      if (searchMatches.length) applySearchHighlights();
      if (selectedId) {{
        const g = nameToGroup[selectedId];
        if (g) g.classList.add('selected');
      }}
    }} catch (err) {{
      status.textContent = 'Render error: ' + err.message;
    }}
  }}, 20);
}}

// ── Node map: DOT name → SVG <g> element ─────────────────────────────────────
let nameToGroup = {{}};

function buildNodeMap() {{
  nameToGroup = {{}};
  document.querySelectorAll('#svg-wrap g[id^="node"] > title').forEach(t => {{
    const g = t.closest('g');
    if (g) nameToGroup[t.textContent.trim()] = g;
  }});
}}

// ── Selection ─────────────────────────────────────────────────────────────────
let selectedId = null;

function selectNode(id, center = true) {{
  if (selectedId && nameToGroup[selectedId])
    nameToGroup[selectedId].classList.remove('selected', 'search-current');
  selectedId = id;
  if (!id) {{ updateSelBar(null); return; }}
  const g = nameToGroup[id];
  if (g) {{
    g.classList.add('selected');
    if (center) centerOnGroup(g);
  }}
  updateSelBar(id);
}}

function updateSelBar(id) {{
  const bar = document.getElementById('sel-bar');
  if (!id) {{ bar.style.display = 'none'; return; }}
  const info = NODE_SEARCH.find(n => n.id === id);
  if (!info) {{ bar.style.display = 'none'; return; }}
  const adj = ADJACENCY[id] || {{}};
  bar.innerHTML =
    `<b>${{id}}</b>  ${{info.text.slice(0,120)}}` +
    `  <span style="color:#64748b">` +
    `↑ ${{adj.parents?.length ?? 0}} parent(s)  ` +
    `↓ ${{adj.children?.length ?? 0}} child(ren)</span>`;
  bar.style.display = 'block';
}}

function centerOnGroup(g) {{
  const vp   = document.getElementById('viewport');
  const bbox = g.getBBox();
  const cx   = bbox.x + bbox.width  / 2;
  const cy   = bbox.y + bbox.height / 2;
  tx = vp.clientWidth  / 2 - cx * scale;
  ty = vp.clientHeight / 2 - cy * scale;
  applyTransform();
}}

// Click on overlay → find node under cursor and select it
const overlay = document.getElementById('overlay');
overlay.addEventListener('click', e => {{
  if (wasDragging) return;   // ignore click that ends a drag
  overlay.style.pointerEvents = 'none';
  const els = document.elementsFromPoint(e.clientX, e.clientY);
  overlay.style.pointerEvents = '';
  const g = els.find(el => el.closest?.('g[id^="node"]'))?.closest('g[id^="node"]');
  if (g) {{
    const title = g.querySelector(':scope > title');
    if (title) selectNode(title.textContent.trim());
  }}
}});

// ── Keyboard navigation ───────────────────────────────────────────────────────
window.addEventListener('keydown', e => {{
  // Don't steal keys from the search box (except Escape)
  if (document.activeElement === document.getElementById('search-input')) {{
    if (e.key === 'Escape') {{ document.activeElement.blur(); clearSearch(); }}
    return;
  }}

  if (e.key === '+' || e.key === '=') {{ e.preventDefault(); zoomStep(1.3); return; }}
  if (e.key === '-' || e.key === '_') {{ e.preventDefault(); zoomStep(1/1.3); return; }}
  if (e.key === '0')                  {{ e.preventDefault(); resetView(); return; }}
  if (e.key === '/')                  {{ e.preventDefault(); document.getElementById('search-input').focus(); return; }}

  const NAV = ['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Tab'];
  if (!NAV.includes(e.key)) return;
  e.preventDefault();

  // If nothing selected yet, pick first node
  if (!selectedId) {{
    selectNode(NODE_ORDER[0]);
    return;
  }}

  const adj  = ADJACENCY[selectedId] || {{}};
  const idx  = NODE_ORDER.indexOf(selectedId);

  if (e.key === 'Tab') {{
    // Tab / Shift-Tab: cycle through all nodes in DOT order
    const next = e.shiftKey
      ? NODE_ORDER[(idx - 1 + NODE_ORDER.length) % NODE_ORDER.length]
      : NODE_ORDER[(idx + 1) % NODE_ORDER.length];
    selectNode(next);

  }} else if (e.key === 'ArrowRight') {{
    // first child
    if (adj.children?.length) selectNode(adj.children[0]);

  }} else if (e.key === 'ArrowLeft') {{
    // first parent
    if (adj.parents?.length) selectNode(adj.parents[0]);

  }} else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {{
    // Siblings: other children of the first parent; fall back to global order
    const parent   = adj.parents?.[0];
    const siblings = parent ? (ADJACENCY[parent]?.children ?? []) : NODE_ORDER;
    const si       = siblings.indexOf(selectedId);
    if (si !== -1) {{
      const delta = e.key === 'ArrowDown' ? 1 : -1;
      const next  = siblings[(si + delta + siblings.length) % siblings.length];
      selectNode(next);
    }} else {{
      const delta = e.key === 'ArrowDown' ? 1 : -1;
      selectNode(NODE_ORDER[(idx + delta + NODE_ORDER.length) % NODE_ORDER.length]);
    }}
  }}
}});

// ── Search ────────────────────────────────────────────────────────────────────
let searchMatches = [];   // DOT IDs of matching nodes
let searchIdx     = -1;

function onSearchInput() {{
  const q = document.getElementById('search-input').value.trim().toLowerCase();
  clearSearchHighlights();
  if (!q) {{ searchMatches = []; searchIdx = -1; updateSearchCount(); return; }}
  searchMatches = NODE_SEARCH.filter(n => n.text.includes(q)).map(n => n.id);
  searchIdx     = searchMatches.length ? 0 : -1;
  updateSearchCount();
  applySearchHighlights();
  if (searchMatches.length) jumpToMatch(0);
}}

function onSearchKey(e) {{
  if (e.key === 'Enter')  {{ e.preventDefault(); searchStep(e.shiftKey ? -1 : +1); }}
  if (e.key === 'Escape') {{ clearSearch(); document.getElementById('search-input').blur(); }}
}}

function searchStep(delta) {{
  if (!searchMatches.length) return;
  searchIdx = (searchIdx + delta + searchMatches.length) % searchMatches.length;
  updateSearchCount();
  jumpToMatch(searchIdx);
}}

function jumpToMatch(i) {{
  const id = searchMatches[i];
  // mark current match distinctly
  searchMatches.forEach((mid, mi) => {{
    const g = nameToGroup[mid];
    if (!g) return;
    g.classList.toggle('search-current', mi === i);
    g.classList.toggle('search-match',   mi !== i);
  }});
  selectNode(id, true);   // center viewport
}}

function applySearchHighlights() {{
  searchMatches.forEach((mid, mi) => {{
    const g = nameToGroup[mid];
    if (!g) return;
    g.classList.add(mi === searchIdx ? 'search-current' : 'search-match');
  }});
}}

function clearSearchHighlights() {{
  document.querySelectorAll('#svg-wrap g.search-match, #svg-wrap g.search-current')
    .forEach(g => g.classList.remove('search-match', 'search-current'));
}}

function clearSearch() {{
  clearSearchHighlights();
  searchMatches = [];
  searchIdx     = -1;
  document.getElementById('search-input').value = '';
  updateSearchCount();
}}

function updateSearchCount() {{
  const el = document.getElementById('search-count');
  if (!searchMatches.length) {{ el.textContent = ''; return; }}
  el.textContent = `${{searchIdx + 1}} / ${{searchMatches.length}}`;
}}

// ── Pan / zoom ────────────────────────────────────────────────────────────────
let tx = 0, ty = 0, scale = 1;

function applyTransform() {{
  document.getElementById('svg-wrap').style.transform =
    `translate(${{tx}}px,${{ty}}px) scale(${{scale}})`;
  document.getElementById('zoom-label').textContent = Math.round(scale * 100) + '%';
}}

function zoomAround(factor, cx, cy) {{
  tx = cx - (cx - tx) * factor;
  ty = cy - (cy - ty) * factor;
  scale *= factor;
  applyTransform();
}}

function zoomStep(factor) {{
  const r = document.getElementById('viewport').getBoundingClientRect();
  zoomAround(factor, r.width / 2, r.height / 2);
}}

function resetView() {{
  const vp  = document.getElementById('viewport');
  const svg = document.querySelector('#svg-wrap svg');
  if (!svg) return;
  const svgW = svg.viewBox.baseVal.width  || svg.width.baseVal.value  || 800;
  const svgH = svg.viewBox.baseVal.height || svg.height.baseVal.value || 600;
  scale = Math.min(vp.clientWidth / svgW, vp.clientHeight / svgH) * 0.95;
  tx    = (vp.clientWidth  - svgW * scale) / 2;
  ty    = (vp.clientHeight - svgH * scale) / 2;
  applyTransform();
}}

// scroll-wheel zoom toward cursor
overlay.addEventListener('wheel', e => {{
  e.preventDefault();
  const r = overlay.getBoundingClientRect();
  zoomAround(e.deltaY < 0 ? 1.12 : 1/1.12, e.clientX - r.left, e.clientY - r.top);
}}, {{ passive: false }});

// drag to pan — track whether we actually dragged (to suppress click-to-select)
let drag = null, wasDragging = false;
overlay.addEventListener('mousedown', e => {{
  if (e.button !== 0) return;
  e.preventDefault();
  drag = {{ ox: e.clientX - tx, oy: e.clientY - ty }};
  wasDragging = false;
  overlay.classList.add('panning');
}});
window.addEventListener('mousemove', e => {{
  if (!drag) return;
  const newTx = e.clientX - drag.ox;
  const newTy = e.clientY - drag.oy;
  if (Math.abs(newTx - tx) > 2 || Math.abs(newTy - ty) > 2) wasDragging = true;
  tx = newTx; ty = newTy;
  applyTransform();
  positionTooltip(e.clientX, e.clientY);
}});
window.addEventListener('mouseup', () => {{
  drag = null;
  overlay.classList.remove('panning');
}});

// ── Hover tooltip (probes through overlay) ────────────────────────────────────
const tip = document.getElementById('tooltip');

overlay.addEventListener('mousemove', e => {{
  if (drag) return;
  overlay.style.pointerEvents = 'none';
  const els = document.elementsFromPoint(e.clientX, e.clientY);
  overlay.style.pointerEvents = '';
  const nodeG = els.find(el => el.closest?.('g[id^="node"]'))?.closest('g[id^="node"]');
  if (nodeG) {{
    const t = nodeG.querySelector(':scope > title');
    if (t) {{
      // use tooltip attribute text from the DOT (stored in SVG <title> of the <g>)
      // Graphviz puts the node's tooltip= value in a nested <title> on the shape, not
      // the group title. Fall back to the group title (which is the DOT node name).
      const shapeTip = nodeG.querySelector('a > title') || nodeG.querySelector(':scope > g > title');
      tip.textContent = shapeTip ? shapeTip.textContent : t.textContent;
      tip.style.display = 'block';
      positionTooltip(e.clientX, e.clientY);
      return;
    }}
  }}
  tip.style.display = 'none';
}});
overlay.addEventListener('mouseleave', () => {{ tip.style.display = 'none'; }});

function positionTooltip(cx, cy) {{
  if (tip.style.display !== 'block') return;
  const ow = tip.offsetWidth, oh = tip.offsetHeight;
  tip.style.left = (cx + 14 + ow > window.innerWidth  ? cx - ow - 14 : cx + 14) + 'px';
  tip.style.top  = (cy + 14 + oh > window.innerHeight ? cy - oh - 14 : cy + 14) + 'px';
}}
</script>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.json [output.html]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    html_path  = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".html")
    dot_path   = html_path.with_suffix(".dot")

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    if "Blocks" not in data:
        print("Error: no 'Blocks' key — is this a Textract AnalyzeDocument response?",
              file=sys.stderr)
        sys.exit(1)

    blocks = data["Blocks"]
    edge_count = sum(len(rel.get("Ids", []))
                     for b in blocks for rel in b.get("Relationships", []))
    stats = f"{len(blocks)} nodes  ·  {edge_count} edges"

    dot_src, graph_data = build_dot_and_data(data)
    html_src = build_html(dot_src, graph_data, title=f"Textract — {input_path.stem}", stats=stats)

    dot_path.write_text(dot_src,  encoding="utf-8")
    html_path.write_text(html_src, encoding="utf-8")

    print(f"DOT  → {dot_path}")
    print(f"HTML → {html_path}  ({stats})")
    print()
    print("Keyboard shortcuts:")
    print("  Arrow keys  navigate graph edges (←parent  →child  ↑↓siblings)")
    print("  Tab/Shift+Tab  cycle all nodes in order")
    print("  /  focus search box   +/-  zoom   0  fit view")
    print("  Search: Enter/▶ next match, Shift+Enter/◀ previous")


if __name__ == "__main__":
    main()
