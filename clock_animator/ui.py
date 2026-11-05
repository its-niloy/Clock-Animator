"""Task-focused native sidebar: choose hands, check rotation, then animate."""
from textwrap import wrap

import bpy

from . import core
from .constants import (
    BOUNCE, CHRONO, CROWN_RATIO, CROWN_SOURCE, DAMPING, DATE_BLEND, DATE_START,
    FACTORS, MODE, MOVEMENT_PRESETS, OFFSET, PAUSED, RIG_ID, ROLE, SPEED, START_H, START_M, START_S, TIME,
)
from .motion import clock_text


def section(layout, settings, key, label):
    row = layout.row()
    row.prop(settings, key, text=label, icon='TRIA_DOWN' if getattr(settings, key) else 'TRIA_RIGHT', emboss=False)
    return layout.column() if getattr(settings, key) else None


def tool(layout, action, text, icon='NONE', enabled=True):
    row = layout.row()
    row.enabled = enabled
    button = row.operator('clock.tool', text=text, icon=icon)
    button.action = action
    return button


def hint(layout, text, context, icon='NONE'):
    width = max(22, int(context.region.width / (7 * (context.preferences.system.ui_scale or 1.0))) - 6)
    for index, line in enumerate(wrap(text, width=width, break_long_words=False, break_on_hyphens=False)):
        layout.label(text=line, icon=icon if index == 0 else 'NONE')


def custom(layout, obj, key, label):
    if key in obj:
        layout.prop(obj, core.prop_path(key), text=label)
    else:
        layout.label(text=f'Missing {label}; update clock', icon='ERROR')


def time_fields(layout, owner, keys, label, custom_properties=False):
    layout.label(text=label)
    row = layout.row(align=True)
    for key, short in zip(keys, ('H', 'M', 'S')):
        if custom_properties:
            custom(row, owner, key, short)
        else:
            row.prop(owner, key, text=short)


def setup_problem(scene, settings, check_axis=False):
    try:
        core.validate(scene, settings)
        if check_axis:
            core.hand_axis(settings)
    except ValueError as error:
        return str(error)
    return ''


def draw_hands(layout, settings):
    for role in FACTORS:
        layout.prop(settings, role, text=role.title())
    layout.separator(factor=0.5)
    layout.operator('clock.assign', text='Find Hands by Name', icon='VIEWZOOM')


def draw_alignment(layout, settings, context):
    layout.prop(settings, 'auto_axis')
    if settings.auto_axis:
        try:
            layout.label(text='Detected axle: local ' + core.hand_axis(settings), icon='CHECKMARK')
        except ValueError:
            hint(layout, 'Could not detect the axle. Turn off Auto Detect Axle and choose X, Y or Z.', context, 'INFO')
    else:
        layout.prop(settings, 'axis', expand=True)
    layout.prop(settings, 'reverse', text='Turn the other way')
    layout.separator(factor=0.5)
    problem = setup_problem(context.scene, settings, check_axis=True)
    tool(layout, 'TEST', 'Preview a 15 Degree Turn', 'HIDE_OFF', enabled=not problem)
    if settings.helper_collection:
        hint(layout, 'The wireframe shows the turn. Your original hands stay in place.', context)
        tool(layout, 'CLEAR', 'Clear Preview', 'X')
    fixes = section(layout, settings, 'show_alignment', 'Pivot and axle helpers')
    if fixes:
        hint(fixes, 'Hand origins should meet at the dial center. Place the 3D cursor there before moving origins.', context)
        row = fixes.row()
        row.enabled = settings.controller is None
        row.operator('clock.pivots', text='Move Origins to 3D Cursor')
        if settings.controller:
            hint(fixes, 'Remove the rig before moving origins.', context)
        tool(fixes, 'HELPERS', 'Show Axle Helpers', 'EMPTY_ARROWS')


