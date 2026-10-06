# Plan Review

## Verdict
**NEEDS REVISION** — the plan contains five concrete flaws that, if implemented as written, will produce incorrect infrastructure (mismatched CORS header values), a misleading implementation model for the cache function, an XSS surface in the datalist population, and two gaps that will confuse the implementer. None of the flaws are architectural; all are correctable with targeted edits before implementation begins.

---

## Flaws Found

- **Flaw 1 — CORS `Access-Control-Allow-Methods` stated as matching the existing codebase but it does not:** Step 3, item 7 specifies `Access-Control-Allow-Methods = "'GET,OPTIONS'"` and simultaneously claims this value "must match exactly the value used in every other OPTIONS integration response in the file (lines 84, 156, 222, 305)." Reading the actual `api_gateway.tf`, lines 84–88 (`upload_url_options`), 155–159 (`job_id_options`), and 220–225 (`receipts_options`) all use `'GET,POST,OPTIONS'`. Line 304–308 (`receipt_id_options`) uses `'DELETE,PATCH,OPTIONS'`. No existing route uses `'GET,OPTIONS'`. The plan's own cross-reference claim is false. The instruction to match the existing value and the value shown (`'GET,OPTIONS'`) are contradictory. If an implementer matches the existing pattern, they will write `'GET,POST,OPTIONS'` (incorrect for a GET-only route). If they use what the plan shows, they will contradict the plan's own rationale. The plan must resolve this contradiction by stating that `'GET,OPTIONS'` is the deliberately correct value for a GET-only route and explicitly acknowledging that existing routes over-declare methods (which is their own inconsistency, not a model to copy).

- **Flaw 2 — Processor `_get_store_names()` is a false model for sorting and deduplication:** Step 6 says to "Model the scan loop on the processor's `_get_store_names()` (processor/handler.py lines 74–96)." Reading the actual function (confirmed lines 74–96 of `lambda/processor/handler.py`): it appends names to a plain list and assigns that list directly to `_STORES_CACHE` at line 95 — no deduplication, no sorting. The plan then correctly adds `sorted(set(...))` as a "critical addition." But calling the processor function a model while simultaneously saying its most relevant output line must not be followed creates a false reference. An implementer who copies the function verbatim will produce an unsorted, non-deduplicated list. The description must clearly separate what to copy (the scan loop and pagination mechanics, `ProjectionExpression`, `ExpressionAttributeNames`) from what must not be copied (the cache-assignment line `_STORES_CACHE = names`).

