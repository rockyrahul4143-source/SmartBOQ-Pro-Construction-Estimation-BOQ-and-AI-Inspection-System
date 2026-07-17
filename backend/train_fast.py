import sys, os, site, pathlib, time

USER_SITE = site.getusersitepackages()
if USER_SITE and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)
GIS_SITE = r'C:\Program Files\QGIS 3.44.11\apps\Python312\Lib\site-packages'
if os.path.exists(GIS_SITE) and GIS_SITE not in sys.path:
    sys.path.insert(0, GIS_SITE)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['DATABASE_URL'] = 'sqlite:///./smartboq.db'
os.environ['SECRET_KEY'] = 'local-dev-secret-key-smartboq-pro-2024'
os.environ['ALLOWED_ORIGINS'] = '*'

print('='*60)
print('  SmartBOQ Pro - Fast AI Model Training')
print('  Dataset: smartboq-pro/Datasets/Positive + Negative')
print('='*60)

try:
    import tensorflow as tf
    print(f'  TensorFlow {tf.__version__} ready')
except ImportError:
    import subprocess
    subprocess.run([sys.executable,'-m','pip','install','tensorflow','--user','-q'], check=False)
    sys.path.insert(0, site.getusersitepackages())
    import tensorflow as tf
    print(f'  TensorFlow {tf.__version__} ready')

import numpy as np
from PIL import Image
from sklearn.model_selection import train_test_split

BASE_DIR    = pathlib.Path(__file__).parent
ML_DIR      = BASE_DIR / 'ml_models'
ML_DIR.mkdir(exist_ok=True)
DATASET_DIR = BASE_DIR.parent / 'Datasets'
POS_DIR     = DATASET_DIR / 'Positive'
NEG_DIR     = DATASET_DIR / 'Negative'

pos = len(list(POS_DIR.glob('*.jpg'))) if POS_DIR.exists() else 0
neg = len(list(NEG_DIR.glob('*.jpg'))) if NEG_DIR.exists() else 0
print(f'  Positive: {pos} images | Negative: {neg} images')
if pos == 0 or neg == 0:
    print('ERROR: Dataset not found. Expected:')
    print(f'  {POS_DIR}')
    print(f'  {NEG_DIR}')
    sys.exit(1)

def load_images(folder, label, size=(120,120), max_count=1500):
    folder = pathlib.Path(folder)
    files  = sorted(folder.glob('*.jpg'))[:max_count]
    images, labels = [], []
    print(f'    Loading {len(files)} from {folder.name}/ ...', flush=True)
    for i, f in enumerate(files):
        try:
            img = Image.open(f).convert('RGB').resize(size)
            images.append(np.array(img, dtype=np.float32) / 255.0)
            labels.append(label)
        except:
            pass
        if (i+1) % 500 == 0:
            print(f'      {i+1}/{len(files)}...', flush=True)
    return np.array(images, dtype=np.float32), np.array(labels, dtype=np.float32)

def build_model(base_fn, input_shape=(120,120,3)):
    base = base_fn(weights='imagenet', include_top=False, input_shape=input_shape)
    base.trainable = False
    x = tf.keras.layers.GlobalAveragePooling2D()(base.output)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dense(128, activation='relu')(x)
    x = tf.keras.layers.Dropout(0.4)(x)
    out = tf.keras.layers.Dense(1, activation='sigmoid')(x)
    m = tf.keras.Model(base.input, out)
    m.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return m

def es():
    return tf.keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True, monitor='val_accuracy')

