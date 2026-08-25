import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote_plus

import boto3

from dynamo import update_job, get_job, now_iso, dyn_s, dyn_n, dyn_bool
from pricing import check_price_sum
from line_items import write_line_items, LineItemContext
from image_processing import (
    _to_jpeg,
    _compute_skew_angle,
    _deskew_correction,
    _deskew_image,
    crop_receipt,
)
from textract_pipeline import TextractResult, _textract_lines, _debug_block_list
from bedrock_extraction import (
    BEDROCK_MODEL_ID,
    _run_bedrock,
    _validate_classification,
    _fix_weighted_item_prices,
    _compute_net_prices,
)

@dataclass
class ReceiptAnalysis:
    store_category: str
    vendor: str
    receipt_date: str
    total: str
    items: list
    price_check_warning: bool
    price_check_message: str
    debug_s3_key: str
    textract_debug_s3_key: str
    cropped_s3_key: str | None = None


DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]
LINE_ITEMS_TABLE = os.environ.get("LINE_ITEMS_TABLE", "")
IMAGE_HASHES_TABLE = os.environ.get("IMAGE_HASHES_TABLE", "")
S3_BUCKET = os.environ["S3_UPLOADS_BUCKET"]
PRIMARY_REGION = os.environ.get("PRIMARY_REGION", "ap-southeast-2")

s3 = boto3.client("s3", region_name=PRIMARY_REGION)
dynamodb = boto3.client("dynamodb", region_name=PRIMARY_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=PRIMARY_REGION)
textract = boto3.client("textract", region_name=PRIMARY_REGION)

# Wire the module-level clients into the sub-modules that need them
import textract_pipeline as _tp
import bedrock_extraction as _be
_tp.set_textract_client(textract)
_be.set_bedrock_client(bedrock)


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

        try:
            _process_s3_record(bucket, key, job_id)
        except Exception:
            _mark_job_failed(job_id)
            raise


def _mark_job_failed(job_id: str) -> None:
    try:
        update_job(dynamodb, DYNAMODB_TABLE, job_id, {
            "status": dyn_s("FAILED"),
            "updated_at": dyn_s(now_iso()),
        })
    except Exception as exc:
        print(f"ERROR marking job {job_id} as FAILED: {exc}")


def _process_s3_record(bucket: str, key: str, job_id: str) -> None:
    existing = get_job(dynamodb, DYNAMODB_TABLE, job_id)
    if existing and existing["status"] == "COMPLETE":
        print(f"Job {job_id} already COMPLETE — skipping")
        return

    user_id = (existing or {}).get("user_id") or "unknown"
    user_email = (existing or {}).get("email") or ""
    created_at = (existing or {}).get("created_at") or now_iso()

    update_job(dynamodb, DYNAMODB_TABLE, job_id, {
        "status": dyn_s("PROCESSING"),
        "updated_at": dyn_s(now_iso()),
    })

    image_data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    image_hash = hashlib.sha256(image_data).hexdigest()

    prior_job_id = lookup_image_hash(user_id, image_hash)
    if prior_job_id:
        prior = get_job(dynamodb, DYNAMODB_TABLE, prior_job_id)
        prior_status = prior["status"] if prior else None
        if prior_status == "COMPLETE":
            print(f"DUPLICATE image_hash={image_hash[:12]}… prior_job={prior_job_id}")
            s3.delete_object(Bucket=bucket, Key=key)
            update_job(dynamodb, DYNAMODB_TABLE, job_id, {
                "status": dyn_s("DUPLICATE"),
                "image_hash": dyn_s(image_hash),
                "updated_at": dyn_s(now_iso()),
            })
            return

    result = analyze_receipt(bucket, key, job_id, user_id, image_data=image_data)

    expiry = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
    update_job(dynamodb, DYNAMODB_TABLE, job_id, {
        "status": dyn_s("COMPLETE"),
        "store_category": dyn_s(result.store_category),
        "price_check_warning": dyn_bool(result.price_check_warning),
        "price_check_message": dyn_s(result.price_check_message),
        "vendor": dyn_s(result.vendor),
        "receipt_date": dyn_s(result.receipt_date),
        "total": dyn_s(result.total),
        "items": dyn_s(json.dumps(result.items)),
        "debug_s3_key": dyn_s(result.debug_s3_key),
        "textract_debug_s3_key": dyn_s(result.textract_debug_s3_key),
        **( {"cropped_s3_key": dyn_s(result.cropped_s3_key)} if result.cropped_s3_key else {} ),
        "image_hash": dyn_s(image_hash),
        "updated_at": dyn_s(now_iso()),
        "expires_at": dyn_n(expiry),
    })

    store_image_hash(user_id, image_hash, job_id, expiry)

    if LINE_ITEMS_TABLE:
        ctx = LineItemContext(
            job_id=job_id,
            user_id=user_id,
            user_email=user_email,
            created_at=created_at,
            vendor=result.vendor,
            receipt_date=result.receipt_date,
            store_category=result.store_category,
            expires_at=expiry,
        )
        write_line_items(dynamodb, LINE_ITEMS_TABLE, ctx, result.items)


