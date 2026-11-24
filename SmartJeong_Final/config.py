import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def _merge(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base

def load_config():
    with open(BASE_DIR / 'config.json', 'r') as f:
        config = json.load(f)

    local_file = BASE_DIR / 'config.local.json'
    if local_file.exists():
        with open(local_file, 'r') as f:
            config = _merge(config, json.load(f))
    return config
