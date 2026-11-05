"""Real Blender feature and workflow checks for Clock Animator 2."""
from math import floor, pi
from pathlib import Path
import random
import subprocess
import sys
import traceback

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_tests as base  # noqa: E402
from clock_animator import core, features  # noqa: E402
from clock_animator.constants import (  # noqa: E402
    BOUNCE, CHRONO, CROWN_REST, DATE_BLEND, DATE_START, ELAPSED,
    MODE, OWNER, PAUSED, RATE, RATES, RIG_ID, RUNNING,
    SPEED, START_H, START_M, START_S, TICK, TIME,
)
from clock_animator.motion import ramp_seconds  # noqa: E402

OUTPUT = Path(__file__).resolve().parent / 'output' / ('advanced-' + bpy.app.version_string.replace(' ', '_'))
OUTPUT.mkdir(parents=True, exist_ok=True)


def fresh(precision=False):
    scene, settings, hands = base.fresh()
    settings.precision = precision
    settings.date_object = settings.chrono_second = settings.chrono_minute = settings.chrono_hour = None
    settings.gear_object = settings.gear_source = None
    settings.helper_collection = None
    return scene, settings, hands, base.apply(settings)


def empty(scene, name):
    obj = bpy.data.objects.new(name, None)
    scene.collection.objects.link(obj)
    return obj


def set_time(scene, ctrl, seconds):
    ctrl[MODE], ctrl[START_H], ctrl[START_M], ctrl[START_S] = 1, 0, 0, 0.0
    ctrl[ELAPSED] = float(seconds)
    ctrl.update_tag()
    features.refresh(scene)


def valid(ctrl):
    for obj in (ctrl, *core.managed_hands(ctrl)):
        for curve in core.drivers(obj):
            assert curve.driver.is_valid and curve.driver.is_simple_expression, (obj.name, curve.driver.expression)
            assert not curve.modifiers


def test_shot_and_manager():
    scene, settings, hands, ctrl = fresh()
    settings.range_start, settings.range_end, settings.easing = 1, 121, 'LINEAR'
    settings.shot_start_h, settings.shot_start_m, settings.shot_start_s = 10, 10, 0
    settings.shot_end_h, settings.shot_end_m, settings.shot_end_s = 11, 45, 0
    settings.shot_days = 0
    assert bpy.ops.clock.tool(action='SHOT') == {'FINISHED'}
    for frame, expected in ((1, 36600), (61, 39450), (121, 42300), (151, 42300)):
        scene.frame_set(frame)
        assert abs(ctrl[TIME] - expected) < 0.01, (frame, ctrl[TIME], expected)
    action = ctrl.animation_data.action
    matrix = hands['second'].matrix_world.copy()
    base.apply(settings)
    assert settings.controller == ctrl and ctrl.animation_data.action == action
    assert max(abs(hands['second'].matrix_world[i][j] - matrix[i][j]) for i in range(4) for j in range(4)) < 1e-6
    settings.controller = None
    settings.second, settings.minute, settings.hour = None, None, None
    settings.controller = ctrl
    assert all(getattr(settings, role) == obj for role, obj in hands.items())
    assert settings.axis == 'Y'
    valid(ctrl)
    settings.easing = 'SMOOTH'
    features.shot(scene)
    scene.frame_set(31)
    assert abs(ctrl[TIME] - (36600 + (42300 - 36600) * 0.15625)) < 0.02


def test_ramp_pause_resume():
    scene, settings, hands, ctrl = fresh()
    scene.render.fps_base = 1.001
    settings.range_start, settings.range_end = 1, 121
    settings.ramp_first, settings.ramp_last = 1.0, 20.0
    for easing in ('LINEAR', 'SMOOTH'):
        ctrl[MODE] = 0
        ctrl.update_tag()
        settings.easing = easing
        features.speed_ramp(scene)
        frames = [1, 17, 61, 121, 145]
        random.Random(5).shuffle(frames)
        for frame in frames:
            scene.frame_set(frame)
            expected = ramp_seconds(frame, 1, 121, 1, 20, 24 / 1.001, easing == 'SMOOTH')
            assert abs(ctrl[ELAPSED] - expected) < 0.0001, (frame, ctrl[ELAPSED], expected)
    scene.frame_set(61)
    value = ctrl[TIME]
    features.pause_resume(scene)
    scene.frame_set(100)
    assert ctrl[PAUSED] and ctrl[TIME] == value
    ctrl[SPEED] = 2.0
    features.pause_resume(scene)
    scene.frame_set(124)
    assert abs(ctrl[TIME] - (value + 2 * 1.001)) < 0.01
    valid(ctrl)


