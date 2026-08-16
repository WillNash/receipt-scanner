#!/usr/bin/env python3
"""
Visualize a Textract AnalyzeDocument JSON response as an interactive HTML graph.
Each node shows its BlockType, text content, and key metadata. Hover for the full block.

Usage:
    python3 scripts/visualize_textract.py input.json
    python3 scripts/visualize_textract.py input.json output.html
"""

import html as _html
import json
import sys
from pathlib import Path

# ── Appearance ────────────────────────────────────────────────────────────────

NODE_STYLES = {
    "PAGE":          {"bg": "#2563eb", "border": "#1d4ed8", "font": "#fff"},
    "LINE":          {"bg": "#16a34a", "border": "#15803d", "font": "#fff"},
    "WORD":          {"bg": "#86efac", "border": "#16a34a", "font": "#111"},
    "TABLE":         {"bg": "#d97706", "border": "#b45309", "font": "#fff"},
    "TABLE_TITLE":   {"bg": "#7c3aed", "border": "#6d28d9", "font": "#fff"},
    "CELL":          {"bg": "#fde68a", "border": "#d97706", "font": "#111"},
    "MERGED_CELL":   {"bg": "#fb923c", "border": "#ea580c", "font": "#fff"},
    "KEY_VALUE_SET": {"bg": "#e11d48", "border": "#be123c", "font": "#fff"},
}
DEFAULT_STYLE = {"bg": "#94a3b8", "border": "#64748b", "font": "#111"}

EDGE_COLORS = {
    "CHILD":       "#6b7280",
    "VALUE":       "#f59e0b",
    "MERGED_CELL": "#fb923c",
    "TABLE_TITLE": "#7c3aed",
}


# ── Node label & tooltip ──────────────────────────────────────────────────────

def make_label(block: dict) -> str:
    bt = block["BlockType"]
    parts = [bt]

    conf = block.get("Confidence")
    if conf is not None:
        parts[0] += f" {conf:.0f}%"

    text = block.get("Text", "")
    if text:
        display = text if len(text) <= 28 else text[:25] + "…"
        parts.append(f'"{display}"')

    if bt in ("CELL", "MERGED_CELL"):
        row, col = block.get("RowIndex", "?"), block.get("ColumnIndex", "?")
        rs, cs = block.get("RowSpan", 1), block.get("ColumnSpan", 1)
        span = f" span {rs}×{cs}" if rs > 1 or cs > 1 else ""
        parts.append(f"R{row} C{col}{span}")

    if bt == "KEY_VALUE_SET":
        entities = block.get("EntityTypes", [])
        if entities:
            parts.append(", ".join(entities))

    if bt == "WORD":
        tt = block.get("TextType")
        if tt:
            parts.append(tt)

    return "\n".join(parts)


def make_tooltip(block: dict) -> str:
    bt = block["BlockType"]
    rows = [f"<b>{bt}</b>", f"<small>id: {block['Id']}</small>"]

    conf = block.get("Confidence")
    if conf is not None:
        rows.append(f"Confidence: {conf:.2f}%")

    text = block.get("Text")
    if text is not None:
        rows.append(f"Text: <i>{_html.escape(text)}</i>")

    tt = block.get("TextType")
    if tt:
        rows.append(f"TextType: {tt}")

    entities = block.get("EntityTypes")
    if entities:
        rows.append(f"EntityTypes: {', '.join(entities)}")

    if "RowIndex" in block:
        rows.append(
            f"Row {block['RowIndex']}  Col {block['ColumnIndex']}  "
            f"RowSpan {block.get('RowSpan',1)}  ColSpan {block.get('ColumnSpan',1)}"
        )

    bb = block.get("Geometry", {}).get("BoundingBox", {})
    if bb:
        rows.append(
            f"BBox  L {bb['Left']:.3f}  T {bb['Top']:.3f}  "
            f"W {bb['Width']:.3f}  H {bb['Height']:.3f}"
        )

    rels = block.get("Relationships", [])
    if rels:
        for rel in rels:
            rows.append(f"{rel['Type']}: {len(rel['Ids'])} id(s)")

    return "<br>".join(rows)


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph(data: dict) -> tuple[list, list]:
    blocks = data.get("Blocks", [])
    nodes, edges = [], []

    for block in blocks:
        bt = block["BlockType"]
        style = NODE_STYLES.get(bt, DEFAULT_STYLE)

        nodes.append({
            "id": block["Id"],
            "label": make_label(block),
            "tooltip": make_tooltip(block),
            "color": {
                "background": style["bg"],
                "border": style["border"],
                "highlight": {"background": style["bg"], "border": "#fff"},
            },
            "font": {"color": style["font"], "size": 11, "face": "monospace"},
            "shape": "box",
            "blockType": bt,
        })

        for rel in block.get("Relationships", []):
            rel_type = rel["Type"]
            edge_color = EDGE_COLORS.get(rel_type, "#9ca3af")
            for child_id in rel.get("Ids", []):
                edges.append({
                    "from": block["Id"],
                    "to": child_id,
                    "label": rel_type,
                    "arrows": "to",
                    "color": {"color": edge_color, "highlight": "#fff"},
                    "font": {"size": 9, "color": edge_color, "strokeWidth": 0},
                    "smooth": {"type": "continuous"},
                })

    return nodes, edges


