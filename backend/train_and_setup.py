"""
SmartBOQ Pro — Auto Train & Setup AI Models
============================================
Run this script with Python 3.12 (QGIS):
  "C:\Program Files\QGIS 3.44.11\apps\Python312\python.exe" train_and_setup.py

What it does:
  1. Installs TensorFlow + dependencies
  2. Trains Model 1: Concrete Crack (ResNet50+VGG16+InceptionV3) from archive.zip
  3. Trains Model 2: Pothole Detection (MobileNetV2) from archive (2).zip
  4. Saves all .h5 files to ml_models/
  5. Verifies models load correctly
"""
import subprocess, sys, os, pathlib

PYTHON = sys.executable
ML_DIR = pathlib.Path(__file__).parent / "ml_models"
ML_DIR.mkdir(exist_ok=True)

DATASET_BASE = pathlib.Path(r"C:\Users\acer\OneDrive\Desktop\Automated Quantity")
ZIP_CRACK    = DATASET_BASE / "archive (1).zip"      # Surface crack dataset
ZIP_POTHOLE  = DATASET_BASE / "archive (2).zip"      # Pothole dataset

# ── Step 1: Install packages ──────────────────────────
def install(pkg):
    print(f"  Installing {pkg}...")
    subprocess.run([PYTHON, "-m", "pip", "install", pkg, "--user", "-q"], check=False)

print("\n" + "="*60)
print(" STEP 1: Installing TensorFlow and dependencies")
print("="*60)
for pkg in ["tensorflow", "numpy", "pillow", "scikit-learn", "opencv-python-headless"]:
    install(pkg)

# Now import
print("\nImporting packages...")
import site
sys.path.insert(0, site.getusersitepackages())

try:
    import tensorflow as tf
    print(f"TensorFlow {tf.__version__} ready")
except ImportError as e:
    print(f"ERROR: TensorFlow not available: {e}")
    sys.exit(1)

import numpy as np
import zipfile, shutil, json, math
from PIL import Image
from sklearn.model_selection import train_test_split
from tensorflow.keras.applications import ResNet50, VGG16, MobileNetV2
from tensorflow.keras import layers, Model
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# ── Step 2: Extract datasets ──────────────────────────
print("\n" + "="*60)
print(" STEP 2: Extracting datasets")
print("="*60)

EXTRACT_DIR = pathlib.Path(r"C:\Users\acer\AppData\Local\Temp\smartboq_datasets")
CRACK_DIR   = EXTRACT_DIR / "crack"
POTHOLE_DIR = EXTRACT_DIR / "pothole"

def extract_if_needed(zip_path, target_dir):
    if not target_dir.exists() or not any(target_dir.rglob("*.jpg")):
        print(f"  Extracting {zip_path.name} ...")
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(target_dir)
        print(f"  Extracted to {target_dir}")
    else:
        print(f"  Already extracted: {target_dir}")

if ZIP_CRACK.exists():
    extract_if_needed(ZIP_CRACK, CRACK_DIR)
else:
    print(f"  WARNING: {ZIP_CRACK} not found")

if ZIP_POTHOLE.exists():
    extract_if_needed(ZIP_POTHOLE, POTHOLE_DIR)
else:
    print(f"  WARNING: {ZIP_POTHOLE} not found")


# ── Helper: load images from folder ──────────────────
def load_images_from_dir(directory, label, size=(120, 120), max_count=3000):
    """Load images from a directory, resize, normalize."""
    images, labels = [], []
    directory = pathlib.Path(directory)
    if not directory.exists():
        return np.array([]), np.array([])
    files = list(directory.glob("*.jpg")) + list(directory.glob("*.png"))
    files = files[:max_count]
    print(f"    Loading {len(files)} images from {directory.name}...")
    for f in files:
        try:
            img = Image.open(f).convert("RGB").resize(size)
            images.append(np.array(img, dtype=np.float32) / 255.0)
            labels.append(label)
        except Exception:
            pass
    return np.array(images), np.array(labels)


# ── Step 3: Train Concrete Crack Model ───────────────
print("\n" + "="*60)
print(" STEP 3: Training Concrete Crack Detection Model")
print("         (ResNet50 - from notebook 1)")
print("="*60)

crack_model_path   = ML_DIR / "ResNet50_model.h5"
vgg16_model_path   = ML_DIR / "VGG16_model.h5"
inception_path     = ML_DIR / "InceptionV3_model.h5"

pos_dir = CRACK_DIR / "Positive"
neg_dir = CRACK_DIR / "Negative"

