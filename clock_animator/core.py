"""Native driver construction and reversible rig management. No UI or operators."""
from math import isfinite
from uuid import uuid4
from .state import atomic

from .constants import (
    SOURCE, HAND_PREFIX, PHASE_PREFIX, CONTROLLER, REST_DELTA, REST_DELTA_QUAT, PLAYBACK_BASE, CONFIG_AUTO, BASE, BIAS,
    AXES, CROWN_AXIS, CROWN_RATIO, CROWN_REST, CROWN_SECONDS_PER_RADIAN, CROWN_SOURCE,
    BOUNCE, CHRONO, CONFIG_AXIS, CONFIG_REVERSE, DAMPING, DATE_BLEND, DATE_START,
    DRIVEN_AXIS, ELAPSED, FACTORS, HAND_KEYS, MODE, OFFSET, OWNER, PAUSED, PRECISION, RATE, RATES, REST, ROLE, RUNNING, STEPS,
    REST_MODE, REST_ROTATION, RIG_ID, ROTATION_ORDERS, SPEED, START_H, START_M, START_S,
    TICK, TIME, TIME_EXPRESSION,
)


def time_expression(use_crown=False):
    if use_crown:
        return f'{TIME_EXPRESSION} + (c - cr) * gear * {CROWN_SECONDS_PER_RADIAN:.15f}'
    return TIME_EXPRESSION


def hand_expression(base: float, role: str, reverse: bool = False) -> str:
    """Build a native expression with fixed-notation literals."""
    if role not in RATES or not isfinite(base):
        raise ValueError("Invalid hand role or non-finite rest angle")
    rate = RATES[role] * (-1 if reverse else 1)
    return f"({base:.15f}) + ({rate:.15f}) * (t - tick*(t - floor(t)))"


def match_role(name: str):
    """Return an unambiguous name match, never infer from selection order."""
    name = name.lower()
    roles = [role for role, tokens in (
        ('second', ('sec',)), ('minute', ('min',)), ('hour', ('hour', 'hr')),
    ) if any(token in name for token in tokens)]
    if len(roles) > 1:
        raise ValueError(f"Ambiguous hand name: {name}. Use sec, min, or hour")
    return roles[0] if roles else None


def assigned(settings):
    return [(role, getattr(settings, role)) for role in FACTORS if getattr(settings, role)]


def validate_frames(scene, first, last):
    limits = scene.bl_rna.properties['frame_current']
    if first > last or first < limits.hard_min or last > limits.hard_max or last-first > 1_000_000:
        raise ValueError('Choose a range within Blender timeline limits, at most one million frames')


def managed_hands(controller):
    import bpy

    rig_id = controller.get(RIG_ID)
    return [obj for obj in bpy.data.objects if rig_id and obj.get(OWNER) == rig_id and belongs_to(obj, controller)]


def belongs_to(obj, controller):
    """An ID pointer survives real duplication and scene copies; UUID strings do not."""
    if CONTROLLER in obj:
        return obj.get(CONTROLLER) == controller
    return any(target.id == controller for fc in drivers(obj) for variable in fc.driver.variables for target in variable.targets)


def drivers(obj):
    return list(obj.animation_data.drivers) if obj.animation_data else []


def _curve_groups(obj):
    """Read only the action slots actually bound to this object or its NLA strips."""
    animation = obj.animation_data
    if not animation:
        return []
    bindings = [(animation.action, getattr(animation, 'action_slot', None))] if animation.action else []
    bindings += [(strip.action, getattr(strip, 'action_slot', None)) for track in animation.nla_tracks for strip in track.strips if strip.action]
    groups = []
    for action, slot in bindings:
        if getattr(action, 'is_action_layered', False):
            for layer in action.layers:
                for strip in layer.strips:
                    for bag in getattr(strip, 'channelbags', ()):
                        if slot and bag.slot_handle == slot.handle:
                            groups.append(bag.fcurves)
        elif hasattr(action, 'fcurves'):
            groups.append(action.fcurves)
    return groups


