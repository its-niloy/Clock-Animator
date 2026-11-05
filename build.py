"""Build the Blender extension archive without external libraries."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import tomllib
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / 'clock_animator'


def build(blender=None, plain_zip=False):
    manifest = tomllib.loads((PACKAGE / 'blender_manifest.toml').read_text(encoding='utf-8'))
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    extension = dist / f"clock_animator-{manifest['version']}.zip"
    # Publish only a complete validated archive; a failed build keeps the last ZIP.
    with TemporaryDirectory(prefix='clock-build-', dir=dist) as temporary:
        staged = Path(temporary) / extension.name
        _write_archive(staged, blender, plain_zip)
        os.replace(staged, extension)
    print(f'Extension: {extension}')
    return extension


def _write_archive(extension, blender, plain_zip):
    files = sorted(path for path in PACKAGE.rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc')
    binary = blender or shutil.which('blender')
    used_blender = False
    if binary and not plain_zip:
        profile = ROOT / '.tools' / 'build-profile'
        profile.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env['BLENDER_USER_RESOURCES'] = str(profile)
        env['BLENDER_USER_CONFIG'] = str(profile / 'config')
        result = subprocess.run(
            [binary, '-b', '--factory-startup', '--command', 'extension', 'build',
             '--source-dir', str(PACKAGE), '--output-filepath', str(extension)],
            env=env, capture_output=True, text=True, timeout=180,
        )
        print(result.stdout, end='')
        if result.returncode:
            unsupported = any(s in result.stdout + result.stderr for s in ('unknown command', 'unrecognized arguments', 'Unknown argument', 'command "extension" not found'))
            if not unsupported:
                raise RuntimeError(result.stdout + result.stderr)
        else:
            used_blender = True
    if not used_blender:
        with ZipFile(extension, 'w', ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, path.relative_to(PACKAGE).as_posix())
    with ZipFile(extension) as archive:
        assert 'blender_manifest.toml' in archive.namelist()
        assert '__init__.py' in archive.namelist()
        assert not any('__pycache__' in name for name in archive.namelist())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', help='Path to Blender executable')
    parser.add_argument('--plain-zip', action='store_true', help='Exercise the standard library fallback')
    args = parser.parse_args()
    build(args.blender, args.plain_zip)
