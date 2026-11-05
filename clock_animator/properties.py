"""Scene settings for the active clock."""
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty

from .constants import MOVEMENT_PRESETS, RIG_ID


def sync_controller(self, context):
    if self.controller:
        from .features import load_clock
        load_clock(self)


def controller_poll(self, obj):
    return obj.type == 'EMPTY' and RIG_ID in obj and not obj.library and not obj.override_library and obj.name in self.id_data.objects


class ClockRigSettings(bpy.types.PropertyGroup):
    second: PointerProperty(name="Second", type=bpy.types.Object)
    minute: PointerProperty(name="Minute", type=bpy.types.Object)
    hour: PointerProperty(name="Hour", type=bpy.types.Object)
    use_crown: BoolProperty(
        name="Use Crown / Rotor", default=False,
        description="Drive all hands from this object's rotation through adjustable gearing",
    )
    crown: PointerProperty(name="Crown / Rotor", type=bpy.types.Object)
    crown_axis: EnumProperty(
        name="Crown Axis", items=[(axis, axis, f"Turn about the crown's local {axis}") for axis in 'XYZ'],
        default='X', description="Local spindle axis of the crown; independent of the hands' axis",
    )
    controller: PointerProperty(
        name="Clock", type=bpy.types.Object, poll=controller_poll, update=sync_controller,
        description="Choose a saved clock; More > Manage clocks lets you rename or create another",
    )
    axis: EnumProperty(
        name="Rotation Axis",
        items=[(axis, axis, f"Rotate about local {axis}") for axis in 'XYZ'],
        default='Y',
        description="Local axis; Y without Reverse is clockwise facing front (-Y)",
    )
    auto_axis: BoolProperty(name='Auto Detect Axle', default=True,
        description='Use the thin dimension of all mesh hands as the spindle; disable to choose a local axis manually')
    reverse: BoolProperty(
        name="Reverse Direction", default=False,
        description="Flip rotation direction to fix a backwards clock; Y without Reverse is clockwise from -Y",
    )

    ui_page: EnumProperty(name='Task', items=[('ANIMATE', 'Animate', 'Run or animate the clock'),
        ('SETUP', 'Setup', 'Change hand assignments and alignment'),
        ('MORE', 'More', 'Crown, date, gears, stopwatch, export and clock management')], default='ANIMATE')
    setup_stage: EnumProperty(name='Setup step', items=[('HANDS', 'Choose hands', 'Assign the hand objects'),
        ('CHECK', 'Check rotation', 'Preview alignment, then create the clock')], default='HANDS')
    extra_tool: EnumProperty(name='Tool', items=[('CROWN', 'Crown / rotor', 'Drive time by turning an input object'),
        ('DATE', 'Date wheel', 'Connect or create a numbered wheel'),
        ('GEAR', 'Gears', 'Connect visible gears'), ('CHRONO', 'Stopwatch', 'Add independent stopwatch hands'),
        ('EXPORT', 'Bake for export', 'Create a separate animated copy'),
        ('CLOCKS', 'Manage clocks', 'Choose, rename, create or remove a clock')], default='CROWN')
    show_alignment: BoolProperty(name="Alignment", default=False)
    show_advanced: BoolProperty(name="More motion options", default=False)
    precision: BoolProperty(name="Stable long rotations", default=True, description="Keep displayed rotations within one turn; export copies preserve full turn counts")
    animation_tool: EnumProperty(name="Animation", items=[('PLAYBACK','Run the clock','Advance time while the timeline plays'),('SHOT','Move between two times','Choose a start time, end time and frame range'),('RAMP','Gradually change speed','Accelerate or slow down over a frame range')])
    movement: EnumProperty(name="Hand motion", items=MOVEMENT_PRESETS, default='QUARTZ')
    shot_start_h: IntProperty(name="From hour", default=10, min=0, max=23)
    shot_start_m: IntProperty(name="Minute", default=10, min=0, max=59)
    shot_start_s: FloatProperty(name="Second", default=0, min=0, max=59.999)
    shot_end_h: IntProperty(name="To hour", default=11, min=0, max=23)
    shot_end_m: IntProperty(name="Minute", default=45, min=0, max=59)
    shot_end_s: FloatProperty(name="Second", default=0, min=0, max=59.999)
    shot_days: IntProperty(name="Extra days", default=0, min=-365, max=365, description="Add or subtract full days; use 1 to cross midnight forward")
    range_start: IntProperty(name="First frame", default=1)
    range_end: IntProperty(name="Last frame", default=120)
    easing: EnumProperty(name="Easing", items=[('LINEAR','Linear','Constant rate'),('SMOOTH','Ease in and out','Smooth start and finish')], default='SMOOTH')
    ramp_first: FloatProperty(name="Start speed", default=1, soft_min=-100, soft_max=100)
    ramp_last: FloatProperty(name="End speed", default=20, soft_min=-100, soft_max=100)
    crown_turns: FloatProperty(name="Turn amount", default=0.25, description="Crown revolutions; negative values turn backwards")
    mechanism: EnumProperty(name="Add", items=[('DATE','Date wheel','Drive a date ring'),('GEAR','Geared object','Drive an exposed gear'),('CHRONO','Stopwatch','Add chronograph hands')])
    date_object: PointerProperty(name="Date wheel", type=bpy.types.Object)
    date_axis: EnumProperty(name="Wheel axis", items=[(x,x,'Local spindle axis') for x in 'XYZ'], default='Z')
    date_reverse: BoolProperty(name="Reverse wheel", default=False)
    date_radius: FloatProperty(name="Wheel radius", default=0.5, min=0.001, subtype='DISTANCE')
    gear_object: PointerProperty(name="Driven gear", type=bpy.types.Object)
    gear_source: PointerProperty(name="Driving object", type=bpy.types.Object)
    gear_axis: EnumProperty(name="Gear axis", items=[(x,x,'Local spindle axis') for x in 'XYZ'], default='Y')
    gear_source_axis: EnumProperty(name="Source axis", items=[(x,x,'Local spindle axis') for x in 'XYZ'], default='Y')
    gear_teeth: IntProperty(name="Driven teeth", default=40, min=1, max=10000)
    source_teeth: IntProperty(name="Driving teeth", default=20, min=1, max=10000)
    gear_reverse: BoolProperty(name="Opposite direction", default=True)
    chrono_second: PointerProperty(name="Stopwatch second", type=bpy.types.Object)
    chrono_minute: PointerProperty(name="Stopwatch minute", type=bpy.types.Object)
    chrono_hour: PointerProperty(name="Stopwatch hour", type=bpy.types.Object)
    chrono_axis: EnumProperty(name="Stopwatch axis", items=[(x,x,'Local spindle axis') for x in 'XYZ'], default='Y')
    helper_collection: PointerProperty(type=bpy.types.Collection)
    bake_start: IntProperty(name="First frame", default=1)
    bake_end: IntProperty(name="Last frame", default=250)
    bake_step: IntProperty(name="Sample every", default=1, min=1, max=120, description="Sampling interval in frames; 1 preserves every frame")
    export_collection: PointerProperty(type=bpy.types.Collection)
