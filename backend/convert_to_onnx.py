"""
Convert Keras .h5 models to ONNX format for Render deployment.
Run: python convert_to_onnx.py
"""
import sys, os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

from pathlib import Path
import numpy as np

ML_DIR = Path(__file__).parent / "ml_models"

MODELS = [
    ("crack_model.h5",       (1, 160, 160, 3)),   # smallest first
    ("VGG16_model.h5",       (1, 120, 120, 3)),
    ("ResNet50_model.h5",    (1, 120, 120, 3)),
    ("InceptionV3_model.h5", (1, 150, 150, 3)),
]

def convert_one(h5_name, input_shape):
    h5_path   = ML_DIR / h5_name
    onnx_path = ML_DIR / h5_name.replace(".h5", ".onnx")

    if not h5_path.exists():
        print(f"SKIP {h5_name} — file not found"); return False
    if onnx_path.exists():
        print(f"OK   {onnx_path.name} already exists ({onnx_path.stat().st_size/1e6:.1f} MB)"); return True

    print(f"Loading {h5_name}...", flush=True)
    import tensorflow as tf
    model = tf.keras.models.load_model(str(h5_path), compile=False)
    print(f"  Loaded. Converting to ONNX...", flush=True)

    import tf2onnx
    import onnx
    spec = (tf.TensorSpec(input_shape, tf.float32, name="input"),)
    model_proto, _ = tf2onnx.convert.from_keras(model, input_signature=spec, opset=13)
    onnx.save(model_proto, str(onnx_path))
    size = onnx_path.stat().st_size / 1e6
    print(f"  Saved {onnx_path.name} ({size:.1f} MB) ✓", flush=True)
    del model
    return True

if __name__ == "__main__":
    print("=== ONNX Conversion ===")
    for h5, shape in MODELS:
        try:
            convert_one(h5, shape)
        except Exception as e:
            print(f"FAIL {h5}: {e}", flush=True)

    print("\n=== Results ===")
    for f in sorted(ML_DIR.glob("*.onnx")):
        print(f"  {f.name}  {f.stat().st_size/1e6:.1f} MB")
