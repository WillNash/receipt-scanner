# Plan Review

## Verdict
**NEEDS REVISION** — three flaws require correction before implementation begins. None invalidate the overall design, but two will produce incorrect runtime behaviour and one introduces unnecessary complexity that contradicts the codebase's own documented conventions.

---

## Flaws Found

- **Flaw 1 — Timeout relationship is inverted between plan and researcher source:** Step 2a specifies `[timeout:90]` as the Overpass server-side query budget and step 2b specifies `urlopen(req, timeout=95)` as the client socket timeout, framing the 5-second gap as deliberate so "the server always aborts first." However, the researcher's own Gotchas note (section 5, last bullet) states: "Add `[timeout:N]` in the Overpass query (N seconds) — must be at least as large as the HTTP client timeout." The Overpass server-side timeout must be >= the client socket timeout, not less than it. The researcher's own working code example (section 4) also demonstrates this: the query uses `[timeout:60]` while `urlopen` is called with `timeout=90`. When the server-side `[timeout:90]` fires at 90 s and the socket is set to 95 s, there is only a 5-second window for Overpass to write its error body and close the connection before the client's socket errors out with `socket.timeout`. Under any server load or network latency, the socket may time out first, raising `socket.timeout` (wrapped in `urllib.error.URLError`) — which is not caught by the plan's `urllib.error.HTTPError` handler and will produce an unhandled exception with no meaningful error message rather than a clean `sys.exit(1)`. The consequence: under a slow-server or slow-network condition the script will crash with an unhelpful traceback instead of surfacing the Overpass error cleanly. Fix: set the Overpass query to `[timeout:60]` and the socket timeout to `90`, matching the researcher's documented pattern, so the server always has time to complete or abort and write a response before the client disconnects.

- **Flaw 2 — `batch_write_item` with hand-rolled retry contradicts the codebase's one-off script convention:** Step 2d specifies a full `batch_write_item` implementation: 25-item chunking, `UnprocessedItems` inspection, and an exponential-back-off retry loop. The explorer (section 3, "DynamoDB Write Patterns") explicitly documents that "the one-off scripts only use `put_item` / `scan` / `query`" and that `batch_write_item` appears only in the processor Lambda. The explorer's own recommendation for the new script (section 6B) says `dynamodb.put_item(TableName=TABLE, Item={...})` with no mention of batching. For the expected data volume (tens to a few hundred shops within a 10 km radius of Palmerston North), a simple `put_item` loop is correct, consistent with project conventions, and produces the same idempotency guarantee (`put_item` is an unconditional full-replace on matching key). The plan's batch approach adds approximately 40 lines of non-trivial retry logic with its own failure modes (the retry payload scoping issue noted in the previous review iteration) and diverges from the codebase pattern without any performance justification. Consequence if left in: increased implementation complexity, a higher surface area for bugs, and a script that reads differently from every other one-off script in the project.

- **Flaw 3 — `out center tags;` framing in Step 2a and Risks item 1 is misleading:** Step 2a presents `out center tags;` as the preferred form and Risks item 1 defends it by claiming `out center;` "may also return tags in practice (the keyword is not always required)." This frames `tags` as a safety modifier. The researcher document (section 2) uses `out center;` without `tags` as the canonical working form, and the JSON response examples (section 1) show full tag data is present with `out center;`. In Overpass QL, `out center;` is equivalent to `out body center;` and includes tags by default in JSON output mode. The `tags` keyword is not a separate modifier that enables tag output — it is redundant in this position. Writing `out center tags;` is not standard documented Overpass QL syntax and could produce a parse warning or unexpected behaviour on some server versions. Consequence if the misleading framing is left in: the implementer believes `tags` is necessary for correctness and will keep it even if server-side warnings appear, instead of switching to the standard `out center;` form.

---

## Suggested Improvements

- **Improvement 1 — Fix timeout ordering to match researcher's documented pattern:** In step 2a, change the `OVERPASS_QUERY` constant to `[timeout:60]`. In step 2b, change `urlopen(req, timeout=95)` to `urlopen(req, timeout=90)`. Update the explanatory text to state the correct relationship: "The client socket timeout (90 s) must exceed the server-side query timeout (60 s) so Overpass always finishes or aborts and writes a response body before the client closes the connection." Also add a second `except urllib.error.URLError` clause (after `HTTPError`) to catch network-level errors, printing `exc.reason` to stderr and calling `sys.exit(1)`.

