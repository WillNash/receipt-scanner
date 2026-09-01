# Research Findings — Overpass API & DynamoDB Upsert

## Sources
- [Overpass API - OpenStreetMap Wiki](https://wiki.openstreetmap.org/wiki/Overpass_API)
- [Overpass API/Overpass QL - OpenStreetMap Wiki](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL)
- [Overpass API by Example - OpenStreetMap Wiki](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_API_by_Example)
- [boto3 DynamoDB batch_writer docs](https://docs.aws.amazon.com/boto3/latest/reference/services/dynamodb/table/batch_writer.html)
- [boto3 DynamoDB update_item docs](https://docs.aws.amazon.com/boto3/latest/reference/services/dynamodb/table/update_item.html)
- [DynamoDB PutItem vs UpdateItem - Dynobase](https://dynobase.dev/dynamodb-putitem-vs-updateitem/)

---

## 1. Overpass API

The Overpass API is a read-only HTTP API for querying OpenStreetMap data. Queries are written in Overpass QL and submitted as an HTTP POST with the query string in a `data` form field.

**Public endpoints (no auth):**
- `https://overpass-api.de/api/interpreter` — primary global instance, most reliable
- `https://overpass.private.coffee/api/interpreter` — community mirror

**Rate limiting / etiquette:**
- Stay under 10,000 queries/day and 1 GB/day.
- Always send an identifying `User-Agent` header.
- No parallel requests from the same script.
- On HTTP 429 or 406, pause 30 seconds before retrying.

**JSON response — node element:**
```json
{
  "type": "node",
  "id": 123456789,
  "lat": -40.3523,
  "lon": 175.6082,
  "tags": {
    "name": "New World Palmerston North",
    "shop": "supermarket",
    "addr:street": "Main Street"
  }
}
```

**JSON response — way element (with `out center`):**
```json
{
  "type": "way",
  "id": 987654321,
  "center": { "lat": -40.3510, "lon": 175.6100 },
  "tags": {
    "name": "Pak'nSave Palmerston North",
    "shop": "supermarket"
  }
}
```

Ways do NOT have top-level `lat`/`lon`. `out center` returns a bounding-box centroid per way.

---

## 2. Overpass QL Query

```
[out:json][timeout:60][maxsize:10000000];
(
  node["shop"](around:10000,-40.3523,175.6082);
  way["shop"](around:10000,-40.3523,175.6082);
);
out center;
```

- `around:10000` = 10,000 m = 10 km radius
- `out center` gives `lat`/`lon` on nodes and `center.lat`/`center.lon` on ways
- `[maxsize:10000000]` caps response to 10 MB

---

## 3. boto3 DynamoDB — upsert and bulk writes

**put_item vs update_item:**
- `put_item` replaces the entire item. Attributes not included are deleted if item already exists.
- `update_item` with `SET` UpdateExpression is the correct upsert: creates if missing, updates only named attributes if exists.

**batch_writer:**
- Chunks writes into batches of 25, up to 16 MB per batch.
- Automatically retries unprocessed items.
- Only supports `put_item` (full replace) and `delete_item`. Does NOT support `update_item`.
- For a one-shot seed script where full-replace is acceptable, `batch_writer` is the right choice.

**boto3 — batch_writer example:**
```python
with table.batch_writer() as batch:
    for shop in shops:
        tags = shop.get("tags", {})
        if shop["type"] == "node":
            lat, lon = str(shop["lat"]), str(shop["lon"])
        else:
            lat = str(shop["center"]["lat"])
            lon = str(shop["center"]["lon"])
        batch.put_item(Item={
            "store_id": f"{shop['type']}/{shop['id']}",
            "osm_type": shop["type"],
            "name": tags.get("name", ""),
            "shop_type": tags.get("shop", ""),
            "lat": lat,
            "lon": lon,
        })
```

---

## 4. requests vs urllib.request

- `requests` is third-party; must be pip-installed.
- `urllib.request` is stdlib (already used in `scripts/smoke_test.py`).
- For a local one-off script, `urllib.request` avoids requiring a pip install.
- `urllib.request` POST with form-encoded body:
```python
import urllib.request, urllib.parse
body = urllib.parse.urlencode({"data": QUERY}).encode()
req = urllib.request.Request(
    "https://overpass-api.de/api/interpreter",
    data=body,
    headers={"User-Agent": "receipt-scanner-store-scraper/1.0"},
)
with urllib.request.urlopen(req, timeout=90) as resp:
    data = json.load(resp)
```

---

## 5. Gotchas

- boto3 resource API does NOT accept Python `float`. Use `Decimal` or store as strings to avoid `TypeError: Float types are not supported`. Storing lat/lon as strings is simplest.
- `put_item` silently deletes attributes not in the call when item already exists — safe for a seed script since all attributes are always written.
- Ways don't have top-level `lat`/`lon` — must check `el["type"]` and use `el["center"]["lat"]` for ways.
- Add `[timeout:N]` in the Overpass query (N seconds) — must be at least as large as the HTTP client timeout.
