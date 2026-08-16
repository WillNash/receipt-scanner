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
    response = textract.analyze_expense(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    print("TEXTRACT_RAW_RESPONSE", json.dumps(response, default=str))

    vendor = ""
    receipt_date = ""
    total = ""
    items = []

    for doc in response.get("ExpenseDocuments", []):
        for field in doc.get("SummaryFields", []):
            field_type = field.get("Type", {}).get("Text", "")
            value = field.get("ValueDetection", {}).get("Text", "")
            if field_type == "VENDOR_NAME" and not vendor:
                vendor = value
            elif field_type == "INVOICE_RECEIPT_DATE" and not receipt_date:
                receipt_date = value
            elif field_type == "TOTAL" and not total:
                total = value

        for group in doc.get("LineItemGroups", []):
            for line_item in group.get("LineItems", []):
                item = {}
                for expense_field in line_item.get("LineItemExpenseFields", []):
                    field_type = expense_field.get("Type", {}).get("Text", "")
                    value = expense_field.get("ValueDetection", {}).get("Text", "")
                    if field_type == "ITEM":
                        item["description"] = value
                    elif field_type == "QUANTITY":
                        item["quantity"] = value
                    elif field_type == "UNIT_PRICE":
                        item["unit_price"] = value
                    elif field_type == "PRICE":
                        item["price"] = value
                if item:
                    items.append(item)

    print("TEXTRACT_RAW_ITEMS", json.dumps(items))
    reconciled = reconcile_line_items(items)
    print("TEXTRACT_RECONCILED_ITEMS", json.dumps(reconciled))

    return {
        "vendor": vendor or "Unknown vendor",
        "receipt_date": receipt_date or "",
        "total": total or "",
        "items": reconciled,
    }


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

    Textract AnalyzeExpense can mis-pair the second line with the wrong
    description above it. Fix in two passes:
      1. Strip pricing from items where qty * unit_price != price — these
         are items that received another item's price row by mistake.
      2. Merge consecutive (description-only, price-only) pairs — the
         orphaned price row belongs to the description immediately above it.
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
    # They are not necessarily adjacent: Textract may order the second line of a
    # multi-unit item well away from its description. Collect both sets globally,
    # pair them in order of first appearance, and insert the merged item at the
    # description's original position (preserving receipt order).
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

    # Pair description-only with price-only in positional order
    merged_at = {}   # desc index -> merged item dict
    skip = set()     # price-only indices to drop (merged into desc position)
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
