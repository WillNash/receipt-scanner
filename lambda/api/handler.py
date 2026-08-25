import json
import os
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config
from constants import VALID_ITEM_CATEGORIES
from dynamo import update_job, now_iso, dyn_s, dyn_n, dyn_bool
from line_items import write_line_items, LineItemContext
from pricing import check_price_sum

DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]
LINE_ITEMS_TABLE = os.environ.get("LINE_ITEMS_TABLE", "")
IMAGE_HASHES_TABLE = os.environ.get("IMAGE_HASHES_TABLE", "")
UPLOADS_BUCKET = os.environ["UPLOADS_BUCKET"]
COGNITO_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
COGNITO_APP_CLIENT_ID = os.environ["COGNITO_APP_CLIENT_ID"]
PRIMARY_REGION = os.environ.get("PRIMARY_REGION", "ap-southeast-2")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
DAILY_UPLOAD_LIMIT = int(os.environ.get("DAILY_UPLOAD_LIMIT", "50"))
GLOBAL_UPLOAD_LIMIT = int(os.environ.get("GLOBAL_UPLOAD_LIMIT", "100"))

dynamodb = boto3.client("dynamodb", region_name=PRIMARY_REGION)
s3 = boto3.client(
    "s3",
    region_name=PRIMARY_REGION,
    endpoint_url=f"https://s3.{PRIMARY_REGION}.amazonaws.com",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,PATCH,OPTIONS",
    "Content-Type": "application/json",
}

VALID_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
}

# Module-level JWKS cache — populated once per Lambda container (cold start only).
# Warm invocations reuse _jwks_cache and skip the Cognito network fetch.
_jwks_cache = None


def get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        jwks_url = (
            f"https://cognito-idp.{PRIMARY_REGION}.amazonaws.com"
            f"/{COGNITO_POOL_ID}/.well-known/jwks.json"
        )
        with urllib.request.urlopen(jwks_url) as resp:
            _jwks_cache = json.loads(resp.read())
    return _jwks_cache


def _route(method: str, path: str, user_id: str, user_email: str, event: dict):
    job_id = (event.get("pathParameters") or {}).get("jobId")
    body = json.loads(event.get("body") or "{}") if method in ("POST", "PATCH") else {}

    if method == "POST" and path.endswith("/upload-url"):
        return handle_upload_url(event, user_id, user_email)
    if method == "GET" and path.endswith("/receipts"):
        return handle_list_receipts(user_id)
    if method == "GET" and "/jobs/" in path:
        return handle_get_job(job_id, user_id)
    if method == "DELETE" and "/receipts/" in path:
        return handle_delete_receipt(job_id, user_id)
    if method == "PATCH" and "/receipts/" in path:
        return handle_edit_receipt(job_id, user_id, body)
    return make_response(404, {"error": "Not found"})


def lambda_handler(event, context):
    method = event.get("httpMethod", "")
    path = event.get("path", "")

    if method == "OPTIONS":
        return make_response(200, {})

    try:
        user_id, user_email = get_user_id(event)
    except Exception as exc:
        return make_response(401, {"error": f"Unauthorized: {exc}"})

    return _route(method, path, user_id, user_email, event)


def _check_and_increment_count(counter_key: str, limit: int) -> bool:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    expiry = int((datetime.now(timezone.utc) + timedelta(days=2)).timestamp())
    resp = dynamodb.update_item(
        TableName=DYNAMODB_TABLE,
        Key={"job_id": dyn_s(counter_key)},
        UpdateExpression="ADD upload_count :one SET expires_at = if_not_exists(expires_at, :exp)",
        ExpressionAttributeValues={":one": dyn_n(1), ":exp": dyn_n(expiry)},
        ReturnValues="UPDATED_NEW",
    )
    return int(resp["Attributes"]["upload_count"]["N"]) <= limit


def check_and_increment_global_count() -> bool:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _check_and_increment_count(f"COUNT#GLOBAL#{today}", GLOBAL_UPLOAD_LIMIT)


def check_and_increment_daily_count(user_id: str) -> bool:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _check_and_increment_count(f"COUNT#{user_id}#{today}", DAILY_UPLOAD_LIMIT)


