import json
import os
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config

DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]
LINE_ITEMS_TABLE = os.environ.get("LINE_ITEMS_TABLE", "")
IMAGE_HASHES_TABLE = os.environ.get("IMAGE_HASHES_TABLE", "")
UPLOADS_BUCKET = os.environ["UPLOADS_BUCKET"]
COGNITO_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
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
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
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


def lambda_handler(event, context):
    method = event.get("httpMethod", "")
    path = event.get("path", "")

    if method == "OPTIONS":
        return make_response(200, {})

    try:
        user_id, user_email = get_user_id(event)
    except Exception as exc:
        return make_response(401, {"error": f"Unauthorized: {exc}"})

    if method == "POST" and path.endswith("/upload-url"):
        return handle_upload_url(event, user_id, user_email)
    elif method == "GET" and path.endswith("/receipts"):
        return handle_list_receipts(user_id)
    elif method == "GET" and "/jobs/" in path:
        job_id = (event.get("pathParameters") or {}).get("jobId")
        return handle_get_job(job_id, user_id)
    elif method == "DELETE" and "/receipts/" in path:
        job_id = (event.get("pathParameters") or {}).get("jobId")
        return handle_delete_receipt(job_id, user_id)
    else:
        return make_response(404, {"error": "Not found"})


def check_and_increment_global_count() -> bool:
    resp = dynamodb.update_item(
        TableName=DYNAMODB_TABLE,
        Key={"job_id": {"S": "COUNT#GLOBAL"}},
        UpdateExpression="ADD upload_count :one",
        ExpressionAttributeValues={":one": {"N": "1"}},
        ReturnValues="UPDATED_NEW",
    )
    count = int(resp["Attributes"]["upload_count"]["N"])
    return count <= GLOBAL_UPLOAD_LIMIT


def check_and_increment_daily_count(user_id: str) -> bool:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    expiry = int((datetime.now(timezone.utc) + timedelta(days=2)).timestamp())
    resp = dynamodb.update_item(
        TableName=DYNAMODB_TABLE,
        Key={"job_id": {"S": f"COUNT#{user_id}#{today}"}},
        UpdateExpression="ADD upload_count :one SET expires_at = if_not_exists(expires_at, :exp)",
        ExpressionAttributeValues={
            ":one": {"N": "1"},
            ":exp": {"N": str(expiry)},
        },
        ReturnValues="UPDATED_NEW",
    )
    count = int(resp["Attributes"]["upload_count"]["N"])
    return count <= DAILY_UPLOAD_LIMIT


def handle_upload_url(event, user_id: str, user_email: str):
    body = json.loads(event.get("body") or "{}")
    content_type = body.get("contentType", "image/jpeg")

    if content_type not in VALID_CONTENT_TYPES:
        return make_response(400, {"error": f"Unsupported content type: {content_type}"})

    if not check_and_increment_global_count():
        return make_response(429, {"error": "Global upload limit reached."})

    if not check_and_increment_daily_count(user_id):
        return make_response(429, {"error": "Daily upload limit reached. Try again tomorrow."})

    ext = VALID_CONTENT_TYPES[content_type]
    job_id = str(uuid.uuid4())
    s3_key = f"uploads/{user_id}/{job_id}.{ext}"
    now = now_iso()
    expiry = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())

    dynamodb.put_item(
        TableName=DYNAMODB_TABLE,
        Item={
            "job_id": {"S": job_id},
            "user_id": {"S": user_id},
            "email": {"S": user_email},
            "s3_key": {"S": s3_key},
            "status": {"S": "PENDING"},
            "created_at": {"S": now},
            "updated_at": {"S": now},
            "expires_at": {"N": str(expiry)},
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
        ExpressionAttributeValues={":uid": {"S": user_id}},
        ScanIndexForward=False,
        Limit=20,
    )
    receipts = [format_receipt(item) for item in result.get("Items", [])]
    return make_response(200, {"receipts": receipts})


def handle_get_job(job_id: str | None, user_id: str):
    if not job_id:
        return make_response(400, {"error": "jobId required"})

    result = dynamodb.get_item(
        TableName=DYNAMODB_TABLE,
        Key={"job_id": {"S": job_id}},
    )
    item = result.get("Item")
    if not item:
        return make_response(404, {"error": "Job not found"})

    if item.get("user_id", {}).get("S") != user_id:
        return make_response(403, {"error": "Forbidden"})

    return make_response(200, format_receipt(item))


def handle_delete_receipt(job_id: str | None, user_id: str):
    if not job_id:
        return make_response(400, {"error": "jobId required"})

    result = dynamodb.get_item(
        TableName=DYNAMODB_TABLE,
        Key={"job_id": {"S": job_id}},
    )
    item = result.get("Item")
    if not item:
        return make_response(404, {"error": "Job not found"})
    if item.get("user_id", {}).get("S") != user_id:
        return make_response(403, {"error": "Forbidden"})

    image_hash = item.get("image_hash", {}).get("S")
    created_at = item.get("created_at", {}).get("S", "")

    # Delete the job record
    dynamodb.delete_item(
        TableName=DYNAMODB_TABLE,
        Key={"job_id": {"S": job_id}},
    )

    # Delete the dedup hash so the image can be re-uploaded later
    if image_hash and IMAGE_HASHES_TABLE:
        dynamodb.delete_item(
            TableName=IMAGE_HASHES_TABLE,
            Key={"user_id": {"S": user_id}, "image_hash": {"S": image_hash}},
        )

    # Delete all line items for this job
    if LINE_ITEMS_TABLE and created_at:
        prefix = f"{created_at}#{job_id}#"
        resp = dynamodb.query(
            TableName=LINE_ITEMS_TABLE,
            KeyConditionExpression="#uid = :uid AND begins_with(#sk, :prefix)",
            ExpressionAttributeNames={"#uid": "user_id", "#sk": "item_sk"},
            ExpressionAttributeValues={
                ":uid": {"S": user_id},
                ":prefix": {"S": prefix},
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

    return make_response(200, {"deleted": True})


def format_receipt(item: dict) -> dict:
    items_raw = item.get("items", {}).get("S", "[]")
    try:
        line_items = json.loads(items_raw)
    except (json.JSONDecodeError, TypeError):
        line_items = []

    debug_url = None
    debug_key = item.get("debug_s3_key", {}).get("S")
    if debug_key:
        debug_url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": UPLOADS_BUCKET,
                "Key": debug_key,
                "ResponseContentDisposition": f"attachment; filename=textract_{item['job_id']['S']}.json",
            },
            ExpiresIn=3600,
        )

    return {
        "jobId": item["job_id"]["S"],
        "status": item.get("status", {}).get("S", "UNKNOWN"),
        "vendor": item.get("vendor", {}).get("S"),
        "receiptDate": item.get("receipt_date", {}).get("S"),
        "total": item.get("total", {}).get("S"),
        "items": line_items,
        "debugUrl": debug_url,
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
        options={"verify_aud": False, "verify_at_hash": False},
    )
    return claims["sub"], claims.get("email", "")


def make_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
