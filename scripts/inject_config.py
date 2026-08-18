#!/usr/bin/env python3
"""
Read Terraform outputs and inject config values into frontend/app.js (from template).
Re-runs are idempotent: always reads from app.js.template (source of truth with placeholders),
writes resolved content to app.js (generated, .gitignored).
Then syncs frontend/ to the S3 frontend bucket.
"""
import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TF_DIR = os.path.join(PROJECT_ROOT, "terraform")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
APP_JS_TMPL = os.path.join(FRONTEND_DIR, "app.js.template")
APP_JS_OUT = os.path.join(FRONTEND_DIR, "app.js")
FLUTTER_CONFIG_DIR = os.path.join(PROJECT_ROOT, "mobile", "lib", "core", "config")
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


def inject_config(outputs: dict) -> None:
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

    replacements = {
        "__API_BASE_URL__":      api_url,
        "__COGNITO_LOGIN_URL__": login_url,
        "__COGNITO_TOKEN_URL__": token_url,
        "__COGNITO_CLIENT_ID__": client_id,
        "__REDIRECT_URI__":      redirect_uri,
    }

    # Always read from the template — never the previously generated file
    with open(APP_JS_TMPL) as f:
        content = f.read()

    for placeholder, value in replacements.items():
        content = content.replace(f'"{placeholder}"', f'"{value}"')

    with open(APP_JS_OUT, "w") as f:
        f.write(content)

    print(f"Config injected → {APP_JS_OUT}")


def inject_flutter_config(outputs: dict) -> None:
    if not os.path.exists(FLUTTER_CONFIG_TMPL):
        print("Flutter config template not found — skipping Flutter config injection.")
        return

    replacements = {
        "__API_BASE_URL__":      outputs["api_invoke_url"].rstrip("/"),
        "__COGNITO_CLIENT_ID__": outputs["cognito_client_id"],
        "__COGNITO_BASE_URL__":  outputs["cognito_base_url"].rstrip("/"),
        "__COGNITO_REGION__":    outputs.get("primary_region", "ap-southeast-2"),
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
            "aws", "s3", "sync", FRONTEND_DIR, f"s3://{bucket_name}/",
            "--delete",
            "--region", region,
            "--cache-control", "max-age=0,no-cache",
            "--exclude", "*.template",  # do not upload the source template
        ],
        check=True,
    )
    print(f"Frontend synced → s3://{bucket_name}/")


def main() -> None:
    print("Reading Terraform outputs…")
    outputs = get_tf_outputs()

    region = outputs.get("primary_region", "ap-southeast-2")

    inject_config(outputs)
    inject_flutter_config(outputs)
    sync_to_s3(outputs["frontend_bucket_name"], region)

    print(f"\nDone! App live at: https://{outputs['cloudfront_domain']}/")


if __name__ == "__main__":
    main()
