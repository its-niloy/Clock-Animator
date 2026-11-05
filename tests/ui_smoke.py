"""Draw the guided flow and every task in a real Blender window; verify Undo."""
from pathlib import Path
import sys
import traceback

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import clock_animator  # noqa: E402
from clock_animator import ui  # noqa: E402
from clock_animator.constants import START_M, TICK  # noqa: E402

large_ui = '--large-ui' in sys.argv
if large_ui:
    bpy.context.preferences.view.ui_scale = 1.25
OUTPUT = ROOT / 'tests' / 'output' / ('ui-' + bpy.app.version_string.replace(' ', '_') + ('-large' if large_ui else ''))
OUTPUT.mkdir(parents=True, exist_ok=True)
clock_animator.register()
scene = bpy.context.scene
original_draw = ui.CLOCK_PT_animator.draw
states = ['FIRST', 'HANDS', 'CHECK', 'PREVIEW', 'EVERYDAY', 'PLAYING', 'SHOT',
          'SAVED', 'RAMP', 'ADVANCED', 'CROWN', 'DATE', 'DATE_CONNECTED', 'GEAR', 'STOPWATCH',
          'EXPORT', 'EXPORTED', 'CLOCKS', 'SETUP', 'BROKEN']
phase, attempts = 0, 0
draws = [0] * len(states)
errors = []


def checked_draw(self, context):
    try:
        original_draw(self, context)
        draws[phase] += 1
    except Exception:
        errors.append(traceback.format_exc())


ui.CLOCK_PT_animator.draw = checked_draw
bpy.utils.unregister_class(ui.CLOCK_PT_animator)
assert ui.CLOCK_PT_animator.bl_category == 'Clock'
bpy.utils.register_class(ui.CLOCK_PT_animator)
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.show_region_ui = True
        area.tag_redraw()


def dismiss():
    bpy.context.window.event_simulate(type='ESC', value='PRESS')
    bpy.context.window.event_simulate(type='ESC', value='RELEASE')


def redraw():
    for area in bpy.context.screen.areas:
        area.tag_redraw()


def capture(name):
    bpy.ops.screen.screenshot(filepath=str(OUTPUT / name))


def native_context():
    area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    return bpy.context.temp_override(area=area, region=region)


