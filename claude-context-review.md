# Plan Review

## Verdict
**NEEDS REVISION** — the plan has one unresolved contradiction between its own guidance and the researcher's API findings, plus two minor but consequential gaps in step specification. All structural assumptions (file locations, resource names, line references, dataclass shapes) are accurate and confirmed against the actual source code.

---

## Flaws Found

- **Flaw 1 — Tool schema type: plan and researcher directly contradict each other:**
  The plan (Step 1, and the Risks & Blockers section) explicitly forbids `"type": ["string", "null"]` in the Bedrock tool spec, stating the Converse API "may raise a `ValidationException` for non-scalar type values." It instructs using `"type": "string"` only and encoding the no-match case as the sentinel string `"null"`.

  The researcher document (section 2, Tool schema block) does the opposite: it specifies `"matched_name": { "type": ["string", "null"] }` as the recommended schema, with no qualification or warning about ValidationException.

  These two sources are in direct conflict. The plan's actual code sample (Step 1 prose) commits to the scalar string approach, while the researcher's schema commits to the array-union approach. Because the implementer is given both documents, this unresolved contradiction will force a runtime gamble. The existing `RECEIPT_TOOL` in `bedrock_extraction.py` (confirmed by reading the source) uses only scalar `"type"` values throughout — every property uses `"type": "string"` or `"type": "integer"`, never an array. Following codebase consistency strongly favours the scalar approach.

  **Consequence if left unfixed:** If the implementer follows the researcher's schema and the Bedrock AU cross-region inference profile rejects array-type `"type"` values, every `_match_store()` call will raise a `ClientError`. Even though the call is wrapped in a try/except (as Step 5 correctly specifies), every receipt processed while this misconfiguration exists will log a `STORE_MATCH_ERROR` and store no matched_store — the feature is silently broken until the schema is fixed and the Lambda redeployed. Alternatively, if the implementer follows the plan's sentinel-string approach and `["string", "null"]` would have worked, unnecessary complexity is introduced (the sentinel mapping) and the model could theoretically return the string `"null"` for a store actually named "null".

- **Flaw 2 — `_get_store_names()` cache-assignment behaviour for the empty-STORES_TABLE guard is underspecified:**
  Step 3 says: "Returns `[]` if `STORES_TABLE` is empty (guards against missing env var)." It does not specify whether to assign `_STORES_CACHE = []` before returning or to return `[]` without touching the cache sentinel. This matters: if the early-return assigns `_STORES_CACHE = []`, then a subsequent redeployment that corrects the missing `STORES_TABLE` env var will never trigger a real scan within that execution environment's lifetime — the cache is permanently poisoned as an empty list until the environment is recycled. Conversely, if the early-return leaves `_STORES_CACHE = None`, the guard check runs on every invocation when `STORES_TABLE` is unset, which is a harmless no-op but leaves the sentinel in an unexpected state that a future reader of the code may find confusing.

  **Consequence if left unfixed:** Low correctness risk under normal operations (env var will be set in production), but in a misconfigured deployment the cache could be permanently stale for the lifetime of any execution environment that ran before the env var was corrected, without any log warning.

- **Flaw 3 — Step 6's `matched_store` insertion point into the `update_job(...)` dict is underspecified:**
  Step 6 says to add the conditional spread "alongside the existing one for `cropped_s3_key`" at "lines 153-168." The actual file confirms the `cropped_s3_key` spread is on line 164. The plan's code sample shows the new spread inserted, but does not show its exact position relative to `"image_hash"` and `"updated_at"`. In a Python dict literal, trailing commas on preceding lines must be present; the instruction "alongside" is ambiguous about whether the new line goes before or after line 164's `cropped_s3_key` spread. While Python dict ordering is semantically irrelevant here, an implementer inserting after line 164 without ensuring the trailing comma is present (it is, in the actual code) could create a syntax error. The plan should show the exact two-line context for the insertion.

  **Consequence if left unfixed:** Low risk (syntax errors fail immediately at import time), but the vagueness creates unnecessary ambiguity.

---

## Suggested Improvements

- **Improvement 1 — Commit explicitly to the scalar-type approach and explain why:**
  Remove the "may raise" hedge from the Risks section and replace it with a definitive statement: "The `MATCH_STORE_TOOL` must use `"type": "string"` for `matched_name`, consistent with all other tool property declarations in `bedrock_extraction.py`. The researcher's example schema using `["string", "null"]` is JSON Schema-valid but has not been validated against the AU cross-region inference profile and conflicts with the established codebase pattern. The no-match case is handled by the `"null"` sentinel string." This closes the contradiction.

