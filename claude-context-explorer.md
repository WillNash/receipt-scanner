# Claude Context Explorer — DynamoDB Stores Table + Populate Script

## Task
Add a DynamoDB table for storing retail store names near Palmerston North NZ, populated by a one-off Python script querying the OpenStreetMap Overpass API.

---

## 1. Terraform DynamoDB Table Definitions and Naming Conventions

**File:** `/workspace/active_repo/terraform/dynamodb.tf`

All three existing tables follow a strictly uniform pattern:
- `name = "${var.project_name}-<suffix>"` — actual deployed names are `receipt-scanner-jobs`, `receipt-scanner-image-hashes`, `receipt-scanner-line-items`
- `billing_mode = "PAY_PER_REQUEST"` on every table (no provisioned capacity anywhere)
- `ttl` block present on every table: `attribute_name = "expires_at"`, `enabled = true`
- Tags block always: `Project = var.project_name` and `Environment = var.environment`
- Only key attributes appear in `attribute {}` blocks; non-key attrs are schema-free and must NOT be declared

The new table should follow this same pattern exactly and be named `"${var.project_name}-stores"`.

---

## 2. How `project_name` is Used in Resource Naming

**File:** `/workspace/active_repo/terraform/variables.tf`
- Default value in code: `"bedrock-image-ai"`

**File:** `/workspace/active_repo/terraform/terraform.tfvars`
- Actual deployed value: `"receipt-scanner"`

So all real deployed resource names use `receipt-scanner-` as a prefix. This is a known inconsistency documented in CLAUDE.md.

`project_name` is used as a prefix in:
- All DynamoDB table `name` fields
- All IAM role and policy `name` fields
- All Lambda function names (see `lambda.tf`)
- Tags on all resources

The new table's deployed name will therefore be `receipt-scanner-stores`.

**Warning:** `scripts/export_receipts.py` hardcodes `TABLE = "bedrock-image-ai-jobs"` instead of deriving the name from variables. The new populate script should instead hardcode `"receipt-scanner-stores"` (matching the actual tfvars value) or accept it as a CLI argument.

---

## 3. Existing Python Script Patterns

### AWS Authentication
All scripts use `boto3` with **no explicit profile, no `boto3.Session`, no credential arguments** — pure ambient credential chain (env vars, `~/.aws/credentials`, instance profile):

```python
# Pattern from export_receipts.py
import boto3
REGION = "ap-southeast-2"
dynamodb = boto3.client("dynamodb", region_name=REGION)
```

This is the only pattern present. No script uses `boto3.resource("dynamodb")` (the high-level resource interface).

