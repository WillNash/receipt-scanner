import os

from constants import VALID_ITEM_CATEGORIES
from pricing import to_float

VALID_STORE_CATEGORIES = {
    "grocery", "petrol", "pharmacy", "restaurant", "fast_food", "cafe",
    "hardware", "department_store", "clothing", "electronics",
    "health_beauty", "liquor", "other",
}

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0"
)

def _build_receipt_tool() -> dict:
    item_properties = {
        "description": {
            "type": "string",
            "description": (
                "Product name only. "
                "Do not include quantity, unit price, or totals in this field."
            ),
        },
        "quantity": {
            "type": "string",
            "description": (
                "Pure numeric count or measured weight — no units. "
                "quantity × unit_price must equal price. "
                "Examples: '2' for two units, '1.741' for 1.741 kg of a weight-priced item. "
                "For a fixed-price item like 'PAMS CHEESE BLOCK 1KG' bought once: quantity is '1'."
            ),
        },
        "package_size": {
            "type": "string",
            "description": (
                "Size or weight label from the product name for fixed-price items "
                "(e.g. '1KG', '500G', '2L', '750ML', '400G'). "
                "Set only when the weight/volume is part of the product's brand name, "
                "not for weight-priced items sold by the kg/g where quantity carries the weight."
            ),
        },
        "unit_price": {
            "type": "string",
            "description": (
                "Price per single unit without currency symbol. "
                "If the receipt shows '2 @ $1.79', unit_price is '1.79'."
            ),
        },
        "line_total": {
            "type": "string",
            "description": (
                "The amount printed at the right edge of this line item, without currency symbol. "
                "Transcribe it exactly — do not add or subtract the discount. "
                "For '2 @ $1.79  $3.58', line_total is '3.58'. "
                "For '1.741 Kg @ $1.49/Kg  $2.59', line_total is '2.59'."
            ),
        },
        "discount": {
            "type": "string",
            "description": (
                "Discount as a negative number without currency symbol. "
                "If the receipt shows a discount line of '-$0.58' for this item, "
                "discount is '-0.58'. Merge it into this item — do not create a separate item for it."
            ),
        },
        "item_category": {
            "type": "string",
            "description": (
                "Product category. Pick exactly one: "
                "fruit_veg | dairy | meat_seafood | bakery | deli | frozen | "
                "pantry | snacks | confectionery | beverages | alcohol | "
                "household | personal_care | pet | tobacco | non_food | other. "
                "Use 'other' for generic descriptions like 'Value Pack' or bare SKU codes."
            ),
        },
        "nova_group": {
            "type": "integer",
            "description": (
                "NOVA food processing group: "
                "1=unprocessed/minimally processed (fresh apple, plain chicken, brown rice), "
                "2=culinary ingredient (olive oil, butter, sugar, plain flour), "
                "3=processed food (canned tuna, block cheese, sourdough loaf, canned tomatoes), "
                "4=ultra-processed (chips, instant noodles, diet cola, flavoured yoghurt, breakfast bars). "
                "Use null for non-food items."
            ),
        },
    }

    receipt_properties = {
        "store_category": {
            "type": "string",
            "description": (
                "Type of store. Pick exactly one: "
                "grocery | petrol | pharmacy | restaurant | fast_food | cafe | "
                "hardware | department_store | clothing | electronics | "
                "health_beauty | liquor | other"
            ),
        },
        "vendor": {
            "type": "string",
            "description": "Store or vendor name",
        },
        "receipt_date": {
            "type": "string",
            "description": "Date of purchase, normalised to YYYY-MM-DD format (e.g. '2026-08-28'). Parse whatever date format is printed on the receipt and return it in this format.",
        },
        "total": {
            "type": "string",
            "description": "Final total amount paid, without currency symbol, e.g. '42.50'",
        },
        "items": {
            "type": "array",
            "description": (
                "Every purchased line item. Exclude summary lines "
                "such as subtotal, GST, EFTPOS, cash, and change."
            ),
            "items": {
                "type": "object",
                "properties": item_properties,
                "required": ["description"],
            },
        },
    }

    return {
        "toolSpec": {
            "name": "extract_receipt",
            "description": "Extract and classify structured data from a receipt.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": receipt_properties,
                    "required": ["store_category", "vendor", "receipt_date", "total", "items"],
                }
            },
        }
    }


# Tool definition — forces structured JSON output from the model
RECEIPT_TOOL = _build_receipt_tool()

bedrock = None  # injected by handler via set_bedrock_client()


def set_bedrock_client(client) -> None:
    """Inject the shared Bedrock client from handler."""
    global bedrock
    bedrock = client