# ── HTML template ─────────────────────────────────────────────────────────────

def render_html(nodes: list, edges: list, title: str) -> str:
    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)

    legend_html = ""
    for bt, style in NODE_STYLES.items():
        legend_html += (
            f'<div class="leg-item">'
            f'<span class="leg-box" style="background:{style["bg"]};border-color:{style["border"]}"></span>'
            f'{bt}</div>\n'
        )

    # Block type list for the filter dropdown (built from actual data)
    all_types = sorted({n["blockType"] for n in nodes})
    type_opts = "\n".join(
        f'<label><input type="checkbox" value="{t}" checked onchange="applyFilter()"> {t}</label>'
        for t in all_types
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>{_html.escape(title)}</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #0f172a; color: #e2e8f0; height: 100vh;
        display: flex; flex-direction: column; overflow: hidden; }}

#toolbar {{ padding: 0.6rem 1rem; background: #1e293b;
            border-bottom: 1px solid #334155;
            display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; flex-shrink: 0; }}
#toolbar h1 {{ font-size: 0.95rem; font-weight: 700; color: #f8fafc; white-space: nowrap; }}
#stats {{ font-size: 0.78rem; color: #94a3b8; white-space: nowrap; }}

.btn {{ padding: 0.3rem 0.8rem; border-radius: 5px; border: 1px solid #334155;
        background: #334155; color: #e2e8f0; cursor: pointer; font-size: 0.78rem;
        transition: background 0.15s; white-space: nowrap; }}
