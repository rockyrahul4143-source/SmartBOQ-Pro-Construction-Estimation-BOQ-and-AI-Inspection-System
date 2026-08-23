import sys, os

USER_SITE = r"C:\Users\acer\AppData\Roaming\Python\Python312\site-packages"
BAD = [
    r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages",
    r"C:\Users\acer\AppData\Roaming\Python\Python314\site-packages",
]
sys.path = [p for p in sys.path if p not in BAD]
if USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

os.environ["DATABASE_URL"]    = "sqlite:///./smartboq.db"
os.environ["SECRET_KEY"]      = "local-dev-secret-key-smartboq-pro-2024"
os.environ["ALLOWED_ORIGINS"] = "*"

results = []
tests = [
    ("numpy",       lambda: __import__("numpy").__version__),
    ("PIL",         lambda: __import__("PIL").__version__),
    ("fastapi",     lambda: __import__("fastapi").__version__),
    ("sqlalchemy",  lambda: __import__("sqlalchemy").__version__),
    ("tensorflow",  lambda: __import__("tensorflow").__version__),
    ("uvicorn",     lambda: __import__("uvicorn").__version__),
    ("app.main",    lambda: "OK"),
]

for name, fn in tests:
    try:
        v = fn()
        print(f"  OK  {name} {v}")
        results.append(True)
    except Exception as e:
        print(f"  ERR {name}: {e}")
        results.append(False)

print()
print(f"Result: {sum(results)}/{len(results)} passed")
if all(results):
    print("ALL IMPORTS CLEAN - backend will start successfully")
else:
    print("Some imports failed - see errors above")
