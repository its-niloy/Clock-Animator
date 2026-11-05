"""Run inside real Blender; exceptions must result in a nonzero process exit."""
import math
from pathlib import Path
import struct
import subprocess
import sys
import traceback

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clock_animator import core  # noqa: E402
from clock_animator.constants import (  # noqa: E402
    AXES, CROWN_AXIS, CROWN_RATIO, CROWN_REST, CROWN_SOURCE,
    FACTORS, HAND_KEYS, OFFSET, RATES, REST, RIG_ID, ROTATION_ORDERS,
    SPEED, START_H, START_M, START_S, TICK, TIME,
)

OUTPUT = ROOT / 'tests' / 'output' / bpy.app.version_string.replace(' ', '_')
OUTPUT.mkdir(parents=True, exist_ok=True)
MAX_IDEAL_ERROR = 0.0
CHECKS = 0
ROWS = []


def f32(value):
    return struct.unpack('f', struct.pack('f', value))[0]


def check_angles(scene, ctrl, hands, bases=None, axis=1, reverse=False, frames=(1, 24, 25, 48, 1441, 86401)):
    global MAX_IDEAL_ERROR, CHECKS
    for frame in frames:
        scene.frame_set(frame)
        ideal_t = ctrl[START_H] * 3600 + ctrl[START_M] * 60 + ctrl[START_S] + (frame - ctrl[OFFSET]) * scene.render.fps_base / scene.render.fps * ctrl[SPEED]
        # Blender evaluates driver results and rotation RNA as single precision.
        t = f32(ideal_t)
        assert abs(ctrl[TIME] - t) < 1e-6, (ctrl[TIME], t)
        for role, hand in hands.items():
            base = bases[role][axis] if bases else 0
            rate = RATES[role] * (-1 if reverse else 1)
            actual = hand.rotation_euler[axis]
            stored = f32(base + float(f'{rate:.15f}') * (math.floor(t) if ctrl[TICK] else t))
            ideal = base + rate * (math.floor(ideal_t) if ctrl[TICK] else ideal_t)
            assert abs(actual - stored) < 1e-6, (role, frame, actual, stored)
            MAX_IDEAL_ERROR = max(MAX_IDEAL_ERROR, abs(actual - ideal))
            CHECKS += 1
        for obj in (ctrl, *hands.values()):
            for curve in core.drivers(obj):
                assert curve.driver.is_simple_expression
                assert curve.driver.is_valid
                assert len(curve.modifiers) == 0


def fresh():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 250
    scene.render.fps, scene.render.fps_base = 24, 1.0
    scene.frame_set(1)
    settings = scene.clock_rig
    settings.axis, settings.reverse = 'Y', False
    settings.auto_axis = False
    settings.precision = False
    settings.use_crown, settings.crown, settings.crown_axis = False, None, 'X'
    hands = {}
    for role in FACTORS:
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.object
        obj.name = 'Hand_' + role.title()
        # Geometry points up along Z with the origin at the clock center.
        for vertex in obj.data.vertices:
            vertex.co.x *= 0.06
            vertex.co.y *= 0.04
            vertex.co.z = (vertex.co.z + 0.5) * (1.0 + len(hands) * 0.2)
        hands[role] = obj
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in hands.values():
        obj.select_set(True)
    bpy.context.view_layer.objects.active = hands['second']
    assert bpy.ops.clock.assign() == {'FINISHED'}
    assert all(getattr(settings, role) == obj for role, obj in hands.items())
    return scene, settings, hands


def apply(settings):
    assert bpy.ops.clock.apply() == {'FINISHED'}
    return settings.controller


def set_controls(scene, ctrl, **values):
    for key, value in values.items():
        ctrl[key] = value
    ctrl.update_tag()
    scene.frame_set(scene.frame_current)


def expect_error(operator, text):
    try:
        result = operator()
        assert result == {'CANCELLED'}, result
    except RuntimeError as error:
        assert text.lower() in str(error).lower(), str(error)