def draw_setup(layout, settings, context):
    editing = settings.controller is not None
    if not editing and settings.setup_stage == 'HANDS':
        layout.label(text='1 of 2  /  Choose hands', icon='OBJECT_DATA')
        hint(layout, 'Pick your hand objects with the eyedroppers. One hand is enough to start.', context)
        draw_hands(layout, settings)
        assigned = core.assigned(settings)
        problem = setup_problem(context.scene, settings) if assigned else ''
        if problem:
            hint(layout, problem, context, 'ERROR')
        layout.separator()
        row = layout.column()
        row.scale_y = 1.35
        tool(row, 'SETUP_NEXT', 'Next: Check Rotation', 'FORWARD', enabled=bool(assigned) and not problem)
        return
    if editing:
        layout.label(text='Hands and alignment', icon='OBJECT_DATA')
        draw_hands(layout, settings)
        layout.separator()
    else:
        layout.label(text='2 of 2  /  Check rotation', icon='ORIENTATION_LOCAL')
        hint(layout, 'Preview the plane and direction of the turn. Your starting pose is kept.', context)
    draw_alignment(layout, settings, context)
    hint(layout, 'For an exact time display, pose the hands at 12 before creating the clock.', context)
    problem = setup_problem(context.scene, settings, check_axis=True)
    if problem:
        hint(layout, problem, context, 'ERROR')
    layout.separator()
    if not editing:
        tool(layout, 'SETUP_BACK', 'Back: Choose Hands', 'BACK')
    row = layout.row()
    row.enabled = not problem
    row.scale_y = 1.4
    row.operator('clock.apply', text='Update Clock' if editing else 'Create Clock', icon='TIME')


def play_button(layout, context):
    playing = context.screen.is_animation_playing
    row = layout.row()
    row.scale_y = 1.35
    row.operator('screen.animation_play', text='Stop Playback' if playing else 'Play Animation', icon='PAUSE' if playing else 'PLAY')


def draw_motion(layout, settings):
    layout.label(text='Hand motion')
    label = next(label for key, label, _ in MOVEMENT_PRESETS if key == settings.movement)
    layout.operator_menu_enum('clock.movement', 'preset', text=label)


def draw_animation(layout, settings, context):
    ctrl = settings.controller
    layout.prop(settings, 'animation_tool', text='')
    layout.separator(factor=0.5)
    saved = bool(ctrl.get(MODE))
    if settings.animation_tool == 'PLAYBACK':
        if saved and not ctrl.get(PAUSED):
            hint(layout, 'A custom time animation is active. Play it, or switch back to a running clock.', context, 'KEY_HLT')
            play_button(layout, context)
            tool(layout, 'PLAYBACK', 'Use a Running Clock')
        else:
            box = layout.box()
            if ctrl.get(PAUSED):
                hint(box, 'Clock time is held at this frame.', context, 'PAUSE')
                tool(box, 'PAUSE', 'Resume Clock From Here', 'PLAY')
            else:
                time_fields(box, ctrl, (START_H, START_M, START_S), f'Time at frame {ctrl.get(OFFSET, 1):g}', True)
            custom(box, ctrl, SPEED, 'Speed')
            box.label(text='1 = real time')
            draw_motion(layout, settings)
            play_button(layout, context)
            if not context.screen.is_animation_playing:
                hint(layout, 'Play advances the Blender timeline.', context)
    else:
        box = layout.box()
        if settings.animation_tool == 'SHOT':
            time_fields(box, settings, ('shot_start_h', 'shot_start_m', 'shot_start_s'), 'From time')
            time_fields(box, settings, ('shot_end_h', 'shot_end_m', 'shot_end_s'), 'To time')
        else:
            hint(box, 'Change speed without jumping in time.', context)
            box.prop(settings, 'ramp_first', text='From speed')
            box.prop(settings, 'ramp_last', text='To speed')
        box.separator(factor=0.5)
        box.prop(settings, 'range_start', text='First frame')
        box.prop(settings, 'range_end', text='Last frame')
        if saved:
            hint(layout, "Replaces this clock's time animation.", context, 'INFO')
        row = layout.column()
        row.scale_y = 1.25
        tool(row, 'SHOT' if settings.animation_tool == 'SHOT' else 'RAMP',
             'Replace Time Animation' if saved else 'Create Time Animation', 'KEY_HLT')
        if saved:
            play_button(layout, context)
    layout.separator()
    options = section(layout, settings, 'show_advanced', 'Timing and motion options')
    if options:
        if settings.animation_tool != 'PLAYBACK':
            options.prop(settings, 'easing')
            if settings.animation_tool == 'SHOT':
                options.prop(settings, 'shot_days')
            draw_motion(options, settings)
        options.operator('clock.realtime', text='Start at My Local Time')
        tool(options, 'PAUSE', 'Resume Clock From Here' if ctrl.get(PAUSED) else 'Hold Clock at This Frame')
        custom(options, ctrl, BOUNCE, 'Tick rebound')
        custom(options, ctrl, DAMPING, 'Settling')
        options.prop(settings, 'precision')
        options.operator('clock.apply', text='Apply Precision Setting')