def handle_upload_url(event, user_id: str, user_email: str):
    body = json.loads(event.get("body") or "{}")
    content_type = body.get("contentType", "image/jpeg")
    image_hash = body.get("imageHash")

    if content_type not in VALID_CONTENT_TYPES:
        return make_response(400, {"error": f"Unsupported content type: {content_type}"})

    if image_hash and IMAGE_HASHES_TABLE:
        resp = dynamodb.get_item(
            TableName=IMAGE_HASHES_TABLE,
            Key={"user_id": dyn_s(user_id), "image_hash": dyn_s(image_hash)},
        )
        if resp.get("Item"):
            prior_job_id = resp["Item"].get("job_id", {}).get("S", "")
            return make_response(409, {"error": "duplicate", "jobId": prior_job_id})

    if not check_and_increment_daily_count(user_id):
        return make_response(429, {
            "error": f"You've reached your daily limit of {DAILY_UPLOAD_LIMIT} uploads. Try again tomorrow.",
            "limitType": "user",
        })

    if not check_and_increment_global_count():
        return make_response(429, {
            "error": "Today's global upload limit has been reached. Try again tomorrow.",
            "limitType": "global",
        })

    ext = VALID_CONTENT_TYPES[content_type]
    job_id = str(uuid.uuid4())
    s3_key = f"uploads/{user_id}/{job_id}.{ext}"
    now = now_iso()
    expiry = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())

    dynamodb.put_item(
        TableName=DYNAMODB_TABLE,
        Item={
            "job_id": dyn_s(job_id),
            "user_id": dyn_s(user_id),
            "email": dyn_s(user_email),
            "s3_key": dyn_s(s3_key),
            "status": dyn_s("PENDING"),
            "created_at": dyn_s(now),
            "updated_at": dyn_s(now),
            "expires_at": dyn_n(expiry),
        },
    )

    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": UPLOADS_BUCKET,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=300,
    )
    return make_response(200, {"jobId": job_id, "uploadUrl": upload_url, "s3Key": s3_key})


def handle_list_receipts(user_id: str):
    result = dynamodb.query(
        TableName=DYNAMODB_TABLE,
        IndexName="user-jobs-index",
        KeyConditionExpression="#uid = :uid",
        ExpressionAttributeNames={"#uid": "user_id"},
        ExpressionAttributeValues={":uid": dyn_s(user_id)},
        ScanIndexForward=False,
        Limit=20,
    )
    receipts = [
        format_receipt(item)
        for item in result.get("Items", [])
        if item.get("status", {}).get("S") != "DUPLICATE"
    ]
    return make_response(200, {"receipts": receipts})


def _fetch_job_item(job_id: str | None, user_id: str):
    """Fetch the raw DynamoDB job item and enforce ownership.

    Returns the item dict on success, or a make_response error dict on failure.
    """
    if not job_id:
        return make_response(400, {"error": "jobId required"})
    result = dynamodb.get_item(
        TableName=DYNAMODB_TABLE,
        Key={"job_id": dyn_s(job_id)},
    )
    item = result.get("Item")
    if not item:
        return make_response(404, {"error": "Job not found"})
    if item.get("user_id", {}).get("S") != user_id:
        return make_response(403, {"error": "Forbidden"})
    return item


def handle_get_job(job_id: str | None, user_id: str):
    item = _fetch_job_item(job_id, user_id)
    if "statusCode" in item:
        return item
    return make_response(200, format_receipt(item))


def _delete_line_items_for_job(job_id: str, user_id: str, created_at: str) -> None:
    """Query and batch-delete all line_items rows for a given job."""
    prefix = f"{created_at}#{job_id}#"
    resp = dynamodb.query(
        TableName=LINE_ITEMS_TABLE,
        KeyConditionExpression="#uid = :uid AND begins_with(#sk, :prefix)",
        ExpressionAttributeNames={"#uid": "user_id", "#sk": "item_sk"},
        ExpressionAttributeValues={
            ":uid": dyn_s(user_id),
            ":prefix": dyn_s(prefix),
        },
        ProjectionExpression="#uid, #sk",
    )
    keys_to_delete = [
        {"user_id": it["user_id"], "item_sk": it["item_sk"]}
        for it in resp.get("Items", [])
    ]
    for i in range(0, len(keys_to_delete), 25):
        chunk = keys_to_delete[i:i + 25]
        dynamodb.batch_write_item(
            RequestItems={
                LINE_ITEMS_TABLE: [
                    {"DeleteRequest": {"Key": key}} for key in chunk
                ]
            }
        )