.btn:hover {{ background: #475569; }}
.btn.active {{ background: #2563eb; border-color: #1d4ed8; }}

#legend {{ display: flex; gap: 0.6rem; flex-wrap: wrap; align-items: center;
           font-size: 0.72rem; color: #cbd5e1; }}
.leg-item {{ display: flex; align-items: center; gap: 0.3rem; }}
.leg-box  {{ width: 13px; height: 13px; border-radius: 2px; border: 2px solid;
             flex-shrink: 0; }}

#filter-panel {{ position: absolute; top: 3rem; left: 1rem; z-index: 200;
                 background: #1e293b; border: 1px solid #334155; border-radius: 8px;
                 padding: 0.75rem 1rem; display: none; min-width: 160px;
                 box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
#filter-panel label {{ display: flex; align-items: center; gap: 0.4rem;
                       font-size: 0.8rem; padding: 0.15rem 0; cursor: pointer; color: #cbd5e1; }}
#filter-panel input {{ accent-color: #2563eb; }}

#network {{ flex: 1; position: relative; }}

#tooltip {{ position: fixed; background: rgba(15,23,42,0.95); color: #e2e8f0;
            padding: 0.6rem 0.9rem; border-radius: 7px; font-size: 0.78rem;
            pointer-events: none; display: none; max-width: 360px; line-height: 1.65;
            z-index: 300; border: 1px solid #334155;
            box-shadow: 0 4px 20px rgba(0,0,0,0.6); }}
#tooltip b {{ color: #f8fafc; font-size: 0.85rem; }}
#tooltip small {{ color: #64748b; }}
</style>
</head>
<body>

<div id="toolbar">
  <h1>Textract Block Graph</h1>
  <span id="stats"></span>

  <button class="btn" onclick="network.fit()">Fit view</button>
  <button class="btn" id="physics-btn" onclick="togglePhysics()">Pause physics</button>
  <button class="btn" onclick="toggleFilter()">Filter types</button>

  <div id="legend">{legend_html}</div>
</div>

<div id="filter-panel">
  {type_opts}
</div>

<div id="network"></div>
<div id="tooltip"></div>

<script>
// ── Data ────────────────────────────────────────────────────────────────────
const rawNodes = {nodes_json};
const rawEdges = {edges_json};

const nodeDS = new vis.DataSet(rawNodes);
const edgeDS = new vis.DataSet(rawEdges);

document.getElementById('stats').textContent =
  `${{rawNodes.length}} nodes  ·  ${{rawEdges.length}} edges`;

// ── Network ──────────────────────────────────────────────────────────────────
const network = new vis.Network(
  document.getElementById('network'),
  {{ nodes: nodeDS, edges: edgeDS }},
  {{
    physics: {{
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {{
        gravitationalConstant: -60,
        centralGravity: 0.005,
        springLength: 120,
        springConstant: 0.06,
        damping: 0.5,
        avoidOverlap: 0.5,
      }},
      stabilization: {{ iterations: 200, fit: true }},
    }},
    interaction: {{
      hover: true,
      navigationButtons: true,
      keyboard: {{ enabled: true, bindToWindow: false }},
      tooltipDelay: 9999,   // disable built-in tooltip; we use our own
    }},
    nodes: {{ borderWidth: 2, margin: 6 }},
    edges: {{ width: 1.2 }},
  }}
);

// ── Physics toggle ───────────────────────────────────────────────────────────
let physicsOn = true;
network.on('stabilizationIterationsDone', () => {{
  network.setOptions({{ physics: {{ enabled: false }} }});
  physicsOn = false;
  document.getElementById('physics-btn').textContent = 'Resume physics';
}});

function togglePhysics() {{
  physicsOn = !physicsOn;
  network.setOptions({{ physics: {{ enabled: physicsOn }} }});
  document.getElementById('physics-btn').textContent =
    physicsOn ? 'Pause physics' : 'Resume physics';
  document.getElementById('physics-btn').classList.toggle('active', physicsOn);
}}

// ── Type filter ───────────────────────────────────────────────────────────────
function toggleFilter() {{
  const p = document.getElementById('filter-panel');
  p.style.display = p.style.display === 'block' ? 'none' : 'block';
}}

document.addEventListener('click', e => {{
  const p = document.getElementById('filter-panel');
  if (!p.contains(e.target) && !e.target.closest('.btn')) {{
    p.style.display = 'none';
  }}
}});

function applyFilter() {{
  const checked = new Set(
    [...document.querySelectorAll('#filter-panel input:checked')].map(i => i.value)
  );
  const hiddenNodeIds = new Set();
  nodeDS.update(rawNodes.map(n => {{
    const hide = !checked.has(n.blockType);
    if (hide) hiddenNodeIds.add(n.id);
    return {{ id: n.id, hidden: hide }};
  }}));
  edgeDS.update(rawEdges.map(e => ({{
    id: e.id,
    hidden: hiddenNodeIds.has(e.from) || hiddenNodeIds.has(e.to),
  }})));
}}

// ── Tooltip ───────────────────────────────────────────────────────────────────
const tooltipEl = document.getElementById('tooltip');
const nodeTooltipMap = Object.fromEntries(rawNodes.map(n => [n.id, n.tooltip]));

network.on('hoverNode', params => {{
  const tip = nodeTooltipMap[params.node];
  if (tip) {{
    tooltipEl.innerHTML = tip;
    tooltipEl.style.display = 'block';
  }}
}});
network.on('blurNode', () => {{ tooltipEl.style.display = 'none'; }});
document.addEventListener('mousemove', e => {{
  if (tooltipEl.style.display === 'block') {{
    const x = e.clientX + 14, y = e.clientY + 14;
    const ow = tooltipEl.offsetWidth, oh = tooltipEl.offsetHeight;
    tooltipEl.style.left = (x + ow > window.innerWidth  ? x - ow - 20 : x) + 'px';
    tooltipEl.style.top  = (y + oh > window.innerHeight ? y - oh - 20 : y) + 'px';
  }}
}});
</script>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.json [output.html]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".html")

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    if "Blocks" not in data:
        print("Error: JSON does not contain a 'Blocks' key — is this a Textract response?", file=sys.stderr)
        sys.exit(1)

    nodes, edges = build_graph(data)
    html = render_html(nodes, edges, title=f"Textract — {input_path.name}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Written: {output_path}")
    print(f"  {len(nodes)} nodes  ·  {len(edges)} edges")


if __name__ == "__main__":
    main()
