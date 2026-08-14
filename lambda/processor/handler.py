import io
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote_plus

import boto3

DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]
DYNAMODB_REGION = os.environ.get("DYNAMODB_REGION", "ap-southeast-2")
BEDROCK_MODEL = os.environ.get("BEDROCK_MODEL_ID", "us.meta.llama3-2-11b-instruct-v1:0")
S3_BUCKET = os.environ["S3_UPLOADS_BUCKET"]
S3_REGION = os.environ.get("S3_REGION", "ap-southeast-2")

s3 = boto3.client("s3", region_name=S3_REGION)
dynamodb = boto3.client("dynamodb", region_name=DYNAMODB_REGION)
# region_name="us-east-1" sets the boto3 signing region to us-east-1, which satisfies
# Bedrock's geofencing requirement for the us.meta inference profile. The Lambda itself
# runs in ap-southeast-2 — only the API call is signed and routed to us-east-1.
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

CLASSIFY_PROMPT = (
    'Look at this image carefully. Classify the primary emotion shown as either "happy" or "sad".\n\n'
    "Respond ONLY with valid JSON in this exact format (no markdown, no explanation outside the JSON):\n"
    '{"label": "happy", "reasoning": "...", "confidence": 0.85}\n\n'
    "Rules:\n"
    '- label must be exactly "happy" or "sad" (lowercase)\n'
    "- reasoning: 1-2 sentences explaining your classification\n"
    "- confidence: float between 0.0 and 1.0"
)


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
        user_id = parts[1] if len(parts) >= 3 else "unknown"
        job_id = parts[2].rsplit(".", 1)[0] if len(parts) >= 3 else key

        update_job(job_id, {
            "status": {"S": "PROCESSING"},
            "updated_at": {"S": now_iso()},
        })

        image_bytes = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        png_bytes = convert_to_png_resized(image_bytes)
        result = classify_image(png_bytes)

        expiry = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
        update_job(job_id, {
            "status": {"S": "COMPLETE"},
            "label": {"S": result["label"]},
            "reasoning": {"S": result["reasoning"]},
            "confidence": {"N": str(result["confidence"])},
            "updated_at": {"S": now_iso()},
            "expires_at": {"N": str(expiry)},
        })


def convert_to_png_resized(image_bytes: bytes) -> bytes:
    from PIL import Image

    max_dim = 1120
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if img.width > max_dim or img.height > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def classify_image(image_bytes: bytes) -> dict:
    response = bedrock.converse(
        modelId=BEDROCK_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"image": {"format": "png", "source": {"bytes": image_bytes}}},
                {"text": CLASSIFY_PROMPT},
            ],
        }],
        inferenceConfig={"maxTokens": 512, "temperature": 0.1, "topP": 0.9},
    )
    raw = response["output"]["message"]["content"][0]["text"]
    return parse_classification(raw)


def parse_classification(text: str) -> dict:
    # Try direct JSON parse first
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Try to extract a JSON object from the response
    match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Keyword fallback — model did not follow the JSON format
    label = "happy" if "happy" in text.lower() else "sad"
    pct_match = re.search(r"(\d+\.?\d*)\s*%", text)
    confidence = float(pct_match.group(1)) / 100 if pct_match else 0.5
    return {"label": label, "reasoning": text[:300], "confidence": round(confidence, 2)}


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