def train_model(tag, path, base_fn, img_size, max_per_class):
    if path.exists():
        print(f'\n  {tag} already exists ({round(path.stat().st_size/1048576,1)} MB) - SKIP')
        return
    print(f'\n  Training {tag} ({img_size[0]}x{img_size[1]})...', flush=True)
    t0 = time.time()
    Xp,yp = load_images(POS_DIR, 1, img_size, max_per_class)
    Xn,yn = load_images(NEG_DIR, 0, img_size, max_per_class)
    X = np.concatenate([Xp,Xn]); y = np.concatenate([yp,yn])
    Xt,Xv,yt,yv = train_test_split(X,y, test_size=0.2, random_state=42, stratify=y)
    print(f'    Train:{len(Xt)} Val:{len(Xv)}', flush=True)
    m = build_model(base_fn, (*img_size, 3))
    m.fit(Xt,yt, validation_data=(Xv,yv), epochs=15, batch_size=64, callbacks=[es()], verbose=1)
    m.save(str(path))
    print(f'  SAVED: {path.name} ({round(path.stat().st_size/1048576,1)} MB) in {round(time.time()-t0)}s')
    del m,X,y,Xp,Xn,yp,yn,Xt,Xv,yt,yv

from tensorflow.keras.applications import ResNet50, VGG16, InceptionV3, MobileNetV2

train_model('[1/4] ResNet50',    ML_DIR/'ResNet50_model.h5',    ResNet50,    (120,120), 1500)
train_model('[2/4] VGG16',       ML_DIR/'VGG16_model.h5',       VGG16,        (120,120), 1500)
train_model('[3/4] InceptionV3', ML_DIR/'InceptionV3_model.h5', InceptionV3, (150,150), 1200)

mp = ML_DIR / 'crack_model.h5'
if not mp.exists():
    print('\n  Training [4/4] MobileNetV2 (160x160)...', flush=True)
    t0 = time.time()
    Xp,yp = load_images(POS_DIR, 1, (160,160), 1200)
    Xn,yn = load_images(NEG_DIR, 0, (160,160), 1200)
    X = np.concatenate([Xp,Xn]); y = np.concatenate([yp,yn])
    Xt,Xv,yt,yv = train_test_split(X,y, test_size=0.2, random_state=42, stratify=y)
    base = MobileNetV2(input_shape=(160,160,3), include_top=False, weights='imagenet')
    base.trainable = False
    xb = tf.keras.layers.GlobalAveragePooling2D()(base.output)
    xb = tf.keras.layers.Dropout(0.2)(xb)
    out = tf.keras.layers.Dense(1, activation='sigmoid')(xb)
    m   = tf.keras.Model(base.input, out)
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-4), loss='binary_crossentropy', metrics=['accuracy'])
    m.fit(Xt,yt, validation_data=(Xv,yv), epochs=10, batch_size=64, callbacks=[es()], verbose=1)
    base.trainable = True
    for lyr in base.layers[:-30]: lyr.trainable = False
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-5), loss='binary_crossentropy', metrics=['accuracy'])
    m.fit(Xt,yt, validation_data=(Xv,yv), epochs=5, batch_size=32, callbacks=[es()], verbose=1)
    m.save(str(mp))
    print(f'  SAVED crack_model.h5 ({round(mp.stat().st_size/1048576,1)} MB) in {round(time.time()-t0)}s')
    del m,X,y,Xp,Xn,yp,yn,Xt,Xv,yt,yv
else:
    print('\n  [4/4] MobileNetV2 already exists - SKIP')

print('\n'+'='*60)
print('  VERIFICATION')
print('='*60)
all_ok = True
for name, path in [
    ('ResNet50', ML_DIR/'ResNet50_model.h5'),
    ('VGG16', ML_DIR/'VGG16_model.h5'),
    ('InceptionV3', ML_DIR/'InceptionV3_model.h5'),
    ('MobileNetV2', ML_DIR/'crack_model.h5'),
]:
    if path.exists():
        sz = round(path.stat().st_size/1048576,1)
        try:
            m2 = tf.keras.models.load_model(str(path)); del m2
            print(f'  OK  {name}: {sz} MB')
        except Exception as e:
            print(f'  ERR {name}: {e}'); all_ok=False
    else:
        print(f'  !!  {name}: NOT FOUND'); all_ok=False
print('='*60)
print('  ALL 4 MODELS READY!' if all_ok else '  Some models missing.')
print('='*60)
