#!/usr/bin/env python3
"""
Basic smoke tests — run after terraform apply + inject_config.py.
Verifies that CloudFront and API Gateway are reachable.
Does not test end-to-end image classification (requires a real browser session).
"""
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TF_DIR = os.path.join(PROJECT_ROOT, "terraform")


def get_tf_outputs() -> dict:
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=TF_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    return {k: v["value"] for k, v in json.loads(result.stdout).items()}


def check_url(url: str, expected_status: int, label: str) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            actual = resp.status
    except urllib.error.HTTPError as exc:
        actual = exc.code
    except Exception as exc:
        print(f"  FAIL  {label}: {exc}")
        return False

    ok = actual == expected_status
    icon = "  OK  " if ok else "  FAIL"
    print(f"{icon}  {label}: expected HTTP {expected_status}, got {actual}")
    return ok


def main() -> None:
    print("Reading Terraform outputs…\n")
    try:
        outputs = get_tf_outputs()
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: could not read Terraform outputs — run terraform apply first.\n{exc}")
        sys.exit(1)

    cf_url = f"https://{outputs['cloudfront_domain']}"
    api_url = outputs["api_invoke_url"].rstrip("/")

    print("Running smoke tests…\n")
    results = [
        check_url(cf_url + "/", 200, "CloudFront index.html"),
        check_url(api_url + "/upload-url", 401, "API /upload-url returns 401 (no auth)"),
    ]

    print(f"\nLogin URL (for manual testing):\n  {outputs['cognito_login_url']}\n")

    if all(results):
        print("All smoke tests passed.")
    else:
        print("Some tests failed — check CloudWatch logs and Terraform outputs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
