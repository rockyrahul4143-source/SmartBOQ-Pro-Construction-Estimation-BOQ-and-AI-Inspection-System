"""
Local dev server. Run: python start_local.py
"""
import sys, os

os.environ["DATABASE_URL"]    = "sqlite:///./smartboq.db"
os.environ["SECRET_KEY"]      = "local-dev-secret-key-smartboq-pro-2024"
os.environ["ALLOWED_ORIGINS"] = "*"

site_pkg = r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages"
if site_pkg not in sys.path:
    sys.path.insert(0, site_pkg)

if __name__ == "__main__":
    import uvicorn
    print("🚀  SmartBOQ Pro API starting on http://localhost:8000")
    print("📖  API Docs: http://localhost:8000/docs")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
