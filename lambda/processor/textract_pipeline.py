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
    resp = textract.detect_document_text(Document={"Bytes": image_bytes})
    all_blocks = resp["Blocks"]
    blocks = [b for b in all_blocks if b["BlockType"] == "LINE"]
    words  = [b for b in all_blocks if b["BlockType"] == "WORD"]

    if not blocks:
        return TextractResult(text="", lines=[], blocks=[], words=[], rows=[], line_height=0.0, step_tol=0.0)

    rows, line_height, step_tol = group_blocks(words)
    lines = [" ".join(b["Text"] for b in row) for row in rows]
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


def _debug_block_list(blocks: list, word_rows: list) -> list:
    """Slim Textract LINE blocks down to JSON-serialisable dicts.

    Row index is assigned via each LINE block's first child word in the
    word-based grouping, so blocks that share a word row share an index.
    """
    word_id_to_row: dict[str, int] = {}
    for row_idx, row_words in enumerate(word_rows):
        for word in row_words:
            word_id_to_row[word["Id"]] = row_idx

    result = []
    for block in blocks:
        bb = block["Geometry"]["BoundingBox"]
        line_row = -1
        for rel in block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for wid in rel["Ids"]:
                    if wid in word_id_to_row:
                        line_row = word_id_to_row[wid]
                        break
                if line_row != -1:
                    break
        result.append({
            "text":       block.get("Text", ""),
            "confidence": round(block.get("Confidence", 0), 1),
            "top":        round(bb["Top"],    4),
            "left":       round(bb["Left"],   4),
            "width":      round(bb["Width"],  4),
            "height":     round(bb["Height"], 4),
            "row":        line_row,
        })
    return result


def _debug_word_list(words: list, word_rows: list) -> list:
    """Slim Textract WORD blocks, annotated with their word-based row index.

    Words are sorted by Top so they read top-to-bottom in the debug output.
    """
    word_id_to_row: dict[str, int] = {}
    for row_idx, row_words in enumerate(word_rows):
        for word in row_words:
            word_id_to_row[word["Id"]] = row_idx

    result = []
    for word in sorted(words, key=lambda b: b["Geometry"]["BoundingBox"]["Top"]):
        bb = word["Geometry"]["BoundingBox"]
        result.append({
            "text":       word.get("Text", ""),
            "confidence": round(word.get("Confidence", 0), 1),
            "top":        round(bb["Top"],    4),
            "left":       round(bb["Left"],   4),
            "width":      round(bb["Width"],  4),
            "height":     round(bb["Height"], 4),
            "row":        word_id_to_row.get(word["Id"], -1),
        })
    return result
