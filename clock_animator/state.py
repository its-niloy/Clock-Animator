"""Rollback clock edits when a native Blender operation fails."""
from contextlib import contextmanager
from functools import wraps


def _value(value):
    if hasattr(value, 'to_dict'):
        return {k: _value(v) for k, v in value.items()}
    if hasattr(value, 'to_list'):
        return value.to_list()
    return value


def _properties(rna):
    result = {}
    for prop in rna.bl_rna.properties:
        if not prop.is_readonly and prop.type not in {'COLLECTION', 'POINTER'}:
            value = getattr(rna, prop.identifier)
            result[prop.identifier] = tuple(value) if getattr(prop, 'is_array', False) else value
    return result


def driver_state(curve):
    driver = curve.driver
    variables = []
    for variable in driver.variables:
        targets = []
        for target in variable.targets:
            values = _properties(target)
            values['id'] = target.id
            targets.append(values)
        variables.append((variable.name, variable.type, targets))
    return (curve.data_path, curve.array_index, driver.type, driver.expression,
            driver.use_self, variables, _properties(curve),
            [(m.type, _properties(m)) for m in curve.modifiers])


def restore_driver(obj, saved):
    path, index, kind, expression, use_self, variables, values, modifiers = saved
    curve = obj.driver_add(path, index) if not path.startswith('[') else obj.driver_add(path)
    for modifier in list(curve.modifiers):
        curve.modifiers.remove(modifier)
    for variable in list(curve.driver.variables):
        curve.driver.variables.remove(variable)
    driver = curve.driver
    driver.type, driver.expression, driver.use_self = kind, expression, use_self
    for name, kind, targets in variables:
        variable = driver.variables.new()
        variable.name, variable.type = name, kind
        for target, attributes in zip(variable.targets, targets):
            # id_type must precede id; Blender validates the pointer on assignment.
            for key in ('id_type', 'id'):
                if key in attributes:
                    setattr(target, key, attributes[key])
            for key, value in attributes.items():
                if key not in {'id', 'id_type'}:
                    setattr(target, key, value)
    for key, value in values.items():
        if key not in {'data_path', 'array_index'}:
            setattr(curve, key, value)
    for kind, attributes in modifiers:
        modifier = curve.modifiers.new(kind)
        for key, value in attributes.items():
            setattr(modifier, key, value)


def _points(curve):
    return [_properties(point) for point in curve.keyframe_points]


def _restore_points(curve, points):
    curve.keyframe_points.clear()
    curve.keyframe_points.add(len(points))
    for point, attributes in zip(curve.keyframe_points, points):
        for name, value in attributes.items():
            setattr(point, name, value)
    curve.update()


@contextmanager
def preserve(objects, scene):
    import bpy
    from . import core

    objects = list(dict.fromkeys(o for o in objects if o))
    snapshots = []
    existing = set(bpy.data.objects)
    frame, subframe = scene.frame_current, scene.frame_subframe
    settings = scene.clock_rig
    settings_values = {p.identifier: getattr(settings, p.identifier) for p in settings.bl_rna.properties
                       if not p.is_readonly and p.identifier != 'rna_type'}
    for obj in objects:
        action = obj.animation_data.action if obj.animation_data else None
        slot = getattr(obj.animation_data, 'action_slot', None) if obj.animation_data else None
        snapshots.append((obj, {k: _value(v) for k, v in obj.items()},
                          {name: getattr(obj, name).copy() if hasattr(getattr(obj, name), 'copy') else tuple(getattr(obj, name))
                           for name in ('rotation_euler', 'rotation_quaternion', 'rotation_axis_angle', 'delta_rotation_euler', 'delta_rotation_quaternion')},
                          obj.rotation_mode, [driver_state(fc) for fc in core.drivers(obj)], action, slot,
                          [(fc, _points(fc), fc.extrapolation) for fc in core._rotation_curves(obj)]))
    try:
        yield
    except Exception:
        for obj, props, rotations, mode, drivers, action, slot, curves in snapshots:
            for fc in list(core.drivers(obj)):
                obj.driver_remove(fc.data_path) if fc.data_path.startswith('[') else obj.driver_remove(fc.data_path, fc.array_index)
            for key in list(obj.keys()):
                if key not in props:
                    del obj[key]
            for key, value in props.items():
                obj[key] = value
            obj.rotation_mode = mode
            for name, value in rotations.items():
                setattr(obj, name, value)
            if obj.animation_data:
                changed_action = obj.animation_data.action
                obj.animation_data.action = action
                if slot:
                    obj.animation_data.action_slot = slot
                if changed_action and changed_action != action and not changed_action.users:
                    bpy.data.actions.remove(changed_action)
            original_curves = {fc for fc, _, _ in curves}
            for fc in core._rotation_curves(obj):
                if fc not in original_curves:
                    for group in core._curve_groups(obj):
                        if fc in list(group):
                            group.remove(fc)
                            break
            for fc, points, extrapolation in curves:
                _restore_points(fc, points)
                fc.extrapolation = extrapolation
            for driver in drivers:
                restore_driver(obj, driver)
            obj.update_tag()
        for obj in set(bpy.data.objects) - existing:
            bpy.data.objects.remove(obj, do_unlink=True)
        # Restore the controller first because its update callback loads saved UI fields.
        settings.controller = settings_values.pop('controller')
        for name, value in settings_values.items():
            setattr(settings, name, value)
        scene.frame_set(frame, subframe=subframe)
        raise


def atomic(function):
    @wraps(function)
    def edit(scene, *args, **kwargs):
        from . import core
        from .constants import CROWN_SOURCE
        settings = scene.clock_rig
        ctrl = settings.controller
        objects = [getattr(settings, name) for name in (
            'controller', 'second', 'minute', 'hour', 'crown', 'date_object',
            'gear_object', 'gear_source', 'chrono_second', 'chrono_minute', 'chrono_hour')]
        if ctrl:
            objects += core.managed_hands(ctrl) + [ctrl.get(CROWN_SOURCE)]
        with preserve(objects, scene):
            return function(scene, *args, **kwargs)
    return edit