- **Improvement 2 — Specify the cache-miss-on-empty-table behaviour explicitly in Step 3:**
  Add one sentence: "If `STORES_TABLE` is empty, return `[]` immediately **without assigning `_STORES_CACHE`**, so that a redeployment adding the env var will trigger a fresh scan on the next cold start rather than reading a stale empty-list cache."

- **Improvement 3 — Show the exact insertion context for the `update_job` dict in Step 6:**
  Replace "alongside the existing one for `cropped_s3_key`" with an explicit before/after, showing the new line inserted directly after the `cropped_s3_key` conditional spread (line 164) and before `"image_hash": dyn_s(image_hash)` (line 165):
  ```python
  **( {"cropped_s3_key": dyn_s(result.cropped_s3_key)} if result.cropped_s3_key else {} ),
  **( {"matched_store": dyn_s(result.matched_store)} if result.matched_store else {} ),
  "image_hash": dyn_s(image_hash),
  ```

- **Improvement 4 — Confirm the IAM `bedrock:InvokeModel` action covers `bedrock.converse()` explicitly:**
  The plan states the existing `BedrockInvokeModel` statement "already covers the Haiku model via wildcard foundation-model and inference-profile ARNs — no change needed there." This is correct and confirmed by the actual `iam.tf`. However, since the `bedrock.converse()` SDK method may map to either `bedrock:InvokeModel` or a separate `bedrock:Converse` action depending on the API version, the plan should cite the existing working evidence: `_run_bedrock()` already calls `bedrock.converse()` successfully under the same IAM statement. This transforms an implicit assumption into a verified fact.

- **Improvement 5 — Testing strategy item 3 is mis-worded (cannot "rename" a DynamoDB table):**
  The Testing Strategy item 3 says "Temporarily set `STORES_TABLE=\"\"` in a test invocation." This is correct. However, the prior review's version of this step mentioned "rename or empty the table" — if that wording survived into any test documentation, it should be corrected, since DynamoDB tables cannot be renamed. The plan as written only says to set the env var to empty, which is the right approach.

---

## Revised Steps (if applicable)

**Revised Step 1 — Tool spec type declaration (replace the ambiguous guidance):**

In `MATCH_STORE_TOOL`, declare `matched_name` as:
```python
"matched_name": {
    "type": "string",
    "description": (
        "The exact string from the candidates list that best matches the OCR vendor. "
        "Return the literal string 'null' if no store in the list is a confident match."
    ),
}
```
This is consistent with all other tool properties in `bedrock_extraction.py` and avoids the unvalidated array-type syntax. In the response parser, map `"null"` (case-insensitive) and empty string both to Python `None`:
```python
raw = (block["toolUse"]["input"].get("matched_name") or "").strip()
return None if raw.lower() in ("null", "") else raw
```
Do not use `"type": ["string", "null"]` from the researcher's example — the established codebase convention is scalar-only type declarations.

**Revised Step 3 — Cache function, empty-table guard (add one sentence):**

```python
_STORES_CACHE: list[str] | None = None

def _get_store_names() -> list[str]:
    global _STORES_CACHE
    if _STORES_CACHE is not None:
        return _STORES_CACHE
    # Do NOT assign _STORES_CACHE here — leave sentinel as None so that
    # a redeployment adding STORES_TABLE triggers a fresh scan on next cold start.
    if not STORES_TABLE:
        return []
    names = []
    kwargs = {
        "TableName": STORES_TABLE,
        "ProjectionExpression": "#n",
        "ExpressionAttributeNames": {"#n": "name"},
    }
    while True:
        resp = dynamodb.scan(**kwargs)
        for item in resp.get("Items", []):
            n = item.get("name", {}).get("S", "").strip()
            if n:
                names.append(n)
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    _STORES_CACHE = names
    return _STORES_CACHE
```

**Revised Step 6 — Exact insertion point in `update_job(...)` dict:**

Insert the new conditional spread directly after the `cropped_s3_key` line and before `"image_hash"`:
```python
        **( {"cropped_s3_key": dyn_s(result.cropped_s3_key)} if result.cropped_s3_key else {} ),
        **( {"matched_store": dyn_s(result.matched_store)} if result.matched_store else {} ),
        "image_hash": dyn_s(image_hash),
```

---

## Summary

The plan is structurally sound: all file paths, resource names, dataclass shapes, line references, and sequencing are confirmed accurate against the actual source code. The one material flaw is an unresolved direct contradiction between the plan's tool schema guidance (scalar `"type": "string"`) and the researcher's example schema (`"type": ["string", "null"]`); this must be explicitly resolved in favour of the scalar approach (consistent with the existing `RECEIPT_TOOL` in the codebase) before implementation begins. The two remaining gaps — the empty-table cache-assignment behaviour and the update_job insertion-point ambiguity — are low-risk but should be tightened to prevent implementer uncertainty.