def prepare(state):
    global scene
    settings = scene.clock_rig
    if state == 'HANDS':
        hand = bpy.context.object
        for vertex in hand.data.vertices:
            vertex.co.x *= 0.1
            vertex.co.z *= 0.01
        hand.name = 'Hand_second'
        for role in ('minute', 'hour'):
            obj = hand.copy()
            obj.data = hand.data.copy()
            obj.name = 'Hand_' + role
            scene.collection.objects.link(obj)
            obj.select_set(True)
        assert bpy.ops.clock.assign() == {'FINISHED'}
    elif state == 'CHECK':
        assert bpy.ops.clock.tool(action='SETUP_NEXT') == {'FINISHED'}
    elif state == 'PREVIEW':
        assert bpy.ops.clock.tool(action='TEST') == {'FINISHED'}
    elif state == 'EVERYDAY':
        bpy.ops.ed.undo_push(message='Before Clock Animator')
        assert bpy.ops.clock.apply('EXEC_DEFAULT', True) == {'FINISHED'}
        assert settings.ui_page == 'ANIMATE' and not settings.helper_collection
        with native_context():
            assert bpy.ops.ed.undo() == {'FINISHED'}
            assert bpy.context.scene.clock_rig.controller is None
            assert bpy.ops.ed.redo() == {'FINISHED'}
            assert bpy.context.scene.clock_rig.controller is not None
        scene = bpy.context.scene
    elif state == 'PLAYING':
        with native_context():
            assert bpy.ops.clock.movement('EXEC_DEFAULT', True, preset='SWEEP') == {'FINISHED'}
            assert bpy.ops.ed.undo() == {'FINISHED'}
            assert bpy.context.scene.clock_rig.controller[TICK] == 1
            assert bpy.ops.ed.redo() == {'FINISHED'}
            assert bpy.context.scene.clock_rig.controller[TICK] == 0
            assert bpy.ops.screen.animation_play() == {'FINISHED'}
        scene = bpy.context.scene
        assert bpy.context.screen.is_animation_playing
    elif state == 'SHOT':
        with native_context():
            assert bpy.ops.screen.animation_play() == {'FINISHED'}
        assert not bpy.context.screen.is_animation_playing
        settings.animation_tool = 'SHOT'
        settings.range_start, settings.range_end = 1, 121
    elif state == 'SAVED':
        assert bpy.ops.clock.tool(action='SHOT') == {'FINISHED'}
        settings.animation_tool = 'PLAYBACK'
    elif state == 'RAMP':
        settings.animation_tool, settings.show_advanced = 'RAMP', False
    elif state == 'ADVANCED':
        settings.show_advanced = True
    elif state == 'CROWN':
        settings.ui_page, settings.extra_tool = 'MORE', 'CROWN'
        crown = bpy.data.objects.new('Crown', None)
        scene.collection.objects.link(crown)
        settings.crown, settings.use_crown = crown, True
        assert bpy.ops.clock.apply(stay_on_page=True) == {'FINISHED'}
        assert settings.ui_page == 'MORE'
    elif state == 'DATE':
        settings.extra_tool = 'DATE'
    elif state == 'DATE_CONNECTED':
        assert bpy.ops.clock.tool(action='CREATE_DATE') == {'FINISHED'}
        assert bpy.ops.clock.tool(action='DATE') == {'FINISHED'}
    elif state == 'GEAR':
        settings.extra_tool = 'GEAR'
    elif state == 'STOPWATCH':
        settings.extra_tool = 'CHRONO'
        obj = bpy.data.objects.new('Stopwatch second', None)
        scene.collection.objects.link(obj)
        settings.chrono_second = obj
        assert bpy.ops.clock.tool(action='CHRONO') == {'FINISHED'}
    elif state == 'EXPORT':
        settings.extra_tool = 'EXPORT'
    elif state == 'EXPORTED':
        settings.bake_start, settings.bake_end = 1, 3
        assert bpy.ops.clock.tool(action='COPY') == {'FINISHED'}
    elif state == 'CLOCKS':
        settings.extra_tool = 'CLOCKS'
    elif state == 'SETUP':
        settings.ui_page, settings.show_alignment = 'SETUP', True
    elif state == 'BROKEN':
        settings.ui_page = 'ANIMATE'
        del settings.controller[START_M]


def advance():
    global phase, attempts
    attempts += 1
    if phase == 0 and attempts % 5 == 0:
        dismiss()
        redraw()
    if errors or attempts > 150:
        capture('failed-state.png')
        print('UI SMOKE FAIL', draws, errors, flush=True)
        import os
        os._exit(1)
    try:
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'UI' and region.active_panel_category != 'Clock':
                        region.active_panel_category = 'Clock'
                        area.tag_redraw()
    except AttributeError:
        # Blender temporarily makes the category read-only before panel initialization.
        return 0.25
    if draws[phase] == 0:
        return 0.25
    if phase == 0 and attempts == 1:
        dismiss()
        redraw()
        return 0.25
    try:
        state = states[phase]
        filename = {'FIRST': 'first-run.png', 'EVERYDAY': 'everyday.png'}.get(state, state.lower() + '.png')
        capture(filename)
        if phase == len(states)-1:
            print(f'UI SMOKE PASS | Blender {bpy.app.version_string} | states={draws} | create/preset undo/redo=PASS | timeline play/stop=PASS', flush=True)
            bpy.ops.wm.quit_blender()
            return None
        phase += 1
        prepare(states[phase])
        redraw()
        return 0.25
    except Exception:
        print(traceback.format_exc(), flush=True)
        import os
        os._exit(1)


dismiss()
bpy.app.timers.register(advance, first_interval=0.5)