- **Improvement 2 — Replace `batch_write_item` loop with simple `put_item` loop:** Rewrite step 2d as: iterate over elements, call `build_item(element)`, skip `None` results, call `dynamodb.put_item(TableName=table, Item=item)` for each, increment a counter, print progress to stderr every 50 items, catch `botocore.exceptions.ClientError` per item and print the error then re-raise. Remove all batching, chunking, `UnprocessedItems`, and exponential back-off logic. This matches the explicit codebase convention the explorer documented.

- **Improvement 3 — Change `out center tags;` to `out center;`:** In step 2a's `OVERPASS_QUERY` constant, use `out center;`. Update Risks item 1 to state accurately: "`out center;` returns full tag data in JSON mode — the `tags` keyword is redundant and not needed."

- **Improvement 4 — Add `urllib.error.URLError` to the exception handler in `fetch_shops()`:** The plan only catches `urllib.error.HTTPError`. Network-level errors (DNS failure, connection timeout, socket timeout) raise `urllib.error.URLError`. Add a second except clause for `URLError` that prints `exc.reason` to stderr and calls `sys.exit(1)`. This is consistent with how `smoke_test.py` handles similar errors.

- **Improvement 5 — Refine testing step 5 (idempotency check) wording:** The statement "the item count in DynamoDB must not increase" conflates idempotency with OSM data stability. A more accurate test: "Run the script a second time immediately. Confirm it exits 0 without errors. Spot-check a specific `store_id` written in the first run and confirm its attributes are intact and unchanged." OSM data is live, so a count comparison is not a reliable idempotency test.

---

## Revised Steps (if applicable)

**Revised Step 2a — OVERPASS_QUERY constant (timeout directive only):**

```python
OVERPASS_QUERY = """\
[out:json][timeout:60][maxsize:10000000];
(
  node["shop"](around:10000,-40.3523,175.6082);
  way["shop"](around:10000,-40.3523,175.6082);
);
out center;
"""
```

**Revised Step 2b — urlopen call and exception handling:**

```python
try:
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.load(resp)
except urllib.error.HTTPError as exc:
    print(f"ERROR: Overpass HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
    sys.exit(1)
except urllib.error.URLError as exc:
    print(f"ERROR: Network error reaching Overpass: {exc.reason}", file=sys.stderr)
    sys.exit(1)

remark = data.get("remark", "")
if remark:
    print(f"ERROR: Overpass remark: {remark}", file=sys.stderr)
    sys.exit(1)
elements = data.get("elements", [])
if not elements:
    print("WARNING: Overpass returned zero elements.", file=sys.stderr)
return elements
```

Explanation of timeout values: the client socket timeout (90 s) is larger than the server-side query budget (60 s). This ensures Overpass always finishes or aborts and writes a complete HTTP response before the client socket closes. The remark guard detects the HTTP-200 error case (Overpass encodes timeout/maxsize errors as HTTP 200 with a `remark` field and an empty `elements` list).

**Revised Step 2d — upsert function (replace batch_write_item with put_item loop):**

- Iterate over `elements`. For each element call `build_item(element)`; skip any that return `None`.
- Call `dynamodb.put_item(TableName=table, Item=item)` for each item.
- Catch `botocore.exceptions.ClientError` per call: print the error code and message to `sys.stderr` and re-raise so the caller sees the failure.
- Increment a success counter after each successful call. Print progress to `sys.stderr` every 50 items (e.g., `"Upserted 50 / 200..."`).
- Return the final count of successfully written items.

This is the pattern used by all one-off scripts in the codebase (see explorer section 3). `put_item` is an unconditional full-replace on matching key, providing the same idempotency guarantee as `batch_write_item` PutRequests.

---

## Summary

The plan correctly captures the Terraform table structure, the `project_name`/`terraform.tfvars` naming subtlety, the requirement for low-level `boto3.client`, the ambient-credentials pattern, and the important Overpass-specific guards (remark field, way centre coordinates, User-Agent). The three flaws — an inverted timeout relationship that contradicts the researcher's own documentation, unnecessary `batch_write_item` complexity that contradicts the codebase's one-off script convention, and a misleadingly framed Overpass output modifier — are all localised to steps 2a, 2b, and 2d. None require structural changes. Apply the revised steps above and implementation can safely begin.
