"""
Watches ml_models/ folder for new .h5 files.
When all expected models appear, restarts the backend server.
Run: "C:\Program Files\QGIS 3.44.11\apps\Python312\python.exe" watch_and_restart.py
"""
import sys, os, time, subprocess, pathlib

sys.path.insert(0, r"C:\Program Files\QGIS 3.44.11\apps\Python312\Lib\site-packages")
import site; sys.path.insert(0, site.getusersitepackages())

ML_DIR = pathlib.Path(__file__).parent / "ml_models"
PYTHON = sys.executable

EXPECTED_MODELS = [
    "ResNet50_model.h5",
    "VGG16_model.h5",
    "InceptionV3_model.h5",
    "crack_model.h5",
]

print("Watching ml_models/ for trained model files...")
print(f"Expected: {EXPECTED_MODELS}\n")

last_state = {}

while True:
    current = {}
    for name in EXPECTED_MODELS:
        p = ML_DIR / name
        if p.exists():
            current[name] = p.stat().st_size

    # Show progress
    new_files = [n for n in current if n not in last_state]
    for n in new_files:
        size_mb = round(current[n] / 1_048_576, 1)
        print(f"  [NEW] {n} ({size_mb} MB) — model saved!")

    last_state = current.copy()

    found = [n for n in EXPECTED_MODELS if n in current and current[n] > 1_000_000]
    print(f"\r  Progress: {len(found)}/{len(EXPECTED_MODELS)} models ready "
          f"({', '.join(found) if found else 'waiting...'})", end="", flush=True)

    if len(found) >= 1:   # restart as soon as at least 1 model is ready
        print(f"\n\n  {len(found)} model(s) found! Restarting backend with AI support...")
        # Kill existing backend
        os.system('taskkill /F /FI "WindowTitle eq SmartBOQ Backend*" >nul 2>&1')
        time.sleep(2)
        # Start new backend with Python 3.12
        subprocess.Popen(
            [PYTHON, "start_local_py312.py"],
            cwd=str(pathlib.Path(__file__).parent),
            creationflags=0x00000010,   # CREATE_NEW_CONSOLE
        )
        print("  Backend restarted with TensorFlow!")
        print("  AI Inspection is now LIVE at http://localhost:5173/inspection")
        print(f"  Models loaded: {found}")
        if len(found) < len(EXPECTED_MODELS):
            missing = [n for n in EXPECTED_MODELS if n not in found]
            print(f"  Still training: {missing}")
            print("  Backend will pick up remaining models on next request (lazy loading).")
        break

    time.sleep(10)  # check every 10 seconds
