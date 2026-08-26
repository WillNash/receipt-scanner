import json
import os
import re
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from jose import jwt
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
PRESIGNED_PUT_TTL_SECONDS = 300
PRESIGNED_GET_TTL_SECONDS = 3600
JOB_TTL_DAYS = 7
RECEIPTS_PAGE_SIZE = 20

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


@dataclass
class JobRecord:
    job_id: str
    user_id: str
    email: str
    status: str
    created_at: str
    updated_at: str | None
    vendor: str | None
    receipt_date: str | None
    total: str | None
    items_json: str
    store_category: str | None
    price_check_warning: bool
    price_check_message: str | None
    debug_s3_key: str | None
    textract_debug_s3_key: str | None
    cropped_s3_key: str | None
    image_hash: str | None
    expires_at: int
    s3_key: str | None

    @classmethod
    def from_dynamo(cls, item: dict) -> "JobRecord":
        return cls(
            job_id=item["job_id"]["S"],
            user_id=item.get("user_id", {}).get("S", ""),
            email=item.get("email", {}).get("S", ""),
            status=item.get("status", {}).get("S", "UNKNOWN"),
            created_at=item.get("created_at", {}).get("S", ""),
            updated_at=item.get("updated_at", {}).get("S"),
            vendor=item.get("vendor", {}).get("S"),
            receipt_date=item.get("receipt_date", {}).get("S"),
            total=item.get("total", {}).get("S"),
            items_json=item.get("items", {}).get("S", "[]"),
            store_category=item.get("store_category", {}).get("S"),
            price_check_warning=item.get("price_check_warning", {}).get("BOOL", False),
            price_check_message=item.get("price_check_message", {}).get("S"),
            debug_s3_key=item.get("debug_s3_key", {}).get("S"),
            textract_debug_s3_key=item.get("textract_debug_s3_key", {}).get("S"),
            cropped_s3_key=item.get("cropped_s3_key", {}).get("S"),
            image_hash=item.get("image_hash", {}).get("S"),
            expires_at=int(item.get("expires_at", {}).get("N", "0")),
            s3_key=item.get("s3_key", {}).get("S"),
        )


class _HttpError(Exception):
    """Raised by helpers to short-circuit a handler with an HTTP error response."""
    def __init__(self, status: int, body: dict):
        self.response = make_response(status, body)


_JWKS_TTL_SECONDS = 3600  # re-fetch at most once per hour


class _JwksCache:
    def __init__(self):
        self._data: dict | None = None
        self._fetched_at: datetime | None = None

    def get(self) -> dict:
        now = datetime.now(timezone.utc)
        if self._data is None or (
            self._fetched_at is not None
            and (now - self._fetched_at).total_seconds() > _JWKS_TTL_SECONDS
        ):
            url = (
                f"https://cognito-idp.{PRIMARY_REGION}.amazonaws.com"
                f"/{COGNITO_POOL_ID}/.well-known/jwks.json"
            )
            with urllib.request.urlopen(url) as resp:
                self._data = json.loads(resp.read())
            self._fetched_at = now
        return self._data


# Module-level JWKS cache — refreshed at most once per hour so key rotation
# is picked up without requiring a cold start.
_jwks_cache = _JwksCache()


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

    try:
        return _route(method, path, user_id, user_email, event)
    except _HttpError as exc:
        return exc.response