def test_basic():
    scene, settings, hands = fresh()
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    ctrl = apply(settings)
    assert ctrl.type == 'EMPTY' and ctrl.hide_render
    assert ctrl[START_H] == 12 and ctrl[TICK] == 1 and ctrl[OFFSET] == 1
    assert ctrl.id_properties_ui(START_H).as_dict()['max'] == 23
    for tick in (1, 0):
        set_controls(scene, ctrl, tick=tick)
        check_angles(scene, ctrl, hands)
    assert core.status(settings) == 'Clock animation ready'


def test_rates():
    scene, settings, hands = fresh()
    ctrl = apply(settings)
    for fps, fb in [(25, 1.0), (30, 1.0), (24, 1.001)]:
        scene.render.fps, scene.render.fps_base = fps, fb
        for speed in (2.0, -1.0):
            for tick in (0, 1):
                set_controls(scene, ctrl, start_h=3, start_m=45, start_s=10.0, speed=speed, tick=tick)
                check_angles(scene, ctrl, hands)
    scene.frame_start = 100
    core.remove_rig(settings, clear_slots=False)
    ctrl = apply(settings)
    assert ctrl[OFFSET] == 100.0


def test_axes_parent_and_restore():
    for axis in 'XYZ':
        scene, settings, hands = fresh()
        settings.axis, settings.reverse = axis, True
        parent = bpy.data.objects.new('Parent', None)
        scene.collection.objects.link(parent)
        parent.rotation_euler = (0.4, 0.2, -0.7)
        hands['second'].parent = parent
        for hand in hands.values():
            hand.rotation_euler = (0.1, -0.2, 0.3)
        bases = {role: tuple(hand.rotation_euler) for role, hand in hands.items()}
        driven_bases = {role: tuple(hand.rotation_euler.to_quaternion().to_euler(ROTATION_ORDERS[axis]))
                        for role, hand in hands.items()}
        ctrl = apply(settings)
        check_angles(scene, ctrl, hands, driven_bases, AXES[axis], True)
        original_values = {role: tuple(obj.rotation_euler) for role, obj in hands.items()}
        for _ in range(2):
            ctrl = apply(settings)
            assert all(tuple(obj.rotation_euler) == original_values[role] for role, obj in hands.items())
        name = ctrl.name
        assert bpy.ops.clock.remove() == {'FINISHED'}
        assert name not in bpy.data.objects and settings.controller is None
        for role, obj in hands.items():
            assert tuple(obj.rotation_euler) == bases[role]
            assert not core.drivers(obj)
            assert all(key not in obj for key in HAND_KEYS)
            assert getattr(settings, role) is None


def test_rotation_modes():
    for mode in ('QUATERNION', 'AXIS_ANGLE', 'ZYX'):
        scene, settings, hands = fresh()
        obj = hands['second']
        obj.rotation_euler = (0.2, 0.3, -0.4)
        obj.rotation_quaternion = (0.9238795, 0, 0.3826834, 0)
        obj.rotation_axis_angle = (0.5, 0, 1, 0)
        obj.rotation_mode = mode
        rest = tuple(obj.rotation_euler)
        quaternion, aa = tuple(obj.rotation_quaternion), tuple(obj.rotation_axis_angle)
        bpy.context.view_layer.update()
        matrix = obj.matrix_basis.copy()
        apply(settings)
        assert list(obj[REST]) == list(rest)
        scene.frame_set(1)
        # Default 12h is whole revolutions; compare the effective pose with float RNA tolerance.
        assert obj.rotation_mode == ROTATION_ORDERS[settings.axis]
        assert max(abs(obj.matrix_basis[i][j] - matrix[i][j]) for i in range(4) for j in range(4)) < 0.001
        core.remove_rig(settings)
        assert obj.rotation_mode == mode and tuple(obj.rotation_euler) == rest
        assert tuple(obj.rotation_quaternion) == quaternion and tuple(obj.rotation_axis_angle) == aa