def _run_deskew_pipeline(data: bytes, skew_threshold: float) -> tuple[bytes, TextractResult, float | None, float | None, bool]:
    """Run initial Textract, compute skew, conditionally deskew and re-run.

    Returns (final_bytes, textract_result, skew, correction, deskew_applied).
    """
    tr = _textract_lines(data)

    skew = _compute_skew_angle(tr.blocks)
    correction = _deskew_correction(skew, skew_threshold)
    deskew_applied = correction is not None
    if deskew_applied:
        print(f"DESKEW angle={skew:.2f}° correction={correction:.1f}° — rotating and re-running Textract")
        data = _deskew_image(data, correction)
        tr = _textract_lines(data)
    else:
        print(f"DESKEW skew={skew:.2f}° — no correction" if skew is not None else "DESKEW insufficient lines")

    return data, tr, skew, correction, deskew_applied


def _save_debug_payloads(
    job_id: str,
    user_id: str,
    tr: TextractResult,
    skew: float | None,
    correction: float | None,
    deskew_applied: bool,
    extracted: dict,
    usage: dict,
    price_check: dict,
    skew_threshold: float,
) -> tuple[str, str]:
    """Write both debug JSON files to S3. Returns (claude_debug_key, textract_debug_key)."""
    textract_debug_key = save_debug(job_id, user_id, {
        "deskew": {
            "angle_deg": round(skew, 3) if skew is not None else None,
            "correction_deg": round(correction, 1) if correction is not None else None,
            "applied": deskew_applied,
            "threshold_deg": skew_threshold,
        },
        "row_grouping": {
            "line_height": round(tr.line_height, 4),
            "step_tol": round(tr.step_tol, 4),
        },
        "blocks": _debug_block_list(tr.blocks, tr.rows),
        "lines": tr.lines,
    }, suffix="_textract")
    claude_debug_key = save_debug(job_id, user_id, {
        "model": BEDROCK_MODEL_ID,
        "extracted": extracted,
        "usage": usage,
        "price_check": price_check,
    })
    return claude_debug_key, textract_debug_key


def analyze_receipt(bucket: str, key: str, job_id: str, user_id: str, image_data: bytes | None = None) -> ReceiptAnalysis:
    SKEW_THRESHOLD = 1.0  # degrees — below this, noise outweighs benefit

    cropped_key = crop_receipt(s3, bucket, key, image_data=image_data)

    if cropped_key:
        data = s3.get_object(Bucket=bucket, Key=cropped_key)["Body"].read()
    else:
        raw = image_data or s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        data = _to_jpeg(raw)

    _, tr, skew, correction, deskew_applied = _run_deskew_pipeline(data, SKEW_THRESHOLD)

    extracted, usage = _run_bedrock(tr.text)

    _validate_classification(extracted)
    corrections = _fix_weighted_item_prices(extracted.get("items", []))
    if corrections:
        print(f"WEIGHTED_PRICE_FIX_TOTAL corrections={corrections}")
    _compute_net_prices(extracted.get("items", []))
    price_check = check_price_sum(extracted.get("items", []), extracted.get("total", ""))
    if price_check["warning"]:
        print(f"PRICE_CHECK_WARNING {price_check}")

    claude_debug_key, textract_debug_key = _save_debug_payloads(
        job_id, user_id, tr, skew, correction, deskew_applied, extracted, usage, price_check, SKEW_THRESHOLD,
    )

    return ReceiptAnalysis(
        store_category=extracted.get("store_category") or "other",
        vendor=extracted.get("vendor") or "Unknown vendor",
        receipt_date=extracted.get("receipt_date") or "",
        total=extracted.get("total") or "",
        items=extracted.get("items") or [],
        price_check_warning=price_check["warning"],
        price_check_message=price_check["message"],
        debug_s3_key=claude_debug_key,
        textract_debug_s3_key=textract_debug_key,
        cropped_s3_key=cropped_key,
    )


def save_debug(job_id: str, user_id: str, payload: dict, suffix: str = "") -> str:
    debug_key = f"debug/{user_id}/{job_id}{suffix}.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=debug_key,
        Body=json.dumps(payload, default=str).encode(),
        ContentType="application/json",
    )
    return debug_key


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
            "user_id":    dyn_s(user_id),
            "image_hash": dyn_s(image_hash),
            "job_id":     dyn_s(job_id),
            "expires_at": dyn_n(expires_at),
        },
    )


