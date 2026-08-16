import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote_plus

import boto3

DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]
S3_BUCKET = os.environ["S3_UPLOADS_BUCKET"]
PRIMARY_REGION = os.environ.get("PRIMARY_REGION", "ap-southeast-2")

s3 = boto3.client("s3", region_name=PRIMARY_REGION)
dynamodb = boto3.client("dynamodb", region_name=PRIMARY_REGION)
textract = boto3.client("textract", region_name=PRIMARY_REGION)

FOOTER_RE = re.compile(
    r"\b(TOTAL|SUBTOTAL|SUB\s+TOTAL|BALANCE\s+DUE|EFTPOS|GST|TAX|"
    r"CHANGE|CASH|CREDIT|DEBIT|CARD|PURCHASE|TERMINAL|TRAN|CHEQUE|SUPERVISOR)\b",
    re.IGNORECASE,
)
HEADER_DESCS = {"ITEM", "DESCRIPTION", "PRODUCT", "ITEMS", "ITEM NAME"}


def lambda_handler(event, context):
    batch_item_failures = []
    for record in event.get("Records", []):
        try:
            process_record(record)
        except Exception as exc:
            print(f"ERROR processing message {record['messageId']}: {exc}")
            batch_item_failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": batch_item_failures}


def process_record(record):
    body = json.loads(record["body"])

    # S3 sends a test event when a notification is first configured — skip it
    if body.get("Event") == "s3:TestEvent":
        return

    for s3_record in body.get("Records", []):
        bucket = s3_record["s3"]["bucket"]["name"]
        key = unquote_plus(s3_record["s3"]["object"]["key"])

        # Key format: uploads/{user_id}/{job_id}.{ext}
        parts = key.split("/")
        job_id = parts[2].rsplit(".", 1)[0] if len(parts) >= 3 else key

        # Idempotency guard: SQS delivers at-least-once, so the same message can
        # arrive after a successful run. Skip Textract entirely if already done.
        existing = dynamodb.get_item(
            TableName=DYNAMODB_TABLE,
            Key={"job_id": {"S": job_id}},
        )
        if existing.get("Item", {}).get("status", {}).get("S") == "COMPLETE":
            print(f"Job {job_id} already COMPLETE — skipping Textract call")
            continue

        update_job(job_id, {
            "status": {"S": "PROCESSING"},
            "updated_at": {"S": now_iso()},
        })

        result = analyze_receipt(bucket, key, job_id)

        expiry = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
        update_job(job_id, {
            "status": {"S": "COMPLETE"},
            "vendor": {"S": result["vendor"]},
            "receipt_date": {"S": result["receipt_date"]},
            "total": {"S": result["total"]},
            "items": {"S": json.dumps(result["items"])},
            "debug_s3_key": {"S": result["debug_s3_key"]},
            "updated_at": {"S": now_iso()},
            "expires_at": {"N": str(expiry)},
        })


def save_debug(job_id: str, payload: dict) -> str:
    """Persist raw Textract response to S3 and return the object key."""
    debug_key = f"debug/{job_id}.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=debug_key,
        Body=json.dumps(payload, default=str).encode(),
        ContentType="application/json",
    )
    return debug_key


def analyze_receipt(bucket: str, key: str, job_id: str) -> dict:
    response = textract.analyze_document(
        Document={"S3Object": {"Bucket": bucket, "Name": key}},
        FeatureTypes=["TABLES", "FORMS"],
    )
    debug_s3_key = save_debug(job_id, response)
    print("TEXTRACT_BLOCK_COUNT", len(response.get("Blocks", [])))

    blocks_by_id = {b["Id"]: b for b in response.get("Blocks", [])}
    word_to_line = build_word_to_line_map(blocks_by_id)
    is_landscape = detect_is_landscape(blocks_by_id)
    print("TEXTRACT_ORIENTATION", "landscape" if is_landscape else "portrait")

    vendor, receipt_date, total = extract_summary_fields(blocks_by_id)
    items = extract_line_items(blocks_by_id, word_to_line, is_landscape)

    print("TEXTRACT_RAW_ITEMS", json.dumps(items))
    reconciled = reconcile_line_items(items)
    print("TEXTRACT_RECONCILED_ITEMS", json.dumps(reconciled))

    return {
        "vendor": vendor or "Unknown vendor",
        "receipt_date": receipt_date or "",
        "total": total or "",
        "items": reconciled,
        "debug_s3_key": debug_s3_key,
    }


