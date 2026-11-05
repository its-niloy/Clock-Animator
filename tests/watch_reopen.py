"""Run against the corrected asset with no add-on loaded and auto-run disabled."""
import bpy
from mathutils import Vector

bpy.context.window.scene = bpy.data.scenes['Cycles']
scene = bpy.context.scene
hands = [bpy.data.objects[name] for name in ('Circle.028', 'Circle.029', 'Circle.030')]
scene.frame_set(scene.frame_start)
normals = {obj: (obj.matrix_basis.to_3x3().inverted().transposed() @ Vector((0, 0, 1))).normalized() for obj in hands}
before = hands[0].matrix_basis.copy()
for frame in (25, 121, 1, 49):
    scene.frame_set(frame)
    for obj in hands:
        normal = (obj.matrix_basis.to_3x3().inverted().transposed() @ Vector((0, 0, 1))).normalized()
        assert normal.dot(normals[obj]) > 1-1e-6
        assert all(fc.driver.is_valid and fc.driver.is_simple_expression for fc in obj.animation_data.drivers)
assert max(abs(before[i][j]-hands[0].matrix_basis[i][j]) for i in range(3) for j in range(3)) > 0.00001
assert not hasattr(bpy.types.Scene, 'clock_rig')
print('WATCH REOPEN PASS: no add-on, auto-run disabled, native seek and spindle remain correct')
