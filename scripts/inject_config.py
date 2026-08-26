#!/usr/bin/env python3
"""
Read Terraform outputs, write frontend/.env.production with VITE_* vars,
build the Vue frontend with `npm run build`, then sync dist/ to the S3
frontend bucket.
"""
import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TF_DIR = os.path.join(PROJECT_ROOT, "terraform")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")
APP_JS_TMPL = os.path.join(FRONTEND_DIR, "app.js.template")
APP_JS_OUT = os.path.join(FRONTEND_DIR, "app.js")
FLUTTER_CONFIG_DIR = os.path.join(PROJECT_ROOT, "mobile_new", "lib", "core", "config")
FLUTTER_CONFIG_TMPL = os.path.join(FLUTTER_CONFIG_DIR, "app_config.dart.template")
FLUTTER_CONFIG_OUT = os.path.join(FLUTTER_CONFIG_DIR, "app_config.dart")


def get_tf_outputs() -> dict:
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=TF_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    return {k: v["value"] for k, v in json.loads(result.stdout).items()}


def _build_config_values(outputs: dict) -> dict:
    """Return the five config values derived from Terraform outputs."""
    cf_domain = outputs["cloudfront_domain"]
    api_url = outputs["api_invoke_url"].rstrip("/")
    client_id = outputs["cognito_client_id"]
    redirect_uri = f"https://{cf_domain}/callback"

    # Use the dedicated cognito_base_url output — no fragile regex parsing
    cognito_base = outputs["cognito_base_url"]
    token_url = f"{cognito_base}/oauth2/token"
    login_url = (
        f"{cognito_base}/login"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&scope=email+openid+profile"
        f"&redirect_uri={redirect_uri}"
    )
    return {
        "api_url":      api_url,
        "login_url":    login_url,
        "token_url":    token_url,
        "client_id":    client_id,
        "redirect_uri": redirect_uri,
    }


def write_env_file(outputs: dict) -> None:
    """Write frontend/.env.production with VITE_* variables for Vite build."""
    cfg = _build_config_values(outputs)
    env_path = os.path.join(FRONTEND_DIR, ".env.production")
    lines = [
        f"VITE_API_BASE_URL={cfg['api_url']}",
        f"VITE_COGNITO_LOGIN_URL={cfg['login_url']}",
        f"VITE_COGNITO_TOKEN_URL={cfg['token_url']}",
        f"VITE_COGNITO_CLIENT_ID={cfg['client_id']}",
        f"VITE_REDIRECT_URI={cfg['redirect_uri']}",
    ]
    with open(env_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Env file written → {env_path}")


def build_frontend() -> None:
    """Install npm dependencies (if needed) then build."""
    import shutil
    if not shutil.which("npm"):
        print("ERROR: npm not found. Install Node.js 20+ then re-run.", file=sys.stderr)
        print("  Ubuntu/Debian: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs", file=sys.stderr)
        print("  macOS:         brew install node", file=sys.stderr)
        sys.exit(1)

    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.isdir(node_modules):
        print("Installing frontend dependencies…")
        subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True)

    print("Building frontend…")
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True)
    print(f"Frontend built → {DIST_DIR}")


def inject_flutter_config(outputs: dict) -> None:
    if not os.path.exists(FLUTTER_CONFIG_TMPL):
        print("Flutter config template not found — skipping Flutter config injection.")
        return

    replacements = {
        "__API_BASE_URL__":      outputs["api_invoke_url"].rstrip("/"),
        "__COGNITO_CLIENT_ID__": outputs["cognito_client_id"],
        "__COGNITO_BASE_URL__":  outputs["cognito_base_url"].rstrip("/"),
    }

    with open(FLUTTER_CONFIG_TMPL) as f:
        content = f.read()

    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)

    with open(FLUTTER_CONFIG_OUT, "w") as f:
        f.write(content)

    print(f"Flutter config injected → {FLUTTER_CONFIG_OUT}")


def sync_to_s3(bucket_name: str, region: str) -> None:
    subprocess.run(
        [
            "aws", "s3", "sync", DIST_DIR, f"s3://{bucket_name}/",
            "--delete",
            "--region", region,
            "--cache-control", "max-age=0,no-cache",
        ],
        check=True,
    )
    print(f"Frontend synced → s3://{bucket_name}/")


def main() -> None:
    print("Reading Terraform outputs…")
    outputs = get_tf_outputs()

    region = outputs.get("primary_region", "ap-southeast-2")

    write_env_file(outputs)
    build_frontend()
    inject_flutter_config(outputs)
    sync_to_s3(outputs["frontend_bucket_name"], region)

    print(f"\nDone! App live at: https://{outputs['cloudfront_domain']}/")


if __name__ == "__main__":
    main()