def test_movement_and_rebound():
    scene, settings, hands, ctrl = fresh()
    ctrl[START_H], ctrl[START_M], ctrl[START_S] = 0, 0, 10.0
    for preset, hz in (('QUARTZ', 1), ('MECH6', 6), ('MECH8', 8), ('SWEEP', 0)):
        settings.movement = preset
        features.movement(scene)
        scene.frame_set(6)
        t = 10 + 5 / 24
        expected = RATES['second'] * (floor(t * hz) / hz if hz else t)
        assert abs(hands['second'].rotation_euler.y - expected) < 1e-6
    settings.movement = 'QUARTZ'
    features.movement(scene)
    ctrl[BOUNCE] = 0.02
    ctrl.update_tag()
    scene.frame_set(7)
    assert abs(hands['second'].rotation_euler.y - RATES['second'] * 10) > 0.001
    scene.frame_set(25)
    assert abs(hands['second'].rotation_euler.y - RATES['second'] * 11) < 1e-6
    valid(ctrl)


def test_crown_tools():
    scene, settings, hands, ctrl = fresh()
    crown = base.add_crown(scene, settings)
    ctrl = base.apply(settings)
    base.set_controls(scene, ctrl, speed=0.0, tick=0)
    settings.crown_turns = 0.25
    assert bpy.ops.clock.tool(action='KEY_CROWN') == {'FINISHED'}
    scene.frame_set(25)
    assert bpy.ops.clock.tool(action='QUARTER') == {'FINISHED'}
    assert abs(ctrl[TIME] - 44100) < 0.01, (ctrl[TIME], crown.rotation_euler.x, ctrl[CROWN_REST], [(tuple(k.co)) for fc in core._rotation_curves(crown) for k in fc.keyframe_points])
    assert abs(crown.rotation_euler.x - ctrl[CROWN_REST] - pi / 2) < 1e-6
    assert crown.animation_data.action
    scene.frame_set(49)
    assert bpy.ops.clock.tool(action='FULL') == {'FINISHED'}
    assert abs(ctrl[TIME] - 47700) < 0.01
    scene.frame_set(73)
    settings.crown_turns = -0.25
    assert bpy.ops.clock.tool(action='TURN') == {'FINISHED'}
    assert abs(ctrl[TIME] - 46800) < 0.01
    valid(ctrl)


def test_date_wheel():
    scene, settings, hands, ctrl = fresh()
    obj = features.create_date_wheel(scene)
    assert obj.type == 'MESH' and len(obj.data.vertices) > 200
    assert not any(o.type == 'FONT' for o in scene.objects)
    ctrl[DATE_START] = 28
    features.add_date(scene)
    features.add_date(scene)
    for seconds, position in ((0, 27), (86400, 28), (4 * 86400, 31), (-86400, 26)):
        set_time(scene, ctrl, seconds)
        assert abs(obj.rotation_euler.z - position * 2 * pi / 31) < 1e-6
    ctrl[DATE_START], ctrl[DATE_BLEND] = 1, 100.0
    set_time(scene, ctrl, 86350)
    assert abs(obj.rotation_euler.z - pi / 31) < 1e-6
    settings.controller = None
    settings.controller = ctrl
    assert settings.date_object == obj
    valid(ctrl)
    base.apply(settings)
    assert obj.get(OWNER) == ctrl[RIG_ID] and core.drivers(obj)
    base.add_crown(scene, settings)
    ctrl = base.apply(settings)
    ctrl[DATE_BLEND], ctrl[DATE_START] = 0.0, 1
    set_time(scene, ctrl, 5)
    settings.crown.rotation_euler.x -= 0.1
    settings.crown.update_tag()
    features.refresh(scene)
    assert ctrl[TIME] < 0 and abs(obj.rotation_euler.z + 2 * pi / 31) < 1e-6
    core.remove_rig(settings)
    assert OWNER not in obj and not core.drivers(obj)


