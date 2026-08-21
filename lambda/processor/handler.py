import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote_plus

import boto3
import cv2
import numpy as np

DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]
LINE_ITEMS_TABLE = os.environ.get("LINE_ITEMS_TABLE", "")
IMAGE_HASHES_TABLE = os.environ.get("IMAGE_HASHES_TABLE", "")
S3_BUCKET = os.environ["S3_UPLOADS_BUCKET"]
PRIMARY_REGION = os.environ.get("PRIMARY_REGION", "ap-southeast-2")
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0"
)

s3 = boto3.client("s3", region_name=PRIMARY_REGION)
dynamodb = boto3.client("dynamodb", region_name=PRIMARY_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=PRIMARY_REGION)
textract = boto3.client("textract", region_name=PRIMARY_REGION)

# Tool definition — forces structured JSON output from the model
RECEIPT_TOOL = {
    "toolSpec": {
        "name": "extract_receipt",
        "description": "Extract structured data from a receipt image.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "vendor": {
                        "type": "string",
                        "description": "Store or vendor name",
                    },
                    "receipt_date": {
                        "type": "string",
                        "description": "Date of purchase as printed on the receipt",
                    },
                    "total": {
                        "type": "string",
                        "description": "Final total amount paid, without currency symbol, e.g. '42.50'",
                    },
                    "items": {
                        "type": "array",
                        "description": (
                            "Every purchased line item. Exclude summary lines "
                            "such as subtotal, GST, EFTPOS, cash, and change."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {
                                    "type": "string",
                                    "description": (
                                        "Product name only. "
                                        "Do not include quantity, unit price, or totals in this field."
                                    ),
                                },
                                "quantity": {
                                    "type": "string",
                                    "description": (
                                        "Number of units purchased. "
                                        "If the receipt shows '2 @ $1.79', quantity is '2'. "
                                        "For weight-based items e.g. '1.5 Kg @ $2.99/Kg', quantity is '1.5 Kg'."
                                    ),
                                },
                                "unit_price": {
                                    "type": "string",
                                    "description": (
                                        "Price per single unit without currency symbol. "
                                        "If the receipt shows '2 @ $1.79', unit_price is '1.79'."
                                    ),
                                },
                                "price": {
                                    "type": "string",
                                    "description": (
                                        "Final line total after any discount, without currency symbol, e.g. '3.00'. "
                                        "If a discount line follows this item, subtract it here."
                                    ),
                                },
                                "discount": {
                                    "type": "string",
                                    "description": (
                                        "Discount as a negative number without currency symbol. "
                                        "If the receipt shows a discount line of '-$0.58' for this item, "
                                        "discount is '-0.58'. Merge it into this item — do not create a separate item for it. "
                                        "price should equal (quantity * unit_price) + discount."
                                    ),
                                },
                            },
                            "required": ["description"],
                        },
                    },
                },
                "required": ["vendor", "receipt_date", "total", "items"],
            }
        },
    }
}


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
            print(f"Job {job_id} already COMPLETE — skipping")
            continue

        user_id = existing_item.get("user_id", {}).get("S", "unknown")
        user_email = existing_item.get("email", {}).get("S", "")
        created_at = existing_item.get("created_at", {}).get("S", now_iso())

        update_job(job_id, {
            "status": {"S": "PROCESSING"},
            "updated_at": {"S": now_iso()},
        })

        image_data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        image_hash = hashlib.sha256(image_data).hexdigest()

        prior_job_id = lookup_image_hash(user_id, image_hash)
        if prior_job_id:
            prior_resp = dynamodb.get_item(
                TableName=DYNAMODB_TABLE,
                Key={"job_id": {"S": prior_job_id}},
            )
            prior_status = prior_resp.get("Item", {}).get("status", {}).get("S")
            if prior_status == "COMPLETE":
                print(f"DUPLICATE image_hash={image_hash[:12]}… prior_job={prior_job_id}")
                s3.delete_object(Bucket=bucket, Key=key)
                update_job(job_id, {
                    "status": {"S": "DUPLICATE"},
                    "image_hash": {"S": image_hash},
                    "updated_at": {"S": now_iso()},
                })
                continue

        result = analyze_receipt(bucket, key, job_id, user_id, image_data=image_data)

        expiry = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
        update_job(job_id, {
            "status": {"S": "COMPLETE"},
            "vendor": {"S": result["vendor"]},
            "receipt_date": {"S": result["receipt_date"]},
            "total": {"S": result["total"]},
            "items": {"S": json.dumps(result["items"])},
            "debug_s3_key": {"S": result["debug_s3_key"]},
            "textract_debug_s3_key": {"S": result["textract_debug_s3_key"]},
            **( {"cropped_s3_key": {"S": result["cropped_s3_key"]}} if result.get("cropped_s3_key") else {} ),
            "image_hash": {"S": image_hash},
            "updated_at": {"S": now_iso()},
            "expires_at": {"N": str(expiry)},
        })

        store_image_hash(user_id, image_hash, job_id, expiry)

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