def build_word_to_line_map(blocks_by_id: dict) -> dict[str, str]:
    """Map each WORD block ID to its parent LINE block ID."""
    w2l: dict[str, str] = {}
    for block in blocks_by_id.values():
        if block.get("BlockType") != "LINE":
            continue
        for rel in block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for child_id in rel["Ids"]:
                    w2l[child_id] = block["Id"]
    return w2l


def detect_is_landscape(blocks_by_id: dict) -> bool:
    """
    Receipt was photographed landscape (rotated 90°) when most LINE blocks are
    taller than they are wide — each receipt row runs vertically in the image.
    """
    horiz = vert = 0
    for block in blocks_by_id.values():
        if block.get("BlockType") != "LINE":
            continue
        bb = block.get("Geometry", {}).get("BoundingBox", {})
        w, h = bb.get("Width", 0), bb.get("Height", 0)
        if w > h * 1.5:
            horiz += 1
        elif h > w * 1.5:
            vert += 1
    return vert > horiz


def get_text(block_id: str, blocks_by_id: dict) -> str:
    """Concatenate WORD children of a block in Textract order."""
    block = blocks_by_id.get(block_id, {})
    parts = []
    for rel in block.get("Relationships", []):
        if rel["Type"] == "CHILD":
            for child_id in rel["Ids"]:
                child = blocks_by_id.get(child_id, {})
                if child.get("BlockType") == "WORD":
                    parts.append(child.get("Text", ""))
    return " ".join(parts)


def get_cell_line_groups(
    cell_id: str,
    blocks_by_id: dict,
    word_to_line: dict[str, str],
    is_landscape: bool,
) -> list[str]:
    """
    Return the text of each visual line within a CELL, in receipt reading order.

    Groups the cell's WORD children by parent LINE block, then sorts those lines by
    the axis that matches receipt orientation:
      - Portrait  (lines horizontal in image): ascending Top
      - Landscape / 90° CW (lines vertical in image): descending Left
        (receipt rows run right-to-left across the image for a CW-rotated receipt)

    LINE.Text is used directly so Textract's own reading-order reconstruction handles
    rotated text — reconstructing from WORD positions would reverse the words.

    Most cells return one element. Cells where Textract merged two adjacent receipt
    rows into one cell return two elements, triggering expand_multiline_rows to split.
    """
    cell = blocks_by_id.get(cell_id, {})

    seen_lines: dict[str, None] = {}  # insertion-ordered set
    for rel in cell.get("Relationships", []):
        if rel["Type"] != "CHILD":
            continue
        for child_id in rel["Ids"]:
            if blocks_by_id.get(child_id, {}).get("BlockType") != "WORD":
                continue
            line_id = word_to_line.get(child_id)
            if line_id:
                seen_lines[line_id] = None

    if not seen_lines:
        return [""]

    def sort_key(lid: str) -> float:
        bb = blocks_by_id.get(lid, {}).get("Geometry", {}).get("BoundingBox", {})
        # Descending Left for landscape CW: receipt-top rows are furthest right in image
        return -bb.get("Left", 0) if is_landscape else bb.get("Top", 0)

    result = [
        blocks_by_id[lid].get("Text", "").strip()
        for lid in sorted(seen_lines, key=sort_key)
        if blocks_by_id.get(lid, {}).get("Text", "").strip()
    ]
    return result if result else [""]


