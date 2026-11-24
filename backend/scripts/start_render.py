import os
import runpy

runpy.run_path(os.path.join(os.path.dirname(__file__), "initialize_cloud_database.py"), run_name="__main__")
port = os.getenv("PORT", "10000")
os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port, "--proxy-headers"])