def _rotation_curves(obj):
    return list(dict.fromkeys(fc for group in _curve_groups(obj) for fc in group))


def hand_axis(settings):
    """A flat hand spins about its thin dimension, never along its length."""
    if not settings.auto_axis:
        return settings.axis
    axes = []
    for _, obj in assigned(settings):
        if not obj.data or obj.type != 'MESH' or not obj.data.vertices:
            raise ValueError('Automatic axle detection needs mesh hands; disable Auto Detect Axle to choose manually')
        bounds = [max(v.co[i] for v in obj.data.vertices)-min(v.co[i] for v in obj.data.vertices) for i in range(3)]
        ranked = sorted(range(3), key=lambda i: bounds[i])
        if bounds[ranked[1]] <= 1e-12 or bounds[ranked[0]] > bounds[ranked[1]] * 0.35:
            raise ValueError(f'{obj.name}: axle is ambiguous; disable Auto Detect Axle and choose X, Y or Z')
        axes.append('XYZ'[ranked[0]])
    if not axes or len(set(axes)) != 1:
        raise ValueError('Hands have different local axles; align their local axes or choose the axis manually')
    return axes[0]


def validate(scene, settings):
    """Reject conflicts before touching any user animation."""
    hands = assigned(settings)
    if not hands:
        raise ValueError("Assign at least one hand")
    if len({obj.as_pointer() for _, obj in hands}) != len(hands):
        raise ValueError("Each hand must be a distinct object")
    ctrl = settings.controller
    if ctrl and (not ctrl.get(RIG_ID) or ctrl.library or ctrl.override_library or ctrl.name not in scene.objects):
        raise ValueError("Choose a local Clock Animator controller")
    if ctrl and ctrl.animation_data and ctrl.animation_data.nla_tracks:
        raise ValueError('Controller NLA is not supported; use clock animation tools')
    active_id = ctrl.get(RIG_ID) if ctrl else None
    for _, obj in hands:
        if obj == ctrl or RIG_ID in obj:
            raise ValueError(f"{obj.name}: a controller cannot be a hand")
        if obj.name not in scene.objects or obj.library or obj.override_library:
            raise ValueError(f"{obj.name}: hand must be a local object in this scene")
        if obj.get(OWNER) and (obj.get(OWNER) != active_id or not belongs_to(obj, ctrl)):
            raise ValueError(f"{obj.name}: already belongs to another clock")
        if any(key in obj for key in HAND_KEYS) and not obj.get(OWNER):
            raise ValueError(f"{obj.name}: reserved clock properties already exist")
        own_axis = obj.get(DRIVEN_AXIS) if obj.get(OWNER) == active_id else None
        for curve in drivers(obj) + _rotation_curves(obj):
            if curve.data_path.startswith(('rotation_', 'delta_rotation_')):
                if curve in drivers(obj) and curve.data_path == 'rotation_euler' and curve.array_index == own_axis and obj.get(ROLE, 'second') in FACTORS:
                    continue
                raise ValueError(f"{obj.name}: existing rotation animation; remove or bake it first")
        if not all(isfinite(v) for v in (*obj.rotation_euler, *obj.rotation_quaternion, *obj.rotation_axis_angle, *obj.delta_rotation_euler, *obj.delta_rotation_quaternion)):
            raise ValueError(f"{obj.name}: rest rotation must be finite")
    if ctrl:
        for obj in managed_hands(ctrl):
            if obj.library or obj.override_library:
                raise ValueError(f"{obj.name}: cannot restore a linked hand")
            if obj.get(ROLE) == 'gear':
                source = obj.get(SOURCE)
                seen = {obj}
                while source and source.get(ROLE) == 'gear':
                    if source in seen:
                        raise ValueError('A geared object has a cyclic source; remove that mechanism first')
                    seen.add(source)
                    source = source.get(SOURCE)
                if not source:
                    raise ValueError(f'{obj.name}: driving object missing; remove that mechanism first')
    if settings.use_crown:
        crown = settings.crown
        if not crown:
            raise ValueError('Choose a Crown / Rotor object, or disable Use Crown / Rotor')
        if crown.library or crown.override_library or crown.name not in scene.objects:
            raise ValueError(f'{crown.name}: crown must be a local object in this scene')
        if crown == ctrl or RIG_ID in crown or OWNER in crown or any(crown == hand for _, hand in hands):
            raise ValueError('Crown / Rotor must be separate from the hands and controllers')
        ancestor = crown.parent
        while ancestor:
            if ancestor == ctrl or OWNER in ancestor or any(ancestor == hand for _, hand in hands):
                raise ValueError(f'{crown.name}: crown cannot be parented to a clock hand or controller')
            ancestor = ancestor.parent
        if any(fc.data_path.startswith(('rotation_', 'delta_rotation_')) for fc in drivers(crown)):
            raise ValueError(f'{crown.name}: use crown rotation keyframes instead of rotation drivers')
        if crown.rotation_mode != ROTATION_ORDERS[settings.crown_axis] and any(
            fc.data_path.startswith(('rotation_', 'delta_rotation_')) for fc in _rotation_curves(crown)
        ):
            raise ValueError(f'{crown.name}: existing crown animation requires {ROTATION_ORDERS[settings.crown_axis]} Euler for {settings.crown_axis}; set the mode before keyframing')
        values = (crown.rotation_quaternion if crown.rotation_mode == 'QUATERNION' else
                  crown.rotation_axis_angle if crown.rotation_mode == 'AXIS_ANGLE' else crown.rotation_euler)
        if not all(isfinite(value) for value in values):
            raise ValueError(f'{crown.name}: crown rotation must be finite')
    return hands