def test_local_axis_rotation():
    """Compare actual Local gizmo rotation with the driven pose, not Euler numbers."""
    from mathutils import Euler

    for axis in 'YXZ':
        for mode in ('XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX', 'QUATERNION', 'AXIS_ANGLE'):
            for reverse in (False, True):
                scene, settings, hands = fresh()
                obj = hands['second']
                settings.minute, settings.hour = None, None
                settings.axis, settings.reverse = axis, reverse
                for other in hands.values():
                    other.select_set(other == obj)
                parent = bpy.data.objects.new('Tilted_Parent', None)
                scene.collection.objects.link(parent)
                parent.location = (-0.3, 0.6, 0.2)
                parent.rotation_euler = (0.23, -0.42, 0.6)
                parent.scale = (1.2, 1.2, 1.2)
                obj.parent = parent
                obj.location = (0.2, -0.3, 0.5)
                obj.scale = (1.4, 0.7, 1.2)
                rotation = Euler((1.1, 0.65, -0.7), 'XYZ').to_quaternion()
                obj.rotation_mode = mode
                if mode == 'QUATERNION':
                    obj.rotation_quaternion = rotation
                elif mode == 'AXIS_ANGLE':
                    vector, angle = rotation.to_axis_angle()
                    obj.rotation_axis_angle = (angle, *vector)
                else:
                    obj.rotation_euler = rotation.to_euler(mode)
                bpy.context.view_layer.update()
                rest_basis = obj.matrix_basis.copy()
                spindle = obj.matrix_world.to_3x3().col[AXES[axis]].normalized()
                delta = (-1 if reverse else 1) * math.pi / 2
                assert bpy.ops.transform.rotate(
                    value=delta, orient_axis=axis, orient_type='LOCAL',
                    constraint_axis=tuple(axis == item for item in 'XYZ'),
                ) == {'FINISHED'}
                bpy.context.view_layer.update()
                manual = obj.matrix_world.copy()
                obj.matrix_basis = rest_basis
                bpy.context.view_layer.update()
                original_euler = tuple(obj.rotation_euler)
                original_quat = tuple(obj.rotation_quaternion)
                original_aa = tuple(obj.rotation_axis_angle)
                ctrl = apply(settings)
                set_controls(scene, ctrl, start_h=0, start_m=0, start_s=0.0, speed=1.0, tick=0)
                scene.frame_set(361)
                error = max(abs(obj.matrix_world[i][j] - manual[i][j]) for i in range(4) for j in range(4))
                assert error < 2e-5, (axis, mode, reverse, error, 'does not match manual LOCAL rotation')
                apply(settings)
                error = max(abs(obj.matrix_world[i][j] - manual[i][j]) for i in range(4) for j in range(4))
                assert error < 2e-5, ('reapply', axis, mode, reverse, error, tuple(obj.rotation_euler))
                for tick in (0, 1):
                    set_controls(scene, settings.controller, tick=tick)
                    for frame in (1, 13, 37, 121, 721, 1441):
                        scene.frame_set(frame)
                        actual_spindle = obj.matrix_world.to_3x3().col[AXES[axis]].normalized()
                        assert (actual_spindle - spindle).length < 2e-6, (axis, mode, reverse, tick, frame, 'axle tilted')
                core.remove_rig(settings)
                assert obj.rotation_mode == mode and tuple(obj.rotation_euler) == original_euler
                assert tuple(obj.rotation_quaternion) == original_quat
                assert tuple(obj.rotation_axis_angle) == original_aa
                assert obj.parent == parent
                assert max(abs(obj.matrix_basis[i][j] - rest_basis[i][j]) for i in range(4) for j in range(4)) < 2e-6


