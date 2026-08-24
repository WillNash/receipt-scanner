from dataclasses import dataclass

from constants import VALID_ITEM_CATEGORIES
from pricing import to_n


@dataclass
class LineItemContext:
    job_id: str
    user_id: str
    user_email: str
    created_at: str
    vendor: str
    receipt_date: str
    store_category: str
    expires_at: int


def write_line_items(
    dynamodb,
    table_name: str,
    ctx: LineItemContext,
    items: list,
) -> None:
    """Write per-line-item records to DynamoDB for a completed or edited receipt.

    Skips items with no description. Clamps item_category to 'other' when the
    value is absent or not in VALID_ITEM_CATEGORIES.
    """
    for i, item in enumerate(items):
        description = str(item.get("description") or "").strip()
        if not description:
            continue

        item_sk = f"{ctx.created_at}#{ctx.job_id}#{i:03d}"
        desc_created = f"{description}#{ctx.created_at}"

        record: dict = {
            "user_id":        {"S": ctx.user_id},
            "item_sk":        {"S": item_sk},
            "job_id":         {"S": ctx.job_id},
            "description":    {"S": description},
            "desc_created":   {"S": desc_created},
            "email":          {"S": ctx.user_email},
            "vendor":         {"S": ctx.vendor},
            "receipt_date":   {"S": ctx.receipt_date},
            "store_category": {"S": ctx.store_category},
            "created_at":     {"S": ctx.created_at},
            "expires_at":     {"N": str(ctx.expires_at)},
        }

        for field in ("quantity", "unit_price", "price", "discount"):
            n = to_n(item.get(field))
            if n:
                record[field] = n

        pkg_size = str(item.get("package_size") or "").strip()
        if pkg_size:
            record["package_size"] = {"S": pkg_size}

        item_category = item.get("item_category", "other")
        if item_category not in VALID_ITEM_CATEGORIES:
            item_category = "other"
        record["item_category"] = {"S": item_category}

        nova = item.get("nova_group")
        if isinstance(nova, int) and nova in (1, 2, 3, 4):
            record["nova_group"] = {"N": str(nova)}

        dynamodb.put_item(TableName=table_name, Item=record)
        print(f"LINE_ITEM_WRITTEN {ctx.job_id}#{i:03d} {description!r} [{item_category}]")
