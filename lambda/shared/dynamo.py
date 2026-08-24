def dyn_s(v: str) -> dict:
    return {"S": v}


def dyn_n(v) -> dict:
    return {"N": str(v)}


def dyn_bool(v: bool) -> dict:
    return {"BOOL": bool(v)}


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
