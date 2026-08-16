#!/usr/bin/env python3
"""
Parse a Textract AnalyzeDocument JSON file and produce an HTML file that renders
the block graph using Graphviz (via @viz-js/viz WebAssembly in the browser).

Each node shows its BlockType and key content.  Hover for the full block details.

Usage:
    python3 scripts/visualize_textract.py input.json
    python3 scripts/visualize_textract.py input.json output.html   # explicit output path

A .dot file is also written alongside the HTML for use in desktop Graphviz tools.
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


# ── DOT generation ────────────────────────────────────────────────────────────

def dot_escape(s: str) -> str:
    """Escape a string for use inside a DOT double-quoted attribute."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def node_label(block: dict) -> str:
    """Short label rendered inside the graph node."""
    bt = block["BlockType"]
    parts = [bt]

    conf = block.get("Confidence")
    if conf is not None:
        parts[0] += f" {conf:.0f}%"

    text = block.get("Text", "")
    if text:
        clipped = text if len(text) <= 30 else text[:27] + "…"
        parts.append(f'"{clipped}"')

    if bt in ("CELL", "MERGED_CELL"):
        row, col = block.get("RowIndex", "?"), block.get("ColumnIndex", "?")
        rs, cs = block.get("RowSpan", 1), block.get("ColumnSpan", 1)
        span = f" {rs}×{cs}" if rs > 1 or cs > 1 else ""
        parts.append(f"R{row} C{col}{span}")

    if bt == "KEY_VALUE_SET":
        entities = block.get("EntityTypes", [])
        if entities:
            parts.append(",".join(entities))

    if bt == "WORD" and block.get("TextType"):
        parts.append(block["TextType"])

    return "\\n".join(parts)   # DOT \n = line break inside node label


def node_tooltip(block: dict) -> str:
    """Full block details as plain text for the SVG tooltip."""
    bt = block["BlockType"]
    rows = [bt, f"id: {block['Id']}"]

    conf = block.get("Confidence")
    if conf is not None:
        rows.append(f"confidence: {conf:.2f}%")
    if "Text" in block:
        rows.append(f"text: {block['Text']}")
    if "TextType" in block:
        rows.append(f"textType: {block['TextType']}")
    if "EntityTypes" in block:
        rows.append(f"entityTypes: {', '.join(block['EntityTypes'])}")
    if "RowIndex" in block:
        rows.append(
            f"row {block['RowIndex']}  col {block['ColumnIndex']}  "
            f"rowSpan {block.get('RowSpan',1)}  colSpan {block.get('ColumnSpan',1)}"
        )
    bb = block.get("Geometry", {}).get("BoundingBox", {})
    if bb:
        rows.append(
            f"bbox  L {bb['Left']:.3f}  T {bb['Top']:.3f}  "
            f"W {bb['Width']:.3f}  H {bb['Height']:.3f}"
        )
    for rel in block.get("Relationships", []):
        rows.append(f"{rel['Type']}: {len(rel['Ids'])} child(ren)")

    return "\\n".join(rows)


def build_dot(data: dict) -> str:
    blocks = data["Blocks"]
    id_to_n = {b["Id"]: f"n{i}" for i, b in enumerate(blocks)}

    lines: list[str] = [
        "digraph textract {",
        '  graph [rankdir=TB, splines=polyline, bgcolor="#f8fafc", pad="0.4,0.4", fontname=Helvetica];',
        '  node  [fontname=Helvetica, fontsize=9, style="filled,rounded", margin="0.12,0.06", penwidth=1.5];',
        '  edge  [fontname=Helvetica, fontsize=7, arrowsize=0.6];',
        "",
    ]

    for block in blocks:
        nid = id_to_n[block["Id"]]
        bt = block["BlockType"]
        s = NODE_STYLE.get(bt, DEFAULT_STYLE)
        label = dot_escape(node_label(block))
        tooltip = dot_escape(node_tooltip(block))
        lines.append(
            f'  {nid} [label="{label}", tooltip="{tooltip}", '
            f'fillcolor="{s["bg"]}", color="{s["border"]}", fontcolor="{s["font"]}"];'
        )

    lines.append("")

    for block in blocks:
        src = id_to_n[block["Id"]]
        for rel in block.get("Relationships", []):
            rt = rel["Type"]
            ec = EDGE_COLOR.get(rt, "#9ca3af")
            for child_id in rel.get("Ids", []):
                if child_id in id_to_n:
                    dst = id_to_n[child_id]
                    lines.append(
                        f'  {src} -> {dst} [label="{rt}", color="{ec}", fontcolor="{ec}"];'
                    )

    lines.append("}")
    return "\n".join(lines)


# ── HTML template ─────────────────────────────────────────────────────────────

