"""Regression cases discovered during the production audit; run in real Blender."""
from pathlib import Path
import sys
import traceback
from unittest.mock import patch

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import advanced_tests as base  # noqa: E402
from clock_animator import core, features  # noqa: E402
from clock_animator.constants import (  # noqa: E402
    CHRONO, CONTROLLER, ELAPSED, OWNER, PAUSED, SPEED, TIME, TOOL_SETTINGS,
)


def difference(a, b):
    return max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4))


def test_delta_rotation():
    scene, settings, hands, ctrl = base.fresh()
    core.remove_rig(settings, clear_slots=False)
    for mode in ('XYZ', 'QUATERNION', 'AXIS_ANGLE'):
        obj = hands['second']
        obj.rotation_mode = mode
        obj.rotation_euler = (0.7, 0.3, -0.5)
        obj.rotation_quaternion = (0.8, 0.2, 0.3, 0.4)
        obj.rotation_axis_angle = (0.7, 1, 0, 0)
        obj.delta_rotation_euler = (0.4, -0.6, 0.9)
        obj.delta_rotation_quaternion = (0.9, 0.1, 0.2, 0.3)
        features.refresh(scene)
        before = obj.matrix_basis.copy()
        core._set_local_axis(obj, 'Y')
        features.refresh(scene)
        assert difference(before, obj.matrix_basis) < 1e-5, mode


def test_rebuild_rollback():
    scene, settings, hands, ctrl = base.fresh(precision=True)
    old = {o: (tuple(o.rotation_euler), [(f.data_path, f.array_index, f.driver.expression) for f in core.drivers(o)]) for o in (ctrl, *hands.values())}
    original = core._driver
    def fail(obj, *args, **kwargs):
        if obj == hands['minute']:
            raise ValueError('injected driver failure')
        return original(obj, *args, **kwargs)
    try:
        with patch.object(core, '_driver', fail):
            core.apply_rig(scene, settings)
    except ValueError:
        pass
    else:
        raise AssertionError('Fault was not injected')
    for o, (rotation, curves) in old.items():
        assert [(f.data_path, f.array_index, f.driver.expression) for f in core.drivers(o)] == curves, o.name
        assert max(abs(a-b) for a,b in zip(o.rotation_euler, rotation)) < 1e-6, o.name


def test_pause_keeps_past():
    scene, settings, hands, ctrl = base.fresh()
    settings.range_start, settings.range_end, settings.easing = 1, 121, 'SMOOTH'
    features.shot(scene)
    curve = features._curve(ctrl, ELAPSED)
    expected = {f: curve.evaluate(f) for f in (1, 12.5, 31, 49.25, 60)}
    scene.frame_set(61)
    features.pause_resume(scene)
    for f, value in expected.items():
        assert abs(features._curve(ctrl, ELAPSED).evaluate(f)-value) < 0.003, (f, value, features._curve(ctrl, ELAPSED).evaluate(f))
    scene.frame_set(80)
    assert ctrl[PAUSED] and abs(ctrl[ELAPSED]-curve.evaluate(61)) < 0.003


def test_pause_without_curve():
    scene, settings, hands, ctrl = base.fresh()
    base.set_time(scene, ctrl, 60)
    features.pause_resume(scene)
    scene.frame_set(120)
    assert abs(ctrl[TIME]-60) < 0.01


def test_playback_stopped_days():
    scene, settings, hands, ctrl = base.fresh()
    base.set_time(scene, ctrl, 2*86400+1234)
    ctrl[SPEED] = 0.0
    features.playback(scene)
    assert abs(ctrl[TIME]-(2*86400+1234)) < 0.1, ctrl[TIME]


def test_layered_slot_isolation():
    if bpy.app.version < (4, 4, 0):
        return
    scene, settings, hands, ctrl = base.fresh()
    other = base.empty(scene, 'Other animated object')
    other[ELAPSED] = 0.0
    other.keyframe_insert(core.prop_path(ELAPSED), frame=1)
    other[ELAPSED] = 20.0
    other.keyframe_insert(core.prop_path(ELAPSED), frame=80)
    action = other.animation_data.action
    original_curve = features._curve(other, ELAPSED)
    ctrl.animation_data.action = action
    slot = action.slots.new(id_type='OBJECT', name='Clock only')
    ctrl.animation_data.action_slot = slot
    ctrl.keyframe_insert(core.prop_path(ELAPSED), frame=1)
    settings.range_start, settings.range_end = 1, 121
    features.shot(scene)
    assert [(p.co.x, p.co.y) for p in original_curve.keyframe_points] == [(1, 0), (80, 20)]