if pos_dir.exists() and neg_dir.exists():
    IMG_SIZE = (120, 120)
    print("  Loading images (3000 per class for speed)...")
    X_pos, y_pos = load_images_from_dir(pos_dir, 1, IMG_SIZE, max_count=3000)
    X_neg, y_neg = load_images_from_dir(neg_dir, 0, IMG_SIZE, max_count=3000)

    if len(X_pos) > 0 and len(X_neg) > 0:
        X = np.concatenate([X_pos, X_neg])
        y = np.concatenate([y_pos, y_neg])
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        print(f"  Train: {len(X_train)}, Val: {len(X_val)}")

        def build_binary_model(base_app, input_shape=(120,120,3)):
            base = base_app(weights="imagenet", include_top=False, input_shape=input_shape)
            base.trainable = False
            x = layers.GlobalAveragePooling2D()(base.output)
            x = layers.Dense(128, activation="relu")(x)
            x = layers.Dropout(0.5)(x)
            out = layers.Dense(1, activation="sigmoid")(x)
            m = Model(base.input, out)
            m.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
            return m

        es = EarlyStopping(patience=3, restore_best_weights=True, monitor="val_accuracy")

        # Train ResNet50
        print("\n  Training ResNet50...")
        model_r = build_binary_model(ResNet50)
        model_r.fit(X_train, y_train, validation_data=(X_val, y_val),
                    epochs=10, batch_size=32, callbacks=[es], verbose=1)
        model_r.save(str(crack_model_path).replace("ResNet50","ResNet50"))
        model_r.save(str(crack_model_path))
        print(f"  Saved: {crack_model_path}")

        # Train VGG16
        print("\n  Training VGG16...")
        model_v = build_binary_model(VGG16)
        model_v.fit(X_train, y_train, validation_data=(X_val, y_val),
                    epochs=10, batch_size=32, callbacks=[es], verbose=1)
        model_v.save(str(vgg16_model_path))
        print(f"  Saved: {vgg16_model_path}")

        # InceptionV3 needs 150x150
        print("\n  Training InceptionV3 (150x150)...")
        from tensorflow.keras.applications import InceptionV3
        X_pos_iv3, y_pos_iv3 = load_images_from_dir(pos_dir, 1, (150,150), max_count=2000)
        X_neg_iv3, y_neg_iv3 = load_images_from_dir(neg_dir, 0, (150,150), max_count=2000)
        if len(X_pos_iv3) > 0 and len(X_neg_iv3) > 0:
            Xi = np.concatenate([X_pos_iv3, X_neg_iv3])
            yi = np.concatenate([y_pos_iv3, y_neg_iv3])
            Xt, Xv, yt, yv = train_test_split(Xi, yi, test_size=0.2, random_state=42, stratify=yi)
            model_i = build_binary_model(InceptionV3, (150,150,3))
            model_i.fit(Xt, yt, validation_data=(Xv, yv),
                        epochs=10, batch_size=32, callbacks=[es], verbose=1)
            model_i.save(str(inception_path))
            print(f"  Saved: {inception_path}")
    else:
        print("  WARNING: Not enough images found in Positive/Negative folders")
else:
    print(f"  WARNING: Crack dataset folders not found at {pos_dir} / {neg_dir}")


# ── Step 4: Train Pothole Model ───────────────────────
print("\n" + "="*60)
print(" STEP 4: Training Pothole Detection Model")
print("         (MobileNetV2 - from notebook 2)")
print("="*60)

pothole_model_path = ML_DIR / "crack_model.h5"
PATCH_SIZE = 160

