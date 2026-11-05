"""Undoable user actions with readable error reporting."""
import bpy

from . import core
from .constants import CROWN_AXIS, CROWN_REST, CROWN_SOURCE, MODE, MOVEMENT_PRESETS, PAUSED, PREVIEW, START_H, START_M, START_S


class ClockOperator:
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            message = self.run(context)
        except Exception as error:
            self.report({'ERROR'}, str(error) or type(error).__name__)
            return {'CANCELLED'}
        self.report({'INFO'}, message)
        return {'FINISHED'}


class CLOCK_OT_assign(ClockOperator, bpy.types.Operator):
    bl_idname = 'clock.assign'
    bl_label = 'Assign From Selection'
    bl_description = 'Match sec, min, hour or hr in selected object names'

    def run(self, context):
        matches = {}
        for obj in context.selected_objects:
            role = core.match_role(obj.name)
            if role:
                if role in matches:
                    raise ValueError(f"Multiple {role} hands selected; pick one manually")
                matches[role] = obj
        if not matches:
            raise ValueError("No matching names. Rename hands with sec, min or hour, or pick them manually")
        for role, obj in matches.items():
            setattr(context.scene.clock_rig, role, obj)
        return f"Assigned {len(matches)} hand(s)"


class CLOCK_OT_apply(ClockOperator, bpy.types.Operator):
    bl_idname = 'clock.apply'
    bl_label = 'Create Clock Animation'
    bl_description = 'Create or update the rig using these hands and their local spindle axis'

    stay_on_page: bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})

    def run(self, context):
        from . import features
        settings = context.scene.clock_rig
        core.apply_rig(context.scene, settings)
        if settings.helper_collection and settings.helper_collection.get(PREVIEW):
            features.clear_helpers(context.scene)
        if not self.stay_on_page:
            settings.ui_page = 'ANIMATE'
        settings.setup_stage = 'HANDS'
        settings.show_alignment = settings.show_advanced = False
        return 'Clock animation created'


class CLOCK_OT_movement(ClockOperator, bpy.types.Operator):
    bl_idname = 'clock.movement'
    bl_label = 'Choose Hand Motion'
    bl_description = 'Apply this hand motion immediately; no separate Apply step is needed'

    preset: bpy.props.EnumProperty(name='Hand motion', items=MOVEMENT_PRESETS)

    def run(self, context):
        from . import features
        features.controller(context.scene)
        context.scene.clock_rig.movement = self.preset
        features.movement(context.scene)
        return 'Hand motion updated'


class CLOCK_OT_remove(ClockOperator, bpy.types.Operator):
    bl_idname = 'clock.remove'
    bl_label = 'Remove Clock Animation'

    def run(self, context):
        core.remove_rig(context.scene.clock_rig)
        return 'Clock animation removed; original hand poses restored'


class CLOCK_OT_pivots(ClockOperator, bpy.types.Operator):
    bl_idname = 'clock.pivots'
    bl_label = 'Set Hand Pivots To 3D Cursor'
    bl_description = 'Move hand origins to the cursor, keeping geometry in place (Object Mode only)'

    def run(self, context):
        if context.mode != 'OBJECT':
            raise ValueError('Switch to Object Mode to set hand pivots')
        hands = list(dict.fromkeys(obj for _, obj in core.assigned(context.scene.clock_rig)))
        if not hands:
            raise ValueError('Assign at least one hand')
        for obj in hands:
            if not obj.data or obj.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META', 'ARMATURE', 'LATTICE'}:
                raise ValueError(f"{obj.name}: object has no supported origin geometry")
            if obj.data.users > 1:
                raise ValueError(f"{obj.name}: multi-user data; make the data single-user first")
            if obj.library or obj.data.library or obj.override_library:
                raise ValueError(f"{obj.name}: linked data cannot be edited")
            if obj.name not in context.view_layer.objects or obj.hide_get() or obj.hide_viewport or obj.hide_select:
                raise ValueError(f"{obj.name}: make the hand visible and selectable first")
            if obj.get(core.OWNER):
                raise ValueError(f"{obj.name}: remove clock animation before changing pivots")
        selected = list(context.selected_objects)
        active = context.view_layer.objects.active
        try:
            for obj in selected:
                obj.select_set(False)
            for obj in hands:
                obj.select_set(True)
                context.view_layer.objects.active = obj
                try:
                    result = bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                    if result != {'FINISHED'}:
                        raise ValueError('origin operation cancelled')
                except Exception as error:
                    raise ValueError(f"{obj.name}: could not set pivot: {error}") from error
                finally:
                    obj.select_set(False)
        finally:
            for obj in selected:
                obj.select_set(True)
            context.view_layer.objects.active = active
        return f"Set {len(hands)} pivot(s) to the 3D cursor"


class CLOCK_OT_realtime(ClockOperator, bpy.types.Operator):
    bl_idname = 'clock.realtime'
    bl_label = 'Real Time Start'
    bl_description = 'Set the starting time from this computer, anchored at the current frame'

    def run(self, context):
        from datetime import datetime
        from .constants import OFFSET, PLAYBACK_BASE

        from .features import controller
        ctrl = controller(context.scene)
        crown = ctrl.get(CROWN_SOURCE)
        if CROWN_SOURCE in ctrl and not crown:
            raise ValueError('Crown input missing; re-create animation first')
        now = datetime.now()
        ctrl[START_H], ctrl[START_M] = now.hour, now.minute
        ctrl[START_S] = now.second + now.microsecond / 1_000_000
        ctrl[OFFSET] = float(context.scene.frame_current) + context.scene.frame_subframe
        ctrl[MODE], ctrl[PAUSED] = 0, 0
        ctrl[PLAYBACK_BASE] = 0.0
        if crown:
            ctrl[CROWN_REST] = float(crown.rotation_euler[int(ctrl[CROWN_AXIS])])
        ctrl.update_tag()
        context.scene.frame_set(context.scene.frame_current, subframe=context.scene.frame_subframe)
        return 'Clock starts at local computer time on the current frame'


