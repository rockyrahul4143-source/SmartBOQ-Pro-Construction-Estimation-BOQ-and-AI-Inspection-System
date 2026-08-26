"""
Upload SmartBOQ ML models to Hugging Face Hub.

Run once from your local machine:
    python upload_models_to_hf.py

Steps:
1. Go to https://huggingface.co/join  (free account)
2. Go to https://huggingface.co/settings/tokens
3. Create a token with WRITE permission
4. Run: python upload_models_to_hf.py
   (it will ask for your HF_TOKEN and HF_USERNAME)

After upload, set these on Render Environment:
    HF_REPO_ID = <your-username>/smartboq-models
"""
import os
import sys
from pathlib import Path

ML_DIR = Path(__file__).parent / "ml_models"
MODELS = [
    "ResNet50_model.h5",
    "VGG16_model.h5",
    "InceptionV3_model.h5",
    "crack_model.h5",
]

def main():
    # Check models exist
    missing = [m for m in MODELS if not (ML_DIR / m).exists()]
    if missing:
        print(f"Missing models: {missing}")
        print(f"Expected in: {ML_DIR}")
        sys.exit(1)

    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError:
        print("Install: pip install huggingface_hub")
        sys.exit(1)

    token = os.getenv("HF_TOKEN") or input("Enter your Hugging Face WRITE token: ").strip()
    username = os.getenv("HF_USERNAME") or input("Enter your Hugging Face username: ").strip()
    repo_id = f"{username}/smartboq-models"

    api = HfApi()

    # Create repo (private model repo)
    print(f"\nCreating/verifying repo: {repo_id}")
    try:
        create_repo(repo_id=repo_id, repo_type="model", private=False, token=token, exist_ok=True)
        print(f"  Repo ready: https://huggingface.co/{repo_id}")
    except Exception as e:
        print(f"  Repo error: {e}")
        sys.exit(1)

    # Upload each model
    for fname in MODELS:
        path = ML_DIR / fname
        size_mb = path.stat().st_size / 1_048_576
        print(f"\nUploading {fname} ({size_mb:.1f} MB)...")
        try:
            api.upload_file(
                path_or_fileobj=str(path),
                path_in_repo=fname,
                repo_id=repo_id,
                repo_type="model",
                token=token,
            )
            print(f"  ✓ Uploaded {fname}")
        except Exception as e:
            print(f"  ✗ Failed {fname}: {e}")
            sys.exit(1)

    print(f"\n{'='*50}")
    print("ALL MODELS UPLOADED SUCCESSFULLY")
    print(f"Repo: https://huggingface.co/{repo_id}")
    print(f"\nNow set this on Render Environment:")
    print(f"  HF_REPO_ID = {repo_id}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