def test_gears():
    scene, settings, hands, ctrl = fresh(precision=True)
    gear = empty(scene, 'Driven Gear')
    settings.gear_object, settings.gear_source = gear, hands['second']
    settings.gear_teeth, settings.source_teeth, settings.gear_reverse = 40, 20, True
    features.add_gear(scene)
    second = empty(scene, 'Second Gear')
    settings.gear_object, settings.gear_source = second, gear
    settings.gear_teeth, settings.source_teeth = 10, 20
    features.add_gear(scene)
    set_time(scene, ctrl, 61)
    delta = 61 - 43200
    assert abs(gear.rotation_euler.y - base.f32(float(f'{-RATES["second"] * 0.5:.15f}') * delta)) < 1e-6
    assert abs(second.rotation_euler.y - base.f32(float(f'{RATES["second"]:.15f}') * delta)) < 1e-6
    assert second[RATE] > 0 and gear[RATE] < 0
    settings.reverse = True
    base.apply(settings)
    assert abs(gear.rotation_euler.y - base.f32(float(f'{RATES["second"] * 0.5:.15f}') * delta)) < 1e-6
    assert abs(second.rotation_euler.y - base.f32(float(f'{-RATES["second"]:.15f}') * delta)) < 1e-6
    settings.gear_object, settings.gear_source = gear, hands['second']
    settings.gear_teeth, settings.source_teeth = 30, 20
    features.add_gear(scene)
    assert abs(gear.rotation_euler.y) < 1e-6
    valid(ctrl)
    try:
        features.remove_mechanism(scene, gear)
    except ValueError as error:
        assert 'driven' in str(error)
    else:
        raise AssertionError('Dependent gear removal must be refused')
    valid(ctrl)


def test_stopwatch():
    scene, settings, hands, ctrl = fresh()
    seconds, minutes = empty(scene, 'Chrono seconds'), empty(scene, 'Chrono minutes')
    settings.chrono_second, settings.chrono_minute = seconds, minutes
    features.add_chronograph(scene)
    features.chronograph(scene, 'START')
    scene.frame_set(49)
    assert abs(ctrl[CHRONO] - 2) < 1e-6
    assert abs(seconds.rotation_euler.y - pi / 15) < 1e-6
    features.chronograph(scene, 'STOP')
    scene.frame_set(97)
    assert abs(ctrl[CHRONO] - 2) < 1e-6
    features.chronograph(scene, 'START')
    scene.frame_set(121)
    assert abs(ctrl[CHRONO] - 3) < 1e-6
    clock = ctrl[TIME]
    features.chronograph(scene, 'RESET')
    scene.frame_set(145)
    assert ctrl[CHRONO] == 0 and not ctrl[RUNNING]
    assert ctrl[TIME] > clock
    valid(ctrl)


def test_alignment_helpers():
    scene, settings, hands, ctrl = fresh()
    before = {obj: obj.matrix_world.copy() for obj in hands.values()}
    features.setup_helpers(scene, test_rotation=True)
    collection = settings.helper_collection
    assert len(collection.objects) == 6 and all(o.hide_render for o in collection.objects)
    unrelated = empty(scene, 'User object in preview collection')
    collection.objects.link(unrelated)
    features.clear_helpers(scene)
    assert unrelated.name in scene.objects and collection.name in bpy.data.collections
    assert all(max(abs(obj.matrix_world[i][j] - matrix[i][j]) for i in range(4) for j in range(4)) < 1e-6 for obj, matrix in before.items())


def test_precision_and_export_copy():
    scene, settings, hands, ctrl = fresh(precision=True)
    ctrl[SPEED], ctrl[TICK] = 1.0, 0
    ctrl.update_tag()
    scene.frame_set(1_000_000)
    seconds = 43200 + 999999 / 24
    expected = RATES['second'] * (seconds % 60)
    assert abs(hands['second'].rotation_euler.y - expected) < 1e-6
    assert len(core.drivers(ctrl)) == 4
    settings.bake_start, settings.bake_end, settings.bake_step = 1, 49, 1
    current = scene.frame_current
    count, samples = features.bake_copy(scene)
    assert count == 3 and samples == 49 and scene.frame_current == current
    assert all(core.drivers(obj) for obj in hands.values())
    copies = list(settings.export_collection.objects)
    assert all(not core.drivers(obj) and OWNER not in obj for obj in copies)
    originals = {o.name: o for o in hands.values()}
    for frame in (1, 17, 49):
        scene.frame_set(frame)
        for copy in copies:
            original = originals[copy.name.removesuffix(' Baked')]
            assert max(abs(copy.matrix_world[i][j] - original.matrix_world[i][j]) for i in range(4) for j in range(4)) < 0.0002
    valid(ctrl)


def test_validation_and_independent_clocks():
    scene, settings, hands, ctrl = fresh()
    settings.range_start, settings.range_end = 10, 10
    base.expect_error(lambda: bpy.ops.clock.tool(action='SHOT'), 'Last frame')
    settings.gear_object, settings.gear_source = hands['second'], hands['second']
    base.expect_error(lambda: bpy.ops.clock.tool(action='GEAR'), 'separate')
    old = ctrl
    features.new_clock(settings)
    assert settings.controller is None and settings.second is None
    settings.second = empty(scene, 'Other second')
    second = base.apply(settings)
    assert second != old
    settings.controller = old
    assert settings.second == hands['second']
    base.apply(settings)
    assert core.drivers(second)