def build_html(dot_src: str, title: str, stats: str) -> str:
    dot_json = json.dumps(dot_src)

    legend_items = ""
    for bt, s in NODE_STYLE.items():
        legend_items += (
            f'<span class="leg-item">'
            f'<span class="leg-box" style="background:{s["bg"]};border-color:{s["border"]}"></span>'
            f'{bt}</span>\n'
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
#toolbar {{ padding: 0.55rem 1rem; background: #1e293b;
            border-bottom: 1px solid #334155;
            display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; flex-shrink: 0; }}
#toolbar h1 {{ font-size: 0.9rem; font-weight: 700; color: #f1f5f9; white-space: nowrap; }}
#stats      {{ font-size: 0.75rem; color: #94a3b8; white-space: nowrap; }}

.btn {{ padding: 0.28rem 0.65rem; border-radius: 4px; border: 1px solid #475569;
        background: #334155; color: #e2e8f0; cursor: pointer; font-size: 0.75rem;
        transition: background 0.12s; white-space: nowrap; line-height: 1; }}
.btn:hover  {{ background: #475569; }}
.btn.active {{ background: #2563eb; border-color: #1d4ed8; }}

.btn-group {{ display: flex; gap: 0.25rem; align-items: center; }}
.sep {{ width: 1px; height: 1.4rem; background: #475569; flex-shrink: 0; }}

/* zoom buttons — square, larger font */
#btn-zoomin, #btn-zoomout {{ font-size: 1rem; padding: 0.1rem 0.55rem; font-weight: 700; }}

#zoom-label {{ font-size: 0.72rem; color: #94a3b8; min-width: 3.2rem; text-align: center; }}

#legend {{ display: flex; gap: 0.45rem; flex-wrap: wrap; align-items: center;
           font-size: 0.7rem; color: #cbd5e1; }}
.leg-item {{ display: flex; align-items: center; gap: 0.25rem; }}
.leg-box  {{ width: 12px; height: 12px; border-radius: 2px; border: 2px solid; flex-shrink: 0; }}

/* ── canvas area ── */
#viewport {{ flex: 1; overflow: hidden; position: relative; background: #f8fafc; }}

/* svg lives here, transformed for pan/zoom */
#svg-wrap {{ position: absolute; top: 0; left: 0; transform-origin: 0 0; }}
#svg-wrap svg {{ display: block; max-width: none; max-height: none; }}

/* transparent overlay — sits on top of the SVG and owns ALL mouse events for
   pan/zoom so SVG child elements can never eat a drag or scroll */
#overlay {{ position: absolute; inset: 0; z-index: 10; cursor: grab; }}
#overlay.panning {{ cursor: grabbing; }}

#status {{ position: absolute; inset: 0; display: flex; align-items: center;
           justify-content: center; font-size: 1rem; color: #64748b;
           background: #f8fafc; z-index: 20; }}

/* ── tooltip ── */
#tooltip {{ position: fixed; background: rgba(15,23,42,0.93); color: #e2e8f0;
            padding: 0.5rem 0.8rem; border-radius: 6px; font-size: 0.74rem;
            pointer-events: none; display: none; white-space: pre;
            max-width: 400px; line-height: 1.6; z-index: 500;
            border: 1px solid #334155; box-shadow: 0 4px 18px rgba(0,0,0,0.6); }}
</style>
</head>
<body>

<div id="toolbar">
  <h1>Textract Block Graph</h1>
  <span id="stats">{stats}</span>

  <div class="sep"></div>

  <!-- engine selector -->
  <div class="btn-group">
    <button class="btn active" onclick="render('dot')"   id="btn-dot">dot</button>
    <button class="btn"        onclick="render('fdp')"   id="btn-fdp">fdp</button>
    <button class="btn"        onclick="render('sfdp')"  id="btn-sfdp">sfdp</button>
    <button class="btn"        onclick="render('neato')" id="btn-neato">neato</button>
    <button class="btn"        onclick="render('circo')" id="btn-circo">circo</button>
  </div>

  <div class="sep"></div>

  <!-- zoom controls -->
  <div class="btn-group">
    <button class="btn" id="btn-zoomout" onclick="zoomStep(1/1.3)" title="Zoom out (-)">−</button>
    <span id="zoom-label">100%</span>
    <button class="btn" id="btn-zoomin"  onclick="zoomStep(1.3)"   title="Zoom in (+)">+</button>
  </div>
  <button class="btn" onclick="resetView()">Fit</button>

  <div class="sep"></div>
  <div id="legend">{legend_items}</div>
</div>

<div id="viewport">
  <div id="svg-wrap"></div>
  <div id="overlay"></div>
  <div id="status">Rendering graph…</div>
</div>
<div id="tooltip"></div>

<script>
const DOT_SRC = {dot_json};

// ── Viz.js ────────────────────────────────────────────────────────────────────
let vizInstance = null;

Viz.instance().then(v => {{
  vizInstance = v;
  render('dot');
}}).catch(err => {{
  document.getElementById('status').textContent = 'Failed to load Viz.js: ' + err;
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
      const wrap = document.getElementById('svg-wrap');
      wrap.innerHTML = '';
      wrap.appendChild(svg);
      status.style.display = 'none';
      resetView();
    }} catch (err) {{
      status.textContent = 'Render error: ' + err.message;
    }}
  }}, 20);
}}

// ── Pan / zoom ────────────────────────────────────────────────────────────────
let tx = 0, ty = 0, scale = 1;

function applyTransform() {{
  document.getElementById('svg-wrap').style.transform =
    `translate(${{tx}}px,${{ty}}px) scale(${{scale}})`;
  document.getElementById('zoom-label').textContent =
    Math.round(scale * 100) + '%';
}}

function zoomAround(factor, cx, cy) {{
  tx    = cx - (cx - tx) * factor;
  ty    = cy - (cy - ty) * factor;
  scale = scale * factor;
  applyTransform();
}}

function zoomStep(factor) {{
  const vp   = document.getElementById('viewport');
  const rect = vp.getBoundingClientRect();
  zoomAround(factor, rect.width / 2, rect.height / 2);
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

// keyboard shortcuts
window.addEventListener('keydown', e => {{
  if (e.target.tagName === 'INPUT') return;
  if (e.key === '+' || e.key === '=') zoomStep(1.3);
  if (e.key === '-' || e.key === '_') zoomStep(1/1.3);
  if (e.key === '0')                  resetView();
}});

// ── Overlay: owns all pan + zoom events ──────────────────────────────────────
const overlay = document.getElementById('overlay');

// scroll-wheel zoom — zooms toward the cursor position
overlay.addEventListener('wheel', e => {{
  e.preventDefault();
  const rect   = overlay.getBoundingClientRect();
  const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
  zoomAround(factor, e.clientX - rect.left, e.clientY - rect.top);
}}, {{ passive: false }});

// drag to pan
let drag = null;
overlay.addEventListener('mousedown', e => {{
  if (e.button !== 0) return;
  e.preventDefault();
  drag = {{ ox: e.clientX - tx, oy: e.clientY - ty }};
  overlay.classList.add('panning');
}});
window.addEventListener('mousemove', e => {{
  if (!drag) return;
  tx = e.clientX - drag.ox;
  ty = e.clientY - drag.oy;
  applyTransform();
  // while dragging, also update tooltip position but don't re-probe
  positionTooltip(e.clientX, e.clientY);
}});
window.addEventListener('mouseup', () => {{
  drag = null;
  overlay.classList.remove('panning');
}});

// ── Tooltip — probe through overlay to find SVG node under cursor ─────────────
const tip = document.getElementById('tooltip');

overlay.addEventListener('mousemove', e => {{
  if (drag) return;   // don't flicker during pan
  // temporarily disable overlay so elementsFromPoint sees the SVG behind it
  overlay.style.pointerEvents = 'none';
  const els = document.elementsFromPoint(e.clientX, e.clientY);
  overlay.style.pointerEvents = '';

  const nodeG = els.find(el => el.closest?.('g[id^="node"]'))?.closest('g[id^="node"]');
  if (nodeG) {{
    const title = nodeG.querySelector(':scope > title');
    if (title) {{
      tip.textContent = title.textContent;
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
    stem = input_path.stem
    out_dir = Path(sys.argv[2]).parent if len(sys.argv) > 2 else input_path.parent
    html_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".html")
    dot_path  = html_path.with_suffix(".dot")

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    if "Blocks" not in data:
        print("Error: no 'Blocks' key — is this a Textract AnalyzeDocument response?", file=sys.stderr)
        sys.exit(1)

    blocks = data["Blocks"]
    edge_count = sum(
        len(rel.get("Ids", []))
        for b in blocks
        for rel in b.get("Relationships", [])
    )
    stats = f"{len(blocks)} nodes  ·  {edge_count} edges"

    dot_src = build_dot(data)
    html_src = build_html(dot_src, title=f"Textract — {stem}", stats=stats)

    dot_path.write_text(dot_src, encoding="utf-8")
    html_path.write_text(html_src, encoding="utf-8")

    print(f"DOT  → {dot_path}")
    print(f"HTML → {html_path}  ({stats})")
    print()
    print("Open the HTML in a browser (needs internet for @viz-js/viz CDN).")
    print("Use the engine buttons to switch layouts; dot/fdp work best for this data.")


if __name__ == "__main__":
    main()
