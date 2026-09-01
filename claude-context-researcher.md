# Research Findings — Haiku Store Matching via Bedrock

## Sources
- [Claude Haiku 4.5 - Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-haiku-4-5.html)
- [Invoke Anthropic Claude on Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-runtime_example_bedrock-runtime_InvokeModel_AnthropicClaude_section.html)
- [Best practices for querying DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/QueryAndScanGuidelines.html)
- [boto3 DynamoDB scan](https://docs.aws.amazon.com/boto3/latest/reference/services/dynamodb/table/scan.html)
- [Lambda execution environment lifecycle](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html)

---

## 1. Claude Haiku via Bedrock — Model IDs and Region Availability

| Model | Model ID | Status |
|---|---|---|
| Claude 3 Haiku | `anthropic.claude-3-haiku-20240307-v1:0` | Active, in-region ap-southeast-2 |
| Claude 3.5 Haiku | `anthropic.claude-3-5-haiku-20241022-v1:0` | Legacy, EOL June 2026 |
| Claude Haiku 4.5 | `au.anthropic.claude-haiku-4-5-20251001-v1:0` | Active, AU cross-region profile |

The existing processor already uses `au.anthropic.claude-haiku-4-5-20251001-v1:0` via the `BEDROCK_MODEL_ID` env var. The store matching call should use the same `BEDROCK_MODEL_ID` — no new model ID needed.

The existing processor uses `bedrock.converse()` with `toolConfig` to force structured JSON output. The store-matching call should follow the same pattern for consistency.

---

## 2. Fuzzy Store Name Matching — Prompt Design

Use `converse()` with a tool to force structured output. JSON with `null` for no-match is unambiguous.

**System prompt:**
```
You are a store name matcher. Given a raw OCR string from a receipt and a list of
known store names, identify the best match.

Rules:
- Ignore store branch numbers (e.g., '#47'), abbreviations, punctuation differences, and spacing.
- Match on the core brand name (e.g., 'PAK N SAVE' matches 'Pak'nSave').
- If no store in the list is a plausible match, return null for matched_name.
- Respond ONLY with the tool call. No explanation.
```

**Tool schema:**
```json
{
  "name": "match_store",
  "description": "Return the best-matching store name or null",
  "input_schema": {
    "type": "object",
    "properties": {
      "matched_name": {
        "type": ["string", "null"],
        "description": "Exact string from the candidates list, or null if no match"
      }
    },
    "required": ["matched_name"]
  }
}
```

**User message:**
```
OCR string: "PAK N SAVE #47"

Known store names:
- Pak'nSave Palmerston North
- New World Palmerston North

Return the tool call.
```

**Response parsing:** iterate `response["output"]["message"]["content"]` for a `toolUse` block, extract `input["matched_name"]`. Returns `None` (Python) if JSON null.

---

## 3. DynamoDB Scan — Full Table Read

For a small table (hundreds of items), full scan with no filter is correct. Always use the pagination loop even for small tables — DynamoDB can return a subset even under 1 MB.

Use `ProjectionExpression` to fetch only the `name` attribute, reducing bandwidth:

```python
def load_store_names(client, table_name: str) -> list[str]:
    names = []
    kwargs = {
        "TableName": table_name,
        "ProjectionExpression": "#n",
        "ExpressionAttributeNames": {"#n": "name"},  # 'name' is a reserved word
    }
    while True:
        resp = client.scan(**kwargs)
        for item in resp.get("Items", []):
            n = item.get("name", {}).get("S", "").strip()
            if n:
                names.append(n)
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return names
```

Note: `name` is a DynamoDB reserved word — must use `ExpressionAttributeNames` alias.

---

## 4. Module-Level Cache Pattern

Simple sentinel pattern — no TTL needed since stores data is refreshed weekly by a separate Lambda. The processor already uses `batch_size=1` on SQS so concurrency conflicts are not a concern.

```python
_STORE_NAMES: list[str] | None = None

def _get_store_names() -> list[str]:
    global _STORE_NAMES
    if _STORE_NAMES is None:
        _STORE_NAMES = load_store_names(dynamodb, os.environ.get("STORES_TABLE", ""))
    return _STORE_NAMES
```

**Gotchas:**
- Cache is per-execution-environment, not shared across concurrent Lambda instances.
- Cache is lost on environment recycle (typically every few hours or after idle period).
- Only cache read-only, non-user-specific data at module level.
- `name` is a DynamoDB reserved word — ProjectionExpression requires ExpressionAttributeNames alias.

---

## 5. Stored Field Name

The stores table items use `name` for the canonical store name (set by `populate_stores.py` and `stores_refresh/handler.py`). Items with empty `name` (unnamed OSM shops) should be filtered out before building the candidate list.
