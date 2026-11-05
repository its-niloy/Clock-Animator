"""Animation tools and optional clock mechanisms. No UI or operators."""
from math import cos, floor, isfinite, pi, sin

import bpy

from . import core
from .state import atomic
from .constants import (
    SOURCE, SOURCE_ZERO, BASE, GEAR_RATIO, SOURCE_AXIS, GEAR_TEETH, SOURCE_TEETH, DATE_REVERSE, TOOL_SETTINGS, PREVIEW, HELPER, HAND_PREFIX,
    CONTROLLER, PLAYBACK_BASE, CONFIG_AUTO, BIAS, GEAR_SCHEMA,
    AXES, BOUNCE, CHRONO, CONFIG_AXIS, CONFIG_REVERSE, CROWN_AXIS, CROWN_SOURCE,
    DATE_BLEND, DATE_START, DRIVEN_AXIS, ELAPSED, FACTORS, HAND_KEYS, MODE, OFFSET,
    OWNER, PAUSED, PRECISION, RATE, RIG_ID, ROLE,
    ROTATION_ORDERS, RUNNING, SPEED, START_H, START_M, START_S, STEPS, TICK, TIME,
)
from .motion import ramp_seconds

TOOL_FIELDS = ('animation_tool', 'shot_start_h', 'shot_start_m', 'shot_start_s', 'shot_end_h',
               'shot_end_m', 'shot_end_s', 'shot_days', 'range_start', 'range_end', 'easing', 'ramp_first', 'ramp_last')


def controller(scene):
    ctrl = scene.clock_rig.controller
    if not ctrl or not ctrl.get(RIG_ID):
        raise ValueError('Create or choose a clock first')
    if ctrl.library or ctrl.override_library or ctrl.name not in scene.objects:
        raise ValueError('Choose an editable clock in this scene')
    if ctrl.animation_data and ctrl.animation_data.nla_tracks:
        raise ValueError('Controller NLA is not supported; flatten it before using clock tools')
    if any(key not in ctrl for key in (MODE, ELAPSED, STEPS, PLAYBACK_BASE)):
        raise ValueError('Update this clock before using the new animation tools')
    return ctrl


def refresh(scene):
    scene.frame_set(scene.frame_current, subframe=scene.frame_subframe)


def load_clock(settings):
    ctrl = settings.controller
    if not ctrl or CONFIG_AXIS not in ctrl:
        return
    for role in FACTORS:
        setattr(settings, role, ctrl.get(HAND_PREFIX + role))
    settings.axis = ctrl[CONFIG_AXIS]
    settings.auto_axis = bool(ctrl.get(CONFIG_AUTO, False))
    settings.reverse = ctrl.get(CONFIG_REVERSE, False)
    settings.precision = bool(ctrl.get(PRECISION, False))
    settings.crown = ctrl.get(CROWN_SOURCE)
    settings.use_crown = settings.crown is not None
    settings.crown_axis = 'XYZ'[ctrl.get(CROWN_AXIS, 0)]
    settings.movement = ('SWEEP' if not ctrl.get(TICK, 1) else
                         'MECH6' if ctrl.get(STEPS) == 6 else 'MECH8' if ctrl.get(STEPS) == 8 else 'QUARTZ')
    settings.date_object = settings.chrono_second = settings.chrono_minute = settings.chrono_hour = None
    settings.gear_object = settings.gear_source = None
    for key, value in ctrl.get(TOOL_SETTINGS, {}).items():
        if key in TOOL_FIELDS:
            try:
                setattr(settings, key, value)
            except (TypeError, ValueError):
                pass  # A saved tool preference must not block opening the clock.
    for obj in core.managed_hands(ctrl):
        role = obj.get(ROLE)
        if role == 'date':
            settings.date_object = obj
            settings.date_axis = 'XYZ'[obj[DRIVEN_AXIS]]
            settings.date_reverse = bool(obj.get(DATE_REVERSE))
        elif role and role.startswith('chrono_'):
            setattr(settings, role, obj)
            settings.chrono_axis = 'XYZ'[obj[DRIVEN_AXIS]]
        elif role == 'gear' and not settings.gear_object:
            settings.gear_object, settings.gear_source = obj, obj.get(SOURCE)
            settings.gear_axis = 'XYZ'[obj[DRIVEN_AXIS]]
            settings.gear_source_axis = 'XYZ'[obj.get(SOURCE_AXIS, 1)]
            settings.gear_teeth = obj.get(GEAR_TEETH, 40)
            settings.source_teeth = obj.get(SOURCE_TEETH, 20)
            settings.gear_reverse = obj.get(GEAR_RATIO, -1) < 0