def test_local_axis_bake_and_upgrade():
    """A saved 1.0.0-style rig can be re-applied, then baked without tilting."""
    from mathutils import Matrix
    from clock_animator.constants import DRIVEN_AXIS, OWNER, REST_MODE, REST_ROTATION

    for tick in (0, 1):
        scene, settings, hands = fresh()
        obj = hands['second']
        settings.minute, settings.hour = None, None
        obj.rotation_euler = (1.1, 0.65, -0.7)
        bpy.context.view_layer.update()
        rest = obj.rotation_euler.copy()
        expected = rest.to_matrix().to_4x4() @ Matrix.Rotation(math.pi / 2, 4, 'Y')
        ctrl = apply(settings)
        # Reconstruct the old rig's exact rotation channel and ownership metadata.
        core.restore_hand(obj)
        obj[REST], obj[REST_MODE] = list(rest), 'XYZ'
        obj[REST_ROTATION] = list(obj.rotation_axis_angle)
        obj[OWNER], obj[DRIVEN_AXIS] = ctrl[RIG_ID], 1
        core._driver(obj, 'rotation_euler', core.hand_expression(rest.y, 'second'), [
            ('t', ctrl, core.prop_path(TIME), 'OBJECT'), ('tick', ctrl, core.prop_path(TICK), 'OBJECT'),
        ], 1)
        set_controls(scene, ctrl, start_h=0, start_m=0, start_s=0.0, tick=tick)
        scene.frame_set(361)
        assert max(abs(obj.matrix_world[i][j] - expected[i][j]) for i in range(3) for j in range(3)) > 0.1
        apply(settings)
        assert max(abs(obj.matrix_world[i][j] - expected[i][j]) for i in range(3) for j in range(3)) < 2e-5
        samples = {}
        for frame in range(1, 50):
            scene.frame_set(frame)
            samples[frame] = obj.matrix_world.copy()
        core.bake_rig(scene, settings, 1, 49, delete_controller=True)
        assert obj.rotation_mode == 'YXZ'
        for frame, sample in samples.items():
            scene.frame_set(frame)
            assert max(abs(obj.matrix_world[i][j] - sample[i][j]) for i in range(4) for j in range(4)) < 2e-5


def test_partial_and_isolation():
    scene, settings, hands = fresh()
    settings.second = None
    first = apply(settings)
    assert not core.drivers(hands['second'])
    first_id = first[RIG_ID]
    settings.controller = None
    settings.second, settings.minute, settings.hour = hands['second'], None, None
    second = apply(settings)
    assert first[RIG_ID] == first_id and first != second
    check_angles(scene, second, {'second': hands['second']})
    assert bpy.ops.clock.remove() == {'FINISHED'}
    assert first.name in bpy.data.objects and core.drivers(hands['minute'])
    settings.controller = first
    core.remove_rig(settings)
    assert all(not core.drivers(obj) for obj in hands.values())


def test_validation_and_changed_slots():
    scene, settings, hands = fresh()
    settings.minute = hands['second']
    expect_error(bpy.ops.clock.apply, 'distinct')
    assert not any(RIG_ID in obj for obj in bpy.data.objects)
    settings.minute = hands['minute']
    hands['hour'].keyframe_insert('rotation_euler', index=1, frame=1)
    expect_error(bpy.ops.clock.apply, 'existing rotation')
    hands['hour'].animation_data_clear()
    old = apply(settings)
    settings.hour = None
    apply(settings)
    assert not core.drivers(hands['hour']) and REST not in hands['hour']
    del old
    ctrl = settings.controller
    del ctrl[START_M]
    assert 'missing' in core.status(settings)
    apply(settings)
    assert START_M in settings.controller
    settings.controller = None
    expect_error(bpy.ops.clock.apply, 'another clock')