def _to_jpeg(data: bytes) -> bytes:
    """Ensure image bytes are JPEG — converts HEIC and other formats via cv2."""
    if data[:2] == b"\xff\xd8":
        return data
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Cannot decode image ({len(data)//1024}KB)")
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise ValueError("Failed to encode image as JPEG")
    return buf.tobytes()


def _textract_lines(image_bytes: bytes) -> tuple[str, list[str]]:
    """Run Textract DetectDocumentText and return (full_text, lines) in reading order.

    Groups blocks into rows by proximity then sorts left-to-right within each
    row, producing a layout-aware text representation of the receipt.
    """
    resp = textract.detect_document_text(Document={"Bytes": image_bytes})
    blocks = [b for b in resp["Blocks"] if b["BlockType"] == "LINE"]
    blocks.sort(key=lambda b: b["Geometry"]["BoundingBox"]["Top"])

    ROW_GAP = 0.012  # fraction of page height — blocks closer than this are the same row
    rows: list[list] = []
    current: list = []
    for block in blocks:
        if not current or block["Geometry"]["BoundingBox"]["Top"] - current[0]["Geometry"]["BoundingBox"]["Top"] < ROW_GAP:
            current.append(block)
        else:
            rows.append(sorted(current, key=lambda b: b["Geometry"]["BoundingBox"]["Left"]))
            current = [block]
    if current:
        rows.append(sorted(current, key=lambda b: b["Geometry"]["BoundingBox"]["Left"]))

    lines = ["  ".join(b["Text"] for b in row) for row in rows]
    print(f"TEXTRACT lines={len(lines)}")
    return "\n".join(lines), lines


def analyze_receipt(bucket: str, key: str, job_id: str, user_id: str, image_data: bytes | None = None) -> dict:
    cropped_key = crop_receipt(bucket, key, image_data=image_data)

    if cropped_key:
        data = s3.get_object(Bucket=bucket, Key=cropped_key)["Body"].read()
    else:
        raw = image_data or s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        data = _to_jpeg(raw)

    receipt_text, receipt_lines = _textract_lines(data)

    response = bedrock.converse(
        modelId=BEDROCK_MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": (
                            "Here is text extracted by OCR from a receipt, in reading order "
                            "(items on the same row are separated by two spaces):\n\n"
                            f"{receipt_text}\n\n"
                            "Extract all structured data from this receipt. "
                            "Include every purchased product as a line item. "
                            "Exclude summary lines such as subtotal, GST, EFTPOS, cash, and change. "
                            "Return all prices and totals without currency symbols. "
                            "For multi-unit lines like 'ITEM NAME  $price' followed by '2 @  $1.79', "
                            "set quantity to '2', unit_price to '1.79', price to the line total. "
                            "For weight-based lines like '1.741 Kg @  $1.49/Kg', "
                            "set quantity to '1.741 Kg', unit_price to '1.49'. "
                            "If a discount appears as a product name repeated with a negative amount (e.g. 'BROCCOLI  -$0.58'), "
                            "merge it into the preceding item for that product: set discount to '-0.58' (negative). "
                            "price = (quantity * unit_price) + discount. "
                            "Do not create a separate line item for discounts. "
                            "Use an empty string for any field you cannot determine."
                        )
                    }
                ],
            }
        ],
        toolConfig={
            "tools": [RECEIPT_TOOL],
            "toolChoice": {"tool": {"name": "extract_receipt"}},
        },
    )

    extracted = {}
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if block.get("toolUse", {}).get("name") == "extract_receipt":
            extracted = block["toolUse"]["input"]
            break

    usage = response.get("usage", {})
    print(
        f"BEDROCK_USAGE model={BEDROCK_MODEL_ID} "
        f"input={usage.get('inputTokens')} output={usage.get('outputTokens')}"
    )

    textract_debug_key = save_debug(job_id, user_id, {"lines": receipt_lines}, suffix="_textract")
    claude_debug_key = save_debug(job_id, user_id, {
        "model": BEDROCK_MODEL_ID,
        "extracted": extracted,
        "usage": usage,
    })

    return {
        "vendor": extracted.get("vendor") or "Unknown vendor",
        "receipt_date": extracted.get("receipt_date") or "",
        "total": extracted.get("total") or "",
        "items": extracted.get("items") or [],
        "debug_s3_key": claude_debug_key,
        "textract_debug_s3_key": textract_debug_key,
        "cropped_s3_key": cropped_key,
    }


