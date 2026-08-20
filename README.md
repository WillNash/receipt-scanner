# Receipt Scanner

A demo web application and Flutter mobile app that lets authenticated users upload receipt photos and extract structured data from them. Results include vendor name, date, total, and a per-line-item breakdown with quantities, unit prices, and discounts.

## How it works

Processing uses a two-stage pipeline:

1. **Receipt crop** — OpenCV detects and crops the receipt from the photo using three methods tried in priority order: bright-region detection (white receipt on coloured background), Canny edge contours (general case), and MSER text-density (fallback). The crop is stored in S3.
2. **OCR** — Amazon Textract `DetectDocumentText` extracts the raw text lines from the cropped image, preserving reading order and spatial layout.
3. **Reasoning** — Claude Haiku 4.5 (Amazon Bedrock, cross-region inference) receives the Textract text and returns structured JSON via tool use: vendor, date, total, and per-item description, quantity, unit price, price, and discount.

**Cost per receipt:** ~$0.01 (Textract $0.0015 + Haiku input/output tokens ~$0.008).

## Architecture

```
Browser / Flutter app
  │
  ├── CloudFront ──► S3 (static frontend)
  │
  ├── API Gateway ──► Lambda (api) ──► DynamoDB   (presigned URL, job status, receipt history, edit)
  │
  └── S3 presigned PUT ──► S3 uploads/
                                │
                           S3 event (uploads/ prefix only)
                                │
                               SQS
                                │
                           Lambda (processor)
                                ├── OpenCV crop ──► S3 cropped/
                                ├── Textract DetectDocumentText
                                ├── Bedrock Claude Haiku 4.5
                                └── DynamoDB (jobs, line_items, image_hashes)
```

**All infrastructure runs in `ap-southeast-2` (Sydney).** Bedrock calls route via the `au.` cross-region inference profile to the nearest supported region.

### AWS services

| Service | Purpose |
|---|---|
| CloudFront + S3 | Static frontend hosting |
| Cognito | User authentication (hosted UI, OAuth2 code flow) |
| API Gateway | REST API (`POST /upload-url`, `GET /jobs/{jobId}`, `GET /receipts`, `PATCH /receipts/{jobId}`) |
| Lambda (api) | Presigned URL generation, JWT validation, job polling, receipt history, edit |
| Lambda (processor) | Receipt crop, Textract OCR, Bedrock reasoning, result storage |
| S3 (uploads) | Image storage (`uploads/`, `cropped/`, `debug/` prefixes) |
| SQS | Decouples S3 upload events from Lambda processing; prevents duplicate processing |
| DynamoDB | Three tables: `jobs` (status + results), `line_items` (per-item analytics), `image_hashes` (dedup) |
| Textract | `DetectDocumentText` — accurate OCR optimised for degraded/low-contrast receipts |
| Bedrock | Claude Haiku 4.5 (`au.anthropic.claude-haiku-4-5-20251001-v1:0`) — structured data extraction and reasoning |
| IAM | Least-privilege roles for both Lambda functions |

### DynamoDB tables

| Table | PK / SK | Notes |
|---|---|---|
| `{project_name}-jobs` | PK: `job_id`; GSI: `user_id` + `created_at` | Job status, results, and rate-limit counters |
| `{project_name}-image-hashes` | PK: `user_id`, SK: `image_hash` | Duplicate image detection |
| `{project_name}-line-items` | PK: `user_id`, SK: `item_sk`; GSI: `desc_created` | Per-line-item analytics |

## Prerequisites

- An AWS account with permissions to create the resources above
- Anthropic Claude Haiku 4.5 access enabled via AWS Marketplace in your account
- Python 3.11+ on your local machine
- Internet access (to download Terraform and AWS CLI)

## Deploy

### 1. Install tools

```bash
bash scripts/install_tools.sh
export PATH="$HOME/.local/bin:$HOME/.local/venv/bin:$PATH"
```

Installs Terraform 1.9.8, AWS CLI v2, and Python dependencies into `~/.local/`.

### 2. Configure AWS credentials

```bash
export AWS_ACCESS_KEY_ID="your-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="ap-southeast-2"
# If using temporary credentials:
export AWS_SESSION_TOKEN="your-session-token"

aws sts get-caller-identity
```

### 3. Generate `terraform.tfvars`

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
COGNITO_PREFIX="receipt-scanner-${ACCOUNT_ID: -6}"