def _variable(driver, name, owner, path, id_type='OBJECT'):
    variable = driver.variables.new()
    variable.name = name
    variable.type = 'SINGLE_PROP'
    target = variable.targets[0]
    target.id_type = id_type
    target.id = owner
    target.data_path = path


def prop_path(key):
    return f'["{key}"]'


def _driver(obj, path, expression, variables, index=None):
    curve = obj.driver_add(path) if index is None else obj.driver_add(path, index)
    for modifier in list(curve.modifiers):
        curve.modifiers.remove(modifier)
    driver = curve.driver
    driver.type = 'SCRIPTED'
    for variable in list(driver.variables):
        driver.variables.remove(variable)
    for name, owner, data_path, id_type in variables:
        _variable(driver, name, owner, data_path, id_type)
    driver.expression = expression
    if not driver.is_simple_expression:
        raise ValueError("Blender rejected a native clock expression")
    return curve


def _controller(scene, values=None, crown=None, crown_axis='X', existing=None):
    import bpy

    ctrl = existing or bpy.data.objects.new("Clock_Controller", None)
    if existing is None:
        scene.collection.objects.link(ctrl)
    ctrl.empty_display_type = 'PLAIN_AXES'
    ctrl.empty_display_size = 0.2
    ctrl.hide_render = True
    if RIG_ID not in ctrl:
        ctrl[RIG_ID] = uuid4().hex
    specs = {
        START_H: (12, dict(min=0, max=23, description="Starting hour, 0 to 23")),
        START_M: (0, dict(min=0, max=59, description="Starting minute")),
        START_S: (0.0, dict(min=0.0, max=59.999, description="Starting second")),
        SPEED: (1.0, dict(soft_min=-1000.0, soft_max=1000.0, description="1 = real time; negative runs backwards")),
        TICK: (1, dict(min=0, max=1, description="1 = jump each second; 0 = smooth sweep")),
        OFFSET: (float(scene.frame_start), dict(description="Frame at which starting time is shown")),
        TIME: (0.0, dict(description="Driven unwrapped clock seconds from 00:00:00")),
        MODE: (0, dict(min=0, max=1, description='0 = playback; 1 = saved animation')),
        ELAPSED: (0.0, dict(description='Animated elapsed seconds; generated by shot and ramp tools')),
        PLAYBACK_BASE: (0.0, dict(description='Base elapsed seconds when returning to playback')),
        STEPS: (1.0, dict(min=1.0, max=1000.0, description='Mechanical steps per second')),
        BOUNCE: (0.0, dict(min=0.0, max=0.1, subtype='ANGLE', description='Optional second-hand tick rebound')),
        DAMPING: (6.0, dict(min=0.1, max=30.0, description='How quickly tick rebound settles')),
        CHRONO: (0.0, dict(description='Independent stopwatch elapsed seconds')),
        RUNNING: (0, dict(min=0, max=1)),
        PAUSED: (0, dict(min=0, max=1)),
        DATE_START: (1, dict(min=1, max=31, description='Date shown on the first clock day')),
        DATE_BLEND: (0.0, dict(min=0.0, max=86400.0, description='Seconds before midnight used for date change; 0 = instant')),

    }
    for key, (default, metadata) in specs.items():
        if key not in ctrl:
            ctrl[key] = values.get(key, default) if values else default
        ctrl.id_properties_ui(key).update(**metadata)
    variables = [
        (name, ctrl, prop_path(key), 'OBJECT') for name, key in (
            ('h', START_H), ('m', START_M), ('s', START_S), ('speed', SPEED), ('off', OFFSET), ('mode', MODE), ('elapsed', ELAPSED), ('anchor', PLAYBACK_BASE),
        )
    ] + [('fps', scene, 'render.fps', 'SCENE'), ('fb', scene, 'render.fps_base', 'SCENE')]
    if crown:
        axis = AXES[crown_axis]
        ctrl[CROWN_SOURCE], ctrl[CROWN_AXIS] = crown, axis
        ctrl[CROWN_REST] = values.get(CROWN_REST, float(crown.rotation_euler[axis])) if values else float(crown.rotation_euler[axis])
        ctrl[CROWN_RATIO] = values.get(CROWN_RATIO, 60.0) if values else 60.0
        ctrl.id_properties_ui(CROWN_REST).update(description='Crown angle at setup, in radians')
        ctrl.id_properties_ui(CROWN_RATIO).update(
            soft_min=-1000.0, soft_max=1000.0,
            description='Second-hand turns per crown turn; 60 = one hour of clock time per crown turn; negative reverses gearing',
        )
        variables += [('c', crown, f'rotation_euler[{axis}]', 'OBJECT'),
                      ('cr', ctrl, prop_path(CROWN_REST), 'OBJECT'),
                      ('gear', ctrl, prop_path(CROWN_RATIO), 'OBJECT')]
    else:
        for key in (CROWN_SOURCE, CROWN_AXIS, CROWN_REST, CROWN_RATIO):
            if key in ctrl:
                del ctrl[key]
    expression = time_expression(crown is not None).replace('(frame - off) * fb / fps * speed', '(anchor+(frame-off)*fb/fps*speed if mode==0 else elapsed)')
    _driver(ctrl, prop_path(TIME), expression, variables)
    for role, period in (('second', 60), ('minute', 3600), ('hour', 43200)):
        key = PHASE_PREFIX + role
        if ctrl.get(PRECISION):
            ctrl[key] = 0.0
            _driver(ctrl, prop_path(key), f'fmod(({expression}),{period:.1f})', variables)
        else:
            ctrl.driver_remove(prop_path(key))
            if key in ctrl:
                del ctrl[key]
    return ctrl


