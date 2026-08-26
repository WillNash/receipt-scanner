from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dyn_s(v: str) -> dict:
    return {"S": v}


def dyn_n(v) -> dict:
    return {"N": str(v)}


def dyn_bool(v: bool) -> dict:
    return {"BOOL": bool(v)}


def get_job(dynamodb, table_name: str, job_id: str) -> dict | None:
    resp = dynamodb.get_item(
        TableName=table_name,
        Key={"job_id": {"S": job_id}},
    )
    item = resp.get("Item")
    if not item:
        return None
    return {
        "job_id":     item.get("job_id",      {}).get("S"),
        "user_id":    item.get("user_id",     {}).get("S"),
        "email":      item.get("email",       {}).get("S", ""),
        "status":     item.get("status",      {}).get("S"),
        "created_at": item.get("created_at",  {}).get("S"),
        "s3_key":     item.get("s3_key",      {}).get("S"),
        "image_hash": item.get("image_hash",  {}).get("S"),
    }


def update_job(dynamodb, table_name: str, job_id: str, updates: dict) -> None:
    set_parts = []
    attr_names = {}
    attr_values = {}
    for i, (key, val) in enumerate(updates.items()):
        name_alias = f"#k{i}"
        val_alias = f":v{i}"
        set_parts.append(f"{name_alias} = {val_alias}")
        attr_names[name_alias] = key
        attr_values[val_alias] = val
    dynamodb.update_item(
        TableName=table_name,
        Key={"job_id": {"S": job_id}},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
    )