def new_clock(settings):
    settings.controller = None
    for name in (*FACTORS, 'crown', 'date_object', 'chrono_second', 'chrono_minute', 'chrono_hour', 'gear_object', 'gear_source'):
        setattr(settings, name, None)
    settings.use_crown = False
    settings.ui_page, settings.setup_stage = 'ANIMATE', 'HANDS'
    settings.animation_tool, settings.extra_tool = 'PLAYBACK', 'CROWN'
    settings.show_alignment = settings.show_advanced = False


def _curve(ctrl, key):
    return next((fc for fc in core._rotation_curves(ctrl) if fc.data_path == core.prop_path(key)), None)


def _clear_curve(ctrl, key):
    curve = _curve(ctrl, key)
    if curve:
        curve.keyframe_points.clear()


def keys(ctrl, key, points, interpolation='LINEAR', replace=False, extrapolation='CONSTANT'):
    points = list(points)
    if not points or not all(isfinite(frame) and isfinite(value) for frame, value in points):
        raise ValueError('Animation frames and values must be finite')
    if replace:
        _clear_curve(ctrl, key)
    # One native insert creates the action/slot. Bulk allocation avoids quadratic ramps.
    insertions = points[:1] if replace else points
    for frame, value in insertions:
        ctrl[key] = float(value)
        if not ctrl.keyframe_insert(core.prop_path(key), frame=frame, group='Clock Animation'):
            raise ValueError('Could not insert clock animation key')
    curve = _curve(ctrl, key)
    if not curve:
        raise ValueError('Clock animation curve could not be found')
    if replace:
        curve.keyframe_points.clear()
        curve.keyframe_points.add(len(points))
        curve.keyframe_points.foreach_set('co', [component for point in points for component in point])
    requested = {round(float(frame), 3) for frame, _ in points}
    for point in curve.keyframe_points:
        if round(point.co.x, 3) in requested:
            point.interpolation = interpolation
            if interpolation == 'BEZIER':
                point.handle_left_type = point.handle_right_type = 'AUTO_CLAMPED'
    curve.extrapolation = extrapolation
    curve.update()


def _range(settings):
    core.validate_frames(settings.id_data, settings.range_start, settings.range_end)
    if settings.range_end <= settings.range_start:
        raise ValueError('Last frame must be after first frame')
    return settings.range_start, settings.range_end


def _save_tool_settings(ctrl, settings):
    ctrl[TOOL_SETTINGS] = {name: getattr(settings, name) for name in TOOL_FIELDS}


@atomic
def shot(scene):
    ctrl, settings = controller(scene), scene.clock_rig
    first, last = _range(settings)
    start = settings.shot_start_h * 3600 + settings.shot_start_m * 60 + settings.shot_start_s
    end = settings.shot_end_h * 3600 + settings.shot_end_m * 60 + settings.shot_end_s + settings.shot_days * 86400
    ctrl[START_H], ctrl[START_M], ctrl[START_S] = settings.shot_start_h, settings.shot_start_m, settings.shot_start_s
    keys(ctrl, ELAPSED, [(first, 0), (last, end - start)],
         'BEZIER' if settings.easing == 'SMOOTH' else 'LINEAR', replace=True)
    ctrl[MODE], ctrl[PAUSED] = 1, 0
    settings.animation_tool = 'SHOT'
    _save_tool_settings(ctrl, settings)
    ctrl.update_tag()
    refresh(scene)