def draw_crown(layout, settings, context):
    ctrl = settings.controller
    hint(layout, 'Turn a crown or rotor to advance all three hands through gearing.', context)
    layout.prop(settings, 'use_crown', text='Enable crown control')
    if settings.use_crown:
        layout.prop(settings, 'crown', text='Object')
        layout.label(text='Local spindle axis')
        layout.prop(settings, 'crown_axis', expand=True)
    if settings.use_crown or ctrl.get(CROWN_SOURCE):
        row = layout.row()
        row.enabled = bool(settings.crown) if settings.use_crown else bool(ctrl.get(CROWN_SOURCE))
        button = row.operator('clock.apply', text='Connect / Update Crown' if settings.use_crown else 'Disconnect Crown')
        button.stay_on_page = True
    if ctrl.get(CROWN_SOURCE):
        layout.separator()
        custom(layout, ctrl, CROWN_RATIO, 'Minutes per turn')
        layout.label(text=f'Quarter turn = {ctrl.get(CROWN_RATIO, 0) / 4:g} minutes')
        tool(layout, 'QUARTER', 'Turn 1/4 and Insert Key')
        tool(layout, 'FULL', 'Turn Once and Insert Key')
        layout.prop(settings, 'crown_turns', text='Custom turns')
        tool(layout, 'TURN', 'Turn and Insert Key', 'KEY_HLT')
        tool(layout, 'KEY_CROWN', 'Key Current Crown Pose', 'KEY_HLT')


def draw_part(layout, settings, context):
    ctrl, kind = settings.controller, settings.extra_tool
    if kind == 'DATE':
        hint(layout, 'Place a numbered ring behind the date window, with 1 showing. Then connect it.', context)
        layout.prop(settings, 'date_object', text='Object')
        if not settings.date_object:
            layout.prop(settings, 'date_radius', text='Wheel radius')
            tool(layout, 'CREATE_DATE', 'Create a Numbered Wheel', 'ADD')
            return
        layout.prop(settings, 'date_axis', expand=True)
        layout.prop(settings, 'date_reverse')
        custom(layout, ctrl, DATE_START, 'Starting date')
        custom(layout, ctrl, DATE_BLEND, 'Transition seconds')
        connected = core.belongs_to(settings.date_object, ctrl)
        tool(layout, 'DATE', 'Update Date Wheel' if connected else 'Connect Date Wheel')
    elif kind == 'GEAR':
        hint(layout, 'Choose what drives the gear, then set the tooth counts.', context)
        layout.label(text='Driving object')
        layout.prop(settings, 'gear_source', text='')
        if not settings.gear_source or not core.belongs_to(settings.gear_source, ctrl):
            layout.label(text='Input axis')
            layout.prop(settings, 'gear_source_axis', expand=True)
        layout.label(text='Driven gear')
        layout.prop(settings, 'gear_object', text='')
        layout.label(text='Gear axis')
        layout.prop(settings, 'gear_axis', expand=True)
        layout.prop(settings, 'source_teeth', text='Driving teeth')
        layout.prop(settings, 'gear_teeth', text='Driven teeth')
        layout.prop(settings, 'gear_reverse')
        tool(layout, 'GEAR', 'Connect / Update Gear', enabled=bool(settings.gear_object and settings.gear_source))
    else:
        hint(layout, 'These hands measure elapsed time independently of the main clock.', context)
        for role in FACTORS:
            layout.prop(settings, 'chrono_' + role, text=role.title())
        layout.prop(settings, 'chrono_axis', expand=True)
        has_hands = any(getattr(settings, 'chrono_' + role) for role in FACTORS)
        tool(layout, 'CHRONO', 'Connect / Update Stopwatch', enabled=has_hands)
        connected = any(obj.get(ROLE, '').startswith('chrono_') for obj in core.managed_hands(ctrl))
        if connected:
            layout.separator()
            layout.label(text='Elapsed: ' + clock_text(float(ctrl.get(CHRONO, 0))))
            row = layout.row(align=True)
            for action in ('START', 'STOP', 'RESET'):
                tool(row, action, action.title())
    layout.separator()
    obj = context.active_object
    removable = obj and core.belongs_to(obj, ctrl) and obj.get(ROLE) not in FACTORS
    if removable:
        tool(layout, 'REMOVE_PART', 'Disconnect Selected Part', 'X')