def test_pivots_and_selection():
    scene, settings, hands = fresh()
    scene.cursor.location = (1, 2, 3)
    selected, active = set(bpy.context.selected_objects), bpy.context.view_layer.objects.active
    bpy.context.view_layer.update()
    world = {obj: [obj.matrix_world @ v.co for v in obj.data.vertices] for obj in hands.values()}
    assert bpy.ops.clock.pivots() == {'FINISHED'}
    assert set(bpy.context.selected_objects) == selected and bpy.context.view_layer.objects.active == active
    for obj in hands.values():
        assert (obj.matrix_world.translation - scene.cursor.location).length < 1e-6
        assert all((obj.matrix_world @ v.co - co).length < 1e-6 for v, co in zip(obj.data.vertices, world[obj]))
    duplicate = hands['second'].copy()
    scene.collection.objects.link(duplicate)
    selected, active = set(bpy.context.selected_objects), bpy.context.view_layer.objects.active
    expect_error(bpy.ops.clock.pivots, 'multi-user')
    assert set(bpy.context.selected_objects) == selected and bpy.context.view_layer.objects.active == active
    bpy.ops.object.mode_set(mode='EDIT')
    expect_error(bpy.ops.clock.pivots, 'Object Mode')
    bpy.ops.object.mode_set(mode='OBJECT')


def test_bake_and_realtime():
    for tick in (0, 1):
        scene, settings, hands = fresh()
        ctrl = apply(settings)
        set_controls(scene, ctrl, start_h=0, start_s=10.0, tick=tick)
        expected = {}
        for frame in range(1, 50):
            scene.frame_set(frame)
            expected[frame] = {role: obj.rotation_euler.y for role, obj in hands.items()}
        scene.frame_set(17, subframe=0.25)
        assert bpy.ops.clock.bake(frame_start=1, frame_end=49, delete_controller=bool(tick)) == {'FINISHED'}
        assert scene.frame_current == 17 and scene.frame_subframe == 0.25
        for obj in hands.values():
            assert not core.drivers(obj)
            curves = core._rotation_curves(obj)
            assert len(curves) == 1
            assert len(curves[0].keyframe_points) == (49 if tick else 2)
            assert all(k.interpolation == ('CONSTANT' if tick else 'LINEAR') for k in curves[0].keyframe_points)
        for frame in range(1, 50):
            scene.frame_set(frame)
            assert all(abs(obj.rotation_euler.y - expected[frame][role]) < 1e-6 for role, obj in hands.items()), (tick, frame, [(role, obj.rotation_euler.y, expected[frame][role]) for role, obj in hands.items()])
        assert (settings.controller is None) == bool(tick)
    scene, settings, hands = fresh()
    ctrl = apply(settings)
    scene.frame_set(48)
    assert bpy.ops.clock.realtime() == {'FINISHED'}
    from datetime import datetime
    now = datetime.now()
    assert ctrl[START_H] == now.hour and ctrl[START_M] == now.minute and ctrl[OFFSET] == 48


def test_names_and_unrelated_animation():
    scene, settings, hands = fresh()
    for obj in hands.values():
        obj.name = 'Unmatched'
    expect_error(bpy.ops.clock.assign, 'No matching')
    hands['second'].name = 'sec_min'
    expect_error(bpy.ops.clock.assign, 'Ambiguous')
    hands['second'].name = 'sec_A'
    hands['minute'].name = 'sec_B'
    expect_error(bpy.ops.clock.assign, 'Multiple second')
    scene, settings, hands = fresh()
    location = hands['second'].driver_add('location', 0)
    location.driver.expression = '2.0'
    apply(settings)
    core.remove_rig(settings)
    assert len(core.drivers(hands['second'])) == 1
    assert core.drivers(hands['second'])[0].data_path == 'location'


def test_native_limits_and_bake_fallback():
    scene, settings, hands = fresh()
    ctrl = apply(settings)
    set_controls(scene, ctrl, start_h=0, tick=0)
    scene.frame_set(2)
    tiny = hands['hour'].rotation_euler.y
    nominal = f32(RATES['hour'] / 24)
    assert abs(tiny - nominal) < 0.0001
    print(f'NATIVE TINY ANGLE | actual={tiny:.12g} | ideal={nominal:.12g}')
    expected = {}
    for frame in range(1, 50):
        scene.frame_set(frame)
        expected[frame] = [obj.rotation_euler.y for obj in hands.values()]
    core.bake_rig(scene, settings, 1, 49)
    for frame in range(1, 50):
        scene.frame_set(frame)
        assert all(abs(obj.rotation_euler.y - value) < 1e-6 for obj, value in zip(hands.values(), expected[frame]))
    assert all(all(key not in obj for key in HAND_KEYS) for obj in hands.values())