def extract_summary_fields(blocks_by_id: dict) -> tuple[str, str, str]:
    vendor = ""
    receipt_date = ""
    total = ""

    kv_pairs: dict[str, str] = {}
    for block in blocks_by_id.values():
        if block.get("BlockType") != "KEY_VALUE_SET":
            continue
        if "KEY" not in block.get("EntityTypes", []):
            continue
        key_text = get_text(block["Id"], blocks_by_id).strip().upper()
        for rel in block.get("Relationships", []):
            if rel["Type"] == "VALUE":
                for val_id in rel["Ids"]:
                    kv_pairs[key_text] = get_text(val_id, blocks_by_id).strip()

    for key, val in kv_pairs.items():
        if not vendor and any(k in key for k in ("VENDOR", "STORE", "MERCHANT", "SHOP")):
            vendor = val
        if not receipt_date and any(k in key for k in ("DATE", "TIME")):
            receipt_date = val
        if not total and any(k in key for k in ("TOTAL", "AMOUNT DUE", "BALANCE")):
            total = val

    if not total:
        for block in sorted(
            blocks_by_id.values(),
            key=lambda b: b.get("Geometry", {}).get("BoundingBox", {}).get("Top", 0),
            reverse=True,
        ):
            if block.get("BlockType") != "LINE":
                continue
            m = re.search(r"\bTOTAL\b.*?(\$?[\d,]+\.\d{2})", block.get("Text", ""), re.IGNORECASE)
            if m:
                total = m.group(1)
                break

    if not vendor:
        lines = sorted(
            [b for b in blocks_by_id.values() if b.get("BlockType") == "LINE"],
            key=lambda b: b.get("Geometry", {}).get("BoundingBox", {}).get("Top", 1),
        )
        if lines:
            vendor = lines[0].get("Text", "").strip()

    return vendor, receipt_date, total


def extract_line_items(
    blocks_by_id: dict,
    word_to_line: dict[str, str],
    is_landscape: bool,
) -> list:
    tables_cells: dict[str, dict[tuple[int, int], list[str]]] = {}
    table_col_counts: dict[str, int] = {}

    for block in blocks_by_id.values():
        if block.get("BlockType") != "TABLE":
            continue
        table_id = block["Id"]
        tables_cells[table_id] = {}
        table_col_counts[table_id] = 0
        for rel in block.get("Relationships", []):
            if rel["Type"] != "CHILD":
                continue
            for cell_id in rel["Ids"]:
                cell = blocks_by_id.get(cell_id, {})
                if cell.get("BlockType") != "CELL":
                    continue
                row = cell.get("RowIndex", 0)
                col = cell.get("ColumnIndex", 0)
                span = cell.get("ColumnSpan", 1)
                lines = get_cell_line_groups(cell_id, blocks_by_id, word_to_line, is_landscape)
                tables_cells[table_id][(row, col)] = lines
                table_col_counts[table_id] = max(
                    table_col_counts[table_id], col + span - 1
                )

    print("TEXTRACT_TABLES_FOUND", len(tables_cells))

    all_items = []
    for table_id, cells in tables_cells.items():
        if not cells:
            continue
        num_cols = table_col_counts[table_id]
        rows: dict[int, dict[int, list[str]]] = {}
        for (row, col), lines in cells.items():
            rows.setdefault(row, {})[col] = lines
        expanded = expand_multiline_rows(rows, num_cols)
        all_items.extend(parse_table_rows(expanded, num_cols))

    return all_items


def expand_multiline_rows(
    rows: dict[int, dict[int, list[str]]], num_cols: int
) -> dict[int, dict[int, str]]:
    """
    When the description cell (col 1) contains multiple LINE groups, split the row
    into virtual rows. The first line keeps the original row's price columns; extra
    lines become orphan description-only rows for reconcile_line_items to pair.
    """
    result: dict[int, dict[int, str]] = {}
    virtual = 0
    for row_idx in sorted(rows.keys()):
        cols = rows[row_idx]
        result[virtual] = {
            col: (cols[col][0] if cols.get(col) else "")
            for col in range(1, num_cols + 1)
        }
        virtual += 1
        for extra_desc in (cols.get(1) or [""])[1:]:
            result[virtual] = {col: "" for col in range(1, num_cols + 1)}
            result[virtual][1] = extra_desc
            virtual += 1
    return result


