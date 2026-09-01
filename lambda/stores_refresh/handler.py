import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import boto3

TABLE = os.environ["STORES_TABLE"]
REGION = os.environ.get("PRIMARY_REGION", "ap-southeast-2")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

OVERPASS_QUERY = """
[out:json][timeout:60][maxsize:10000000];
(
  node["shop"](around:10000,-40.3523,175.6082);
  way["shop"](around:10000,-40.3523,175.6082);
);
out center;
"""


def fetch_shops():
    body = urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode()
    req = urllib.request.Request(
        OVERPASS_URL,
        data=body,
        headers={"User-Agent": "receipt-scanner-store-scraper/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Overpass HTTP error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Overpass request failed: {e.reason}")

    remark = data.get("remark")
    if remark:
        raise RuntimeError(f"Overpass error: {remark}")

    elements = data.get("elements", [])
    if not elements:
        print("WARNING: Overpass returned zero elements — check query or area coverage.", file=sys.stderr)

    return elements


def build_item(el):
    tags = el.get("tags", {})
    if el["type"] == "node":
        lat, lon = str(el["lat"]), str(el["lon"])
    else:
        lat = str(el["center"]["lat"])
        lon = str(el["center"]["lon"])
    return {
        "store_id":  {"S": f"{el['type']}/{el['id']}"},
        "osm_type":  {"S": el["type"]},
        "name":      {"S": tags.get("name", "")},
        "shop_type": {"S": tags.get("shop", "")},
        "lat":       {"S": lat},
        "lon":       {"S": lon},
    }


def lambda_handler(event, context):
    elements = fetch_shops()
    print(f"Fetched {len(elements)} elements from Overpass.", file=sys.stderr)

    dynamodb = boto3.client("dynamodb", region_name=REGION)
    for el in elements:
        dynamodb.put_item(TableName=TABLE, Item=build_item(el))

    print(f"Written {len(elements)} store records to {TABLE}.", file=sys.stderr)
    return {"written": len(elements)}
