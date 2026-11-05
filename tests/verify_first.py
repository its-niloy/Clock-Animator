"""Probe the brief's assumptions before implementing the rig."""
import math
import struct
import bpy

scene = bpy.context.scene
scene.render.fps = 24
scene.render.fps_base = 1.001
ctrl = bpy.data.objects.new('Clock_Controller', None)
scene.collection.objects.link(ctrl)
for key, value in dict(start_h=12, start_m=0, start_s=0.0, speed=1.0,
                       offset=1.0, tick=1, time=0.0).items():
    ctrl[key] = value
fc = ctrl.driver_add('["time"]')
for modifier in list(fc.modifiers):
    fc.modifiers.remove(modifier)
d = fc.driver
d.type = 'SCRIPTED'
for name, owner, path, kind in [
    ('h', ctrl, '["start_h"]', 'OBJECT'), ('m', ctrl, '["start_m"]', 'OBJECT'),
    ('s', ctrl, '["start_s"]', 'OBJECT'), ('speed', ctrl, '["speed"]', 'OBJECT'),
    ('off', ctrl, '["offset"]', 'OBJECT'), ('fps', scene, 'render.fps', 'SCENE'),
    ('fb', scene, 'render.fps_base', 'SCENE')]:
    v = d.variables.new()
    v.name = name
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = kind
    v.targets[0].id = owner
    v.targets[0].data_path = path
d.expression = 'h*3600 + m*60 + s + (frame - off) * fb / fps * speed'
hand = bpy.data.objects.new('Hand', None)
scene.collection.objects.link(hand)
fc = hand.driver_add('rotation_euler', 1)
for modifier in list(fc.modifiers):
    fc.modifiers.remove(modifier)
d = fc.driver
for name, key in [('t', 'time'), ('tick', 'tick')]:
    v = d.variables.new()
    v.name = name
    v.type = 'SINGLE_PROP'
    v.targets[0].id = ctrl
    v.targets[0].data_path = f'["{key}"]'
d.expression = '0.000000000000000 + 0.104719755119660 * (t - tick*(t - floor(t)))'
bpy.context.preferences.filepaths.use_scripts_auto_execute = False
scene.frame_set(25)
expected_t = 43200 + 24 * scene.render.fps_base / 24
assert ctrl['time'] == struct.unpack('f', struct.pack('f', expected_t))[0]
for ob in (ctrl, hand):
    for curve in ob.animation_data.drivers:
        assert curve.driver.is_simple_expression and curve.driver.is_valid
error = abs(hand.rotation_euler.y - math.radians(6) * math.floor(expected_t))
print('VERIFY_FIRST', bpy.app.version_string)
print('a PASS native simple, valid drivers with auto-run disabled')
print('b PASS floor() and built-in frame')
print('c PASS Empty custom property time updates')
print('d PASS Scene fps/fps_base SINGLE_PROP')
print(f'e {"PASS" if error <= 1e-6 else "FAIL"} absolute RNA angle error={error:.12g}')
print('f PENDING actual panel redraw test')
