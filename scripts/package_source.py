"""Create a source handoff without dependencies, weights or personal recordings."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts' / 'forma-coach.zip'
OUTPUT.parent.mkdir(exist_ok=True)
source_dirs = ('backend', 'frontend/src', 'frontend/tests', 'frontend/dist', 'configs', 'ml', 'docs', 'scripts', 'tests')
root_files = ('README.md', '.gitignore', 'Start-Forma.cmd', 'requirements.txt', 'requirements-core.txt', 'requirements-ml.txt', 'requirements-lock.txt',
              'frontend/package.json', 'frontend/package-lock.json', 'frontend/tsconfig.json',
              'frontend/vite.config.ts', 'frontend/index.html', 'data/raw/.gitkeep',
              'data/labeled/.gitkeep', 'models/.gitkeep')
files = {ROOT / name for name in root_files if (ROOT / name).is_file()}
for folder in source_dirs:
    for path in (ROOT / folder).rglob('*'):
        if path.is_file() and not any(part in {'__pycache__', 'tmp', 'node_modules', '.pytest_cache'} for part in path.parts):
            if path.suffix not in {'.pyc', '.sqlite3', '.db', '.onnx', '.pt', '.joblib'}:
                files.add(path)
with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, Path('forma-coach') / path.relative_to(ROOT))
print(f'Packaged {len(files)} files: {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)')