def add_crown(scene, settings, axis='X'):
    crown = bpy.data.objects.new('Crown', None)
    scene.collection.objects.link(crown)
    crown.rotation_euler = (0.2, -0.3, 0.4)
    settings.use_crown, settings.crown, settings.crown_axis = True, crown, axis
    return crown


def check_crown(scene, ctrl, hands, crown, frame, reverse=False):
    scene.frame_set(frame)
    seconds = (ctrl[START_H] * 3600 + ctrl[START_M] * 60 + ctrl[START_S]
               + (frame - ctrl[OFFSET]) * scene.render.fps_base / scene.render.fps * ctrl[SPEED]
               + (crown.rotation_euler[ctrl[CROWN_AXIS]] - ctrl[CROWN_REST]) * ctrl[CROWN_RATIO] / RATES['second'])
    time = f32(seconds)
    assert abs(ctrl[TIME] - time) < 1e-6, (ctrl[TIME], time)
    t = math.floor(time) if ctrl[TICK] else time
    for role, obj in hands.items():
        rate = RATES[role] * (-1 if reverse else 1)
        expected = f32(float(f'{rate:.15f}') * t)
        assert abs(obj.rotation_euler.y - expected) < 1e-6, (role, obj.rotation_euler.y, expected)
    for obj in (ctrl, *hands.values()):
        assert all(fc.driver.is_valid and fc.driver.is_simple_expression for fc in core.drivers(obj))


def test_crown_gearing_and_one_way():
    for axis in 'XYZ':
        scene, settings, hands = fresh()
        crown = add_crown(scene, settings, axis)
        bpy.context.view_layer.update()
        original = crown.matrix_world.copy()
        ctrl = apply(settings)
        assert max(abs(crown.matrix_world[i][j] - original[i][j]) for i in range(4) for j in range(4)) < 1e-6
        assert ctrl[CROWN_SOURCE] == crown and ctrl[CROWN_RATIO] == 60.0
        assert crown.rotation_mode == ROTATION_ORDERS[axis] and not core.drivers(crown)
        rest = ctrl[CROWN_REST]
        values = tuple(crown.rotation_euler)
        for frame in (1, 25, 1441, 86401):
            check_crown(scene, ctrl, hands, crown, frame)
            assert tuple(crown.rotation_euler) == values
        for gear in (60.0, -60.0, 0.0, 12.5):
            for tick in (0, 1):
                set_controls(scene, ctrl, crown_ratio=gear, tick=tick, speed=0.0)
                for angle in (0.01, math.pi / 2, 2 * math.pi, 6 * math.pi, -4 * math.pi):
                    crown.rotation_euler[AXES[axis]] = rest + angle
                    crown.update_tag()
                    check_crown(scene, ctrl, hands, crown, 37)
        set_controls(scene, ctrl, crown_ratio=60.0, speed=2.0)
        check_crown(scene, ctrl, hands, crown, 48)
        before = {role: tuple(obj.rotation_euler) for role, obj in hands.items()}
        ctrl = apply(settings)
        assert ctrl[CROWN_REST] == rest
        assert all(tuple(obj.rotation_euler) == before[role] for role, obj in hands.items())
        settings.reverse = True
        ctrl = apply(settings)
        check_crown(scene, ctrl, hands, crown, 48, reverse=True)
        assert bpy.ops.clock.realtime() == {'FINISHED'}
        assert ctrl[CROWN_REST] == crown.rotation_euler[AXES[axis]]
        check_crown(scene, ctrl, hands, crown, 48, reverse=True)
        values, mode = tuple(crown.rotation_euler), crown.rotation_mode
        core.remove_rig(settings)
        assert tuple(crown.rotation_euler) == values and crown.rotation_mode == mode
        assert not core.drivers(crown)
        assert settings.crown is None and not settings.use_crown
        assert all(not core.drivers(obj) for obj in hands.values())


