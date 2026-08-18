# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

Receipt Scanner — an AWS-hosted web app where authenticated users upload receipt photos and get them scanned by Amazon Textract. Results include vendor, date, total, and per-line-item breakdown.

**Stack:** Python 3.12 (Lambda), Terraform (HCL), vanilla JS SPA (no bundler/framework), Bash scripts. Region: `ap-southeast-2`.

## Commands

All primary operations go through `make`:

```bash
make package    # Build Lambda zip files (runs scripts/package_lambdas.sh)
make plan       # Package + terraform plan
make deploy     # Package + terraform apply + inject frontend config
make smoke      # Smoke test: checks CloudFront 200 + API 401
make destroy    # terraform destroy
```

There are no unit tests and no linter config.

**Useful scripts** (run directly with `python3 scripts/<name>.py`):
- `export_receipts.py` — dumps DynamoDB jobs table to CSV (hardcodes table name `bedrock-image-ai-jobs`)
- `smoke_test.py` — validates deployed endpoints
- `visualize_textract.py` — overlays Textract bounding boxes on an image for debugging
- `inject_config.py` — injects Terraform outputs into `frontend/app.js.template` → `frontend/app.js`

## Architecture

```
Browser
  ├── CloudFront → S3 (static SPA: index.html, styles.css, app.js)
  ├── API Gateway (REST, stage "v1")
  │     POST /upload-url   → Lambda (api) → DynamoDB
  │     GET  /jobs/{jobId} → Lambda (api) → DynamoDB
  │     GET  /receipts     → Lambda (api) → DynamoDB (GSI)
  └── S3 presigned PUT → S3 uploads bucket
                              → S3 event → SQS → Lambda (processor)
                                              → OpenCV MSER crop
                                              → Textract AnalyzeDocument (FORMS)
                                              → DynamoDB (jobs, image_hashes, line_items)
```

### Lambda: `lambda/api/handler.py`

Routes `POST /upload-url`, `GET /jobs/{jobId}`, `GET /receipts`. Auth is handled **inside the Lambda** (not via API Gateway authorizer) — JWKS is fetched from Cognito once per cold start and cached as a module-level global. Rate limits are enforced via DynamoDB counter items (`COUNT#GLOBAL` and `COUNT#{user}#{date}`).

### Lambda: `lambda/processor/handler.py`

SQS consumer. Flow: download image → SHA-256 hash dedup (`image_hashes` table) → optional OpenCV MSER crop → Textract `AnalyzeDocument` with `FORMS` feature → regex-based state machine parses receipt rows → writes to DynamoDB. Textract call is `AnalyzeDocument`, **not** `AnalyzeExpense` (README is wrong on this).

The processor Lambda zip is uploaded via S3 (not direct to Lambda) because `opencv-python-headless` pushes it past the 70 MB direct-upload limit.

### DynamoDB Tables

| Table | PK / SK | Notes |
|---|---|---|
| `{project_name}-jobs` | PK: `job_id`; GSI: `user_id` + `created_at` | Jobs + rate-limit counters |
| `{project_name}-image-hashes` | PK: `user_id`, SK: `image_hash` | Duplicate detection |
| `{project_name}-line-items` | PK: `user_id`, SK: `item_sk`; GSI: `desc_created` | Per-line-item analytics |

### Frontend

`frontend/app.js` is generated (gitignored) — edit `frontend/app.js.template` instead. Cognito uses OAuth2 code flow; tokens are stored in `sessionStorage`. File size limit is 20 MB (README says 5 MB — README is wrong).

## Known Naming Inconsistencies

- `terraform/variables.tf` defaults `project_name` to `"bedrock-image-ai"`, but the README calls it `"receipt-scanner"`. `export_receipts.py` hardcodes `"bedrock-image-ai-jobs"`.
- README documents `AnalyzeExpense` but the processor actually calls `AnalyzeDocument` with `FORMS`.
