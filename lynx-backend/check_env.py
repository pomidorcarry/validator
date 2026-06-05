"""Check .env resolution from config.py perspective."""
import os

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
print(f"_env_path: {os.path.abspath(_env_path)}")
print(f"Exists: {os.path.isfile(_env_path)}")

if os.path.isfile(_env_path):
    with open(_env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip().upper() in ("HTTP_PROXY", "HTTPS_PROXY"):
                    print(f"  {k.strip()} = {v.strip()[:30]}...")
