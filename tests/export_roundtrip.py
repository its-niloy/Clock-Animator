"""Export baked copies, import them again, and compare their sampled world poses."""
from pathlib import Path
import sys

import addon_utils
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import advanced_tests as checks  # noqa: E402
from clock_animator import core, features  # noqa: E402
from clock_animator.constants import TICK  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'tests' / 'output' / ('export-' + bpy.app.version_string.replace(' ', '_'))
OUTPUT.mkdir(parents=True, exist_ok=True)
addon_utils.enable('clock_animator', default_set=False)
addon_utils.enable('io_scene_gltf2', default_set=False)
addon_utils.enable('io_scene_fbx', default_set=False)

for kind in ('GLB', 'FBX'):
    scene, settings, hands, ctrl = checks.fresh(precision=True)
    first, last = 1429, 1465
    scene.frame_start, scene.frame_end = first, last
    ctrl[TICK] = 0
    ctrl.update_tag()
    settings.bake_start, settings.bake_end, settings.bake_step = first, last, 1
    features.bake_copy(scene)
    copies = list(settings.export_collection.objects)
    expected = {}
    for frame in (first, first + 9, first + 18, first + 27, last):
        scene.frame_set(frame)
        expected[frame] = {obj.name: obj.matrix_world.copy() for obj in copies}
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in copies:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    path = OUTPUT / ('clock.' + kind.lower())
    if kind == 'GLB':
        options = dict(filepath=str(path), export_format='GLB', use_selection=True,
                       export_animations=True, export_force_sampling=True, export_frame_range=True)
        properties = bpy.ops.export_scene.gltf.get_rna_type().properties
        if 'export_animation_mode' in properties:
            options['export_animation_mode'] = 'NLA_TRACKS'
        assert bpy.ops.export_scene.gltf(**options) == {'FINISHED'}
    else:
        assert bpy.ops.export_scene.fbx(
            filepath=str(path), use_selection=True, bake_anim=True, bake_anim_use_nla_strips=False,
            bake_anim_use_all_actions=False, bake_anim_step=1, bake_anim_simplify_factor=0,
        ) == {'FINISHED'}
    assert path.exists() and path.stat().st_size > 100
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    if kind == 'GLB':
        assert bpy.ops.import_scene.gltf(filepath=str(path)) == {'FINISHED'}
    else:
        assert bpy.ops.import_scene.fbx(filepath=str(path), anim_offset=0) == {'FINISHED'}
    imported = {name: bpy.data.objects.get(name) for name in expected[first]}
    assert all(imported.values()), (kind, list(bpy.data.objects.keys()))
    first_keys = [point.co.x for obj in imported.values() for curve in core._rotation_curves(obj) for point in curve.keyframe_points]
    assert first_keys, f'{kind}: no animation imported'
    origin = min(first_keys)
    maximum = 0
    for frame, poses in expected.items():
        aligned = frame - first + origin
        scene.frame_set(int(aligned), subframe=aligned - int(aligned))
        for name, matrix in poses.items():
            actual = imported[name].matrix_world
            error = max(abs(actual[i][j] - matrix[i][j]) for i in range(4) for j in range(4))
            maximum = max(maximum, error)
            assert error < 0.002, (kind, name, frame, origin, error, tuple(imported[name].rotation_quaternion),
                                  [(fc.data_path, fc.array_index, [(tuple(p.co)) for p in list(fc.keyframe_points)[:3]]) for fc in core._rotation_curves(imported[name])])
    print(f'EXPORT ROUNDTRIP PASS | {bpy.app.version_string} | {kind} | samples=15 | max_matrix_error={maximum:.9g}', flush=True)
