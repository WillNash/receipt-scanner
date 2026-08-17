import io
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote_plus

import boto3
import cv2
import numpy as np

DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]
LINE_ITEMS_TABLE = os.environ.get("LINE_ITEMS_TABLE", "")
S3_BUCKET = os.environ["S3_UPLOADS_BUCKET"]
PRIMARY_REGION = os.environ.get("PRIMARY_REGION", "ap-southeast-2")

s3 = boto3.client("s3", region_name=PRIMARY_REGION)
dynamodb = boto3.client("dynamodb", region_name=PRIMARY_REGION)
textract = boto3.client("textract", region_name=PRIMARY_REGION)

FOOTER_RE = re.compile(
    # Anchored to row start (after optional item-count prefix like "36 ") so that
    # product names containing footer words (e.g. "COLGATE TOTAL TOOTHPASTE") are
    # not mistaken for summary lines.
    r"^\d*\s*\b(TOTAL|SUBTOTAL|SUB\s+TOTAL|BALANCE\s+DUE|EFTPOS|GST|TAX|"
    r"CHANGE|CASH|CREDIT|DEBIT|CARD|PURCHASE|TERMINAL|TRAN|CHEQUE|SUPERVISOR)\b",
    re.IGNORECASE,
)

# Trailing price on a row: optional $ then digits.cents at end
PRICE_TAIL_RE = re.compile(r"\s+\$?([\d,]+\.\d{2})\s*$")

# Discrete qty row with @: "2 @ $3.49 $6.98"
QTY_RE = re.compile(
    r"^(\d+)\s*[@×xX]\s*\$?([\d.]+)(?:\s+\$?([\d,]+\.\d{2}))?\s*$"
)

# Weight qty row: "1.976 Kg @ $1.99/Kg $3.93", garbled "1.901 Kgug $3.99/Kg $7.58", or "1.401 Kg à $1.99/Kg $2.79"
# [^$\d]* absorbs any separator/OCR garbage between the Kg weight and the unit price
QTY_WEIGHT_RE = re.compile(
    r"^([\d.]+)\s*Kg[^$\d]*\$?([\d.]+)/Kg\s+\$?([\d,]+\.\d{2})\s*$"
)

# Discrete qty row without @: OCR may drop the @ symbol, e.g. "20 $3.99 $7.98" (was "2 @ $3.99 $7.98")
QTY_NO_AT_RE = re.compile(r"^(\d+)\s+\$?([\d.]+)\s+\$?([\d,]+\.\d{2})\s*$")

# Column header rows — skip these
HEADER_LINE_RE = re.compile(r"^item\b.*\bprice\b\s*$", re.IGNORECASE)
HEADER_WORDS = {"ITEM", "DESCRIPTION", "PRODUCT", "ITEMS", "ITEM NAME", "QTY", "UNIT PRICE", "PRICE"}

# Discount line: description column may prefix it, e.g. "BROCCOLI -$0.58"
DISCOUNT_RE = re.compile(r"-\$?([\d,]+\.\d{2})\s*$")

# Tolerance (in normalised image coordinates 0–1) for grouping column blocks on the same row
ROW_TOLERANCE = 0.007


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

    if body.get("Event") == "s3:TestEvent":
        return

    for s3_record in body.get("Records", []):
        bucket = s3_record["s3"]["bucket"]["name"]
        key = unquote_plus(s3_record["s3"]["object"]["key"])

        parts = key.split("/")
        job_id = parts[2].rsplit(".", 1)[0] if len(parts) >= 3 else key

        existing = dynamodb.get_item(
            TableName=DYNAMODB_TABLE,
            Key={"job_id": {"S": job_id}},
        )
        existing_item = existing.get("Item", {})
        if existing_item.get("status", {}).get("S") == "COMPLETE":
            print(f"Job {job_id} already COMPLETE — skipping Textract call")
            continue

        user_id = existing_item.get("user_id", {}).get("S", "unknown")
        user_email = existing_item.get("email", {}).get("S", "")
        created_at = existing_item.get("created_at", {}).get("S", now_iso())

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

        if LINE_ITEMS_TABLE:
            write_line_items(
                job_id=job_id,
                user_id=user_id,
                user_email=user_email,
                created_at=created_at,
                vendor=result["vendor"],
                receipt_date=result["receipt_date"],
                items=result["items"],
                expires_at=expiry,
            )


def save_debug(job_id: str, payload: dict) -> str:
    debug_key = f"debug/{job_id}.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=debug_key,
        Body=json.dumps(payload, default=str).encode(),
        ContentType="application/json",
    )
    return debug_key


