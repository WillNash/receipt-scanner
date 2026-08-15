import json
import os
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

    return {
        "vendor": vendor or "Unknown vendor",
        "receipt_date": receipt_date or "",
        "total": total or "",
        "items": items,
    }


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