@atomic
def speed_ramp(scene):
    ctrl, settings = controller(scene), scene.clock_rig
    first, last = _range(settings)
    effective_fps = scene.render.fps / scene.render.fps_base
    # Anchor the new ramp to the existing base clock at its first frame.
    current, subframe = scene.frame_current, scene.frame_subframe
    try:
        scene.frame_set(first)
        initial = ctrl[ELAPSED] if ctrl[MODE] else ctrl.get(PLAYBACK_BASE, 0) + (first - ctrl[OFFSET]) / effective_fps * ctrl[SPEED]
        points = [(f, initial + ramp_seconds(f, first, last, settings.ramp_first,
                   settings.ramp_last, effective_fps, settings.easing == 'SMOOTH')) for f in range(first, last + 1)]
        horizon = last + max(1, scene.render.fps)
        points.append((horizon, initial + ramp_seconds(horizon, first, last, settings.ramp_first,
                       settings.ramp_last, effective_fps, settings.easing == 'SMOOTH')))
        keys(ctrl, ELAPSED, points, replace=True, extrapolation='LINEAR')
        ctrl[MODE], ctrl[PAUSED] = 1, 0
        settings.animation_tool = 'RAMP'
        _save_tool_settings(ctrl, settings)
        ctrl.update_tag()
    finally:
        scene.frame_set(current, subframe=subframe)


def _truncate(curve, frame):
    """Split a Bezier segment at frame, keeping its entire past shape."""
    value = curve.evaluate(frame)
    points = list(curve.keyframe_points)
    left = next((p for p in reversed(points) if p.co.x < frame), None)
    right = next((p for p in points if p.co.x >= frame), None)
    boundary_handle = None
    # Freeze automatic handles before deleting the future key that defines them.
    handles = [(p, p.handle_left.copy(), p.handle_right.copy()) for p in points]
    for p, hl, hr in handles:
        p.handle_left_type = p.handle_right_type = 'FREE'
        p.handle_left, p.handle_right = hl, hr
    if left and right and right.co.x > frame and left.interpolation == 'BEZIER':
        a, b, c, d = left.co.copy(), left.handle_right.copy(), right.handle_left.copy(), right.co.copy()
        lo, hi = 0.0, 1.0
        for _ in range(50):
            u = (lo + hi) / 2
            x = (1-u)**3*a.x + 3*(1-u)**2*u*b.x + 3*(1-u)*u*u*c.x + u**3*d.x
            if x < frame:
                lo = u
            else:
                hi = u
        u = (lo + hi) / 2
        ab, bc = a.lerp(b, u), b.lerp(c, u)
        abc = ab.lerp(bc, u)
        left.handle_right = ab
        boundary_handle = abc
    elif right and right.co.x == frame:
        boundary_handle = right.handle_left.copy()
    for index in reversed(range(len(curve.keyframe_points))):
        if curve.keyframe_points[index].co.x > frame:
            curve.keyframe_points.remove(curve.keyframe_points[index], fast=True)
    point = curve.keyframe_points.insert(frame, value, options={'FAST'})
    point.handle_left_type = point.handle_right_type = 'FREE'
    if boundary_handle is not None:
        point.handle_left = boundary_handle
    curve.update()
    return value


@atomic
def pause_resume(scene):
    ctrl = controller(scene)
    frame = scene.frame_current + scene.frame_subframe
    fps = scene.render.fps / scene.render.fps_base
    if ctrl[MODE] == 0:
        start = min(scene.frame_start, frame - 1)
        anchor = ctrl.get(PLAYBACK_BASE, 0)
        points = [(start, anchor + (start - ctrl[OFFSET]) / fps * ctrl[SPEED]),
                  (frame, anchor + (frame - ctrl[OFFSET]) / fps * ctrl[SPEED])]
        keys(ctrl, ELAPSED, points, replace=True)
        ctrl[MODE] = 1
    curve = _curve(ctrl, ELAPSED)
    if not curve:
        keys(ctrl, ELAPSED, [(frame, ctrl[ELAPSED])])
        curve = _curve(ctrl, ELAPSED)
    value = _truncate(curve, frame)
    if ctrl.get(PAUSED):
        horizon = max(1, scene.render.fps)
        keys(ctrl, ELAPSED, [(frame, value), (frame + horizon, value + horizon * ctrl[SPEED] / fps)], extrapolation='LINEAR')
        ctrl[PAUSED] = 0
    else:
        keys(ctrl, ELAPSED, [(frame, value)], extrapolation='CONSTANT')
        ctrl[PAUSED] = 1
    ctrl.update_tag()
    refresh(scene)


@atomic
def playback(scene):
    ctrl = controller(scene)
    # Preserve the current base time when switching from a saved shot to playback.
    if ctrl[MODE]:
        value = float(ctrl[ELAPSED])
        ctrl[OFFSET] = scene.frame_current + scene.frame_subframe
        ctrl[PLAYBACK_BASE] = value
    ctrl[MODE], ctrl[PAUSED] = 0, 0
    ctrl.update_tag()
    refresh(scene)