def crop_receipt(bucket: str, key: str) -> None:
    """
    Detect the receipt strip using MSER text-density and crop to it.

    MSER finds stable dark-on-light blobs — printed characters. The receipt has
    hundreds of them; background fabric and surfaces have very few. We project all
    character-like region centres onto the X and Y axes, build a smoothed density
    histogram on each axis, and find the contiguous high-density band. That band
    is the receipt extent on that axis.

    Using the bounding hull of all valid MSER points fails when a handful of
    false-positive blobs appear at the image corners. The density approach is robust
    to sparse background noise because it looks for the densest connected run, not
    the outermost point.
    """
    MSER_SCALE = 2000      # longest side for analysis thumbnail
    MIN_BBOX = 20          # min character blob area (px²) at MSER_SCALE
    MAX_BBOX = 1500        # max character blob area (px²) at MSER_SCALE
    HIST_BINS = 40         # histogram bins along each axis
    SMOOTH_WIN = 5         # smoothing window (bins) for density histogram
    DENSITY_FRAC = 0.60    # fraction of peak density to define "receipt band"
    PAD_FRAC = 0.05        # fractional padding added to each end of the band
    MIN_GAIN = 0.85        # skip if crop keeps ≥85 % of original pixels

    try:
        data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            print("CROP_SKIPPED: could not decode image")
            return

        h, w = img.shape[:2]
        scale = MSER_SCALE / max(h, w)
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
        small = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        mser = cv2.MSER_create(5, MIN_BBOX, MAX_BBOX, 0.25)
        regions, _ = mser.detectRegions(gray)

        valid_cx, valid_cy = [], []
        for region in regions:
            pts = region.reshape(-1, 1, 2)
            rx, ry, rw, rh = cv2.boundingRect(pts)
            if rw == 0 or rh == 0:
                continue
            bbox_area = rw * rh
            aspect = rw / rh
            fill = len(region) / bbox_area          # pixel count / bbox area
            if (0.15 < aspect < 6.0) and (0.1 < fill < 0.9) and (MIN_BBOX < bbox_area < MAX_BBOX):
                valid_cx.append(rx + rw / 2)
                valid_cy.append(ry + rh / 2)

        print(f"MSER regions={len(regions)} text-like={len(valid_cx)}")
        if not valid_cx:
            print("CROP_SKIPPED: no text-like MSER regions found")
            return

        def dense_band(centres, size):
            hist, edges = np.histogram(centres, bins=HIST_BINS, range=(0, size))
            kernel = np.ones(SMOOTH_WIN) / SMOOTH_WIN
            smoothed = np.convolve(hist, kernel, mode="same")
            threshold = smoothed.max() * DENSITY_FRAC
            active = [i for i, s in enumerate(smoothed) if s >= threshold]
            if not active:
                return 0, size
            pad = int(size * PAD_FRAC)
            lo = max(0, int(edges[active[0]]) - pad)
            hi = min(size, int(edges[active[-1] + 1]) + pad)
            return lo, hi

        x_lo, x_hi = dense_band(valid_cx, sw)
        y_lo, y_hi = dense_band(valid_cy, sh)

        left  = max(0, int(x_lo / scale))
        upper = max(0, int(y_lo / scale))
        right = min(w, int(x_hi / scale))
        lower = min(h, int(y_hi / scale))

        pixel_ratio = (right - left) * (lower - upper) / (w * h)
        if pixel_ratio >= MIN_GAIN:
            print(f"CROP_SKIPPED: {pixel_ratio:.0%} of image — no meaningful gain")
            return

        cropped = img[upper:lower, left:right]
        is_jpeg = key.lower().endswith((".jpg", ".jpeg"))
        ext = ".jpg" if is_jpeg else ".png"
        params = [cv2.IMWRITE_JPEG_QUALITY, 95] if is_jpeg else []
        ok, buf = cv2.imencode(ext, cropped, params)
        if not ok:
            print("CROP_SKIPPED: imencode failed")
            return

        cropped_bytes = buf.tobytes()
        print(f"CROP {w}x{h} -> {right-left}x{lower-upper} "
              f"{len(data)//1024}KB -> {len(cropped_bytes)//1024}KB ({pixel_ratio:.0%} area)")
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=cropped_bytes,
            ContentType="image/jpeg" if is_jpeg else "image/png",
        )

    except Exception as exc:
        print(f"CROP_SKIPPED: {exc}")


