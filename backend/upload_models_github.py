"""
Upload SmartBOQ ML models to GitHub Releases.

This creates a release tag 'ml-models-v1' on your GitHub repo
and uploads all 4 .h5 model files as release assets.

GitHub supports files up to 2GB per asset — perfect for our 258MB models.
No new account needed — uses your existing GitHub token.

Usage:
    python upload_models_github.py

You will be prompted for your GitHub token.
Generate one at: https://github.com/settings/tokens/new
Required scope: repo (full repo access)
"""
import os
import sys
import json
import hashlib
from pathlib import Path

REPO   = "rockyrahul4143-source/SmartBOQ-Pro-Construction-Estimation-BOQ-and-AI-Inspection-System"
TAG    = "ml-models-v1"
ML_DIR = Path(__file__).parent / "ml_models"
MODELS = [
    "ResNet50_model.h5",
    "VGG16_model.h5",
    "InceptionV3_model.h5",
    "crack_model.h5",
]

def main():
    # Verify models exist
    for m in MODELS:
        p = ML_DIR / m
        if not p.exists():
            print(f"ERROR: Missing {p}")
            sys.exit(1)
        print(f"  Found {m} ({p.stat().st_size/1_048_576:.1f} MB)")

    import urllib.request
    import urllib.error

    token = os.getenv("GITHUB_TOKEN") or input("\nEnter your GitHub token (repo scope): ").strip()
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "SmartBOQ-Model-Uploader/1.0",
    }

    # Step 1: Create (or get existing) release
    print(f"\n[1/2] Creating GitHub release '{TAG}'...")
    release_url = f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}"
    try:
        req = urllib.request.Request(release_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            release = json.loads(resp.read())
        print(f"      Release already exists: {release['html_url']}")
        upload_url = release["upload_url"].replace("{?name,label}", "")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Create new release
            payload = json.dumps({
                "tag_name": TAG,
                "name": "ML Model Weights v1",
                "body": "SmartBOQ Pro AI Inspection model weights.\n\nModels:\n- ResNet50_model.h5 (Crack detection)\n- VGG16_model.h5 (Crack detection)\n- InceptionV3_model.h5 (Crack detection)\n- crack_model.h5 (Road damage / pothole)",
                "draft": False,
                "prerelease": False,
            }).encode()
            req = urllib.request.Request(
                f"https://api.github.com/repos/{REPO}/releases",
                data=payload,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                release = json.loads(resp.read())
            print(f"      Created: {release['html_url']}")
            upload_url = release["upload_url"].replace("{?name,label}", "")
        else:
            print(f"      ERROR: {e}")
            sys.exit(1)

    # Step 2: Upload each model as a release asset
    print(f"\n[2/2] Uploading model files...")
    raw_headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "SmartBOQ-Model-Uploader/1.0",
    }

    # Get existing assets to avoid re-uploading
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/releases/{release['id']}/assets",
        headers=raw_headers,
    )
    with urllib.request.urlopen(req) as resp:
        existing = {a["name"]: a["browser_download_url"] for a in json.loads(resp.read())}

    download_urls = dict(existing)

    for fname in MODELS:
        if fname in existing:
            print(f"  SKIP {fname} — already uploaded")
            print(f"       URL: {existing[fname]}")
            continue

        path = ML_DIR / fname
        size = path.stat().st_size
        print(f"  Uploading {fname} ({size/1_048_576:.1f} MB)...")

        with open(path, "rb") as f:
            data = f.read()

        asset_headers = {**raw_headers, "Content-Type": "application/octet-stream"}
        req = urllib.request.Request(
            f"{upload_url}?name={fname}",
            data=data,
            headers=asset_headers,
            method="POST",
        )
        req.add_header("Content-Length", str(len(data)))

        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                asset = json.loads(resp.read())
                url = asset["browser_download_url"]
                download_urls[fname] = url
                print(f"  OK  {fname}")
                print(f"      URL: {url}")
        except Exception as e:
            print(f"  FAIL {fname}: {e}")
            sys.exit(1)

    # Step 3: Print the env vars to set on Render
    print(f"\n{'='*60}")
    print("ALL MODELS UPLOADED SUCCESSFULLY")
    print(f"{'='*60}")
    print(f"\nRelease: https://github.com/{REPO}/releases/tag/{TAG}")
    print(f"\nSet these Environment Variables on Render:")
    print(f"  MODEL_DOWNLOAD_TAG = {TAG}")
    print(f"  GITHUB_MODELS_REPO = {REPO}")
    print(f"\nDirect download URLs (for reference):")
    for fname, url in download_urls.items():
        print(f"  {fname}: {url}")
    print(f"{'='*60}")

    # Save URLs to a config file for the startup script
    config = {
        "repo": REPO,
        "tag": TAG,
        "models": download_urls,
    }
    config_path = Path(__file__).parent / "ml_models" / "download_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\nConfig saved to: {config_path}")

if __name__ == "__main__":
    main()