def test_duplicate_clock_isolation():
    scene, settings, hands, ctrl = base.fresh()
    cloned = ctrl.copy()
    scene.collection.objects.link(cloned)
    duplicates = []
    for o in hands.values():
        copy = o.copy()
        copy[CONTROLLER] = cloned
        scene.collection.objects.link(copy)
        for f in core.drivers(copy):
            for v in f.driver.variables:
                if v.targets[0].id == ctrl:
                    v.targets[0].id = cloned
        duplicates.append(copy)
    assert not set(duplicates) & set(core.managed_hands(ctrl))
    core.remove_rig(settings)
    assert all(o.get(OWNER) and core.drivers(o) for o in duplicates)


def test_partial_status_and_muted_driver():
    scene, settings, hands, ctrl = base.fresh()
    core.restore_hand(hands['minute'])
    core.restore_hand(hands['hour'])
    for n in range(2):
        obj = base.empty(scene, 'Optional mechanism')
        features.attach(scene, obj, 'chrono_second', 'Y', 't', [('t', ctrl, core.prop_path(CHRONO), 'OBJECT')])
    assert core.status(settings).startswith('Partial'), core.status(settings)
    core.drivers(hands['second'])[0].mute = True
    assert 'muted' in core.status(settings).lower(), core.status(settings)


def test_gear_chain_offset():
    scene, settings, hands, ctrl = base.fresh()
    base.set_time(scene, ctrl, 0)
    parent, child = base.empty(scene, 'First gear'), base.empty(scene, 'Second gear')
    settings.gear_object, settings.gear_source = parent, hands['second']
    settings.source_teeth, settings.gear_teeth, settings.gear_reverse = 20, 40, False
    features.add_gear(scene)
    base.set_time(scene, ctrl, 15)
    settings.gear_object, settings.gear_source = child, parent
    features.add_gear(scene)
    base.set_time(scene, ctrl, 30)
    before_parent, before_child = parent.rotation_euler.y, child.rotation_euler.y
    settings.gear_object, settings.gear_source = parent, hands['second']
    settings.source_teeth, settings.gear_teeth = 40, 40
    features.add_gear(scene)
    features.refresh(scene)
    assert abs((child.rotation_euler.y-before_child)-0.5*(parent.rotation_euler.y-before_parent)) < 1e-5


def test_animation_rollback():
    scene, settings, hands, ctrl = base.fresh()
    features.shot(scene)
    curve = features._curve(ctrl, ELAPSED)
    expected = [curve.evaluate(frame/4) for frame in range(4, 484)]
    props = dict(ctrl.items())
    original = features.keys
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError('injected key failure')
    try:
        with patch.object(features, 'keys', fail):
            settings.shot_end_h = 20
            features.shot(scene)
    except ValueError:
        pass
    else:
        raise AssertionError('No injected failure')
    assert max(abs(curve.evaluate(frame/4)-value) for frame, value in zip(range(4,484), expected)) < 0.003
    assert ctrl[TIME] == props[TIME]


def test_mechanism_rollback_and_update():
    scene, settings, hands, ctrl = base.fresh()
    settings.chrono_second, settings.chrono_minute = base.empty(scene, 'Chrono A'), base.empty(scene, 'Chrono B')
    original = core._driver
    def fail(obj, *args, **kwargs):
        if obj == settings.chrono_minute:
            raise ValueError('injected output failure')
        return original(obj, *args, **kwargs)
    try:
        with patch.object(core, '_driver', fail):
            features.add_chronograph(scene)
    except ValueError:
        pass
    else:
        raise AssertionError('No injected failure')
    assert not core.drivers(settings.chrono_second) and not core.drivers(settings.chrono_minute)
    assert OWNER not in settings.chrono_second
    features.add_chronograph(scene)
    features.add_chronograph(scene)
    features.chronograph(scene, 'START')
    scene.frame_set(25)
    assert abs(ctrl[CHRONO]-1) < 1e-6


