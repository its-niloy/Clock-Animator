"""Clock Animator registration entry point."""

bl_info = {
    "name": "Clock Animator",
    "author": "Clock Animator contributors",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Clock",
    "description": "Animate analog clock hands from one native time driver",
    "category": "Animation",
}


def register():
    import bpy
    from . import operators, properties, ui

    for cls in (properties.ClockRigSettings, *operators.CLASSES, ui.CLOCK_PT_animator):
        bpy.utils.register_class(cls)
    bpy.types.Scene.clock_rig = bpy.props.PointerProperty(type=properties.ClockRigSettings)


def unregister():
    import bpy
    from . import operators, properties, ui

    del bpy.types.Scene.clock_rig
    for cls in reversed((properties.ClockRigSettings, *operators.CLASSES, ui.CLOCK_PT_animator)):
        bpy.utils.unregister_class(cls)
