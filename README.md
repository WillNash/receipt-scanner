# Image Emotion Classifier

A demo web application that lets authenticated users upload images and have them classified as **happy** or **sad** using [Meta Llama 3.2 Vision 11B](https://aws.amazon.com/bedrock/) via Amazon Bedrock. Results include a label, confidence score, and reasoning from the model.

## Architecture

```
Browser
  │
  ├── CloudFront ──► S3 (static frontend)
  │
  ├── API Gateway ──► Lambda (api) ──► DynamoDB   (presigned URL + job status)
  │
  └── S3 presigned PUT ──► S3 (uploads)
                                │
                           S3 event notification
                                │
                               SQS
                                │
                           Lambda (processor) ──► Bedrock us-east-1
                                │                 (Llama 3.2 Vision 11B)
                                └──► DynamoDB     (write result)
```

**All infrastructure runs in `ap-southeast-2` (Sydney).** The processor Lambda calls Bedrock in `us-east-1` by configuring its boto3 client with `region_name="us-east-1"` — Llama 3.2 Vision is only available via the US cross-region inference profile.

### AWS services used

| Service | Purpose |
|---|---|
| CloudFront + S3 | Static frontend hosting |
| Cognito | User authentication (hosted UI, OAuth2 code flow) |
| API Gateway | REST API (`POST /upload-url`, `GET /jobs/{jobId}`) |
| Lambda (api) | Presigned URL generation, JWT validation, job polling |
| Lambda (processor) | Image resize, Bedrock inference, result storage |
| S3 (uploads) | Temporary image storage |
| SQS | Decouples S3 upload events from Lambda processing |
| DynamoDB | Job status and results |
| IAM | Least-privilege roles for both Lambda functions |
| Bedrock | Llama 3.2 Vision 11B inference (us-east-1) |

## Prerequisites

- An AWS account with permissions to create the resources above
- Python 3.11+ on your local machine
- Internet access (to download Terraform and AWS CLI)

## Deploy

### 1. Enable Bedrock model access

**Do this first** — model access approval must be in place before Terraform apply.

1. Open the AWS Console and switch to **us-east-1**
2. Go to **Amazon Bedrock → Model access**
3. Click **Modify model access**
4. Find **Meta Llama 3.2 11B Instruct** and enable it
5. Accept Meta's licence terms and save — approval is usually instant

### 2. Install tools

Run once. No `sudo` required — everything installs into `~/.local/`.

```bash
cd bedrock-image-ai
bash scripts/install_tools.sh
export PATH="$HOME/.local/bin:$HOME/.local/venv/bin:$PATH"
```

This installs:
- Terraform 1.9.8
- AWS CLI v2
- Python dependencies (boto3, Pillow, python-jose) into a local venv

### 3. Configure AWS credentials

```bash
export AWS_ACCESS_KEY_ID="your-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="ap-southeast-2"
# If using temporary credentials (SSO, assumed role):
export AWS_SESSION_TOKEN="your-session-token"

# Verify
aws sts get-caller-identity
```

### 4. Generate `terraform.tfvars`

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
COGNITO_PREFIX="bedrock-image-ai-${ACCOUNT_ID: -6}"

cat > terraform/terraform.tfvars <<EOF
project_name          = "bedrock-image-ai"
aws_account_id        = "${ACCOUNT_ID}"
cognito_domain_prefix = "${COGNITO_PREFIX}"
primary_region        = "ap-southeast-2"
environment           = "demo"
EOF
```

The Cognito domain prefix must be globally unique across all AWS accounts. If Terraform fails with a domain conflict, change `cognito_domain_prefix` to something unique and re-apply.

### 5. Deploy

```bash
make deploy
```

This runs in sequence:
1. `scripts/package_lambdas.sh` — builds Lambda deployment packages with platform-correct binary wheels
2. `terraform init && terraform apply` — provisions all AWS infrastructure (~10–15 min; CloudFront creation is the slowest step)
3. `scripts/inject_config.py` — reads Terraform outputs, injects them into the frontend, and syncs to S3

When complete, the app URL is printed:

```
Done! App live at: https://d1234abcd.cloudfront.net/
```

### 6. Smoke test

```bash
make smoke
```

Checks that CloudFront returns HTTP 200 and the API returns HTTP 401 (no auth — confirms Lambda is reachable and Cognito enforcement is active). Prints the login URL for manual browser testing.

## Usage

1. Open the CloudFront URL in a browser
2. You are redirected to the Cognito hosted UI — register an account or sign in
3. After login you are redirected back to the app
4. Drop or select an image (JPEG, PNG, GIF, or WebP; max 3.75 MB)
5. Click **Analyse**
6. Watch the status update every 3 seconds: `PENDING → PROCESSING → COMPLETE`
7. The result displays the emotion label, confidence score, and the model's reasoning

To share the demo with others, send them the CloudFront URL. Each user registers their own Cognito account and can only see their own results.

## Project structure

```
bedrock-image-ai/
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
│   ├── dynamodb.tf                 # jobs table, PAY_PER_REQUEST, TTL
│   ├── iam.tf                      # least-privilege roles for both Lambdas
│   ├── lambda.tf                   # processor + api functions, SQS ESM
│   ├── api_gateway.tf              # REST API, CORS, gateway responses
│   └── terraform.tfvars.example
├── lambda/
│   ├── processor/
│   │   ├── handler.py              # SQS consumer → Bedrock → DynamoDB
│   │   └── requirements.txt        # Pillow
│   └── api/
│       ├── handler.py              # presigned URL + job polling, JWT validation
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

Destroys all AWS resources. S3 buckets must be empty first — empty them manually or add a `force_destroy = true` argument to both bucket resources in `terraform/s3.tf` before running destroy.

## Known limitations

| Limitation | Detail |
|---|---|
| Model region | Llama 3.2 Vision is only available in US regions. All Bedrock calls route to `us-east-1` via cross-region inference profile. |
| Model EOL | Llama 3.2 Vision 11B is marked Legacy (EOL July 2026). If it becomes unavailable, change `BEDROCK_MODEL_ID` in `terraform/lambda.tf` to `us.meta.llama3-2-90b-instruct-v1:0` or `us.amazon.nova-pro-v1:0`. |
| Image size | Max 3.75 MB per image; max 1120×1120 px (images are auto-resized before inference). |
| Processing time | Typically 15–45 seconds end-to-end depending on Bedrock latency. |
| No job history | The UI shows the result of the most recent upload in the current session only. |