def _set_local_axis(obj, axis):
    order = ROTATION_ORDERS[axis]
    if obj.rotation_mode == order:
        return
    total = obj.matrix_basis.to_3x3()
    for index in range(3):
        scale = obj.scale[index] * obj.delta_scale[index]
        if abs(scale) < 1e-15:
            raise ValueError(f'{obj.name}: spindle setup needs nonzero object scale')
        total.col[index] = total.col[index] / scale
    if obj.rotation_mode == 'QUATERNION':
        rotation = obj.rotation_quaternion.copy()
    elif obj.rotation_mode == 'AXIS_ANGLE':
        from mathutils import Quaternion
        aa = obj.rotation_axis_angle
        rotation = Quaternion(aa[1:], aa[0])
    else:
        rotation = obj.rotation_euler.to_quaternion()
    rotation.normalize()
    delta = total.to_quaternion() @ rotation.inverted()
    # The first Euler axis rotates in the object's own local frame.
    obj.rotation_mode = order
    obj.rotation_euler = rotation.to_euler(order)
    obj.delta_rotation_euler = delta.to_euler(order)


def remember_hand(obj):
    obj[REST] = list(obj.rotation_euler)
    obj[REST_MODE] = obj.rotation_mode
    obj[REST_ROTATION] = list(obj.rotation_quaternion if obj.rotation_mode == 'QUATERNION' else obj.rotation_axis_angle)
    obj[REST_DELTA] = list(obj.delta_rotation_euler)
    obj[REST_DELTA_QUAT] = list(obj.delta_rotation_quaternion)


