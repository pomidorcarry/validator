import json
from pathlib import Path
from typing import Optional

_ELEMENTS_DIR: Optional[Path] = None


def _get_dir() -> Path:
    global _ELEMENTS_DIR
    if _ELEMENTS_DIR is None:
        from ..core.config import settings
        _ELEMENTS_DIR = Path(settings.storage_path) / "elements"
        _ELEMENTS_DIR.mkdir(parents=True, exist_ok=True)
    return _ELEMENTS_DIR


def save_raw(element_id: str, data: dict) -> None:
    p = _get_dir() / f"{element_id}_raw.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_norm(element_id: str, data: dict) -> None:
    p = _get_dir() / f"{element_id}_norm.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_raw(element_id: str) -> dict:
    p = _get_dir() / f"{element_id}_raw.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def load_norm(element_id: str) -> dict:
    p = _get_dir() / f"{element_id}_norm.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def delete(element_id: str) -> None:
    for suffix in ("_raw.json", "_norm.json"):
        p = _get_dir() / f"{element_id}{suffix}"
        if p.exists():
            p.unlink()


def has_storage(element_id: str) -> bool:
    return (_get_dir() / f"{element_id}_raw.json").exists()