def test_stopwatch_reset_preserves_past():
    scene, settings, hands, ctrl = base.fresh()
    settings.chrono_second = base.empty(scene, 'Stopwatch reset check')
    features.add_chronograph(scene)
    for first, reset in ((1, 121), (999900, 1000000)):
        existing = features._curve(ctrl, CHRONO)
        if existing:
            existing.keyframe_points.clear()
        ctrl[CHRONO] = 0.0
        scene.frame_set(first)
        features.chronograph(scene, 'START')
        curve = features._curve(ctrl, CHRONO)
        expected = {f: curve.evaluate(f) for f in (first+12.5, first+20, reset-1)}
        scene.frame_set(reset)
        features.chronograph(scene, 'RESET')
        for f, value in expected.items():
            assert abs(curve.evaluate(f)-value) < 1e-5, (f, value, curve.evaluate(f))
        assert curve.evaluate(reset) == 0


def test_bake_failure_restores_all_variables():
    scene, settings, hands, ctrl = base.fresh(precision=True)
    original = core._rotation_curves
    fired = False
    def fail(obj):
        nonlocal fired
        if obj == hands['second'] and obj.animation_data and obj.animation_data.action and not fired:
            fired = True
            raise ValueError('injected bake failure')
        return original(obj)
    try:
        with patch.object(core, '_rotation_curves', fail):
            core.bake_rig(scene, settings, 1, 5)
    except ValueError:
        pass
    else:
        raise AssertionError('No injected failure')
    for obj in hands.values():
        assert not obj.animation_data.action
        assert {v.name for v in core.drivers(obj)[0].driver.variables} == {'t', 'tick', 'hz', 'amp', 'damp'}
    scene.frame_set(30)
    base.valid(ctrl)


def test_saved_settings_and_export_geometry():
    scene, settings, hands, ctrl = base.fresh()
    other = base.empty(scene, 'Must not become a controller')
    ctrl[TOOL_SETTINGS] = {'controller': other, 'second': other, 'easing': 'BAD_ENUM'}
    features.load_clock(settings)
    assert settings.controller == ctrl and settings.second == hands['second']
    settings.bake_start, settings.bake_end = 1, 3
    features.bake_copy(scene)
    for obj in settings.export_collection.objects:
        assert obj.data not in {o.data for o in hands.values()}


def test_auto_axle_and_preview():
    from mathutils import Vector
    scene, settings, hands, ctrl = base.fresh()
    core.remove_rig(settings, clear_slots=False)
    for obj in hands.values():
        for v in obj.data.vertices:
            v.co.y, v.co.z = v.co.z, v.co.y
            v.co.z *= 0.1
        obj.rotation_euler = (0.5, 0.7, -0.4)
        obj.scale.x = -1
    settings.auto_axis = True
    assert core.hand_axis(settings) == 'Z'
    features.refresh(scene)
    normals = {obj: (obj.matrix_world.to_3x3().inverted().transposed() @ Vector((0,0,1))).normalized() for obj in hands.values()}
    features.setup_helpers(scene, test_rotation=True)
    features.refresh(scene)
    for role, obj in hands.items():
        preview = next(o for o in settings.helper_collection.objects if o.name.startswith(role.title() + ' +15'))
        normal = (preview.matrix_world.to_3x3().inverted().transposed() @ Vector((0,0,1))).normalized()
        assert normal.dot(normals[obj]) > 1-1e-6
    features.clear_helpers(scene)
    ctrl = core.apply_rig(scene, settings)
    for seconds in (2.5, 15, 30, 45):
        base.set_time(scene, ctrl, seconds)
        for obj in hands.values():
            normal = (obj.matrix_world.to_3x3().inverted().transposed() @ Vector((0,0,1))).normalized()
            assert normal.dot(normals[obj]) > 1-1e-6


def run():
    failures = []
    for name, test in sorted(globals().copy().items()):
        if name.startswith('test_'):
            try:
                test()
                print('AUDIT PASS', name)
            except Exception:
                failures.append(name)
                print('AUDIT FAIL', name)
                traceback.print_exc()
    print('AUDIT SUMMARY', 'failures:', failures)
    assert not failures, failures


if __name__ == '__main__':
    base.base.addon_utils.enable('clock_animator', default_set=True, persistent=True)
    run()
