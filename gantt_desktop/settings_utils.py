"""Robust QSettings read/write helpers handling Qt's Linux INI %General group normalization."""
from typing import Any
from PySide6.QtCore import QSettings


def read_setting(settings: QSettings | None, key: str, default: Any = None) -> Any:
    if settings is None:
        return default
    candidates = [key]
    if key.startswith("General/"):
        candidates.append("general/" + key[8:])
        candidates.append(key[8:])
    elif key.startswith("general/"):
        candidates.append("General/" + key[8:])
        candidates.append(key[8:])
    for candidate in candidates:
        val = settings.value(candidate, None)
        if val is not None:
            return val
    return default



def read_bool_setting(settings: QSettings | None, key: str, default: bool = False) -> bool:
    val = read_setting(settings, key, None)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "on")
    return bool(val)


def read_str_setting(settings: QSettings | None, key: str, default: str = "") -> str:
    val = read_setting(settings, key, None)
    if val is None:
        return default
    return str(val)


def write_setting(settings: QSettings | None, key: str, value: Any) -> None:
    if settings is None:
        return
    settings.setValue(key, value)
    if key.startswith("General/"):
        settings.setValue("general/" + key[8:], value)
    elif key.startswith("general/"):
        settings.setValue("General/" + key[8:], value)
    settings.sync()
