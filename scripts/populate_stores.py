#!/usr/bin/env python3
"""
Populate the stores table from OpenStreetMap via the Overpass API.

Queries all OSM nodes and ways tagged "shop" within 10 km of Palmerston North
and upserts each record into DynamoDB.

Usage:
    python scripts/populate_stores.py
    python scripts/populate_stores.py --table receipt-scanner-stores
    python scripts/populate_stores.py --dry-run
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import boto3

TABLE = "receipt-scanner-stores"
REGION = "ap-southeast-2"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# 10 km radius around Palmerston North, NZ
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
        print(f"Overpass HTTP error: {e.code} {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Overpass request failed: {e.reason}", file=sys.stderr)
        sys.exit(1)

    remark = data.get("remark")
    if remark:
        print(f"Overpass error: {remark}", file=sys.stderr)
        sys.exit(1)

    elements = data.get("elements", [])
    if not elements:
        print("Overpass returned zero elements — check query or area coverage.", file=sys.stderr)

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


def upsert_stores(dynamodb, table, elements, dry_run=False):
    written = 0
    for el in elements:
        item = build_item(el)
        if dry_run:
            name = item["name"]["S"] or "(unnamed)"
            shop_type = item["shop_type"]["S"]
            print(f"  {item['store_id']['S']}  {shop_type}  {name}")
        else:
            dynamodb.put_item(TableName=table, Item=item)
        written += 1
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", default=TABLE, help="DynamoDB table name")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    print("Fetching shops from Overpass API...", file=sys.stderr)
    elements = fetch_shops()
    print(f"Fetched {len(elements)} elements.", file=sys.stderr)

    dynamodb = boto3.client("dynamodb", region_name=REGION)

    if args.dry_run:
        print("Dry run — records that would be written:")

    written = upsert_stores(dynamodb, args.table, elements, dry_run=args.dry_run)

    action = "Would write" if args.dry_run else "Written"
    print(f"{action} {written} store records to {args.table}.", file=sys.stderr)


if __name__ == "__main__":
    main()