def _run_bedrock(receipt_text: str) -> tuple[dict, dict]:
    """Call Bedrock with the OCR text and return (extracted, usage)."""
    response = bedrock.converse(
        modelId=BEDROCK_MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": (
                            "Here is text extracted by OCR from a receipt, in reading order "
                            "(items on the same row are separated by two spaces):\n\n"
                            f"{receipt_text}\n\n"
                            "Extract all structured data from this receipt and classify it. "
                            "Include every purchased product as a line item. "
                            "Exclude summary lines such as subtotal, GST, EFTPOS, cash, and change. "
                            "Return all prices and totals without currency symbols. "
                            "quantity is always a bare number — no units. "
                            "quantity × unit_price must equal price. "
                            "For multi-unit lines like 'ITEM NAME' followed by '2 @  $1.79  $3.58', "
                            "set quantity to '2', unit_price to '1.79', line_total to '3.58'. "
                            "For weight-priced lines like '1.741 Kg @  $1.49/Kg  $2.59', "
                            "set quantity to '1.741', line_total to '2.59' (the right-edge total), "
                            "and unit_price to '1.49'. "
                            "The number at the right edge of the line is line_total — transcribe it exactly. "
                            "Do not compute line_total; do not add or subtract the discount from it. "
                            "For fixed-price items whose product name includes a weight/size (e.g. 'PAMS CHEESE BLOCK 1KG'), "
                            "set quantity to '1' (or the count bought), unit_price to the item price, "
                            "line_total to the same as unit_price, "
                            "and package_size to the size label from the product name (e.g. '1KG'). "
                            "A line that contains only a number, an '@' or similar separator, and a price "
                            "(e.g. '3 @ $0.89', '2 @ $1.79 $3.58') is a quantity/unit-price breakdown "
                            "for the item on the line immediately above — update that item's quantity, "
                            "unit_price, and line_total; do NOT create a new item for this line. "
                            "OCR often misreads '@' as '!', 'J', 'e', or similar characters — "
                            "treat any line matching the pattern <number> <symbol> <price> as a breakdown line. "
                            "Do not create items for lines that consist only of numbers, symbols, or illegible text "
                            "with no recognizable product name — either merge them into the preceding item as a "
                            "quantity breakdown or skip them entirely. Never invent a product name. "
                            "If a discount appears as a product name repeated with a negative amount (e.g. 'BROCCOLI  -$0.58'), "
                            "merge it into the preceding item for that product: set discount to '-0.58' (negative). "
                            "Do not alter line_total when merging a discount. "
                            "Do not create a separate line item for discounts. "
                            "Use an empty string for any field you cannot determine.\n\n"
                            "Classification rules:\n"
                            "- Generic descriptions ('Value Pack', 'Bulk Buy', 'Misc', bare SKU codes) "
                            "-> item_category: 'other', nova_group: null\n"
                            "- Non-food items always have nova_group: null\n"
                            "- Receipt descriptions are often abbreviated; use context clues\n\n"
                            "Classification examples:\n"
                            "  'ANCHOR BLUE MILK 2L'      -> dairy,         nova_group: 1\n"
                            "  'BROCCOLI'                 -> fruit_veg,     nova_group: 1\n"
                            "  'MEADOWFRESH CHSE 500G'    -> dairy,         nova_group: 3\n"
                            "  'HOMEBRAND OLIVE OIL 750ML'-> pantry,        nova_group: 2\n"
                            "  'WATTIES TOMATOES 400G'    -> pantry,        nova_group: 3\n"
                            "  'PRINGLES ORIG 165G'       -> snacks,        nova_group: 4\n"
                            "  'COCA COLA NO SUGAR 1.5L'  -> beverages,     nova_group: 4\n"
                            "  'SPEIGHTS GOLD 12PK'       -> alcohol,       nova_group: null\n"
                            "  'FANCY FEAST CAT FOOD'     -> pet,           nova_group: null\n"
                            "  'GLAD WRAP 30M'            -> household,     nova_group: null\n"
                            "  'VALUE PACK'               -> other,         nova_group: null"
                        )
                    }
                ],
            }
        ],
        toolConfig={
            "tools": [RECEIPT_TOOL],
            "toolChoice": {"tool": {"name": "extract_receipt"}},
        },
    )

    extracted = {}
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if block.get("toolUse", {}).get("name") == "extract_receipt":
            extracted = block["toolUse"]["input"]
            break

    usage = response.get("usage", {})
    print(
        f"BEDROCK_USAGE model={BEDROCK_MODEL_ID} "
        f"input={usage.get('inputTokens')} output={usage.get('outputTokens')}"
    )
    return extracted, usage


def _validate_classification(extracted: dict) -> None:
    """Clamp any out-of-vocabulary classification values to safe defaults in-place."""
    if extracted.get("store_category") not in VALID_STORE_CATEGORIES:
        extracted["store_category"] = "other"
    for item in extracted.get("items", []):
        if item.get("item_category") not in VALID_ITEM_CATEGORIES:
            item["item_category"] = "other"
        nova = item.get("nova_group")
        if nova not in (1, 2, 3, 4, None):
            item["nova_group"] = None


def _fix_weighted_item_prices(items: list) -> int:
    """For weight-priced items (non-integer quantity), trust line_total over unit_price.

    If weight × unit_price ≠ line_total, recalculate unit_price = line_total / weight.
    Returns the number of items corrected.
    """
    corrections = 0
    for item in items:
        qty = to_float(item.get("quantity"))
        unit_price = to_float(item.get("unit_price"))
        line_total = to_float(item.get("line_total"))
        if qty is None or unit_price is None or line_total is None:
            continue
        if qty == 0 or qty % 1 == 0:
            continue
        expected = round(qty * unit_price, 2)
        if abs(expected - line_total) >= 0.01:
            corrected = round(line_total / qty, 2)
            print(
                f"WEIGHTED_PRICE_FIX qty={qty} unit_price={unit_price} line_total={line_total} "
                f"expected={expected} corrected_unit_price={corrected}"
            )
            item["unit_price"] = str(corrected)
            corrections += 1
    return corrections


def _compute_net_prices(items: list) -> None:
    """Set price = line_total + discount for every item, in-place.

    price is the net amount the customer pays. line_total is what is printed on
    the receipt before any discount. Both are stored; price is used for totalling.
    """
    for item in items:
        line_total = to_float(item.get("line_total"))
        if line_total is None:
            continue
        discount = to_float(item.get("discount")) or 0.0
        item["price"] = str(round(line_total + discount, 2))