img_dir = POTHOLE_DIR / "annotated-images"
if img_dir.exists():
    import xml.etree.ElementTree as ET
    import random, cv2

    all_images = list(img_dir.glob("*.jpg"))
    print(f"  Found {len(all_images)} pothole images")

    # Build balanced patch dataset
    PATCH_DIR = EXTRACT_DIR / "patches"
    (PATCH_DIR / "POSITIVE").mkdir(parents=True, exist_ok=True)
    (PATCH_DIR / "NEGATIVE").mkdir(parents=True, exist_ok=True)

    patch_rows = []
    for img_path in all_images:
        xml_path = img_path.with_suffix(".xml")
        try:
            img_cv = cv2.imread(str(img_path))
            if img_cv is None or not xml_path.exists():
                continue
            h, w, _ = img_cv.shape
            tree = ET.parse(xml_path)
            boxes = []
            for obj in tree.findall("object"):
                if obj.find("name").text.lower() == "pothole":
                    b = obj.find("bndbox")
                    boxes.append([int(b.find("xmin").text), int(b.find("ymin").text),
                                  int(b.find("xmax").text), int(b.find("ymax").text)])
            # Positive patches
            for i, (x1, y1, x2, y2) in enumerate(boxes):
                cx, cy = (x1+x2)//2, (y1+y2)//2
                r = PATCH_SIZE // 2
                px1, py1, px2, py2 = max(0,cx-r), max(0,cy-r), min(w,cx+r), min(h,cy+r)
                patch = img_cv[py1:py2, px1:px2]
                if patch.shape[0] > 20 and patch.shape[1] > 20:
                    p_path = PATCH_DIR / "POSITIVE" / f"pos_{img_path.stem}_{i}.jpg"
                    cv2.imwrite(str(p_path), patch)
                    patch_rows.append((str(p_path), 1))
            # Negative patches
            count = 0
            for _ in range(50):
                if count >= 3: break
                nx1 = random.randint(0, max(0, w-PATCH_SIZE))
                ny1 = random.randint(0, max(0, h-PATCH_SIZE))
                nx2, ny2 = nx1+PATCH_SIZE, ny1+PATCH_SIZE
                overlap = any(not(nx2<bx1 or nx1>bx2 or ny2<by1 or ny1>by2) for bx1,by1,bx2,by2 in boxes)
                if not overlap:
                    patch = img_cv[ny1:ny2, nx1:nx2]
                    n_path = PATCH_DIR / "NEGATIVE" / f"neg_{img_path.stem}_{count}.jpg"
                    cv2.imwrite(str(n_path), patch)
                    patch_rows.append((str(n_path), 0))
                    count += 1
        except Exception as ex:
            continue

    print(f"  Generated {len(patch_rows)} patches")
    if len(patch_rows) > 50:
        random.shuffle(patch_rows)
        paths, labels_p = zip(*patch_rows)

        def load_patch(p, size=(160,160)):
            try:
                return np.array(Image.open(p).convert("RGB").resize(size), dtype=np.float32) / 255.0
            except:
                return None

        print("  Loading patches into arrays...")
        imgs, labs = [], []
        for p, l in zip(paths, labels_p):
            img = load_patch(p)
            if img is not None:
                imgs.append(img)
                labs.append(l)

        X = np.array(imgs)
        y = np.array(labs)
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        print(f"  Train: {len(X_train)}, Val: {len(X_val)}")

        # Build MobileNetV2
        base = MobileNetV2(input_shape=(160,160,3), include_top=False, weights="imagenet")
        base.trainable = False
        x = layers.GlobalAveragePooling2D()(base.output)
        x = layers.Dropout(0.2)(x)
        out = layers.Dense(1, activation="sigmoid")(x)
        pothole_model = Model(base.input, out)
        pothole_model.compile(optimizer=tf.keras.optimizers.Adam(1e-4),
                              loss="binary_crossentropy", metrics=["accuracy"])

        print("\n  Training MobileNetV2 (Phase 1)...")
        es2 = EarlyStopping(patience=3, restore_best_weights=True, monitor="val_accuracy")
        pothole_model.fit(X_train, y_train, validation_data=(X_val, y_val),
                          epochs=10, batch_size=32, callbacks=[es2], verbose=1)

        # Fine-tune
        base.trainable = True
        for layer in base.layers[:-30]:
            layer.trainable = False
        pothole_model.compile(optimizer=tf.keras.optimizers.Adam(1e-5),
                              loss="binary_crossentropy", metrics=["accuracy"])
        print("\n  Training MobileNetV2 (Phase 2 fine-tune)...")
        pothole_model.fit(X_train, y_train, validation_data=(X_val, y_val),
                          epochs=10, batch_size=32, callbacks=[es2], verbose=1)

        pothole_model.save(str(pothole_model_path))
        print(f"  Saved: {pothole_model_path}")
else:
    print(f"  WARNING: Pothole dataset not found at {img_dir}")


# ── Step 5: Verify ────────────────────────────────────
print("\n" + "="*60)
print(" STEP 5: Verifying saved models")
print("="*60)
for name, path in [
    ("ResNet50 Crack",    crack_model_path),
    ("VGG16 Crack",       vgg16_model_path),
    ("InceptionV3 Crack", inception_path),
    ("MobileNetV2 Pothole", pothole_model_path),
]:
    if path.exists():
        size_mb = round(path.stat().st_size / 1_048_576, 1)
        try:
            m = tf.keras.models.load_model(str(path))
            print(f"  {name}: LOADED OK ({size_mb} MB) — input {m.input_shape}")
            del m
        except Exception as e:
            print(f"  {name}: EXISTS but LOAD FAILED — {e}")
    else:
        print(f"  {name}: NOT FOUND at {path}")

print("\n" + "="*60)
print(" DONE! All models trained and saved to ml_models/")
print(" Restart the backend to use AI inspection features.")
print("="*60)