def test_crown_keyframes_bake_and_isolation():
    for tick in (0, 1):
        scene, settings, hands = fresh()
        crown = add_crown(scene, settings)
        ctrl = apply(settings)
        rest = ctrl[CROWN_REST]
        for frame, turns in ((1, 0), (25, 1), (49, 4)):
            crown.rotation_euler.x = rest + turns * 2 * math.pi
            crown.keyframe_insert('rotation_euler', index=0, frame=frame)
        for curve in core._rotation_curves(crown):
            for key in curve.keyframe_points:
                key.interpolation = 'LINEAR'
        action = crown.animation_data.action
        set_controls(scene, ctrl, tick=tick)
        expected = {}
        for frame in range(1, 50):
            check_crown(scene, ctrl, hands, crown, frame)
            expected[frame] = [obj.matrix_world.copy() for obj in hands.values()]
        apply(settings)
        assert crown.animation_data.action == action
        scene.frame_set(17, subframe=0.25)
        core.bake_rig(scene, settings, 1, 49, delete_controller=True)
        assert scene.frame_current == 17 and scene.frame_subframe == 0.25
        assert crown.animation_data.action == action and not core.drivers(crown)
        for frame, matrices in expected.items():
            scene.frame_set(frame)
            for obj, matrix in zip(hands.values(), matrices):
                assert max(abs(obj.matrix_world[i][j] - matrix[i][j]) for i in range(4) for j in range(4)) < 0.001
    scene, settings, hands = fresh()
    crown = add_crown(scene, settings)
    first = apply(settings)
    values = [tuple(obj.rotation_euler) for obj in hands.values()]
    settings.controller, settings.use_crown = None, False
    settings.second, settings.minute, settings.hour = None, None, None
    extra = bpy.data.objects.new('Other_Second', None)
    scene.collection.objects.link(extra)
    settings.second = extra
    second = apply(settings)
    crown.rotation_euler.x += 1.0
    crown.update_tag()
    scene.frame_set(scene.frame_current)
    assert tuple(extra.rotation_euler) == (0.0, f32(float(f'{RATES["second"]:.15f}') * second[TIME]), 0.0)
    assert any(tuple(obj.rotation_euler) != value for obj, value in zip(hands.values(), values))
    assert bpy.ops.clock.remove() == {'FINISHED'}
    assert first.name in bpy.data.objects and core.drivers(hands['second'])


def test_crown_validation_and_missing_input():
    scene, settings, hands = fresh()
    settings.use_crown = True
    expect_error(bpy.ops.clock.apply, 'Choose a Crown')
    settings.crown = hands['second']
    expect_error(bpy.ops.clock.apply, 'separate')
    crown = add_crown(scene, settings, 'Y')
    crown.keyframe_insert('rotation_euler', index=1, frame=1)
    expect_error(bpy.ops.clock.apply, 'existing crown animation')
    crown.animation_data_clear()
    crown.parent = hands['hour']
    expect_error(bpy.ops.clock.apply, 'parented')
    crown.parent = None
    curve = crown.driver_add('rotation_euler', 1)
    curve.driver.expression = '0.5'
    expect_error(bpy.ops.clock.apply, 'keyframes instead')
    crown.driver_remove('rotation_euler', 1)
    ctrl = apply(settings)
    del ctrl[CROWN_RATIO]
    assert 'Crown properties missing' in core.status(settings)
    ctrl = apply(settings)
    bpy.data.objects.remove(crown, do_unlink=True)
    scene.frame_set(25)
    assert 'Crown input missing' in core.status(settings)
    settings.use_crown = False
    ctrl = apply(settings)
    assert CROWN_SOURCE not in ctrl
    check_angles(scene, ctrl, hands, frames=(1, 25))