def test_export_failure_preserves_rig():
    scene, settings, hands, ctrl = fresh()
    parent = empty(scene, 'Nonuniform parent')
    parent.scale = (2, 1, 1)
    hands['second'].parent = parent
    hands['second'].rotation_euler.x, hands['second'].rotation_euler.z = 0.5, 0.3
    features.refresh(scene)
    settings.bake_start, settings.bake_end = 1, 3
    objects, actions = set(bpy.data.objects), set(bpy.data.actions)
    try:
        features.bake_copy(scene)
    except ValueError as error:
        assert 'shear' in str(error)
    else:
        raise AssertionError('Unsupported shear must not create a misleading export copy')
    assert set(bpy.data.objects) == objects and set(bpy.data.actions) == actions
    assert scene.clock_rig.controller == ctrl and all(core.drivers(o) for o in hands.values())


def test_old_controller_upgrade():
    from clock_animator.constants import OFFSET, STEPS

    scene, settings, hands, ctrl = fresh()
    variables = [(name, ctrl, core.prop_path(key), 'OBJECT') for name, key in (
        ('h', START_H), ('m', START_M), ('s', START_S), ('speed', SPEED), ('off', OFFSET),
    )] + [('fps', scene, 'render.fps', 'SCENE'), ('fb', scene, 'render.fps_base', 'SCENE')]
    core._driver(ctrl, core.prop_path(TIME), core.time_expression(), variables)
    for key in (MODE, ELAPSED, STEPS):
        del ctrl[key]
    assert 'missing' in core.status(settings)
    try:
        features.controller(scene)
    except ValueError as error:
        assert 'Update' in str(error)
    else:
        raise AssertionError('Old controllers must request an update before running new tools')
    old_id = ctrl[RIG_ID]
    base.apply(settings)
    assert settings.controller == ctrl and ctrl[RIG_ID] == old_id
    assert all(key in ctrl for key in (MODE, ELAPSED, STEPS))
    valid(ctrl)


def test_reopen():
    scene, settings, hands, ctrl = fresh(precision=True)
    settings.range_start, settings.range_end, settings.easing = 1, 121, 'LINEAR'
    settings.shot_start_h, settings.shot_start_m, settings.shot_start_s = 10, 10, 0
    settings.shot_end_h, settings.shot_end_m, settings.shot_end_s, settings.shot_days = 11, 45, 0, 0
    features.shot(scene)
    features.create_date_wheel(scene)
    features.add_date(scene)
    scene.frame_set(61)
    path = OUTPUT / 'advanced.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    result = subprocess.run([bpy.app.binary_path, '-b', '--factory-startup', '--disable-autoexec', str(path),
                             '--python-exit-code', '1', '--python', str(Path(__file__).resolve()), '--', '--reopen'],
                            capture_output=True, text=True, timeout=120)
    (OUTPUT / 'reopen.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'ADVANCED REOPEN PASS' in result.stdout


def main():
    if '--reopen' in sys.argv:
        assert not hasattr(bpy.types.Scene, 'clock_rig')
        ctrl = next(o for o in bpy.data.objects if RIG_ID in o)
        for frame, expected in ((1, 36600), (61, 39450), (121, 42300)):
            bpy.context.scene.frame_set(frame)
            assert abs(ctrl[TIME] - expected) < 0.01
            valid(ctrl)
        print('ADVANCED REOPEN PASS')
        return
    base.addon_utils.enable('clock_animator', default_set=False)
    tests = [test_shot_and_manager, test_ramp_pause_resume, test_movement_and_rebound,
             test_crown_tools, test_date_wheel, test_gears, test_stopwatch,
             test_alignment_helpers, test_precision_and_export_copy,
             test_validation_and_independent_clocks, test_export_failure_preserves_rig,
             test_old_controller_upgrade, test_reopen]
    rows = []
    for test in tests:
        try:
            test()
            rows.append((test.__name__, 'PASS'))
        except Exception:
            rows.append((test.__name__, 'FAIL'))
            traceback.print_exc()
            break
    print('TEST SUMMARY | Advanced tools | Blender', bpy.app.version_string)
    for name, result in rows:
        print(f'{name:44} {result}')
    assert all(result == 'PASS' for _, result in rows), 'Advanced feature check failed'
    print(f'ALL {len(rows)} ADVANCED GROUPS PASSED')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