def movement(scene):
    ctrl = controller(scene)
    preset = scene.clock_rig.movement
    ctrl[TICK] = 0 if preset == 'SWEEP' else 1
    ctrl[STEPS] = {'QUARTZ': 1.0, 'MECH6': 6.0, 'MECH8': 8.0, 'SWEEP': 1.0}[preset]
    ctrl.update_tag()
    refresh(scene)


@atomic
def turn_crown(scene, turns=None, keyframe=True):
    ctrl, settings = controller(scene), scene.clock_rig
    crown = ctrl.get(CROWN_SOURCE)
    if not crown:
        raise ValueError('Connect a crown in Setup, then update the clock')
    axis = int(ctrl[CROWN_AXIS])
    if crown.rotation_mode != ROTATION_ORDERS['XYZ'[axis]]:
        raise ValueError('Crown rotation mode changed; update the clock first')
    turns = settings.crown_turns if turns is None else turns
    if not isfinite(turns):
        raise ValueError('Turn amount must be finite')
    crown.rotation_euler[axis] += turns * 2 * pi
    if keyframe and not crown.keyframe_insert('rotation_euler', index=axis, frame=scene.frame_current + scene.frame_subframe, group='Crown'):
        raise ValueError('Could not keyframe the crown')
    crown.update_tag()
    refresh(scene)


def _validate_output(scene, ctrl, obj, source=None, role=None):
    if not obj:
        raise ValueError('Choose an object first')
    if obj.library or obj.override_library or obj.name not in scene.objects:
        raise ValueError(f'{obj.name}: choose an editable object in this scene')
    if obj == ctrl or obj == ctrl.get(CROWN_SOURCE) or obj == source or RIG_ID in obj:
        raise ValueError('A mechanism must be separate from its driving object and controller')
    updating = core.belongs_to(obj, ctrl) and obj.get(ROLE) == role
    if OWNER in obj and not updating:
        raise ValueError(f'{obj.name}: already rigged; remove it before assigning a new role')
    if any(key in obj for key in HAND_KEYS) and not updating:
        raise ValueError(f'{obj.name}: reserved rig properties already exist')
    if not all(isfinite(value) for value in (*obj.rotation_euler, *obj.rotation_quaternion, *obj.rotation_axis_angle)):
        raise ValueError(f'{obj.name}: object rotation must be finite')
    for fc in core.drivers(obj) + core._rotation_curves(obj):
        if fc.data_path.startswith(('rotation_', 'delta_rotation_')):
            if updating and fc in core.drivers(obj) and fc.data_path == 'rotation_euler' and fc.array_index == obj[DRIVEN_AXIS]:
                continue
            raise ValueError(f'{obj.name}: existing rotation animation would be overwritten')
    pending, seen = [source] if source else [], set()
    while pending:
        ancestor = pending.pop()
        if ancestor == obj:
            raise ValueError('This connection would create a transform cycle')
        if ancestor in seen:
            continue
        seen.add(ancestor)
        pending.extend(item for item in (ancestor.parent, ancestor.get(SOURCE)) if item)
        for fc in core.drivers(ancestor):
            pending.extend(target.id for var in fc.driver.variables for target in var.targets if isinstance(target.id, bpy.types.Object))


def attach(scene, obj, role, axis, expression, variables, rate=None):
    ctrl = controller(scene)
    core.remember_hand(obj)
    obj[OWNER], obj[ROLE], obj[DRIVEN_AXIS] = ctrl[RIG_ID], role, AXES[axis]
    obj[CONTROLLER] = ctrl
    core._set_local_axis(obj, axis)
    base = obj.rotation_euler[AXES[axis]]
    obj[BASE] = base
    try:
        core._driver(obj, 'rotation_euler', f'({base:.15f})+({expression})', variables, AXES[axis])
        if rate is not None:
            obj[RATE] = rate
    except Exception:
        core.restore_hand(obj)
        raise
    refresh(scene)