def parse_table_rows(rows: dict[int, dict[int, str]], num_cols: int) -> list:
    items = []
    for row_idx in sorted(rows.keys()):
        cols = rows[row_idx]
        values = [cols.get(c, "").strip() for c in range(1, num_cols + 1)]
        if not any(values):
            continue
        item = interpret_row(values, num_cols)
        if item:
            items.append(item)
    return items


def interpret_row(values: list[str], num_cols: int) -> dict | None:
    """
    Map column values to item fields.

    Allows description-only rows through (no price/qty) so reconcile_line_items
    can pair them with the following price-only row. Skips:
      - Completely blank rows
      - Known table-header descriptions (Item, Qty, Price …)
      - Rows whose description matches footer/payment keywords
    """
    if not values or not any(v.strip() for v in values):
        return None

    desc = values[0].strip()

    # Skip column header rows
    if desc.upper() in HEADER_DESCS and not any(re.search(r"\d", v) for v in values):
        return None

    # Skip footer/payment rows
    if FOOTER_RE.search(desc):
        return None

    item: dict[str, str] = {}

    if num_cols >= 4:
        if values[0]:
            item["description"] = values[0]
        if len(values) > 1 and values[1]:
            item["quantity"] = values[1]
        if len(values) > 2 and values[2]:
            item["unit_price"] = values[2]
        if len(values) > 3 and values[3]:
            item["price"] = values[3]
    elif num_cols == 3:
        if values[0]:
            item["description"] = values[0]
        middle = values[1] if len(values) > 1 else ""
        m = re.match(r"(\d+)\s*[@x×]\s*\$?([\d.]+)", middle, re.IGNORECASE)
        if m:
            item["quantity"] = m.group(1)
            item["unit_price"] = m.group(2)
        elif middle:
            item["unit_price"] = middle
        if len(values) > 2 and values[2]:
            item["price"] = values[2]
    else:
        if values[0]:
            item["description"] = values[0]
        if len(values) > 1 and values[1]:
            item["price"] = values[1]

    return item if item else None


def parse_price(s: str) -> float | None:
    if not s:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(s))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def reconcile_line_items(items: list) -> list:
    """
    Two-pass clean-up:
      Pass 1 — strip pricing where qty × unit_price ≠ price (column mis-assignment).
      Pass 2 — pair orphan description-only rows with price-only rows in order.
    """
    for item in items:
        qty = parse_price(item.get("quantity"))
        unit = parse_price(item.get("unit_price"))
        price = parse_price(item.get("price"))
        if qty is not None and unit is not None and price is not None:
            if abs(round(qty * unit, 2) - price) > 0.02:
                item.pop("quantity", None)
                item.pop("unit_price", None)
                item.pop("price", None)

    desc_only = [
        i for i, it in enumerate(items)
        if it.get("description", "").strip()
        and not (it.get("price") or it.get("unit_price") or it.get("quantity"))
    ]
    price_only = [
        i for i, it in enumerate(items)
        if (it.get("price") or it.get("unit_price") or it.get("quantity"))
        and not it.get("description", "").strip()
    ]

    merged_at: dict[int, dict] = {}
    skip: set[int] = set()
    for desc_idx, price_idx in zip(desc_only, price_only):
        merged_at[desc_idx] = {**items[price_idx], "description": items[desc_idx]["description"]}
        skip.add(price_idx)

    result = []
    for i, item in enumerate(items):
        if i in skip:
            continue
        if i in merged_at:
            result.append(merged_at[i])
        elif item.get("description", "").strip() or item.get("price") or item.get("unit_price") or item.get("quantity"):
            result.append(item)

    return result


def update_job(job_id: str, fields: dict) -> None:
    parts, values, names = [], {}, {}
    for key, val in fields.items():
        parts.append(f"#{key} = :{key}")
        values[f":{key}"] = val
        names[f"#{key}"] = key

    dynamodb.update_item(
        TableName=DYNAMODB_TABLE,
        Key={"job_id": {"S": job_id}},
        UpdateExpression="SET " + ", ".join(parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
