from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

def load_configs():
    result = {}
    for path in sorted((ROOT / 'configs').glob('*.yaml')):
        config = yaml.safe_load(path.read_text(encoding='utf-8'))
        result[config['id']] = config
    return result

CONFIGS = load_configs()