def handle_delete_receipt(job_id: str | None, user_id: str):
    item = _fetch_job_item(job_id, user_id)
    if "statusCode" in item:
        return item

    image_hash = item.get("image_hash", {}).get("S")
    created_at = item.get("created_at", {}).get("S", "")

    # Atomically delete the job record and the dedup hash together
    transact_items = [
        {"Delete": {"TableName": DYNAMODB_TABLE, "Key": {"job_id": dyn_s(job_id)}}},
    ]
    if image_hash and IMAGE_HASHES_TABLE:
        transact_items.append({
            "Delete": {
                "TableName": IMAGE_HASHES_TABLE,
                "Key": {"user_id": dyn_s(user_id), "image_hash": dyn_s(image_hash)},
            }
        })
    dynamodb.transact_write_items(TransactItems=transact_items)

    # Delete all line items for this job (batch — cannot be in a transaction)
    if LINE_ITEMS_TABLE and created_at:
        try:
            _delete_line_items_for_job(job_id, user_id, created_at)
        except Exception as exc:
            print(f"ERROR delete_line_items job={job_id}: {exc} — line items may be orphaned")

    return make_response(200, {"deleted": True})


def _validate_edit_body(body: dict) -> str | None:
    """Return an error string if the PATCH body fails validation, else None."""
    if "vendor" in body:
        v = body["vendor"]
        if not isinstance(v, str) or len(v) > 200:
            return "vendor must be a string of at most 200 characters"
    if "receiptDate" in body:
        d = body["receiptDate"]
        if not isinstance(d, str) or len(d) > 20:
            return "receiptDate must be a string of at most 20 characters"
        import re
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            return "receiptDate must be in YYYY-MM-DD format"
    if "items" in body:
        items = body["items"]
        if not isinstance(items, list) or len(items) > 200:
            return "items must be a list of at most 200 entries"
        for item in items:
            if not isinstance(item, dict):
                return "each item must be an object"
            if "description" in item:
                desc = item["description"]
                if not isinstance(desc, str) or len(desc) > 500:
                    return "item description must be a string of at most 500 characters"
            if "quantity" in item:
                qty = item["quantity"]
                if not isinstance(qty, str) or len(qty) > 50:
                    return "item quantity must be a string of at most 50 characters"
            for field in ("unit_price", "price", "discount"):
                if field in item:
                    val = item[field]
                    if not isinstance(val, str) or len(val) > 30:
                        return f"item {field} must be a string of at most 30 characters"
    return None


def handle_edit_receipt(job_id: str | None, user_id: str, body: dict):
    err = _validate_edit_body(body)
    if err:
        return make_response(400, {"error": err})

    item = _fetch_job_item(job_id, user_id)
    if "statusCode" in item:
        return item

    updates = {"updated_at": dyn_s(now_iso())}

    if "vendor" in body:
        updates["vendor"] = dyn_s(str(body["vendor"]))

    if "receiptDate" in body:
        updates["receipt_date"] = dyn_s(str(body["receiptDate"]))

    new_items = body.get("items")  # full replacement list
    if new_items is not None:
        updates["items"] = dyn_s(json.dumps(new_items))

        # Recalculate price check so the warning clears once items are corrected
        total_str = item.get("total", {}).get("S", "")
        pc = _recheck_prices(new_items, total_str)
        updates["price_check_warning"] = dyn_bool(pc["warning"])
        updates["price_check_message"] = dyn_s(pc["message"])

        if LINE_ITEMS_TABLE:
            created_at = item.get("created_at", {}).get("S", "")
            try:
                _replace_line_items(job_id, user_id, item, created_at, new_items)
            except Exception as exc:
                print(f"ERROR _replace_line_items job={job_id}: {exc}")
                return make_response(500, {"error": "Failed to update line items"})

    update_job(dynamodb, DYNAMODB_TABLE, job_id, updates)

    refreshed = dynamodb.get_item(
        TableName=DYNAMODB_TABLE,
        Key={"job_id": dyn_s(job_id)},
    )
    return make_response(200, format_receipt(refreshed["Item"]))


def _recheck_prices(items: list, total_str: str) -> dict:
    return check_price_sum(items, total_str)