- **Flaw 3 — XSS surface in datalist population via `innerHTML` in Step 9:** Step 9 in the plan uses DOM methods (`document.createElement("option")` + `opt.value = n`) and explicitly prohibits `innerHTML` with template literals. This is the correct approach. However, the Risks section of the plan simultaneously says "Store names originate from OpenStreetMap via the Overpass scrape and can contain characters such as `"`, `<`, `>`, and `&`" and correctly identifies the XSS risk. Reading the `stores_refresh` Lambda (`lambda/stores_refresh/handler.py` lines 57–64 per the explorer): it writes raw `tags.get("name", "")` values to DynamoDB with no HTML encoding. The plan's Step 9 code block is actually correct (it uses DOM methods). The flaw is that the researcher's reference example (claude-context-researcher.md, section 2, lines 40–42) shows `dl.innerHTML = names.map(n => \`<option value="${n}"></option>\`).join("")` — the XSS-unsafe pattern — as the primary code sample. If the implementer references the researcher document alongside the plan, they may follow the researcher's `innerHTML` example instead of the plan's DOM-method example. The plan must explicitly call out that the researcher's sample is unsafe and must not be followed.

- **Flaw 4 — Plan does not address the unmatched vendor UX gap identified by the explorer:** The explorer (claude-context-explorer.md, lines 182–183) explicitly flags: "If `job.vendor` was set by OCR and does not exactly match any store name, the dropdown will not pre-select it ... At minimum, add the current vendor as an option so Save does not silently blank it." The plan's Step 9 populates the datalist from `data.stores` but does not address this at all. Because the implementation uses `<input type="text">` + `<datalist>` (not a `<select>`), free-text entry is always permitted and the OCR vendor value set at line 527 is retained — so there is no silent-blanking risk in practice. But the plan makes no mention of this, leaving the implementer with no justification if this is challenged during review. The plan must state explicitly that `<input>` + `<datalist>` is not value-enforcing (unlike `<select>`), so the current vendor value is retained even when absent from the datalist options, and therefore no special unmatched-vendor handling is needed.

- **Flaw 5 — Testing Step 1 is mislabelled as a unit-level test:** The testing strategy (point 1) describes creating a Lambda test event with a real JWT and invoking the function directly, then calls this a "Lambda console integration test." This label is correct and the plan is self-consistent here. However, the plan states the test "requires a live Lambda with `STORES_TABLE` set and DynamoDB accessible." What is missing from the testing strategy is any test for the `STORES_TABLE = ""` guard — the partial-deploy scenario that Step 5 specifically protects against with `os.environ.get("STORES_TABLE", "")`. There is no test that confirms `handle_list_stores()` returns `{"stores": []}` (not a 500 or `KeyError`) when `STORES_TABLE` is unset. Given the Risks section calls this scenario out explicitly, the absence of a corresponding test for it is a test gap.

---

## Suggested Improvements

- **Improvement 1 — Resolve the `Access-Control-Allow-Methods` contradiction in Step 3 item 7:** Replace the claim that the value must match existing routes with an explicit statement that `'GET,OPTIONS'` is the correct minimal value for a GET-only route, and acknowledge that existing routes over-declare methods. Remove the instruction to match existing values for this particular header.

- **Improvement 2 — Qualify the processor function as a model in Step 6:** Change the model reference so it names specifically which parts to copy (scan loop, pagination via `ExclusiveStartKey`, `ProjectionExpression = "#n"`, `ExpressionAttributeNames = {"#n": "name"}`, empty-string filtering) and explicitly states that the cache-assignment line `_STORES_CACHE = names` must not be copied — it must be replaced with `_STORES_CACHE = sorted(set(names))`.

- **Improvement 3 — Warn against the researcher's `innerHTML` sample in Step 9:** Add a note in Step 9 that the researcher's reference code (section 2 of claude-context-researcher.md) uses `dl.innerHTML` with template-literal interpolation of OSM name strings, which is the unsafe pattern. The plan's DOM-method implementation is the required approach; the researcher's sample must not be substituted.

- **Improvement 4 — Address the unmatched vendor scenario in Step 9:** Add a note explaining that `<input type="text">` + `<datalist>` does not enforce that the value must appear in the list (unlike `<select>`). The vendor field already contains `job.vendor` set at line 527 before the async fetch begins, so an OCR-scanned vendor absent from the datalist is retained and can be saved unchanged. No special unmatched-vendor handling is required.

- **Improvement 5 — Add a negative-path test to the Testing Strategy:** Add a test case: invoke the `api_handler` Lambda with `STORES_TABLE` set to an empty string (simulating a partial deploy where only the handler code was updated but the Terraform env var was not yet applied). Confirm the response is HTTP 200 with `{"stores": []}` and no exception is raised.

---

## Revised Steps (if applicable)

**Revised Step 3, item 7 — Corrected `Access-Control-Allow-Methods` instruction:**

Replace the current item 7 with:

> `aws_api_gateway_integration_response.stores_options` — `response_parameters` must set:
> - `method.response.header.Access-Control-Allow-Origin = "'*'"`
> - `method.response.header.Access-Control-Allow-Methods = "'GET,OPTIONS'"` — this is the correct minimal value for a GET-only route. Note that existing routes in the file over-declare methods (e.g. `/receipts` OPTIONS states `'GET,POST,OPTIONS'` even though `/receipts` has no POST method defined). Do not copy that pattern here; use only the methods this resource actually exposes.
> - `method.response.header.Access-Control-Allow-Headers = "'Content-Type,Authorization,X-Amz-Date,X-Api-Key'"` — this exact value must match every other OPTIONS integration_response in the file (lines 84, 156, 222, 305). Do not use the narrower `'Content-Type,Authorization'` value shown in the researcher's reference sample.

**Revised Step 6 — Corrected processor model reference:**

Replace:
> "Model the scan loop on the processor's `_get_store_names()` (processor/handler.py lines 74–96), but with one critical addition: after collecting all names from the paginated scan, apply `sorted(set(...))` before assigning to `_STORES_CACHE`. The processor's version stores a raw unsorted list without deduplication; copying it verbatim would produce unsorted, potentially duplicated names in the API response."

With:
> "Copy the scan mechanics from the processor's `_get_store_names()` (processor/handler.py lines 74–96): the `TableName`, `ProjectionExpression = "#n"`, `ExpressionAttributeNames = {"#n": "name"}`, `ExclusiveStartKey` pagination loop, and per-item extraction of `item.get("name", {}).get("S", "").strip()` with empty-string filtering. Do NOT copy the cache-assignment line `_STORES_CACHE = names` from the processor — that stores a raw, unsorted, non-deduplicated list. The API handler must instead assign `_STORES_CACHE = sorted(set(names))` after the loop completes, which simultaneously deduplicates and sorts the names before caching."

**Revised Step 9 — Warning against researcher's `innerHTML` sample and unmatched vendor note:**

After the existing code block showing DOM element creation, add:

> "IMPORTANT: The researcher's reference document (claude-context-researcher.md, section 2) shows a `dl.innerHTML = names.map(...)` pattern using template-literal interpolation. Do not use that pattern — OSM store names are written to DynamoDB unencoded and may contain `<`, `>`, `"`, and `&`. The DOM-method implementation above (`document.createElement / opt.value = n`) is the required approach.
>
> Regarding vendors absent from the datalist: `<input type='text'>` with a `<datalist>` does not enforce that the entered value must appear in the list (unlike `<select>`). The `modal.querySelector('#edit-vendor').value = job.vendor || ''` assignment at line 527 runs synchronously before this fetch begins, so an OCR-extracted vendor that does not appear in the datalist options will still be present in the field and can be saved unchanged. No special handling for unmatched vendors is needed."

---

## Summary

The plan's file-level assumptions, Terraform resource counts, IAM references, Lambda routing logic, and overall sequencing are all verified against the actual source code and are correct. Three issues must be fixed before implementation: (1) the self-contradictory `Access-Control-Allow-Methods` instruction must be resolved in favour of `'GET,OPTIONS'` with an explicit acknowledgement that existing routes over-declare methods; (2) the processor function reference must distinguish which parts to copy from which parts must not be copied; and (3) the implementer must be warned that the researcher's `innerHTML` datalist sample is the unsafe pattern that the plan itself prohibits. Two lower-priority gaps — the unmatched vendor explanation and the missing negative-path test — should also be addressed before implementation.