cat > terraform/terraform.tfvars <<EOF
project_name          = "receipt-scanner"
aws_account_id        = "${ACCOUNT_ID}"
cognito_domain_prefix = "${COGNITO_PREFIX}"
primary_region        = "ap-southeast-2"
environment           = "demo"
EOF
```

The Cognito domain prefix must be globally unique. If Terraform fails with a domain conflict, change `cognito_domain_prefix` and re-apply.

### 4. Deploy

```bash
make deploy
```

Runs in sequence:
1. `scripts/package_lambdas.sh` — builds Lambda deployment packages (processor zip goes via S3 due to opencv-python-headless size)
2. `terraform init && terraform apply` — provisions all AWS infrastructure (~10–15 min; CloudFront creation is the slowest step)
3. `scripts/inject_config.py` — injects Terraform outputs into the frontend and Flutter config, syncs to S3

```
Done! App live at: https://d1234abcd.cloudfront.net/
```

### 5. Smoke test

```bash
make smoke
```

Checks CloudFront returns HTTP 200 and the API returns HTTP 401 (auth required).

## Usage

### Web

1. Open the CloudFront URL and sign in via Cognito
2. Upload one or more receipt photos (JPEG, PNG, or HEIC, max 20 MB each)
3. Processing takes ~10–30 seconds — status updates automatically
4. Completed receipts show vendor, date, total, and line items
5. Each history card has download buttons: **Cropped image**, **Raw OCR (Textract)**, and **AI parsed (Haiku)** for debugging
6. Receipts can be edited (vendor, date, line items) via the Edit button

### Rate limits

| Scope | Limit |
|---|---|
| Daily uploads per user | 50 |
| Global uploads (all users) | 100 |

### Debugging

The history page shows three download buttons per receipt:
- **Cropped image** — the OpenCV-cropped JPEG sent to Textract
- **Raw OCR (Textract)** — the text lines extracted by Textract, in reading order
- **AI parsed (Haiku)** — the structured JSON returned by Claude Haiku 4.5

If items are missing, start with the cropped image to confirm the crop captured the full receipt, then check the Raw OCR file to see if Textract read the missing lines.

## Project structure

```
receipt-scanner/
├── Makefile
├── scripts/
│   ├── install_tools.sh
│   ├── package_lambdas.sh
│   ├── inject_config.py
│   ├── smoke_test.py
│   ├── export_receipts.py          # dump jobs table to CSV
│   └── visualize_textract.py       # overlay Textract bounding boxes on image
├── terraform/
│   ├── providers.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── cognito.tf
│   ├── s3.tf                       # frontend bucket + uploads bucket (CORS)
│   ├── cloudfront.tf
│   ├── sqs.tf                      # main queue (360s visibility) + DLQ
│   ├── dynamodb.tf                 # jobs, line_items, image_hashes tables
│   ├── iam.tf
│   ├── lambda.tf
│   ├── api_gateway.tf
│   └── terraform.tfvars.example
├── lambda/
│   ├── processor/
│   │   ├── handler.py              # SQS consumer → crop → Textract → Bedrock → DynamoDB
│   │   └── requirements.txt        # opencv-python-headless, boto3
│   └── api/
│       ├── handler.py              # presigned URLs, job polling, history, edit, JWT validation
│       └── requirements.txt        # python-jose[cryptography]
├── frontend/
│   ├── index.html
│   ├── app.js.template             # source of truth — placeholders injected at deploy time
│   └── styles.css
└── mobile_new/                     # Flutter iOS/Android app
    └── lib/
        ├── features/
        │   ├── auth/               # Cognito PKCE via flutter_appauth
        │   ├── upload/             # camera, gallery picker, saved captures, upload queue
        │   └── receipts/           # history, pull-to-refresh, edit sheet
        └── ...
```

> `frontend/app.js` and `terraform/terraform.tfvars` are generated and `.gitignore`d.

## Flutter mobile app

The Flutter app in `mobile_new/` connects to the same AWS backend.

**Features:**
- Sign in via Cognito hosted UI (PKCE flow)
- Take photos with the camera — saved to a local `receipt-scanner-images/` folder
- Pick from the device gallery
- Pick from previously taken captures (the Saved tab); processed captures move to a `processed/` subfolder automatically and are restored if the receipt is deleted
- Long-press a saved capture to delete it from the device
- Upload queue with per-item status (uploading → processing → complete/duplicate/failed)
- Receipt history with line items, quantities, unit prices, and discounts
- Edit vendor, date, and line items inline

**Setup:**

`make deploy` automatically injects the API URL and Cognito client ID into `mobile_new/lib/core/config/app_config.dart`.

```bash
cd mobile_new
flutter pub get
flutter run          # connected device or simulator
flutter build apk    # Android release APK
flutter build ipa    # iOS (requires Xcode)
```

## Re-deploying after changes

```bash
make deploy           # Terraform + Lambda + frontend
python3 scripts/inject_config.py   # frontend-only changes
```

## Teardown

```bash
make destroy
```

S3 buckets must be empty first — empty them manually in the console, or add `force_destroy = true` to both bucket resources in `terraform/s3.tf` before running destroy.

## Known limitations

| Limitation | Detail |
|---|---|
| Image formats | JPEG, PNG, HEIC (HEIC is converted to JPEG before processing) |
| Image size | Max 20 MB per upload |
| Bedrock availability | Claude Haiku 4.5 requires AWS Marketplace subscription and Anthropic use case form submission |
| Processing time | Typically 10–30 seconds (crop + Textract + Bedrock round-trip) |
| Receipt history | Shows the 20 most recent completed receipts per user |
| Duplicate detection | Based on SHA-256 hash of the original image — re-uploads of the same photo are marked DUPLICATE and not reprocessed |