def _replace_line_items(job_id: str, user_id: str, job_record: dict, created_at: str, new_items: list) -> None:
    """Delete all existing line_items for this job then insert the new list."""
    # Delete existing rows
    if created_at:
        prefix = f"{created_at}#{job_id}#"
        resp = dynamodb.query(
            TableName=LINE_ITEMS_TABLE,
            KeyConditionExpression="#uid = :uid AND begins_with(#sk, :prefix)",
            ExpressionAttributeNames={"#uid": "user_id", "#sk": "item_sk"},
            ExpressionAttributeValues={
                ":uid": dyn_s(user_id),
                ":prefix": dyn_s(prefix),
            },
            ProjectionExpression="#uid, #sk",
        )
        keys = [{"user_id": it["user_id"], "item_sk": it["item_sk"]} for it in resp.get("Items", [])]
        for i in range(0, len(keys), 25):
            dynamodb.batch_write_item(
                RequestItems={
                    LINE_ITEMS_TABLE: [{"DeleteRequest": {"Key": k}} for k in keys[i:i + 25]]
                }
            )

    # Read context fields from the job record
    ctx = LineItemContext(
        job_id=job_id,
        user_id=user_id,
        user_email=job_record.get("email",          {}).get("S", ""),
        created_at=created_at,
        vendor=job_record.get("vendor",         {}).get("S", ""),
        receipt_date=job_record.get("receipt_date",   {}).get("S", ""),
        store_category=job_record.get("store_category", {}).get("S", "other"),
        expires_at=int(job_record.get("expires_at", {}).get("N", "0")),
    )

    write_line_items(dynamodb, LINE_ITEMS_TABLE, ctx, new_items)



def format_receipt(item: dict) -> dict:
    items_raw = item.get("items", {}).get("S", "[]")
    try:
        line_items = json.loads(items_raw)
    except (json.JSONDecodeError, TypeError):
        line_items = []

    job_id = item["job_id"]["S"]

    def presign(key, filename):
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": UPLOADS_BUCKET, "Key": key,
                    "ResponseContentDisposition": f"attachment; filename={filename}"},
            ExpiresIn=3600,
        )

    debug_url = None
    debug_key = item.get("debug_s3_key", {}).get("S")
    if debug_key:
        debug_url = presign(debug_key, f"claude_{job_id}.json")

    textract_debug_url = None
    textract_debug_key = item.get("textract_debug_s3_key", {}).get("S")
    if textract_debug_key:
        textract_debug_url = presign(textract_debug_key, f"textract_{job_id}.json")

    cropped_image_url = None
    cropped_key = item.get("cropped_s3_key", {}).get("S")
    if cropped_key:
        cropped_image_url = presign(cropped_key, f"cropped_{job_id}.jpg")

    price_check_warning = item.get("price_check_warning", {}).get("BOOL", False)
    price_check_message = item.get("price_check_message", {}).get("S")

    return {
        "jobId": job_id,
        "status": item.get("status", {}).get("S", "UNKNOWN"),
        "storeCategory": item.get("store_category", {}).get("S"),
        "vendor": item.get("vendor", {}).get("S"),
        "receiptDate": item.get("receipt_date", {}).get("S"),
        "total": item.get("total", {}).get("S"),
        "items": line_items,
        "priceCheckWarning": price_check_warning,
        "priceCheckMessage": price_check_message,
        "debugUrl": debug_url,
        "textractDebugUrl": textract_debug_url,
        "croppedImageUrl": cropped_image_url,
        "createdAt": item.get("created_at", {}).get("S"),
        "updatedAt": item.get("updated_at", {}).get("S"),
    }


def get_user_id(event) -> tuple[str, str]:
    """Validate the Cognito JWT and return (sub, email)."""
    from jose import jwt

    headers = event.get("headers") or {}
    # HTTP/2 canonicalises headers to lowercase — check both forms
    auth_header = headers.get("Authorization") or headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing Bearer token")
    token = auth_header[7:]

    jwks = get_jwks()
    claims = jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        audience=COGNITO_APP_CLIENT_ID,
        issuer=f"https://cognito-idp.{PRIMARY_REGION}.amazonaws.com/{COGNITO_POOL_ID}",
        options={"verify_at_hash": False},
    )
    if claims.get("token_use") != "id":
        raise ValueError("Wrong token_use")
    return claims["sub"], claims.get("email", "")


def make_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


