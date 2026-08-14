#!/usr/bin/env bash
# Install Terraform, AWS CLI v2, and Python dependencies — no sudo required.
# Run this once before anything else. Re-running is safe (idempotent).
set -euo pipefail

LOCAL_BIN="$HOME/.local/bin"
mkdir -p "$LOCAL_BIN"
export PATH="$LOCAL_BIN:$PATH"

# ── Terraform ──────────────────────────────────────────────────────────────────
if ! command -v terraform &>/dev/null; then
  echo "=== Installing Terraform ==="
  TF_VERSION="1.9.8"
  curl -sL "https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_amd64.zip" \
    -o /tmp/terraform.zip
  python3 -c "
import zipfile, os
with zipfile.ZipFile('/tmp/terraform.zip') as z:
    z.extract('terraform', '$LOCAL_BIN')
os.chmod('$LOCAL_BIN/terraform', 0o755)
"
  echo "Terraform $(terraform version -json | python3 -c 'import sys,json;print(json.load(sys.stdin)[\"terraform_version\"])')"
else
  echo "Terraform already installed: $(terraform version | head -1)"
fi

# ── AWS CLI v2 ─────────────────────────────────────────────────────────────────
if ! command -v aws &>/dev/null; then
  echo "=== Installing AWS CLI v2 ==="
  curl -sL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  python3 -c "import zipfile; zipfile.ZipFile('/tmp/awscliv2.zip').extractall('/tmp/')"
  /tmp/aws/install \
    --install-dir "$HOME/.local/aws-cli" \
    --bin-dir "$LOCAL_BIN" \
    --update
  echo "AWS CLI $(aws --version)"
else
  echo "AWS CLI already installed: $(aws --version)"
fi

# ── Python venv + dependencies ─────────────────────────────────────────────────
VENV="$HOME/.local/venv"
if [ ! -d "$VENV" ]; then
  echo "=== Creating Python venv ==="
  # Try normal venv; fall back to --without-pip if ensurepip is absent
  python3 -m venv "$VENV" 2>/dev/null || \
    python3 -m venv --without-pip "$VENV"

  # Bootstrap pip if the venv was created without it
  if ! "$VENV/bin/python" -m pip --version &>/dev/null; then
    echo "Bootstrapping pip…"
    curl -sS "https://bootstrap.pypa.io/get-pip.py" | "$VENV/bin/python"
  fi
fi

echo "=== Installing Python dependencies ==="
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet boto3 Pillow "python-jose[cryptography]"

# ── Auto-generate terraform.tfvars ────────────────────────────────────────────
echo ""
echo "=== AWS credentials check ==="
echo "Set these environment variables before continuing:"
echo "  export AWS_ACCESS_KEY_ID=..."
echo "  export AWS_SECRET_ACCESS_KEY=..."
echo "  export AWS_DEFAULT_REGION=ap-southeast-2"
echo "  export AWS_SESSION_TOKEN=...  # if using temporary credentials"
echo ""
echo "Then run:"
echo "  ACCOUNT_ID=\$(aws sts get-caller-identity --query Account --output text)"
echo "  COGNITO_PREFIX=\"bedrock-image-ai-\${ACCOUNT_ID: -6}\""
echo '  cat > terraform/terraform.tfvars <<EOF'
echo '  project_name          = "bedrock-image-ai"'
echo '  aws_account_id        = "${ACCOUNT_ID}"'
echo '  cognito_domain_prefix = "${COGNITO_PREFIX}"'
echo '  primary_region        = "ap-southeast-2"'
echo '  environment           = "demo"'
echo '  EOF'
echo ""
echo "=== Setup complete ==="
echo "Add $LOCAL_BIN to your PATH: export PATH=\"$LOCAL_BIN:\$PATH\""