def _check_and_increment_rate_limits(user_id: str) -> None:
    """Atomically increment both rate-limit counters only if both are under their limit.

    Raises _HttpError(429) if either limit is exceeded.
    Using TransactWriteItems ensures the daily counter is never burned by a global reject.
    """
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    expiry = int((now + timedelta(days=2)).timestamp())
    _update = lambda key, limit: {  # noqa: E731
        "Update": {
            "TableName": DYNAMODB_TABLE,
            "Key": {"job_id": dyn_s(key)},
            "UpdateExpression": "ADD upload_count :one SET expires_at = if_not_exists(expires_at, :exp)",
            "ConditionExpression": "attribute_not_exists(upload_count) OR upload_count < :limit",
            "ExpressionAttributeValues": {
                ":one": dyn_n(1), ":exp": dyn_n(expiry), ":limit": dyn_n(limit),
            },
        }
    }
    try:
        dynamodb.transact_write_items(TransactItems=[
            _update(f"COUNT#{user_id}#{today}", DAILY_UPLOAD_LIMIT),
            _update(f"COUNT#GLOBAL#{today}", GLOBAL_UPLOAD_LIMIT),
        ])
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "TransactionCanceledException":
            raise
        reasons = exc.response.get("CancellationReasons", [{}, {}])
        if reasons[1].get("Code") == "ConditionalCheckFailed":
            raise _HttpError(429, {
                "error": "Today's global upload limit has been reached. Try again tomorrow.",
                "limitType": "global",
            })
        raise _HttpError(429, {
            "error": f"You've reached your daily limit of {DAILY_UPLOAD_LIMIT} uploads. Try again tomorrow.",
            "limitType": "user",
        })


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

    _check_and_increment_rate_limits(user_id)

    ext = VALID_CONTENT_TYPES[content_type]
    job_id = str(uuid.uuid4())
    s3_key = f"uploads/{user_id}/{job_id}.{ext}"
    now = now_iso()
    expiry = int((datetime.now(timezone.utc) + timedelta(days=JOB_TTL_DAYS)).timestamp())

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
        ExpiresIn=PRESIGNED_PUT_TTL_SECONDS,
    )
    return make_response(200, {"jobId": job_id, "uploadUrl": upload_url, "s3Key": s3_key})