def restore_hand(obj):
    axis = obj.get(DRIVEN_AXIS)
    if axis is not None:
        obj.driver_remove('rotation_euler', int(axis))
    if REST in obj:
        mode = obj.get(REST_MODE, 'XYZ')
        obj.rotation_mode = mode
        obj.rotation_euler = obj[REST][:]
        if mode == 'QUATERNION':
            obj.rotation_quaternion = obj[REST_ROTATION][:]
        elif mode == 'AXIS_ANGLE':
            obj.rotation_axis_angle = obj[REST_ROTATION][:]
        if REST_DELTA in obj:
            obj.delta_rotation_euler = obj[REST_DELTA][:]
        if REST_DELTA_QUAT in obj:
            obj.delta_rotation_quaternion = obj[REST_DELTA_QUAT][:]
    for key in HAND_KEYS:
        if key in obj:
            del obj[key]


def remove_rig(settings, clear_slots=True):
    import bpy

    ctrl = settings.controller
    if not ctrl:
        raise ValueError("Select an active clock controller first")
    if not ctrl.get(RIG_ID) or ctrl.library or ctrl.override_library or ctrl.name not in settings.id_data.objects:
        raise ValueError("Choose a local Clock Animator controller")
    for obj in managed_hands(ctrl):
        if obj.library or obj.override_library:
            raise ValueError(f"{obj.name}: cannot restore a linked hand")
    for obj in managed_hands(ctrl):
        restore_hand(obj)
    bpy.data.objects.remove(ctrl, do_unlink=True)
    settings.controller = None
    if clear_slots:
        for role in FACTORS:
            setattr(settings, role, None)
        settings.crown = None
        settings.use_crown = False