class CLOCK_OT_bake(ClockOperator, bpy.types.Operator):
    bl_idname = 'clock.bake'
    bl_label = 'Bake To Keyframes'
    bl_description = 'Sample the active clock for export; use Undo to recover the live rig'

    frame_start: bpy.props.IntProperty(name='Start', default=1)
    frame_end: bpy.props.IntProperty(name='End', default=250)
    delete_controller: bpy.props.BoolProperty(name='Delete controller after bake', default=False)

    def invoke(self, context, event):
        self.frame_start = context.scene.frame_start
        self.frame_end = context.scene.frame_end
        return context.window_manager.invoke_props_dialog(self)

    def run(self, context):
        count, samples = core.bake_rig(
            context.scene, context.scene.clock_rig,
            self.frame_start, self.frame_end, self.delete_controller,
        )
        return f"Baked {count} hand(s), {samples} samples each"


class CLOCK_OT_tool(ClockOperator, bpy.types.Operator):
    bl_idname = 'clock.tool'
    bl_label = 'Clock Tool'
    bl_description = 'Apply a clock tool while preserving source objects'

    action: bpy.props.EnumProperty(items=[(key, label, label) for key, label in (
        ('SHOT', 'Build time animation'), ('RAMP', 'Build speed ramp'),
        ('PAUSE', 'Pause or resume'), ('PLAYBACK', 'Use playback speed'),
        ('MOVEMENT', 'Apply movement'), ('TURN', 'Turn and key crown'),
        ('QUARTER', 'Quarter crown turn'), ('FULL', 'Full crown turn'),
        ('KEY_CROWN', 'Key crown pose'), ('NEW', 'New clock'),
        ('DATE', 'Connect date wheel'), ('CREATE_DATE', 'Create numbered wheel'),
        ('GEAR', 'Connect gear'), ('CHRONO', 'Connect stopwatch'),
        ('START', 'Start stopwatch'), ('STOP', 'Stop stopwatch'), ('RESET', 'Reset stopwatch'),
        ('HELPERS', 'Show spindle helpers'), ('TEST', 'Preview 15 degree rotation'),
        ('CLEAR', 'Clear alignment preview'), ('COPY', 'Bake export copy'),
        ('REMOVE_PART', 'Remove selected mechanism'),
        ('SETUP_NEXT', 'Check rotation'), ('SETUP_BACK', 'Choose hands'),
        ('REVIEW_SETUP', 'Review hand setup'), ('SELECT_EXPORT', 'Select baked copy'),
    )])

    def run(self, context):
        from . import features
        scene = context.scene
        calls = {
            'SHOT': features.shot, 'RAMP': features.speed_ramp,
            'PAUSE': features.pause_resume, 'PLAYBACK': features.playback,
            'MOVEMENT': features.movement, 'TURN': features.turn_crown,
            'DATE': features.add_date, 'CREATE_DATE': features.create_date_wheel,
            'GEAR': features.add_gear, 'CHRONO': features.add_chronograph,
            'HELPERS': features.setup_helpers, 'CLEAR': features.clear_helpers,
        }
        if self.action in calls:
            calls[self.action](scene)
        elif self.action == 'NEW':
            features.new_clock(scene.clock_rig)
        elif self.action == 'SETUP_NEXT':
            core.validate(scene, scene.clock_rig)
            scene.clock_rig.setup_stage = 'CHECK'
        elif self.action == 'SETUP_BACK':
            settings = scene.clock_rig
            if settings.helper_collection and settings.helper_collection.get(PREVIEW):
                features.clear_helpers(scene)
            settings.setup_stage = 'HANDS'
        elif self.action == 'REVIEW_SETUP':
            scene.clock_rig.ui_page = 'SETUP'
        elif self.action == 'SELECT_EXPORT':
            collection = scene.clock_rig.export_collection
            objects = [obj for obj in collection.all_objects if obj.name in context.view_layer.objects and obj.visible_get() and not obj.hide_select] if collection else []
            if not objects:
                raise ValueError('Make the baked collection visible in this view layer first')
            for obj in context.selected_objects:
                obj.select_set(False)
            for obj in objects:
                obj.select_set(True)
            context.view_layer.objects.active = objects[0]
        elif self.action == 'KEY_CROWN':
            features.turn_crown(scene, 0)
        elif self.action in {'QUARTER', 'FULL'}:
            features.turn_crown(scene, 0.25 if self.action == 'QUARTER' else 1.0)
        elif self.action in {'START', 'STOP', 'RESET'}:
            features.chronograph(scene, self.action)
        elif self.action == 'TEST':
            features.setup_helpers(scene, test_rotation=True)
        elif self.action == 'COPY':
            objects, samples = features.bake_copy(scene)
            return f'Created export collection: {objects} object(s), {samples} samples; live rig preserved'
        elif self.action == 'REMOVE_PART':
            features.remove_mechanism(scene, context.object)
        return self.action.replace('_', ' ').title() + ' completed'


CLASSES = (CLOCK_OT_assign, CLOCK_OT_apply, CLOCK_OT_movement, CLOCK_OT_remove, CLOCK_OT_pivots, CLOCK_OT_realtime, CLOCK_OT_bake, CLOCK_OT_tool)
