# Receipt Scanner

A demo web application that lets authenticated users upload receipt images and have them scanned using [Amazon Textract](https://aws.amazon.com/textract/) (`AnalyzeExpense`). Results include the vendor name, date, total, and a line-item breakdown. Multiple receipts can be uploaded and scanned in parallel.

## Architecture

```
Browser
  │
  ├── CloudFront ──► S3 (static frontend)
  │
  ├── API Gateway ──► Lambda (api) ──► DynamoDB   (presigned URL, job status, receipt history)
  │
  └── S3 presigned PUT ──► S3 (uploads)
                                │
                           S3 event notification
                                │
                               SQS
                                │
                           Lambda (processor) ──► Textract AnalyzeExpense
                                │                 (ap-southeast-2)
                                └──► DynamoDB     (write result)
```

**All infrastructure runs in `ap-southeast-2` (Sydney).** Textract is called in the same region as the uploads bucket — no cross-region routing required.

### AWS services used

| Service | Purpose |
|---|---|
| CloudFront + S3 | Static frontend hosting |
| Cognito | User authentication (hosted UI, OAuth2 code flow) |
| API Gateway | REST API (`POST /upload-url`, `GET /jobs/{jobId}`, `GET /receipts`) |
| Lambda (api) | Presigned URL generation, JWT validation, job polling, receipt history |
| Lambda (processor) | Textract inference, result storage |
| S3 (uploads) | Temporary image storage |
| SQS | Decouples S3 upload events from Lambda processing |
| DynamoDB | Job status and results (with GSI for per-user receipt history) |
| Textract | `AnalyzeExpense` — extracts vendor, date, total, and line items |
| IAM | Least-privilege roles for both Lambda functions |

## Prerequisites

- An AWS account with permissions to create the resources above
- Python 3.11+ on your local machine
- Internet access (to download Terraform and AWS CLI)

## Deploy

### 1. Install tools

Run once. No `sudo` required — everything installs into `~/.local/`.

```bash
bash scripts/install_tools.sh
export PATH="$HOME/.local/bin:$HOME/.local/venv/bin:$PATH"
```

This installs:
- Terraform 1.9.8
- AWS CLI v2
- Python dependencies (boto3, python-jose) into a local venv

### 2. Configure AWS credentials

```bash
export AWS_ACCESS_KEY_ID="your-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="ap-southeast-2"
# If using temporary credentials (SSO, assumed role):
export AWS_SESSION_TOKEN="your-session-token"

# Verify
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

The Cognito domain prefix must be globally unique across all AWS accounts. If Terraform fails with a domain conflict, change `cognito_domain_prefix` to something unique and re-apply.

### 4. Deploy

```bash
make deploy
```

This runs in sequence:
1. `scripts/package_lambdas.sh` — builds Lambda deployment packages
2. `terraform init && terraform apply` — provisions all AWS infrastructure (~10–15 min; CloudFront creation is the slowest step)
3. `scripts/inject_config.py` — reads Terraform outputs, injects them into the frontend, and syncs to S3

When complete, the app URL is printed:

```
Done! App live at: https://d1234abcd.cloudfront.net/
```

### 5. Smoke test

```bash
make smoke
```

Checks that CloudFront returns HTTP 200 and the API returns HTTP 401 (no auth — confirms Lambda is reachable and Cognito enforcement is active). Prints the login URL for manual browser testing.

## Usage

Open the CloudFront URL printed at the end of `make deploy`.

1. You are redirected to the Cognito hosted UI — register an account or sign in
2. After login you are redirected back to the upload page
3. Drop or select one or more receipt images (JPEG or PNG, max 5 MB each)
4. Click **Scan receipts**
5. All receipts are uploaded and scanned in parallel — status updates every 3 seconds
6. Each completed receipt displays vendor, date, total, and a line-item table
7. Previous receipts appear in the **Recent receipts** history section below

To share the demo with others, send them the CloudFront URL. Each person registers their own Cognito account and can only see their own receipts.

## Project structure

```
receipt-scanner/
├── Makefile                        # deploy, plan, smoke, destroy targets
├── scripts/
│   ├── install_tools.sh            # one-time tool installation
│   ├── package_lambdas.sh          # build Lambda deployment packages
│   ├── inject_config.py            # inject Terraform outputs into frontend
│   └── smoke_test.py               # post-deploy sanity checks
├── terraform/
│   ├── providers.tf                # AWS provider, ap-southeast-2
│   ├── variables.tf
│   ├── outputs.tf
│   ├── cognito.tf                  # user pool, hosted UI, app client
│   ├── s3.tf                       # frontend bucket (OAC) + uploads bucket (CORS)
│   ├── cloudfront.tf               # distribution with OAC and SPA error handling
│   ├── sqs.tf                      # main queue (360s visibility) + DLQ
│   ├── dynamodb.tf                 # jobs table, PAY_PER_REQUEST, TTL, user GSI
│   ├── iam.tf                      # least-privilege roles for both Lambdas
│   ├── lambda.tf                   # processor + api functions, SQS ESM
│   ├── api_gateway.tf              # REST API, CORS, gateway responses
│   └── terraform.tfvars.example
├── lambda/
│   ├── processor/
│   │   ├── handler.py              # SQS consumer → Textract AnalyzeExpense → DynamoDB
│   │   └── requirements.txt
│   └── api/
│       ├── handler.py              # presigned URL, job polling, receipt history, JWT validation
│       └── requirements.txt        # python-jose[cryptography]
└── frontend/
    ├── index.html
    ├── app.js.template             # source of truth — placeholders injected at deploy
    └── styles.css
```

> `frontend/app.js` and `terraform/terraform.tfvars` are generated files and are `.gitignore`d.

## Re-deploying after changes

**Terraform or Lambda changes:**
```bash
make deploy
```

**Frontend-only changes:**
```bash
python3 scripts/inject_config.py
```

## Teardown

```bash
make destroy
```

Destroys all AWS resources. S3 buckets must be empty first — empty them manually or add `force_destroy = true` to both bucket resources in `terraform/s3.tf` before running destroy.

## Rate limiting

API Gateway throttling is applied at two levels:

| Scope | Limit | Why |
|---|---|---|
| All methods (combined) | 10 req/s, burst 20 | Hard cap on total API traffic — returns HTTP 429 when exceeded |
| `POST /upload-url` only | 2 req/s, burst 5 | Tighter limit since each call triggers a Textract analysis job |

This is stage-level (aggregate across all callers). For per-IP isolation add WAF with a rate-based rule (~$6/month):

```hcl
# terraform/waf.tf
resource "aws_wafv2_web_acl" "api" {
  name  = "${var.project_name}-waf"
  scope = "REGIONAL"
  ...
  rule {
    name     = "rate-limit-per-ip"
    priority = 1
    action { block {} }
    statement {
      rate_based_statement {
        limit              = 100   # requests per 5-minute window per IP
        aggregate_key_type = "IP"
      }
    }
  }
}

resource "aws_wafv2_web_acl_association" "api" {
  resource_arn = aws_api_gateway_stage.main.arn
  web_acl_arn  = aws_wafv2_web_acl.api.arn
}
```

## Known limitations

| Limitation | Detail |
|---|---|
| Image formats | JPEG and PNG only — Textract `AnalyzeExpense` does not support GIF or WebP. |
| Image size | Max 5 MB per image. |
| Receipt quality | Textract accuracy depends on image clarity. Poor lighting or low resolution will reduce field extraction quality. |
| Processing time | Typically 5–20 seconds end-to-end depending on Textract latency. |
| Receipt history | Shows the 20 most recent completed receipts per user (DynamoDB GSI with `Limit=20`). |