@atomic
def apply_rig(scene, settings):
    """Preserve the controller and its animation while rebuilding hand channels."""
    from .motion import movement_expression

    hands = validate(scene, settings)
    axis_name = hand_axis(settings)
    existing = settings.controller
    previous_reverse = bool(existing.get(CONFIG_REVERSE, settings.reverse)) if existing else settings.reverse
    values = None
    if existing:
        values = {key: existing[key] for key in (START_H, START_M, START_S, SPEED, TICK, OFFSET, CROWN_RATIO) if key in existing}
        if settings.use_crown and existing.get(CROWN_SOURCE) == settings.crown and existing.get(CROWN_AXIS) == AXES[settings.crown_axis] and CROWN_REST in existing:
            values[CROWN_REST] = existing[CROWN_REST]
        for obj in managed_hands(existing):
            if obj.get(ROLE, 'second') in FACTORS:
                restore_hand(obj)
    crown = settings.crown if settings.use_crown else None
    if crown:
        _set_local_axis(crown, settings.crown_axis)
    if existing:
        existing[PRECISION] = int(settings.precision)
    ctrl = _controller(scene, values, crown, settings.crown_axis, existing)
    if existing is None:
        settings.range_start = settings.bake_start = scene.frame_start
        settings.range_end = max(scene.frame_start + 1, min(scene.frame_end, scene.frame_start + 119))
        settings.bake_end = scene.frame_end
    if existing is None and settings.precision:
        ctrl[PRECISION] = 1
        _controller(scene, values, crown, settings.crown_axis, ctrl)
    try:
        for role, obj in hands:
            remember_hand(obj)
            obj[OWNER], obj[ROLE] = ctrl[RIG_ID], role
            obj[CONTROLLER] = ctrl
            axis = AXES[axis_name]
            obj[DRIVEN_AXIS] = axis
            _set_local_axis(obj, axis_name)
            rate = RATES[role] * (-1 if settings.reverse else 1)
            obj[RATE] = rate
            obj[BASE] = obj[BIAS] = float(obj.rotation_euler[axis])
            source = PHASE_PREFIX + role if ctrl.get(PRECISION) else TIME
            _driver(obj, 'rotation_euler', movement_expression(obj.rotation_euler[axis], rate, role == 'second'), [
                (name, ctrl, prop_path(key), 'OBJECT') for name, key in (
                    ('t', source), ('tick', TICK), ('hz', STEPS), ('amp', BOUNCE), ('damp', DAMPING),
                )
            ], axis)
        ctrl[CONFIG_AXIS], ctrl[CONFIG_REVERSE], ctrl[CONFIG_AUTO] = axis_name, settings.reverse, settings.auto_axis
        settings.axis = axis_name
        for role in FACTORS:
            ctrl[HAND_PREFIX + role] = getattr(settings, role)
        if any(obj.get(ROLE) == 'gear' for obj in managed_hands(ctrl)):
            from .features import rebuild_gears
            rebuild_gears(scene, ctrl, reverse_changed=previous_reverse != settings.reverse)
        ctrl.update_tag()
        scene.frame_set(scene.frame_current, subframe=scene.frame_subframe)
        if any(not fc.driver.is_valid for obj in (ctrl, *(o for _, o in hands)) for fc in drivers(obj)):
            raise ValueError('A clock driver failed to evaluate')
        settings.controller = ctrl
    except Exception:
        for _, obj in hands:
            if obj.get(OWNER) == ctrl[RIG_ID]:
                restore_hand(obj)
        if existing is None:
            import bpy
            bpy.data.objects.remove(ctrl, do_unlink=True)
        raise
    return ctrl


def status(settings):
    ctrl = settings.controller
    if not ctrl:
        return "Assign hands, then create animation"
    if any(key not in ctrl for key in (START_H, START_M, START_S, SPEED, TICK, TIME, OFFSET, MODE, ELAPSED, STEPS, PLAYBACK_BASE)):
        return "Controller properties missing; re-create animation"
    if CROWN_SOURCE in ctrl:
        crown = ctrl.get(CROWN_SOURCE)
        if not crown:
            return 'Crown input missing; re-create animation'
        if any(key not in ctrl for key in (CROWN_REST, CROWN_RATIO, CROWN_AXIS)):
            return 'Crown properties missing; re-create animation'
        axis = ctrl[CROWN_AXIS]
        if not isinstance(axis, int) or axis not in (0, 1, 2):
            return 'Crown axis invalid; re-create animation'
        if crown.rotation_mode != ROTATION_ORDERS['XYZ'[axis]]:
            return 'Crown rotation mode changed; re-create animation'
    hands = managed_hands(ctrl)
    if any(fc.mute for obj in (ctrl, *hands) for fc in drivers(obj)):
        return 'Clock driver muted; enable it or update clock'
    if any(not fc.driver.is_valid or not fc.is_valid for obj in (ctrl, *hands) for fc in drivers(obj)):
        return "Clock driver invalid; re-create animation"
    if not any(fc.data_path == prop_path(TIME) for fc in drivers(ctrl)) or any(not any(fc.data_path == 'rotation_euler' and fc.array_index == obj.get(DRIVEN_AXIS) for fc in drivers(obj)) for obj in hands):
        return "Clock driver missing; re-create animation"
    if len({obj.get(ROLE, 'second') for obj in hands if obj.get(ROLE, 'second') in FACTORS}) < 3:
        return "Partial clock: one or more hands missing"
    return "Clock animation ready"