def analyze_receipt(bucket: str, key: str, job_id: str) -> dict:
    crop_receipt(bucket, key)
    response = textract.analyze_document(
        Document={"S3Object": {"Bucket": bucket, "Name": key}},
        FeatureTypes=["FORMS"],
    )
    debug_s3_key = save_debug(job_id, response)
    print("TEXTRACT_BLOCK_COUNT", len(response.get("Blocks", [])))

    blocks_by_id = {b["Id"]: b for b in response.get("Blocks", [])}
    is_landscape = detect_is_landscape(blocks_by_id)
    print("TEXTRACT_ORIENTATION", "landscape" if is_landscape else "portrait")

    rows = get_receipt_rows(blocks_by_id, is_landscape)
    print("TEXTRACT_ROW_COUNT", len(rows))

    vendor, receipt_date, total = extract_summary_fields(blocks_by_id, rows)
    items = extract_line_items(rows)

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


def detect_is_landscape(blocks_by_id: dict) -> bool:
    """Receipt photographed 90° CW when most LINE blocks are taller than wide."""
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


def get_receipt_rows(blocks_by_id: dict, is_landscape: bool) -> list[str]:
    """
    Group LINE blocks that share the same visual row and return one text string per row.

    Portrait receipts: group blocks with similar Top values; sort within row by Left.
    Landscape (90° CW) receipts: group blocks with similar Left values; sort within row
    by Top; emit row groups in descending Left order (receipt top = image right).

    Same-row column blocks (description + qty + price) are a few pixels apart on the
    primary axis; consecutive rows are ~10 px apart. ROW_TOLERANCE captures
    same-row columns without merging adjacent rows.
    """
    lines = [b for b in blocks_by_id.values() if b.get("BlockType") == "LINE"]
    if not lines:
        return []

    def bb(b):
        return b.get("Geometry", {}).get("BoundingBox", {})

    if is_landscape:
        primary_key = lambda b: bb(b).get("Left", 0)
        secondary_key = lambda b: bb(b).get("Top", 0)
        row_order_reverse = True   # descending Left = receipt top first
    else:
        primary_key = lambda b: bb(b).get("Top", 0)
        secondary_key = lambda b: bb(b).get("Left", 0)
        row_order_reverse = False  # ascending Top = receipt top first

    sorted_blocks = sorted(lines, key=primary_key)

    # Group into rows
    groups: list[list] = []
    current: list = [sorted_blocks[0]]
    anchor = primary_key(sorted_blocks[0])

    for block in sorted_blocks[1:]:
        pos = primary_key(block)
        if abs(pos - anchor) <= ROW_TOLERANCE:
            current.append(block)
        else:
            groups.append(current)
            current = [block]
            anchor = pos
    groups.append(current)

    # Sort groups in receipt reading order
    def group_primary(g):
        return primary_key(g[0])

    groups.sort(key=group_primary, reverse=row_order_reverse)

    # Within each group sort left-to-right (or top-to-bottom for landscape) and join
    rows = []
    for group in groups:
        group.sort(key=secondary_key)
        text = " ".join(b.get("Text", "").strip() for b in group if b.get("Text", "").strip())
        if text:
            rows.append(text)

    return rows


def get_text(block_id: str, blocks_by_id: dict) -> str:
    """Concatenate WORD children of a block (used for FORMS key-value extraction)."""
    block = blocks_by_id.get(block_id, {})
    parts = []
    for rel in block.get("Relationships", []):
        if rel["Type"] == "CHILD":
            for child_id in rel["Ids"]:
                child = blocks_by_id.get(child_id, {})
                if child.get("BlockType") == "WORD":
                    parts.append(child.get("Text", ""))
    return " ".join(parts)


def extract_summary_fields(blocks_by_id: dict, rows: list[str]) -> tuple[str, str, str]:
    vendor = ""
    receipt_date = ""
    total = ""

    # Try FORMS key-value pairs first
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

    # Fallback: total — scan rows from receipt bottom
    if not total:
        for row in reversed(rows):
            m = re.search(
                r"\bTOTAL\b.*?(\$?[\d,]+\.\d{2})", row, re.IGNORECASE
            )
            if m:
                total = m.group(1)
                break

    # Fallback: date — first row matching a date pattern
    if not receipt_date:
        date_re = re.compile(
            r"\b(\d{1,2}[/-][A-Za-z]{3}[/-]\d{2,4}"
            r"|\d{4}-\d{2}-\d{2}"
            r"|\d{1,2}/\d{1,2}/\d{2,4})\b"
        )
        for row in rows:
            m = date_re.search(row)
            if m:
                receipt_date = m.group(1)
                break

    # Fallback: vendor — first non-trivial row in receipt order
    if not vendor:
        skip_re = re.compile(
            r"^\d{2}:\d{2}"          # time HH:MM
            r"|^NZD\d"               # NZD total header
            r"|\$[\d,]+\.\d{2}"     # price
            r"|\bItem\b.*\bQty\b",  # column header
            re.IGNORECASE,
        )
        for row in rows:
            if row.strip() and not skip_re.search(row):
                vendor = row.strip()
                break

    return vendor, receipt_date, total


