#!/usr/bin/env python3
"""
Export completed receipts from DynamoDB to CSV.

Usage:
    python scripts/export_receipts.py                        # all users
    python scripts/export_receipts.py --user <user_id>      # single user
    python scripts/export_receipts.py --output receipts.csv
"""

import argparse
import csv
import json
import sys

import boto3

TABLE = "bedrock-image-ai-jobs"
REGION = "ap-southeast-2"


def scan_jobs(dynamodb, user_id=None):
    # Counter items (COUNT#...) are excluded client-side below — DynamoDB has no
    # "not begins_with" filter expression.
    kwargs = {
        "TableName": TABLE,
        "FilterExpression": "#s = :complete",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":complete": {"S": "COMPLETE"}},
    }

    if user_id:
        kwargs = {
            "TableName": TABLE,
            "IndexName": "user-jobs-index",
            "KeyConditionExpression": "user_id = :uid",
            "FilterExpression": "#s = :complete",
            "ExpressionAttributeNames": {"#s": "status"},
            "ExpressionAttributeValues": {
                ":uid": {"S": user_id},
                ":complete": {"S": "COMPLETE"},
            },
        }

    paginator_method = "query" if user_id else "scan"
    paginator = dynamodb.get_paginator(paginator_method)

    items = []
    for page in paginator.paginate(**kwargs):
        for item in page["Items"]:
            # Skip counter items
            if item["job_id"]["S"].startswith("COUNT#"):
                continue
            items.append(item)
    return items


def flatten(items):
    rows = []
    for item in items:
        job_id       = item.get("job_id", {}).get("S", "")
        user_id      = item.get("user_id", {}).get("S", "")
        vendor       = item.get("vendor", {}).get("S", "")
        receipt_date = item.get("receipt_date", {}).get("S", "")
        total        = item.get("total", {}).get("S", "")
        created_at   = item.get("created_at", {}).get("S", "")
        line_items   = json.loads(item.get("items", {}).get("S", "[]"))

        if not line_items:
            rows.append({
                "job_id": job_id,
                "user_id": user_id,
                "vendor": vendor,
                "receipt_date": receipt_date,
                "receipt_total": total,
                "created_at": created_at,
                "description": "",
                "quantity": "",
                "unit_price": "",
                "price": "",
                "discount": "",
            })
        else:
            for li in line_items:
                rows.append({
                    "job_id": job_id,
                    "user_id": user_id,
                    "vendor": vendor,
                    "receipt_date": receipt_date,
                    "receipt_total": total,
                    "created_at": created_at,
                    "description": li.get("description", ""),
                    "quantity": li.get("quantity", ""),
                    "unit_price": li.get("unit_price", ""),
                    "price": li.get("price", ""),
                    "discount": li.get("discount", ""),
                })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", help="Filter by user_id")
    parser.add_argument("--output", default="-", help="Output CSV file (default: stdout)")
    args = parser.parse_args()

    dynamodb = boto3.client("dynamodb", region_name=REGION)
    jobs = scan_jobs(dynamodb, user_id=args.user)
    print(f"Found {len(jobs)} completed receipts", file=sys.stderr)

    rows = flatten(jobs)

    fieldnames = ["job_id", "user_id", "vendor", "receipt_date", "receipt_total",
                  "created_at", "description", "quantity", "unit_price", "price", "discount"]

    out = open(args.output, "w", newline="") if args.output != "-" else sys.stdout
    writer = csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    if args.output != "-":
        out.close()
        print(f"Written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
