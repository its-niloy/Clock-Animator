"""Check which tasks are actually exposed, plus the guided native operators."""
from pathlib import Path
from types import SimpleNamespace
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import advanced_tests as base  # noqa: E402
from clock_animator import core, features, ui  # noqa: E402
from clock_animator.constants import MODE, STEPS, TICK  # noqa: E402


class Layout:
    """Record native layout calls without relying on screenshot OCR."""
    def __init__(self, records=None, enabled=True):
        self.records = records if records is not None else []
        self.enabled = enabled

    def row(self, **kwargs):
        return Layout(self.records, self.enabled)

    column = box = row

    def label(self, **kwargs):
        self.records.append(('label', kwargs.get('text', ''), self.enabled))

    def prop(self, owner, key, **kwargs):
        self.records.append(('prop', key, self.enabled))

    def operator(self, name, **kwargs):
        button = SimpleNamespace(**kwargs)
        self.records.append(('operator', name, self.enabled, button))
        return button

    def operator_menu_enum(self, name, key, **kwargs):
        return self.operator(name, **kwargs)

    def separator(self, **kwargs):
        pass


def draw(scene):
    layout = Layout()
    context = SimpleNamespace(scene=scene, region=SimpleNamespace(width=280),
        preferences=bpy.context.preferences, screen=SimpleNamespace(is_animation_playing=False),
        active_object=bpy.context.active_object)
    ui.CLOCK_PT_animator.draw(SimpleNamespace(layout=layout), context)
    return layout.records


def test_guided_setup_and_preview_cleanup():
    scene, settings, hands, ctrl = base.fresh()
    core.remove_rig(settings)
    settings.setup_stage = 'HANDS'
    records = draw(scene)
    assert {r[1] for r in records if r[0] == 'prop'} == {'second', 'minute', 'hour'}
    assert not any(r[0] == 'operator' and r[1] == 'clock.apply' for r in records)
    for role, obj in hands.items():
        setattr(settings, role, obj)
    settings.minute = settings.second
    base.base.expect_error(lambda: bpy.ops.clock.tool(action='SETUP_NEXT'), 'distinct')
    assert settings.setup_stage == 'HANDS'
    settings.minute = hands['minute']
    assert bpy.ops.clock.tool(action='SETUP_NEXT') == {'FINISHED'}
    assert settings.setup_stage == 'CHECK' and not settings.controller
    before = {obj: obj.matrix_basis.copy() for obj in hands.values()}
    assert bpy.ops.clock.tool(action='TEST') == {'FINISHED'}
    assert settings.helper_collection
    assert bpy.ops.clock.tool(action='SETUP_BACK') == {'FINISHED'}
    assert settings.setup_stage == 'HANDS' and not settings.helper_collection
    bpy.ops.clock.tool(action='SETUP_NEXT')
    bpy.ops.clock.tool(action='TEST')
    assert bpy.ops.clock.apply() == {'FINISHED'}
    assert settings.ui_page == 'ANIMATE' and not settings.helper_collection
    assert not settings.show_advanced
    # Removing the rig still restores all original poses after the guided flow.
    core.remove_rig(settings)
    for obj, matrix in before.items():
        assert max(abs(obj.matrix_basis[i][j]-matrix[i][j]) for i in range(4) for j in range(4)) < 1e-6


def test_focused_animation_and_presets():
    scene, settings, hands, ctrl = base.fresh()
    records = draw(scene)
    props = {r[1] for r in records if r[0] == 'prop'}
    operators = {r[1] for r in records if r[0] == 'operator'}
    assert not props & {'crown', 'date_object', 'gear_object', 'chrono_second', 'bake_start', 'controller'}
    assert 'screen.animation_play' in operators and 'clock.apply' not in operators
    for preset, tick, steps in (('SWEEP', 0, 1), ('MECH8', 1, 8), ('QUARTZ', 1, 1)):
        assert bpy.ops.clock.movement(preset=preset) == {'FINISHED'}
        assert ctrl[TICK] == tick and ctrl[STEPS] == steps
    features.shot(scene)
    settings.animation_tool = 'PLAYBACK'
    records = draw(scene)
    assert ctrl[MODE] and core.prop_path('speed') not in {r[1] for r in records if r[0] == 'prop'}
    assert any(r[0] == 'operator' and getattr(r[3], 'action', None) == 'PLAYBACK' for r in records)


def test_optional_tools_and_fresh_start():
    scene, settings, hands, ctrl = base.fresh()
    settings.ui_page = 'MORE'
    expected = {'CROWN': 'use_crown', 'DATE': 'date_object', 'GEAR': 'gear_object',
                'CHRONO': 'chrono_second', 'EXPORT': 'bake_start', 'CLOCKS': 'controller'}
    for tool, field in expected.items():
        settings.extra_tool = tool
        records = draw(scene)
        assert field in {r[1] for r in records if r[0] == 'prop'}, tool
        assert not any(r[0] == 'prop' and r[1] in set(expected.values())-{field} for r in records), tool
    settings.extra_tool = 'EXPORT'
    settings.bake_start, settings.bake_end = 1, 3
    assert bpy.ops.clock.tool(action='COPY') == {'FINISHED'}
    assert bpy.ops.clock.tool(action='SELECT_EXPORT') == {'FINISHED'}
    assert set(bpy.context.selected_objects) == set(settings.export_collection.objects)
    settings.animation_tool, settings.show_advanced, settings.show_alignment = 'RAMP', True, True
    assert bpy.ops.clock.tool(action='NEW') == {'FINISHED'}
    assert not settings.controller and settings.setup_stage == 'HANDS'
    assert settings.animation_tool == 'PLAYBACK' and settings.extra_tool == 'CROWN'
    assert not settings.show_advanced and not settings.show_alignment
    assert ctrl.name in scene.objects and all(core.drivers(o) for o in hands.values())


if __name__ == '__main__':
    base.base.addon_utils.enable('clock_animator', default_set=True, persistent=True)
    for test in (test_guided_setup_and_preview_cleanup, test_focused_animation_and_presets, test_optional_tools_and_fresh_start):
        test()
        print('UX FLOW PASS', test.__name__)