def handle_list_receipts(user_id: str):
    # DynamoDB applies Limit before FilterExpression, so paginate until we have
    # RECEIPTS_PAGE_SIZE COMPLETE results or the GSI is exhausted.
    receipts = []
    last_key = None
    while len(receipts) < RECEIPTS_PAGE_SIZE:
        kwargs = {
            "TableName": DYNAMODB_TABLE,
            "IndexName": "user-jobs-index",
            "KeyConditionExpression": "#uid = :uid",
            "FilterExpression": "#st = :complete",
            "ExpressionAttributeNames": {"#uid": "user_id", "#st": "status"},
            "ExpressionAttributeValues": {":uid": dyn_s(user_id), ":complete": dyn_s("COMPLETE")},
            "ScanIndexForward": False,
            "Limit": RECEIPTS_PAGE_SIZE,
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        result = dynamodb.query(**kwargs)
        for item in result.get("Items", []):
            receipts.append(format_receipt(JobRecord.from_dynamo(item), include_urls=False))
            if len(receipts) >= RECEIPTS_PAGE_SIZE:
                break
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            break
    return make_response(200, {"receipts": receipts})


def _fetch_job_item(job_id: str | None, user_id: str) -> dict:
    """Fetch the raw DynamoDB job item and enforce ownership.

    Raises _HttpError on validation failure, not-found, or ownership mismatch.
    """
    if not job_id:
        raise _HttpError(400, {"error": "jobId required"})
    result = dynamodb.get_item(
        TableName=DYNAMODB_TABLE,
        Key={"job_id": dyn_s(job_id)},
    )
    item = result.get("Item")
    if not item:
        raise _HttpError(404, {"error": "Job not found"})
    if item.get("user_id", {}).get("S") != user_id:
        raise _HttpError(403, {"error": "Forbidden"})
    return item


def handle_get_job(job_id: str | None, user_id: str):
    item = _fetch_job_item(job_id, user_id)
    job = JobRecord.from_dynamo(item)
    return make_response(200, format_receipt(job))


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
    job = JobRecord.from_dynamo(item)

    image_hash = job.image_hash
    created_at = job.created_at

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

    # Delete all S3 objects for this job (best-effort — non-fatal)
    s3_keys = [k for k in [job.s3_key, job.debug_s3_key, job.textract_debug_s3_key, job.cropped_s3_key] if k]
    if s3_keys:
        try:
            s3.delete_objects(
                Bucket=UPLOADS_BUCKET,
                Delete={"Objects": [{"Key": k} for k in s3_keys], "Quiet": True},
            )
        except Exception as exc:
            print(f"ERROR deleting S3 objects for job {job_id}: {exc} — objects may be orphaned")

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
    job = JobRecord.from_dynamo(item)

    updates = {"updated_at": dyn_s(now_iso())}

    if "vendor" in body:
        updates["vendor"] = dyn_s(str(body["vendor"]))

    if "receiptDate" in body:
        updates["receipt_date"] = dyn_s(str(body["receiptDate"]))

    new_items = body.get("items")  # full replacement list
    if new_items is not None:
        updates["items"] = dyn_s(json.dumps(new_items))

        # Recalculate price check so the warning clears once items are corrected
        total_str = job.total or ""
        pc = check_price_sum(new_items, total_str)
        updates["price_check_warning"] = dyn_bool(pc["warning"])
        updates["price_check_message"] = dyn_s(pc["message"])

        if LINE_ITEMS_TABLE:
            created_at = job.created_at
            try:
                _replace_line_items(job_id, user_id, job, created_at, new_items)
            except Exception as exc:
                print(f"ERROR _replace_line_items job={job_id}: {exc}")
                return make_response(500, {"error": "Failed to update line items"})

    update_job(dynamodb, DYNAMODB_TABLE, job_id, updates)

    refreshed = dynamodb.get_item(
        TableName=DYNAMODB_TABLE,
        Key={"job_id": dyn_s(job_id)},
    )
    return make_response(200, format_receipt(JobRecord.from_dynamo(refreshed["Item"])))


def _replace_line_items(job_id: str, user_id: str, job: JobRecord, created_at: str, new_items: list) -> None:
    """Delete all existing line_items for this job then insert the new list."""
    # Delete existing rows
    if created_at:
        _delete_line_items_for_job(job_id, user_id, created_at)

    # Read context fields from the job record
    ctx = LineItemContext(
        job_id=job_id,
        user_id=user_id,
        user_email=job.email,
        created_at=created_at,
        vendor=job.vendor or "",
        receipt_date=job.receipt_date or "",
        store_category=job.store_category or "other",
        expires_at=job.expires_at,
    )

    write_line_items(dynamodb, LINE_ITEMS_TABLE, ctx, new_items)



def format_receipt(job: JobRecord, include_urls: bool = True) -> dict:
    try:
        line_items = json.loads(job.items_json)
    except (json.JSONDecodeError, TypeError):
        line_items = []

    debug_url = None
    textract_debug_url = None
    cropped_image_url = None

    if include_urls:
        def presign(key, filename):
            return s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": UPLOADS_BUCKET, "Key": key,
                        "ResponseContentDisposition": f"attachment; filename={filename}"},
                ExpiresIn=PRESIGNED_GET_TTL_SECONDS,
            )
        if job.debug_s3_key:
            debug_url = presign(job.debug_s3_key, f"claude_{job.job_id}.json")
        if job.textract_debug_s3_key:
            textract_debug_url = presign(job.textract_debug_s3_key, f"textract_{job.job_id}.json")
        if job.cropped_s3_key:
            cropped_image_url = presign(job.cropped_s3_key, f"cropped_{job.job_id}.jpg")

    return {
        "jobId": job.job_id,
        "status": job.status,
        "storeCategory": job.store_category,
        "vendor": job.vendor,
        "receiptDate": job.receipt_date,
        "total": job.total,
        "items": line_items,
        "priceCheckWarning": job.price_check_warning,
        "priceCheckMessage": job.price_check_message,
        "debugUrl": debug_url,
        "textractDebugUrl": textract_debug_url,
        "croppedImageUrl": cropped_image_url,
        "hasCroppedImage": job.cropped_s3_key is not None,
        "createdAt": job.created_at,
        "updatedAt": job.updated_at,
    }


def get_user_id(event) -> tuple[str, str]:
    """Validate the Cognito JWT and return (sub, email)."""
    headers = event.get("headers") or {}
    # HTTP/2 canonicalises headers to lowercase — check both forms
    auth_header = headers.get("Authorization") or headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing Bearer token")
    token = auth_header[7:]

    jwks = _jwks_cache.get()
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