### DynamoDB Write Patterns
- All scripts and Lambdas use the **low-level client** (`boto3.client`), meaning DynamoDB typed attribute dicts: `{"S": "value"}`, `{"N": "42"}`.
- `put_item` is the standard upsert (replaces the entire item if the primary key matches — DynamoDB's native upsert semantics, no ConditionExpression needed for a simple overwrite).
- `batch_write_item` is used in the processor Lambda for bulk writes (`lambda/processor/handler.py`).
- The one-off scripts only use `put_item` / `scan` / `query` — no transactions.

### Script Structure (canonical template: `export_receipts.py`)

```python
#!/usr/bin/env python3
"""
Docstring with description.

Usage:
    python scripts/foo.py [--arg value]
"""

import argparse
import sys
import boto3

TABLE  = "receipt-scanner-<suffix>"
REGION = "ap-southeast-2"

def <domain_logic>(dynamodb, ...):
    ...

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--some-flag", help="...")
    args = parser.parse_args()

    dynamodb = boto3.client("dynamodb", region_name=REGION)
    # do work
    print(f"Progress info", file=sys.stderr)

if __name__ == "__main__":
    main()
```

Progress/debug messages go to `sys.stderr`; data output goes to `sys.stdout` (or a file opened via `--output`).

---

## 4. The Makefile

**File:** `/workspace/active_repo/Makefile`

| Target | Dependencies | What it does |
|---|---|---|
| `setup` | — | Prints setup instructions only |
| `package` | — | Runs `scripts/package_lambdas.sh` |
| `plan` | `package` | `terraform init -upgrade` + `terraform plan -var-file=terraform.tfvars` |
| `apply` | `package` | `terraform init -upgrade` + `terraform apply -var-file=terraform.tfvars` |
| `deploy` | `apply` | `apply` + `python3 scripts/inject_config.py` |
| `frontend-dev` | — | `cd frontend && npm run dev` |
| `smoke` | — | `python3 scripts/smoke_test.py` |
| `destroy` | — | `terraform destroy -var-file=terraform.tfvars` |

One-off scripts are **not wired into Makefile targets** — they are invoked directly as `python3 scripts/<name>.py`. The new populate script should follow this pattern (no Makefile target needed).

To create the table and then populate it, the operator would run:
```
make deploy   # or just: make apply
python3 scripts/populate_stores.py
```

---

## 5. Best Template for the New Script

**File:** `/workspace/active_repo/scripts/export_receipts.py`

This is the closest model because it:
- Is a standalone one-off utility with no Lambda involvement
- Uses `boto3.client("dynamodb", region_name=REGION)` with hardcoded table name and region constants
- Uses low-level typed DynamoDB API (not high-level resource)
- Has a proper `argparse` CLI with `--help`
- Has a `main()` guarded by `if __name__ == "__main__"`
- Prints progress to `sys.stderr`

---

## 6. What the Main Agent Needs to Create

### A. Addition to `/workspace/active_repo/terraform/dynamodb.tf`

Append a new resource block:

```hcl
resource "aws_dynamodb_table" "stores" {
  name         = "${var.project_name}-stores"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "store_id"

  attribute {
    name = "store_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}
```

Design decisions embedded here:
- `store_id` as PK (type String). Use the OSM element reference, e.g. `"node/12345678"` or `"way/98765432"`. This is stable and unique per Overpass element.
- No sort key needed for a simple key-value store lookup table.
- No GSI in the initial version (can add later if the API needs to query by name/category).
- TTL attribute declared but no TTL values will be set on items, matching existing tables.

### B. New file `/workspace/active_repo/scripts/populate_stores.py`

Key implementation points:
- POST to `https://overpass-api.de/api/interpreter` with a body like:
  ```
  [out:json][timeout:60];
  (
    node["shop"](around:10000,-40.3523,175.6082);
    way["shop"](around:10000,-40.3523,175.6082);
  );
  out center tags;
  ```
- Parse JSON response: `response["elements"]` is a list of dicts each with `id`, `type`, `tags` (dict), and for ways `center.lat`/`center.lon`.
- `store_id` value: `f"{element['type']}/{element['id']}"`
- Upsert using `dynamodb.put_item(TableName=TABLE, Item={...})` — no ConditionExpression needed (replaces on matching key).
- Handle missing `name` tag gracefully (skip or store as `"(unnamed)"`).
- Use `urllib.request` (stdlib, already used in `smoke_test.py`) or `requests` (if installed) for the HTTP call.
- Table name constant: `TABLE = "receipt-scanner-stores"` with a `--table` CLI argument to override.
- Add a `User-Agent` header to the Overpass request as good etiquette.
- Print count of upserted stores to `sys.stderr`.

---

## 7. Side-Effects and Caveats the Main Agent Should Be Aware Of

1. **IAM permissions:** The new DynamoDB table is not referenced in `/workspace/active_repo/terraform/iam.tf`. Neither Lambda role has access to it. The populate script runs with the operator's ambient AWS credentials (not Lambda), so no IAM change is needed for the script itself. If any Lambda ever needs to read the stores table, `iam.tf` must be updated with a new statement on the relevant role.

2. **Deployment sequence:** The Terraform resource must be applied (via `make apply` or `make deploy`) before the populate script can write to the table. The table will not exist until Terraform creates it.

3. **Overpass API availability:** The public endpoint `overpass-api.de` has rate limits and occasional downtime. For a one-shot populate script this is acceptable, but the script should handle HTTP errors (non-200 status) and print a meaningful error message.

4. **OSM data completeness:** Not every shop in Palmerston North will have a `name` tag in OSM. The script should decide: skip nameless entries, or store them with the OSM ID as an identifier. Either approach is valid — just document it.

5. **`terraform.tfvars` naming:** The actual project name deployed is `"receipt-scanner"` (from `terraform.tfvars`), NOT `"bedrock-image-ai"` (the variable default in `variables.tf`). Hardcoding `"receipt-scanner-stores"` in the script matches what Terraform will actually create.

6. **No outputs.tf change required:** Unlike infrastructure that the frontend needs, the stores table name does not need to be a Terraform output. It is only used by the one-off script.
