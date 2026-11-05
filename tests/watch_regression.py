"""Verify the supplied watch, without saving over the source asset."""
from math import acos, degrees, pi
from pathlib import Path
import subprocess
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import clock_animator  # noqa: E402
from clock_animator import core, features  # noqa: E402
from clock_animator.constants import ELAPSED, MODE, OFFSET, RATES, SPEED, START_H, START_M, START_S, TICK  # noqa: E402

clock_animator.register()
bpy.context.window.scene = bpy.data.scenes['Cycles']
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.frame_set(scene.frame_start)
settings = scene.clock_rig
hands = {role: bpy.data.objects[name] for role, name in (
    ('second', 'Circle.028'), ('minute', 'Circle.029'), ('hour', 'Circle.030'))}
for role, obj in hands.items():
    setattr(settings, role, obj)
settings.auto_axis = True
assert core.hand_axis(settings) == 'Z'
rest = {o: o.matrix_basis.copy() for o in hands.values()}
normals = {o: (o.matrix_world.to_3x3().inverted().transposed() @ Vector((0, 0, 1))).normalized() for o in hands.values()}
native = {}
selected, active = list(bpy.context.selected_objects), bpy.context.view_layer.objects.active
pivot = scene.tool_settings.transform_pivot_point
try:
    for obj in selected:
        obj.select_set(False)
    scene.tool_settings.transform_pivot_point = 'INDIVIDUAL_ORIGINS'
    for role, obj in hands.items():
        reference = obj.copy()
        scene.collection.objects.link(reference)
        reference.select_set(True)
        bpy.context.view_layer.objects.active = reference
        bpy.context.view_layer.update()
        assert bpy.ops.transform.rotate(value=pi/12, orient_axis='Z', orient_type='LOCAL', constraint_axis=(False,False,True)) == {'FINISHED'}
        bpy.context.view_layer.update()
        native[role] = reference.matrix_world.copy()
        bpy.data.objects.remove(reference, do_unlink=True)
finally:
    scene.tool_settings.transform_pivot_point = pivot
    for obj in selected:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active
features.setup_helpers(scene, test_rotation=True)
features.refresh(scene)
for role, obj in hands.items():
    preview = next(o for o in settings.helper_collection.objects if o.name.startswith(role.title() + ' +15'))
    normal = (preview.matrix_world.to_3x3().inverted().transposed() @ Vector((0, 0, 1))).normalized()
    assert normal.dot(normals[obj]) > 1-1e-6
    assert max(abs(preview.matrix_world[i][j]-native[role][i][j]) for i in range(4) for j in range(4)) < 1e-6
    loc, rot, scale = rest[obj].decompose()
    expected = Matrix.Translation(loc) @ rot.to_matrix().to_4x4() @ Matrix.Rotation(pi/12, 4, 'Z') @ Matrix.Diagonal((*scale, 1))
    assert max(abs(preview.matrix_basis[i][j]-expected[i][j]) for i in range(4) for j in range(4)) < 1e-6
    assert max(abs(obj.matrix_basis[i][j]-rest[obj][i][j]) for i in range(4) for j in range(4)) < 1e-9
features.clear_helpers(scene)
ctrl = core.apply_rig(scene, settings)
ctrl[START_H], ctrl[START_M], ctrl[START_S], ctrl[MODE], ctrl[TICK] = 0, 0, 0.0, 1, 0
worst = 0.0
for seconds in (0, 2.5, 15, 30, 45, 60, 3600, 43200, -2.5, 86400):
    ctrl[ELAPSED] = float(seconds)
    ctrl.update_tag()
    features.refresh(scene)
    for role, obj in hands.items():
        normal = (obj.matrix_world.to_3x3().inverted().transposed() @ Vector((0, 0, 1))).normalized()
        cosine = min(1, max(-1, normal.dot(normals[obj])))
        worst = max(worst, degrees(acos(cosine)))
        assert cosine > 1-1e-6, (role, seconds, cosine)
        loc, rot, scale = rest[obj].decompose()
        expected = Matrix.Translation(loc) @ rot.to_matrix().to_4x4() @ Matrix.Rotation(RATES[role]*seconds, 4, 'Z') @ Matrix.Diagonal((*scale, 1))
        assert max(abs(obj.matrix_basis[i][j]-expected[i][j]) for i in range(4) for j in range(4)) < 2e-6
assert core.status(settings) == 'Clock animation ready'
ctrl[START_H], ctrl[MODE], ctrl[SPEED], ctrl[OFFSET] = 12, 0, 1.0, float(scene.frame_start)
ctrl.update_tag()
scene.frame_set(scene.frame_start)
settings.ui_page = 'ANIMATE'
settings.axis = 'Z'
if '--' in sys.argv:
    destination = Path(sys.argv[sys.argv.index('--')+1]).resolve()
    assert destination != Path(bpy.data.filepath).resolve()
    bpy.ops.wm.save_as_mainfile(filepath=str(destination), copy=True)
    result = subprocess.run([bpy.app.binary_path, '-b', '--factory-startup', '--disable-autoexec',
                             str(destination), '--python-exit-code', '1', '--python', str(ROOT / 'tests' / 'watch_reopen.py')],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0 and 'WATCH REOPEN PASS' in result.stdout, result.stdout + result.stderr
    print('WATCH REOPEN PASS: fresh process, auto-run disabled, no add-on loaded')
print(f'WATCH REGRESSION PASS: auto axle Z; preview and 30 animated hand poses stay in-plane; maximum float normal angle {worst:.6f} degrees')
