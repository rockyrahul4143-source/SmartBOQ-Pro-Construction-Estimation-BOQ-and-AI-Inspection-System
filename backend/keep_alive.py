"""
Keep-alive wrapper: restarts the backend automatically if it crashes.
Run: python keep_alive.py
"""
import subprocess, sys, time, os, site

# Fix _sqlite3.dll for QGIS Python 3.12
for dll_path in [r"C:\Python314\DLLs",
                 r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\DLLs"]:
    if os.path.exists(dll_path):
        os.environ["PATH"] = dll_path + os.pathsep + os.environ.get("PATH", "")

os.environ['DATABASE_URL']    = 'sqlite:///./smartboq.db'
os.environ['SECRET_KEY']      = 'local-dev-secret-key-smartboq-pro-2024'
os.environ['ALLOWED_ORIGINS'] = '*'

PYTHON = sys.executable
SCRIPT = 'start_local_py312.py'

print('SmartBOQ Backend Keep-Alive started.')
while True:
    print(f'\n[{time.strftime("%H:%M:%S")}] Starting backend...')
    proc = subprocess.run([PYTHON, SCRIPT])
    print(f'[{time.strftime("%H:%M:%S")}] Backend stopped (exit {proc.returncode}). Restarting in 3s...')
    time.sleep(3)