def extract_line_items(rows: list[str]) -> list[dict]:
    """
    PAK'nSAVE LINE-based parser. Each `row` string is all column blocks on one receipt
    row joined left-to-right, so column values are already concatenated.

    Row formats after column joining:
      Single item:     DESCRIPTION $PRICE
      Multi-unit:      DESCRIPTION                    (no price on this row)
                       N @ $UNIT_PRICE                (or N @ $UNIT $TOTAL)
      Multi-unit alt:  DESCRIPTION                    (description row)
                       N @ $UNIT $TOTAL               (all three combined)

    State flags:
      items_started — False until the first price or qty row; prevents header rows
                      (store name, address, promo text) from accumulating.
      items_finished — True after the first footer row that carries a price (e.g.
                       "18 BALANCE DUE $138.82"), which signals end of items section.
    """
    items: list[dict] = []
    desc_acc: list[str] = []
    pending_price: str | None = None
    items_started = False
    items_finished = False
    expecting_discount = False  # True immediately after flushing a multi-unit item

    def flush(qty=None, unit=None, override_total=None):
        nonlocal desc_acc, pending_price
        desc = " ".join(desc_acc).strip()
        resolved_total = override_total or pending_price
        item: dict = {}
        if desc:
            item["description"] = desc
        item["quantity"] = qty or "1"
        item["unit_price"] = unit or resolved_total or ""
        if resolved_total:
            item["price"] = resolved_total
        if item.get("description") or item.get("price"):
            items.append(item)
        desc_acc = []
        pending_price = None

    for row in rows:
        text = row.strip()
        if not text or items_finished:
            expecting_discount = False
            continue

        # Skip column header rows (e.g., "Item  Qty  Unit price  Price")
        if text.upper() in HEADER_WORDS or HEADER_LINE_RE.match(text):
            continue

        # ── Discount row: appears immediately after a multi-unit qty row ────────
        if expecting_discount:
            expecting_discount = False
            discount_val = parse_discount(text)
            if discount_val is not None and items:
                last = items[-1]
                try:
                    disc_f = float(discount_val.replace(",", ""))
                    price_f = float(last.get("price", "0").replace(",", ""))
                    last["discount"] = f"{disc_f:.2f}"
                    last["price"] = f"{round(price_f - disc_f, 2):.2f}"
                except (ValueError, TypeError):
                    pass
                continue
            # Not a discount line — fall through to normal processing

        # Footer/payment rows: flush pending item.
        # A footer row that carries a price marks the end of the items section.
        if FOOTER_RE.search(text):
            flush()
            if PRICE_TAIL_RE.search(text):
                items_finished = True
            continue

        # ── Qty row: "N @ $UNIT" or "N @ $UNIT $TOTAL", or no-@ OCR variant ───
        m = QTY_RE.match(text)
        if m:
            qty_str, unit_str, line_total = m.group(1), m.group(2), m.group(3)
        else:
            m = QTY_WEIGHT_RE.match(text)
            if m:
                qty_str, unit_str, line_total = m.group(1), m.group(2), m.group(3)
            else:
                m = QTY_NO_AT_RE.match(text)
                if m:
                    raw_qty, unit_str, line_total = m.group(1), m.group(2), m.group(3)
                    qty_str = raw_qty
                    try:
                        u = float(unit_str)
                        t = float(line_total.replace(",", ""))
                        n = int(raw_qty)
                        if abs(round(n * u, 2) - t) > 0.02:
                            # OCR likely merged "2 @" into "20" — recover true qty
                            q = round(t / u)
                            if q > 0 and abs(round(q * u, 2) - t) <= 0.02:
                                qty_str = str(q)
                    except (ValueError, TypeError):
                        pass

        if m:
            if not items_started:
                # First real content row is a qty line — keep only the last
                # accumulated desc (if any) as the product description, discard header
                items_started = True
                desc_acc = desc_acc[-1:] if desc_acc else []

            # Only attach to pending if qty × unit matches the pending price.
            # A mismatch means this qty row belongs to a different item.
            belongs = True
            if pending_price is not None:
                try:
                    calc = round(float(qty_str) * float(unit_str), 2)
                    pf = float(pending_price.replace(",", ""))
                    if abs(calc - pf) > 0.02:
                        belongs = False
                except (ValueError, TypeError):
                    pass

            if belongs:
                # pending_price is the printed item total; line_total may be a savings display
                flush(qty=qty_str, unit=unit_str, override_total=pending_price or line_total)
                try:
                    if int(qty_str) > 1:
                        expecting_discount = True
                except (ValueError, TypeError):
                    pass
            else:
                # Flush previous item, then emit this as a description-less qty item
                flush()
                try:
                    calc_total = f"{float(qty_str) * float(unit_str):.2f}"
                except (ValueError, TypeError):
                    calc_total = None
                orphan_price = (
                    line_total if (line_total and line_total != "0.00") else None
                ) or calc_total
                if orphan_price:
                    items.append({"quantity": qty_str, "unit_price": unit_str, "price": orphan_price})
                    try:
                        if int(qty_str) > 1:
                            expecting_discount = True
                    except (ValueError, TypeError):
                        pass
            continue

        # ── Row ending with a price ────────────────────────────────────────────
        m_price = PRICE_TAIL_RE.search(text)
        if m_price:
            price_str = m_price.group(1)
            desc_part = text[:m_price.start()].strip()

            if not items_started:
                # First real content row — discard all accumulated header rows
                items_started = True
                desc_acc = []
                pending_price = None
            elif pending_price is not None:
                # Two consecutive price rows → previous item is complete
                flush()

            if desc_part:
                desc_acc.append(desc_part)
            pending_price = price_str
            continue

        # ── Pure description row ───────────────────────────────────────────────
        if not items_started:
            # Still in header section — accumulate but don't emit yet
            desc_acc.append(text)
            continue

        # If the previous row had a price but no qty row followed, it's a complete item
        if pending_price is not None:
            flush()
        desc_acc.append(text)

    flush()
    return items