def save_debug(job_id: str, user_id: str, payload: dict, suffix: str = "") -> str:
    debug_key = f"debug/{user_id}/{job_id}{suffix}.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=debug_key,
        Body=json.dumps(payload, default=str).encode(),
        ContentType="application/json",
    )
    return debug_key


def crop_receipt(bucket: str, key: str, image_data: bytes | None = None) -> str | None:
    """Crop the receipt from the image using multiple detection methods in priority order."""
    DETECT_SCALE = 1200
    MIN_GAIN = 0.85
    PAD_FRAC = 0.025

    try:
        data = image_data if image_data is not None else s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            print("CROP_SKIPPED: could not decode image")
            return

        h, w = img.shape[:2]
        scale = DETECT_SCALE / max(h, w)
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
        small = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)

        result = _find_receipt(small, sw, sh)
        if result is None:
            print("CROP_SKIPPED: no receipt region detected")
            return

        method, sx0, sy0, sx1, sy1 = result

        # Pad in small-image space then scale back
        px, py = int(sw * PAD_FRAC), int(sh * PAD_FRAC)
        left  = max(0, int(max(0, sx0 - px) / scale))
        upper = max(0, int(max(0, sy0 - py) / scale))
        right = min(w,  int(min(sw, sx1 + px) / scale))
        lower = min(h,  int(min(sh, sy1 + py) / scale))

        pixel_ratio = (right - left) * (lower - upper) / (w * h)
        if pixel_ratio >= MIN_GAIN:
            print(f"CROP_SKIPPED ({method}): {pixel_ratio:.0%} — no meaningful gain")
            return None

        cropped = img[upper:lower, left:right]
        ok, buf = cv2.imencode(".jpg", cropped, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            print("CROP_SKIPPED: imencode failed")
            return None

        cropped_bytes = buf.tobytes()
        print(
            f"CROP ({method}) {w}x{h} -> {right-left}x{lower-upper} "
            f"{len(data)//1024}KB -> {len(cropped_bytes)//1024}KB ({pixel_ratio:.0%} area)"
        )
        cropped_key = key.replace("uploads/", "cropped/", 1)
        s3.put_object(
            Bucket=bucket,
            Key=cropped_key,
            Body=cropped_bytes,
            ContentType="image/jpeg",
        )
        return cropped_key

    except Exception as exc:
        print(f"CROP_SKIPPED: {exc}")
        return None


def _find_receipt(small, sw, sh):
    """Try detection methods in priority order. Returns (method, x0, y0, x1, y1) or None."""
    for method, fn in (("bright", _bright_region), ("contour", _edge_contour), ("mser", _mser_density)):
        r = fn(small, sw, sh)
        if r:
            print(f"CROP_METHOD: {method}")
            return (method,) + r
    return None


def _bright_region(small, sw, sh):
    """Find a large bright (white/cream) area — works for receipts on coloured backgrounds."""
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
    l = lab[:, :, 0]
    k = max(3, sw // 80)
    kernel = np.ones((k, k), np.uint8)
    for thresh in (195, 180, 165):
        _, mask = cv2.threshold(l, thresh, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel * 4)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) < 0.12 * sw * sh:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        if bh > 0 and 0.15 < bw / bh < 5.0:
            return x, y, x + bw, y + bh
    return None


def _edge_contour(small, sw, sh):
    """Find the largest enclosed region via Canny edge detection."""
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 30, 100)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=3)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(contours, key=cv2.contourArea, reverse=True):
        if cv2.contourArea(c) < 0.12 * sw * sh:
            break
        x, y, bw, bh = cv2.boundingRect(c)
        if bh > 0 and 0.15 < bw / bh < 5.0:
            return x, y, x + bw, y + bh
    return None


