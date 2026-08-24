def to_float(val) -> float | None:
    try:
        cleaned = str(val).replace(",", "").replace("$", "").strip()
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def to_n(val) -> dict | None:
    try:
        cleaned = str(val).replace(",", "").replace("$", "").strip()
        return {"N": str(float(cleaned))} if cleaned else None
    except (ValueError, TypeError):
        return None


def check_price_sum(items: list, total_str: str) -> dict:
    """Compare sum of item prices to the receipt total.

    Returns a dict with keys: warning (bool), message (str),
    items_sum (float), difference (float | None),
    unparseable_indices (list[int]).
    """
    total = to_float(total_str)
    result: dict = {
        "warning": False,
        "message": "",
        "items_sum": 0.0,
        "difference": None,
        "unparseable_indices": [],
    }

    if total is None:
        result["message"] = "total could not be parsed"
        return result

    item_prices = []
    for i, item in enumerate(items):
        p = to_float(item.get("price"))
        if p is not None:
            item_prices.append(p)
        elif item.get("price"):
            result["unparseable_indices"].append(i)

    items_sum = round(sum(item_prices), 2)
    result["items_sum"] = items_sum
    result["difference"] = round(items_sum - total, 2)

    diff = abs(items_sum - total)
    if diff >= 0.01:
        result["warning"] = True
        direction = "over" if items_sum > total else "under"
        result["message"] = (
            f"item prices sum to {items_sum:.2f} but receipt total is {total:.2f} "
            f"({direction} by {diff:.2f})"
        )
    else:
        result["message"] = f"ok (difference {diff:.2f})"

    return result
