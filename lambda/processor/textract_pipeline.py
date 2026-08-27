from dataclasses import dataclass

from line_grouping import group_blocks

textract = None  # injected by handler via set_textract_client()


def set_textract_client(client) -> None:
    """Inject the shared Textract client from handler."""
    global textract
    textract = client


@dataclass
class TextractResult:
    text: str
    lines: list
    blocks: list
    words: list
    rows: list
    line_height: float
    step_tol: float


def _textract_lines(image_bytes: bytes) -> TextractResult:
    """Run Textract DetectDocumentText and return a TextractResult.

    Two-phase algorithm:
    1. Calibrate: derive the receipt's line height from the distribution of
       consecutive Y-gaps, avoiding any hardcoded page-fraction threshold.
    2. Chain: pop the leftmost unassigned block, then walk right — each step
       uses a rolling Y-tolerance anchored to the current block, so the window
       follows any curvature rather than drifting from the row's origin.
    """
    resp = textract.detect_document_text(Document={"Bytes": image_bytes})
    all_blocks = resp["Blocks"]
    blocks = [b for b in all_blocks if b["BlockType"] == "LINE"]
    words  = [b for b in all_blocks if b["BlockType"] == "WORD"]

    if not blocks:
        return TextractResult(text="", lines=[], blocks=[], words=[], rows=[], line_height=0.0, step_tol=0.0)

    rows, line_height, step_tol = group_blocks(blocks)
    lines = ["  ".join(b["Text"] for b in row) for row in rows]
    print(f"TEXTRACT lines={len(lines)} line_height={line_height:.4f} step_tol={step_tol:.4f}")
    return TextractResult(
        text="\n".join(lines),
        lines=lines,
        blocks=blocks,
        words=words,
        rows=rows,
        line_height=line_height,
        step_tol=step_tol,
    )


def _debug_block_list(blocks: list, rows: list) -> list:
    """Slim Textract LINE blocks down to JSON-serialisable dicts, annotated with row index.

    Blocks are in reading order (sorted by Top). The row index shows which blocks
    were merged together by our ROW_GAP grouping: same row index = same merged line.
    """
    id_to_row = {}
    for row_idx, row_blocks in enumerate(rows):
        for block in row_blocks:
            id_to_row[block["Id"]] = row_idx

    result = []
    for block in blocks:
        bb = block["Geometry"]["BoundingBox"]
        result.append({
            "text":       block.get("Text", ""),
            "confidence": round(block.get("Confidence", 0), 1),
            "top":        round(bb["Top"],    4),
            "left":       round(bb["Left"],   4),
            "width":      round(bb["Width"],  4),
            "height":     round(bb["Height"], 4),
            "row":        id_to_row.get(block["Id"], -1),
        })
    return result


def _debug_word_list(words: list, line_blocks: list, rows: list) -> list:
    """Slim Textract WORD blocks down to JSON-serialisable dicts.

    Each word is annotated with the row index of its parent LINE block so you
    can see whether its physical position matches where the grouping placed it.
    Words are sorted by Top so they read top-to-bottom in the debug output.
    """
    word_to_line: dict[str, str] = {}
    for line in line_blocks:
        for rel in line.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for wid in rel["Ids"]:
                    word_to_line[wid] = line["Id"]

    id_to_row: dict[str, int] = {}
    for row_idx, row_blocks in enumerate(rows):
        for block in row_blocks:
            id_to_row[block["Id"]] = row_idx

    result = []
    for word in sorted(words, key=lambda b: b["Geometry"]["BoundingBox"]["Top"]):
        bb = word["Geometry"]["BoundingBox"]
        parent_line_id = word_to_line.get(word["Id"])
        result.append({
            "text":       word.get("Text", ""),
            "confidence": round(word.get("Confidence", 0), 1),
            "top":        round(bb["Top"],    4),
            "left":       round(bb["Left"],   4),
            "width":      round(bb["Width"],  4),
            "height":     round(bb["Height"], 4),
            "row":        id_to_row.get(parent_line_id, -1),
        })
    return result