def _mser_density(small, sw, sh):
    """Original MSER text-density approach — last-resort fallback."""
    MIN_BBOX, MAX_BBOX = 20, 1500
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
        if (0.15 < rw/rh < 6.0) and (0.1 < len(region)/bbox_area < 0.9) and (MIN_BBOX < bbox_area < MAX_BBOX):
            valid_cx.append(rx + rw / 2)
            valid_cy.append(ry + rh / 2)
    print(f"MSER regions={len(regions)} text-like={len(valid_cx)}")
    if not valid_cx:
        return None
    def dense_band(centres, size):
        hist, edges = np.histogram(centres, bins=40, range=(0, size))
        smoothed = np.convolve(hist, np.ones(5) / 5, mode="same")
        threshold = smoothed.max() * 0.60
        active = [i for i, s in enumerate(smoothed) if s >= threshold]
        if not active:
            return 0, size
        pad = int(size * 0.05)
        return max(0, int(edges[active[0]]) - pad), min(size, int(edges[active[-1] + 1]) + pad)
    x0, x1 = dense_band(valid_cx, sw)
    y0, y1 = dense_band(valid_cy, sh)
    return x0, y0, x1, y1


def lookup_image_hash(user_id: str, image_hash: str) -> str | None:
    if not IMAGE_HASHES_TABLE:
        return None
    resp = dynamodb.get_item(
        TableName=IMAGE_HASHES_TABLE,
        Key={"user_id": {"S": user_id}, "image_hash": {"S": image_hash}},
    )
    return resp.get("Item", {}).get("job_id", {}).get("S")


def store_image_hash(user_id: str, image_hash: str, job_id: str, expires_at: int) -> None:
    if not IMAGE_HASHES_TABLE:
        return
    dynamodb.put_item(
        TableName=IMAGE_HASHES_TABLE,
        Item={
            "user_id":    {"S": user_id},
            "image_hash": {"S": image_hash},
            "job_id":     {"S": job_id},
            "expires_at": {"N": str(expires_at)},
        },
    )


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
    for i, item in enumerate(items):
        description = item.get("description", "").strip()
        if not description:
            continue

        item_sk = f"{created_at}#{job_id}#{i:03d}"
        desc_created = f"{description}#{created_at}"

        def to_n(val):
            try:
                cleaned = str(val).replace(",", "").replace("$", "").strip()
                return {"N": str(float(cleaned))} if cleaned else None
            except (ValueError, TypeError):
                return None

        record: dict = {
            "user_id":      {"S": user_id},
            "item_sk":      {"S": item_sk},
            "job_id":       {"S": job_id},
            "description":  {"S": description},
            "desc_created": {"S": desc_created},
            "email":        {"S": user_email},
            "vendor":       {"S": vendor},
            "receipt_date": {"S": receipt_date},
            "created_at":   {"S": created_at},
            "expires_at":   {"N": str(expires_at)},
        }

        for field in ("quantity", "unit_price", "price", "discount"):
            n = to_n(item.get(field))
            if n:
                record[field] = n

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
