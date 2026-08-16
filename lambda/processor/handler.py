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

        result = analyze_receipt(bucket, key)

        expiry = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
        update_job(job_id, {
            "status": {"S": "COMPLETE"},
            "vendor": {"S": result["vendor"]},
            "receipt_date": {"S": result["receipt_date"]},
            "total": {"S": result["total"]},
            "items": {"S": json.dumps(result["items"])},
            "updated_at": {"S": now_iso()},
            "expires_at": {"N": str(expiry)},
        })


def analyze_receipt(bucket: str, key: str) -> dict:
    response = textract.analyze_document(
        Document={"S3Object": {"Bucket": bucket, "Name": key}},
        FeatureTypes=["TABLES", "FORMS"],
    )
    print("TEXTRACT_BLOCK_COUNT", len(response.get("Blocks", [])))

    blocks_by_id = {b["Id"]: b for b in response.get("Blocks", [])}

    vendor, receipt_date, total = extract_summary_fields(blocks_by_id)
    items = extract_line_items(blocks_by_id)

    print("TEXTRACT_RAW_ITEMS", json.dumps(items))
    reconciled = reconcile_line_items(items)
    print("TEXTRACT_RECONCILED_ITEMS", json.dumps(reconciled))

    return {
        "vendor": vendor or "Unknown vendor",
        "receipt_date": receipt_date or "",
        "total": total or "",
        "items": reconciled,
    }


def get_text(block_id: str, blocks_by_id: dict) -> str:
    block = blocks_by_id.get(block_id, {})
    if block.get("BlockType") == "WORD":
        return block.get("Text", "")
    if block.get("BlockType") == "SELECTION_ELEMENT":
        return ""
    # For LINE or CELL, concatenate children
    parts = []
    for rel in block.get("Relationships", []):
        if rel["Type"] == "CHILD":
            for child_id in rel["Ids"]:
                child = blocks_by_id.get(child_id, {})
                if child.get("BlockType") == "WORD":
                    parts.append(child.get("Text", ""))
    return " ".join(parts)


def extract_summary_fields(blocks_by_id: dict) -> tuple[str, str, str]:
    """
    Extract vendor, date, and total from KEY_VALUE_SET blocks (FORMS feature).
    Falls back to scanning LINE blocks for common receipt header patterns.
    """
    vendor = ""
    receipt_date = ""
    total = ""

    # Collect key->value pairs from FORMS
    kv_pairs = {}
    for block in blocks_by_id.values():
        if block.get("BlockType") != "KEY_VALUE_SET":
            continue
        if "KEY" not in block.get("EntityTypes", []):
            continue
        key_text = get_text(block["Id"], blocks_by_id).strip().upper()
        for rel in block.get("Relationships", []):
            if rel["Type"] == "VALUE":
                for val_id in rel["Ids"]:
                    val_text = get_text(val_id, blocks_by_id).strip()
                    kv_pairs[key_text] = val_text

    # Map common receipt key names
    for key, val in kv_pairs.items():
        if not vendor and any(k in key for k in ("VENDOR", "STORE", "MERCHANT", "SHOP")):
            vendor = val
        if not receipt_date and any(k in key for k in ("DATE", "TIME")):
            receipt_date = val
        if not total and any(k in key for k in ("TOTAL", "AMOUNT DUE", "BALANCE")):
            total = val

    # Fallback: scan LINE blocks for a TOTAL pattern (e.g. "TOTAL  $XX.XX")
    if not total:
        for block in sorted(blocks_by_id.values(), key=lambda b: b.get("Geometry", {}).get("BoundingBox", {}).get("Top", 0), reverse=True):
            if block.get("BlockType") != "LINE":
                continue
            line = block.get("Text", "")
            m = re.search(r"\bTOTAL\b.*?(\$?[\d,]+\.\d{2})", line, re.IGNORECASE)
            if m:
                total = m.group(1)
                break

    # Fallback: vendor is often the first LINE near the top
    if not vendor:
        lines = sorted(
            [b for b in blocks_by_id.values() if b.get("BlockType") == "LINE"],
            key=lambda b: b.get("Geometry", {}).get("BoundingBox", {}).get("Top", 1),
        )
        if lines:
            vendor = lines[0].get("Text", "").strip()

    return vendor, receipt_date, total