@atomic
def add_date(scene):
    settings, ctrl = scene.clock_rig, controller(scene)
    _validate_output(scene, ctrl, settings.date_object, role='date')
    if any(o.get(ROLE) == 'date' and o != settings.date_object for o in core.managed_hands(ctrl)):
        raise ValueError('This clock already has a date wheel; remove that mechanism first')
    if settings.date_object.get(OWNER) == ctrl[RIG_ID]:
        core.restore_hand(settings.date_object)
    sign = -1 if settings.date_reverse else 1
    position = '(floor(t/86400)+day-1+max(0,(t-floor(t/86400)*86400-86400+blend)/max(blend,0.001)))'
    expression = f'{sign * 2 * pi / 31:.15f}*{position}'
    attach(scene, settings.date_object, 'date', settings.date_axis, expression, [
        (n, ctrl, core.prop_path(k), 'OBJECT') for n, k in (('t', TIME), ('day', DATE_START), ('blend', DATE_BLEND))
    ])
    settings.date_object[DATE_REVERSE] = settings.date_reverse


def create_date_wheel(scene):
    """Build static numeral meshes on a ring; only the completed object rotates."""
    from mathutils import Matrix, Vector

    radius = scene.clock_rig.date_radius
    vertices, faces, materials = [], [], []
    for i in range(31):
        a, b = 2 * pi * i / 31, 2 * pi * (i + 1) / 31
        start = len(vertices)
        vertices.extend([(r * sin(angle), r * cos(angle), 0) for angle, r in ((a, radius * 0.83), (a, radius * 1.17), (b, radius * 1.17), (b, radius * 0.83))])
        faces.append(tuple(range(start, start + 4)))
        materials.append(0)
    for number in range(1, 32):
        text = bpy.data.curves.new('Date numeral', 'FONT')
        text.body, text.align_x, text.align_y = str(number), 'CENTER', 'CENTER'
        text.size, text.resolution_u = radius * 0.105, 4
        temporary = bpy.data.objects.new('Date numeral', text)
        scene.collection.objects.link(temporary)
        try:
            bpy.context.view_layer.update()
            mesh = bpy.data.meshes.new_from_object(temporary.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            try:
                angle = 2 * pi * (number - 1) / 31
                transform = Matrix.Translation(Vector((radius * sin(angle), radius * cos(angle), radius * 0.002))) @ Matrix.Rotation(-angle, 4, 'Z')
                start = len(vertices)
                vertices.extend([tuple(transform @ v.co) for v in mesh.vertices])
                faces.extend([tuple(start + v for v in polygon.vertices) for polygon in mesh.polygons])
                materials.extend([1] * len(mesh.polygons))
            finally:
                bpy.data.meshes.remove(mesh)
        finally:
            bpy.data.objects.remove(temporary, do_unlink=True)
            bpy.data.curves.remove(text)
    mesh = bpy.data.meshes.new('Date Wheel')
    mesh.from_pydata(vertices, [], faces)
    for name, color in (('Date paper', (0.9, 0.9, 0.87, 1)), ('Date ink', (0.015, 0.015, 0.015, 1))):
        material = bpy.data.materials.new(name)
        material.diffuse_color = color
        material.use_nodes = True
        material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = color
        mesh.materials.append(material)
    for polygon, material in zip(mesh.polygons, materials):
        polygon.material_index = material
    obj = bpy.data.objects.new('Date_Wheel_1_to_31', mesh)
    scene.collection.objects.link(obj)
    obj.location = scene.cursor.location
    obj.rotation_euler.x = pi / 2
    scene.clock_rig.date_object, scene.clock_rig.date_axis = obj, 'Z'
    return obj


@atomic
def add_gear(scene):
    settings, ctrl = scene.clock_rig, controller(scene)
    obj, source = settings.gear_object, settings.gear_source
    if not source or source.library or source.name not in scene.objects:
        raise ValueError('Choose a local driving object')
    _validate_output(scene, ctrl, obj, source, role='gear')
    ratio = settings.source_teeth / settings.gear_teeth * (-1 if settings.gear_reverse else 1)
    rate = source.get(RATE) if core.belongs_to(source, ctrl) else None
    source_axis = source.get(DRIVEN_AXIS, AXES[settings.gear_source_axis]) if core.belongs_to(source, ctrl) else AXES[settings.gear_source_axis]
    if RATE in obj and rate is None and any(part.get(SOURCE) == obj for part in core.managed_hands(ctrl)):
        raise ValueError('Remove dependent gears before changing this gear to an external input')
    if rate is not None:
        rate *= ratio
        # Use unwrapped shared time, so bounded hand previews cannot reset gear phase.
        time = float(ctrl[TIME])
        quantized = time - ctrl[TICK] * (time - floor(time * ctrl[STEPS]) / ctrl[STEPS])
        zero = source.get(BIAS, source.get(BASE, 0.0)) + source[RATE] * quantized
        expression = '0.0'  # Replaced below once the source reference has been stored.
        variables = [(n, ctrl, core.prop_path(k), 'OBJECT') for n, k in (('t', TIME), ('tick', TICK), ('hz', STEPS))]
    else:
        axis = source_axis
        if source.rotation_mode != ROTATION_ORDERS['XYZ'[axis]]:
            raise ValueError(f'Driving object needs {ROTATION_ORDERS["XYZ"[axis]]} Euler before keyframing')
        zero = float(source.rotation_euler[axis])
        expression = f'{ratio:.15f}*(angle-({zero:.15f}))'
        variables = [('angle', source, f'rotation_euler[{axis}]', 'OBJECT')]
    if obj.get(OWNER) == ctrl[RIG_ID]:
        core.restore_hand(obj)
    attach(scene, obj, 'gear', settings.gear_axis, expression, variables, rate)
    obj[SOURCE] = source
    obj[GEAR_RATIO] = ratio
    obj[SOURCE_ZERO] = zero
    obj[GEAR_SCHEMA] = 1
    obj[SOURCE_AXIS] = source_axis
    obj[GEAR_TEETH], obj[SOURCE_TEETH] = settings.gear_teeth, settings.source_teeth
    rebuild_gears(scene, ctrl)
    refresh(scene)


def rebuild_gears(scene, ctrl, reverse_changed=False):
    """Refresh derived rates after hand direction changes, in dependency order."""
    gears = [obj for obj in core.managed_hands(ctrl) if obj.get(ROLE) == 'gear']
    pending = set(gears)
    for _ in range(len(gears) + 1):
        progressed = False
        for obj in list(pending):
            source = obj.get(SOURCE)
            if not source or source in pending:
                continue
            if core.belongs_to(source, ctrl) and RATE in source:
                rate = source[RATE] * obj[GEAR_RATIO]
                obj[RATE] = rate
                zero = obj[SOURCE_ZERO]
                source_bias = source.get(BIAS, source.get(BASE, 0.0))
                if not obj.get(GEAR_SCHEMA):
                    zero = source_bias + source[RATE] * (zero - ctrl[TICK] * (zero - floor(zero * ctrl[STEPS]) / ctrl[STEPS]))
                    obj[SOURCE_ZERO], obj[GEAR_SCHEMA] = zero, 1
                if reverse_changed:
                    zero = 2 * source.get(BASE, 0.0) - zero
                    obj[SOURCE_ZERO] = zero
                bias = obj[BASE] + obj[GEAR_RATIO] * (source_bias - zero)
                obj[BIAS] = bias
                expression = f'({bias:.15f})+({rate:.15f})*(t-tick*(t-floor(t*hz)/hz))'
                core._driver(obj, 'rotation_euler', expression, [
                    (n, ctrl, core.prop_path(k), 'OBJECT') for n, k in (('t', TIME), ('tick', TICK), ('hz', STEPS))
                ], int(obj[DRIVEN_AXIS]))
            else:
                if RATE in obj:
                    del obj[RATE]
                axis, zero = obj[SOURCE_AXIS], obj[SOURCE_ZERO]
                expression = f'({obj[BASE]:.15f})+({obj[GEAR_RATIO]:.15f})*(angle-({zero:.15f}))'
                core._driver(obj, 'rotation_euler', expression, [('angle', source, f'rotation_euler[{axis}]', 'OBJECT')], int(obj[DRIVEN_AXIS]))
            pending.remove(obj)
            progressed = True
        if not pending or not progressed:
            break
    if pending:
        raise ValueError('A geared object has a missing or cyclic source; repair that connection first')


def remove_mechanism(scene, obj):
    ctrl = controller(scene)
    if not obj or obj.get(OWNER) != ctrl[RIG_ID] or obj.get(ROLE) in FACTORS:
        raise ValueError('Select an optional mechanism belonging to this clock')
    if any(part.get(SOURCE) == obj for part in core.managed_hands(ctrl)):
        raise ValueError('Remove gears driven by this object first')
    core.restore_hand(obj)
    load_clock(scene.clock_rig)
    refresh(scene)


@atomic
def add_chronograph(scene):
    settings, ctrl = scene.clock_rig, controller(scene)
    objects = [(role, getattr(settings, 'chrono_' + role)) for role in FACTORS if getattr(settings, 'chrono_' + role)]
    if not objects:
        raise ValueError('Assign at least one stopwatch hand')
    if len({obj for _, obj in objects}) != len(objects):
        raise ValueError('Stopwatch hands must be distinct objects')
    for role, obj in objects:
        _validate_output(scene, ctrl, obj, role='chrono_' + role)
        if any(part.get(ROLE) == 'chrono_' + role and part != obj for part in core.managed_hands(ctrl)):
            raise ValueError('Remove the existing stopwatch hand before replacing it')
    for role, obj in objects:
        if core.belongs_to(obj, ctrl):
            core.restore_hand(obj)
        rate = {'second': 2 * pi / 60, 'minute': 2 * pi / 3600, 'hour': 2 * pi / 43200}[role]
        attach(scene, obj, 'chrono_' + role, settings.chrono_axis, f'{rate:.15f}*t', [('t', ctrl, core.prop_path(CHRONO), 'OBJECT')])


@atomic
def chronograph(scene, command):
    if command not in {'START', 'STOP', 'RESET'}:
        raise ValueError('Unknown stopwatch command')
    ctrl = controller(scene)
    if not any(o.get(ROLE, '').startswith('chrono_') for o in core.managed_hands(ctrl)):
        raise ValueError('Add stopwatch hands first')
    frame = scene.frame_current + scene.frame_subframe
    curve = _curve(ctrl, CHRONO)
    value = curve.evaluate(frame) if curve else ctrl[CHRONO]
    if curve and command != 'RESET':
        _truncate(curve, frame)
    fps = scene.render.fps / scene.render.fps_base
    if command == 'START':
        horizon = max(1, scene.render.fps)
        keys(ctrl, CHRONO, [(frame, value), (frame + horizon, value + horizon / fps)], extrapolation='LINEAR')
        ctrl[RUNNING] = 1
    elif command == 'STOP':
        keys(ctrl, CHRONO, [(frame, value)], extrapolation='CONSTANT')
        ctrl[RUNNING] = 0
    elif command == 'RESET':
        # Native key insertion merges nearby frames. Allocate the discontinuity
        # directly, with a gap representable by Blender's single-precision keys.
        boundary = frame - max(0.02, abs(frame) * 2**-22)
        if curve:
            _truncate(curve, boundary)
            curve.keyframe_points[-1].interpolation = 'CONSTANT'
            curve.keyframe_points.add(1)
            point = curve.keyframe_points[-1]
            point.co, point.interpolation = (frame, 0), 'CONSTANT'
            curve.extrapolation = 'CONSTANT'
            curve.update()
        else:
            keys(ctrl, CHRONO, [(boundary, value), (frame, 0)], interpolation='CONSTANT', replace=True)
        ctrl[CHRONO] = 0.0
        ctrl[RUNNING] = 0
    ctrl.update_tag()
    refresh(scene)


def setup_helpers(scene, test_rotation=False):
    settings = scene.clock_rig
    hands = core.assigned(settings)
    if not hands:
        raise ValueError('Assign hands first')
    axis = core.hand_axis(settings)
    if settings.helper_collection:
        clear_helpers(scene)
    collection = bpy.data.collections.new('Clock Alignment Preview')
    collection[PREVIEW] = True
    scene.collection.children.link(collection)
    settings.helper_collection = collection
    for role, obj in hands:
        helper = bpy.data.objects.new(role.title() + ' axle', None)
        helper[HELPER] = True
        helper.empty_display_type = 'ARROWS'
        helper.empty_display_size = max(0.05, obj.dimensions.length * 0.25)
        helper.show_in_front, helper.hide_render = True, True
        collection.objects.link(helper)
        helper.matrix_world = obj.matrix_world
        if test_rotation:
            preview = obj.copy()
            preview.animation_data_clear()
            preview.name = role.title() + ' +15 degrees preview'
            preview[HELPER] = True
            preview.hide_render, preview.display_type, preview.show_in_front = True, 'WIRE', True
            collection.objects.link(preview)
            core._set_local_axis(preview, axis)
            preview.rotation_euler[AXES[axis]] += pi / 12
            for key in HAND_KEYS:
                if key in preview:
                    del preview[key]


def clear_helpers(scene):
    collection = scene.clock_rig.helper_collection
    if collection:
        if not collection.get(PREVIEW):
            raise ValueError('This collection is not a clock preview; leave it untouched')
        for obj in list(collection.objects):
            if obj.get(HELPER):
                bpy.data.objects.remove(obj, do_unlink=True)
        if not collection.objects and not collection.children:
            bpy.data.collections.remove(collection)
        scene.clock_rig.helper_collection = None


def bake_copy(scene):
    """Sample evaluated world matrices onto independent export objects."""
    settings, ctrl = scene.clock_rig, controller(scene)
    first, last, step = settings.bake_start, settings.bake_end, settings.bake_step
    core.validate_frames(scene, first, last)
    originals = core.managed_hands(ctrl)
    if not originals:
        raise ValueError('The selected clock has no driven objects')
    collection = bpy.data.collections.new(ctrl.name + ' Export')
    scene.collection.children.link(collection)
    copies = []
    current, subframe = scene.frame_current, scene.frame_subframe
    try:
        for obj in originals:
            copy = obj.copy()
            if obj.data:
                copy.data = obj.data.copy()
            copy.animation_data_clear()
            copy.parent = None
            for constraint in list(copy.constraints):
                copy.constraints.remove(constraint)
            for key in HAND_KEYS:
                if key in copy:
                    del copy[key]
            copy.name = obj.name + ' Baked'
            copy.rotation_mode = 'XYZ'
            collection.objects.link(copy)
            copies.append(copy)
        frames = sorted(set(range(first, last + 1, step)) | {last})
        previous = [None] * len(copies)
        for frame in frames:
            scene.frame_set(frame)
            graph = bpy.context.evaluated_depsgraph_get()
            for index, (obj, copy) in enumerate(zip(originals, copies)):
                matrix = obj.evaluated_get(graph).matrix_world
                location, rotation, scale = matrix.decompose()
                euler = rotation.to_euler('XYZ', previous[index]) if previous[index] else rotation.to_euler('XYZ')
                copy.location, copy.rotation_euler, copy.scale = location, euler, scale
                previous[index] = euler.copy()
                for path in ('location', 'rotation_euler', 'scale'):
                    if not copy.keyframe_insert(path, frame=frame, group='Clock Export'):
                        raise ValueError(f'{copy.name}: failed to bake transform')
        for original, copy in zip(originals, copies):
            for curve in core._rotation_curves(copy):
                for key in curve.keyframe_points:
                    stepped = ctrl.get(TICK) and not ctrl.get(BOUNCE) and original.get(ROLE) in (*FACTORS, 'gear')
                    key.interpolation = 'CONSTANT' if stepped and curve.data_path == 'rotation_euler' else 'LINEAR'
            action = copy.animation_data.action
            track = copy.animation_data.nla_tracks.new()
            track.name = collection.name
            track.strips.new(action.name, first, action)
            copy.animation_data.action = None
        # A second evaluation verifies every sampled transform before delivery.
        for frame in frames:
            scene.frame_set(frame)
            graph = bpy.context.evaluated_depsgraph_get()
            for original, copy in zip(originals, copies):
                a, b = original.evaluated_get(graph).matrix_world, copy.matrix_world
                if max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4)) > 0.0002:
                    raise ValueError(f'{original.name}: transform has shear that cannot be exported as ordinary TRS keys')
    except Exception:
        for copy in copies:
            data = copy.data
            actions = set()
            if copy.animation_data:
                if copy.animation_data.action:
                    actions.add(copy.animation_data.action)
                actions.update(strip.action for track in copy.animation_data.nla_tracks for strip in track.strips if strip.action)
            bpy.data.objects.remove(copy, do_unlink=True)
            if data and not data.users:
                bpy.data.batch_remove(ids=(data,))
            for action in actions:
                if not action.users:
                    bpy.data.actions.remove(action)
        bpy.data.collections.remove(collection)
        raise
    finally:
        scene.frame_set(current, subframe=subframe)
    settings.export_collection = collection
    return len(copies), len(frames)