@atomic
def bake_rig(scene, settings, start, end, delete_controller=False):
    """Sample before removing drivers; roll back if key insertion fails."""
    import bpy

    ctrl = settings.controller
    if not ctrl or not ctrl.get(RIG_ID):
        raise ValueError('Create a clock first')
    validate_frames(scene, start, end)
    hands = managed_hands(ctrl)
    if not hands:
        raise ValueError('No animated hands remain')
    if any(obj.library or obj.override_library for obj in hands):
        raise ValueError('Baking requires local editable hands')
    if any(obj.animation_data and (obj.animation_data.action or obj.animation_data.nla_tracks) for obj in hands):
        raise ValueError('Hands already have an action or NLA tracks; bake onto clean hands')
    if status(settings).startswith(('Clock driver', 'Controller', 'Crown')):
        raise ValueError('Repair the clock drivers before baking')
    if ctrl.animation_data and ctrl.animation_data.nla_tracks:
        raise ValueError('Bake requires controller NLA to be flattened first')
    tick = bool(ctrl.get(TICK, 1))
    current, subframe = scene.frame_current, scene.frame_subframe
    samples = []
    removed = False
    from .state import driver_state, restore_driver
    originals = {obj: driver_state(next(fc for fc in drivers(obj) if fc.data_path == 'rotation_euler' and fc.array_index == obj[DRIVEN_AXIS])) for obj in hands}
    try:
        for frame in range(start, end + 1):
            scene.frame_set(frame)
            samples.append((frame, [obj.rotation_euler[int(obj[DRIVEN_AXIS])] for obj in hands]))
        if not tick and end > start:
            first, last = samples[0][1], samples[-1][1]
            # Blender can clamp tiny driver results to zero; compress only proven linear samples.
            if all(abs(value - (a + (b - a) * (frame - start) / (end - start))) <= 1e-6
                   for frame, values in samples for value, a, b in zip(values, first, last)):
                samples = [samples[0], samples[-1]]
        for obj in hands:
            obj.driver_remove('rotation_euler', int(obj[DRIVEN_AXIS]))
        removed = True
        for frame, values in samples:
            for obj, value in zip(hands, values):
                axis = int(obj[DRIVEN_AXIS])
                obj.rotation_euler[axis] = value
                if not obj.keyframe_insert('rotation_euler', index=axis, frame=frame, group='Clock Bake'):
                    raise ValueError(f'{obj.name}: keyframe insertion failed')
        for obj in hands:
            for curve in _rotation_curves(obj):
                for key in curve.keyframe_points:
                    key.interpolation = 'CONSTANT' if tick else 'LINEAR'
    except Exception:
        if removed:
            for obj in hands:
                action = obj.animation_data.action
                obj.animation_data.action = None
                if action and action.users == 0:
                    bpy.data.actions.remove(action)
                restore_driver(obj, originals[obj])
        raise
    finally:
        scene.frame_set(current, subframe=subframe)
    for obj in hands:
        for key in HAND_KEYS:
            if key in obj:
                del obj[key]
    if delete_controller:
        bpy.data.objects.remove(ctrl, do_unlink=True)
        settings.controller = None
    return len(hands), len(samples)