def extract_line_items(blocks_by_id: dict) -> list:
    """
    Parse TABLE blocks from AnalyzeDocument. For each table, reconstruct rows
    from CELL blocks and interpret columns as receipt line item fields.
    Returns a flat list of item dicts with optional keys: description, quantity,
    unit_price, price.
    """
    # Group cells by table block ID
    tables: dict[str, dict] = {}  # table_id -> {(row, col): text}
    table_col_counts: dict[str, int] = {}

    for block in blocks_by_id.values():
        if block.get("BlockType") != "TABLE":
            continue
        table_id = block["Id"]
        tables[table_id] = {}
        table_col_counts[table_id] = 0
        for rel in block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for cell_id in rel["Ids"]:
                    cell = blocks_by_id.get(cell_id, {})
                    if cell.get("BlockType") != "CELL":
                        continue
                    row = cell.get("RowIndex", 0)
                    col = cell.get("ColumnIndex", 0)
                    span = cell.get("ColumnSpan", 1)
                    text = get_text(cell_id, blocks_by_id).strip()
                    tables[table_id][(row, col)] = text
                    table_col_counts[table_id] = max(
                        table_col_counts[table_id], col + span - 1
                    )

    print("TEXTRACT_TABLES_FOUND", len(tables))

    all_items = []
    for table_id, cells in tables.items():
        if not cells:
            continue
        num_cols = table_col_counts[table_id]
        # Group by row
        rows: dict[int, dict[int, str]] = {}
        for (row, col), text in cells.items():
            rows.setdefault(row, {})[col] = text

        items = parse_table_rows(rows, num_cols)
        all_items.extend(items)

    return all_items


def parse_table_rows(rows: dict, num_cols: int) -> list:
    """
    Interpret table rows as receipt line items.

    PAK'nSAVE receipts typically have 2–4 columns:
      2 cols: description | price
      3 cols: description | qty×unit | price
      4 cols: description | qty | unit_price | price

    We detect the layout from the column count and assign fields accordingly.
    Rows that look like headers (all text, no numbers) are skipped.
    """
    items = []
    sorted_rows = sorted(rows.keys())

    for row_idx in sorted_rows:
        cols = rows[row_idx]
        # Build ordered list of cell values
        values = [cols.get(c, "").strip() for c in range(1, num_cols + 1)]
        if not any(values):
            continue

        item = interpret_row(values, num_cols)
        if item:
            items.append(item)

    return items


def interpret_row(values: list[str], num_cols: int) -> dict | None:
    """
    Map column values to item fields based on column count.
    Returns None for header rows (no numeric price found in last column).
    """
    if not values:
        return None

    price_candidate = values[-1] if values else ""
    # Skip rows where the last column has no recognisable price
    if not re.search(r"\d", price_candidate):
        return None

    item = {}

    if num_cols >= 4:
        # description | quantity | unit_price | price
        if values[0]:
            item["description"] = values[0]
        if len(values) > 1 and values[1]:
            item["quantity"] = values[1]
        if len(values) > 2 and values[2]:
            item["unit_price"] = values[2]
        if len(values) > 3 and values[3]:
            item["price"] = values[3]
    elif num_cols == 3:
        # description | qty×unit_price | price  — or  description | unit_price | price
        if values[0]:
            item["description"] = values[0]
        middle = values[1] if len(values) > 1 else ""
        # "2 @ $6.99" or "2 x $6.99" — split into qty / unit_price
        m = re.match(r"(\d+)\s*[@x×]\s*\$?([\d.]+)", middle, re.IGNORECASE)
        if m:
            item["quantity"] = m.group(1)
            item["unit_price"] = m.group(2)
        elif middle:
            item["unit_price"] = middle
        if len(values) > 2 and values[2]:
            item["price"] = values[2]
    else:
        # 2-column: description | price
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
    PAK'nSAVE-style receipts mix two formats on the same receipt:
      Single:     ITEM_NAME       PRICE
      Multi-unit: ITEM_NAME
                  QTY  UNIT_PRICE  TOTAL (second line)

    AnalyzeDocument TABLES should preserve row boundaries correctly, so this
    reconciliation is now a lighter-touch pass:
      1. Strip pricing from items where qty * unit_price != price — misaligned
         column assignment.
      2. Merge consecutive (description-only, price-only) pairs — the second line
         of a multi-unit item may land as a separate row with no description.
    """
    # Pass 1 — strip mathematically inconsistent pricing
    for item in items:
        qty = parse_price(item.get("quantity"))
        unit = parse_price(item.get("unit_price"))
        price = parse_price(item.get("price"))
        if qty is not None and unit is not None and price is not None:
            if abs(round(qty * unit, 2) - price) > 0.02:
                item.pop("quantity", None)
                item.pop("unit_price", None)
                item.pop("price", None)

    # Pass 2 — merge orphan price rows with unpriced description rows.
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

    merged_at = {}
    skip = set()
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