def parse_price(s: str) -> float | None:
    if not s:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(s))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def parse_discount(text: str) -> str | None:
    """Return the discount amount string if the row is a discount line, else None."""
    m = DISCOUNT_RE.search(text)
    return m.group(1) if m else None


def reconcile_line_items(items: list) -> list:
    """
    Second-pass clean-up: pair orphan description-only rows with price-only rows.
    Also strips qty/unit_price when the math is inconsistent (belt-and-suspenders).
    """
    for item in items:
        qty = parse_price(item.get("quantity"))
        unit = parse_price(item.get("unit_price"))
        price = parse_price(item.get("price"))
        discount = parse_price(item.get("discount")) or 0.0
        if qty is not None and unit is not None and price is not None:
            if abs(round(qty * unit - discount, 2) - price) > 0.02:
                item.pop("quantity", None)
                item.pop("unit_price", None)

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
        elif (item.get("description", "").strip()
              or item.get("price")
              or item.get("unit_price")
              or item.get("quantity")):
            result.append(item)

    return result


def write_line_items(
    job_id: str,
    user_id: str,
    user_email: str,
    created_at: str,
    vendor: str,
    receipt_date: str,
    items: list,
    expires_at: int,
) -> None:
    """Write one DynamoDB record per line item to the line_items table.

    item_sk      = "{created_at}#{job_id}#{NNN}"  — range key, sorts by date
    desc_created = "{description}#{created_at}"   — GSI SK for per-item date queries
    """
    for i, item in enumerate(items):
        description = item.get("description", "").strip()
        if not description:
            continue

        item_sk = f"{created_at}#{job_id}#{i:03d}"
        desc_created = f"{description}#{created_at}"

        def to_n(val):
            """Convert a price/qty string to a numeric DynamoDB N value."""
            try:
                return {"N": str(float(str(val).replace(",", "")))}
            except (ValueError, TypeError):
                return None

        record: dict = {
            "user_id":       {"S": user_id},
            "item_sk":       {"S": item_sk},
            "job_id":        {"S": job_id},
            "description":   {"S": description},
            "desc_created":  {"S": desc_created},
            "email":         {"S": user_email},
            "vendor":        {"S": vendor},
            "receipt_date":  {"S": receipt_date},
            "created_at":    {"S": created_at},
            "expires_at":    {"N": str(expires_at)},
        }

        qty_n      = to_n(item.get("quantity"))
        unit_n     = to_n(item.get("unit_price"))
        price_n    = to_n(item.get("price"))
        discount_n = to_n(item.get("discount"))

        if qty_n:
            record["quantity"] = qty_n
        if unit_n:
            record["unit_price"] = unit_n
        if price_n:
            record["price"] = price_n
        if discount_n:
            record["discount"] = discount_n

        dynamodb.put_item(TableName=LINE_ITEMS_TABLE, Item=record)
        print(f"LINE_ITEM_WRITTEN {job_id}#{i:03d} {description!r}")


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