def draw_more(layout, settings, context):
    layout.prop(settings, 'extra_tool', text='')
    layout.separator()
    if settings.extra_tool == 'CROWN':
        draw_crown(layout, settings, context)
    elif settings.extra_tool in {'DATE', 'GEAR', 'CHRONO'}:
        draw_part(layout, settings, context)
    elif settings.extra_tool == 'EXPORT':
        hint(layout, 'Create a baked copy for export. Your original clock stays editable.', context)
        layout.prop(settings, 'bake_start', text='First frame')
        layout.prop(settings, 'bake_end', text='Last frame')
        layout.prop(settings, 'bake_step', text='Sample every (frames)')
        tool(layout, 'COPY', 'Create Export Copy', 'DUPLICATE')
        if settings.export_collection:
            layout.separator()
            layout.label(text='Your export copy is ready', icon='CHECKMARK')
            tool(layout, 'SELECT_EXPORT', 'Select Export Objects', 'RESTRICT_SELECT_OFF')
            hint(layout, 'Then use File > Export with Selected Objects enabled.', context)
    else:
        layout.prop(settings, 'controller', text='Clock')
        layout.prop(settings.controller, 'name', text='Name')
        tool(layout, 'NEW', 'Set Up Another Clock', 'ADD')
        layout.separator()
        hint(layout, 'Removing the rig restores the original hand poses and keeps your model.', context)
        layout.operator('clock.remove', text='Remove Rig / Restore Hands', icon='X')


class CLOCK_PT_animator(bpy.types.Panel):
    bl_label = 'Clock Animator'
    bl_idname = 'CLOCK_PT_animator'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Clock'

    def draw(self, context):
        layout, settings = self.layout, context.scene.clock_rig
        layout.use_property_split = False
        layout.use_property_decorate = False
        ctrl = settings.controller
        if not ctrl:
            draw_setup(layout, settings, context)
            if any(obj.get(RIG_ID) for obj in context.scene.objects):
                layout.separator()
                layout.prop(settings, 'controller', text='Use existing clock')
            return
        if sum(bool(obj.get(RIG_ID)) for obj in context.scene.objects) > 1:
            layout.prop(settings, 'controller', text='Clock')
        row = layout.row()
        row.scale_y = 1.25
        row.prop(settings, 'ui_page', expand=True)
        layout.separator(factor=0.5)
        if settings.ui_page == 'SETUP':
            draw_setup(layout, settings, context)
            return
        if settings.ui_page == 'MORE':
            draw_more(layout, settings, context)
            return
        box = layout.box()
        row = box.row()
        row.scale_y = 1.5
        row.label(text=clock_text(float(ctrl.get(TIME, 0))), icon='TIME')
        message = core.status(settings)
        if message.startswith('Partial'):
            count = len({obj.get(ROLE, 'second') for obj in core.managed_hands(ctrl) if obj.get(ROLE, 'second') in FACTORS})
            box.label(text=f'{count} hand clock', icon='INFO')
        elif message != 'Clock animation ready':
            hint(box, message, context, 'ERROR')
            tool(box, 'REVIEW_SETUP', 'Review Setup')
            return
        draw_animation(layout, settings, context)