def test_fresh_process(use_crown=False):
    scene, settings, hands = fresh()
    crown = add_crown(scene, settings, 'Z') if use_crown else None
    ctrl = apply(settings)
    set_controls(scene, ctrl, start_h=3, start_m=45, start_s=10.0, tick=0, speed=-1.0)
    scene.render.fps, scene.render.fps_base = 24, 1.001
    if crown:
        for frame, turns in ((1, 0), (49, 3)):
            crown.rotation_euler.z = ctrl[CROWN_REST] + turns * 2 * math.pi
            crown.keyframe_insert('rotation_euler', index=2, frame=frame)
    blend = OUTPUT / ('crown.blend' if use_crown else 'clock.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    command = [bpy.app.binary_path, '-b', '--factory-startup', '--disable-autoexec', str(blend),
               '--python-exit-code', '1', '--python', str(Path(__file__).resolve()), '--', '--reopen']
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    (OUTPUT / ('reopen-crown.log' if use_crown else 'reopen.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'FRESH PROCESS PASS' in result.stdout
    print('FRESH PROCESS PASS (auto-run disabled, add-on not enabled)')


def test_crown_fresh_process():
    test_fresh_process(use_crown=True)


def test_lifecycle():
    addon_utils.disable('clock_animator', default_set=False)
    for _ in range(2):
        assert not hasattr(bpy.types.Scene, 'clock_rig')
        assert not hasattr(bpy.types, 'CLOCK_PT_animator')
        addon_utils.enable('clock_animator', default_set=False)
        assert hasattr(bpy.types.Scene, 'clock_rig')
        addon_utils.disable('clock_animator', default_set=False)
    assert not hasattr(bpy.types.Scene, 'clock_rig')
    from clock_animator import operators, properties, ui
    for cls in (properties.ClockRigSettings, *operators.CLASSES, ui.CLOCK_PT_animator):
        assert not cls.is_registered


def main():
    print('Clock Animator | Blender', bpy.app.version_string, flush=True)
    if '--reopen' in sys.argv:
        bpy.context.preferences.filepaths.use_scripts_auto_execute = False
        assert not hasattr(bpy.types.Scene, 'clock_rig')
        ctrl = next(obj for obj in bpy.data.objects if RIG_ID in obj)
        hands = {role: bpy.data.objects['Hand_' + role.title()] for role in FACTORS}
        if CROWN_SOURCE in ctrl:
            for frame in (1, 24, 25, 48, 1441, 86401):
                check_crown(bpy.context.scene, ctrl, hands, ctrl[CROWN_SOURCE], frame)
        else:
            check_angles(bpy.context.scene, ctrl, hands)
        print('FRESH PROCESS PASS', flush=True)
        return
    addon_utils.enable('clock_animator', default_set=False)
    assert hasattr(bpy.types.Scene, 'clock_rig')
    for test in (test_basic, test_rates, test_axes_parent_and_restore, test_rotation_modes,
                 test_local_axis_rotation, test_local_axis_bake_and_upgrade,
                 test_partial_and_isolation, test_validation_and_changed_slots,
                 test_pivots_and_selection, test_bake_and_realtime, test_names_and_unrelated_animation,
                 test_native_limits_and_bake_fallback, test_crown_gearing_and_one_way,
                 test_crown_keyframes_bake_and_isolation, test_crown_validation_and_missing_input,
                 test_fresh_process, test_crown_fresh_process, test_lifecycle):
        try:
            test()
            ROWS.append((test.__name__, 'PASS'))
        except Exception:
            ROWS.append((test.__name__, 'FAIL'))
            traceback.print_exc()
            break
    print('\nTEST SUMMARY')
    for name, result in ROWS:
        print(f'{name:40} {result}')
    print(f'Angle samples: {CHECKS}; max ideal absolute error: {MAX_IDEAL_ERROR:.12g} rad')
    print('VERIFY a-d: PASS if basic/rates passed; e: FAIL strict 1e-6 ideal precision; f: separate UI test')
    if any(result != 'PASS' for _, result in ROWS):
        raise AssertionError('Clock Animator tests failed')
    print(f'ALL {len(ROWS)} GROUPS PASSED', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
