"""Install and enable the built ZIP through Blender's extension installer."""
from pathlib import Path
import sys
import tomllib

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [path for path in sys.path if Path(path or '.').resolve() != ROOT]
version = tomllib.loads((ROOT / 'clock_animator' / 'blender_manifest.toml').read_text(encoding='utf-8'))['version']
extension = ROOT / 'dist' / f'clock_animator-{version}.zip'

repo_dir = ROOT / '.tools' / ('package-repo-' + bpy.app.version_string.replace(' ', '_'))
repo_dir.mkdir(parents=True, exist_ok=True)
repo = bpy.context.preferences.extensions.repos.new(name='Clock Test', module='clock_test', custom_directory=str(repo_dir))
assert bpy.ops.extensions.package_install_files(filepath=str(extension), repo=repo.module, enable_on_install=True) == {'FINISHED'}
module = 'bl_ext.' + repo.module + '.clock_animator'
assert module in sys.modules
installed = sys.modules[module]
assert Path(installed.__file__).resolve().is_relative_to(repo_dir.resolve())
assert Path(installed.__file__).read_bytes() == (ROOT / 'clock_animator' / '__init__.py').read_bytes()
installed_manifest = tomllib.loads(Path(installed.__file__).with_name('blender_manifest.toml').read_text(encoding='utf-8'))
assert installed_manifest['version'] == version
assert hasattr(bpy.types.Scene, 'clock_rig')
bpy.context.scene.clock_rig.auto_axis = False
bpy.context.scene.clock_rig.second = bpy.context.object
assert bpy.ops.clock.apply() == {'FINISHED'}
assert bpy.ops.clock.remove() == {'FINISHED'}
assert bpy.ops.preferences.addon_disable(module=module) == {'FINISHED'}
assert not hasattr(bpy.types.Scene, 'clock_rig')
print('EXTENSION INSTALL PASS', flush=True)
