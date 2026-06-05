"""Quick test: does the proxy get loaded and used?"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

# Before importing config, check env
print(f"HTTP_PROXY before import: {os.environ.get('HTTP_PROXY', '(not set)')}")
print(f"HTTPS_PROXY before import: {os.environ.get('HTTPS_PROXY', '(not set)')}")

from app.core.config import settings, _env_path

# After config import
print(f"\n_env_path: {_env_path}")
print(f"Exists: {os.path.isfile(_env_path)}")
print(f"HTTP_PROXY after config: {os.environ.get('HTTP_PROXY', '(not set)')}")
print(f"HTTPS_PROXY after config: {os.environ.get('HTTPS_PROXY', '(not set)')}")
print(f"API key: {settings.openai_api_key[:15]}...")
print(f"Model: {settings.openai_model}")
