# Clock Animator test report

## Release preflight, 2026-11-05

The full runner was repeated before publication on Blender 4.2.23 and 5.2.3.
All 49 runtime/task-flow groups per version, 20 native UI states, installer checks,
fresh-process checks, GLB/FBX round trips, formula tests, build-failure tests and
Ruff passed. The known strict ideal unwrapped-angle precision requirement remains
unmet and is explicitly separated from those passing implementation checks.
The local run log is `tests/output/release-1.0.0-validation.log`.

## 1.0.0 task-focused UI and illustrated guide

This is a UI revision of the requested 1.0.0 package, not a version bump.

The first-use flow now has Choose hands and Check rotation steps, followed by
Animate. Existing clocks use Animate / Setup / More. The live engine and all
thirteen requested feature areas remain available.

Validation retains the 46 prior runtime groups and adds three task-flow groups
per version, for **49 groups per version**. Twenty native sidebar states per
version cover the setup steps, effective/saved animation controls, all extra tools,
export readiness and damaged-controller recovery. Create and preset Undo/Redo
and timeline Play/Stop are exercised in actual windows. A separate 125% UI-scale
run checks the Blender 5.2 layout. Logs: `tests/output/ux-final-validation.log`,
`0-ui.log`, `1-ui.log`, and `1-ui-large.log`.

The illustrated README uses seven local figures assembled from actual native
sidebar captures. Its local links, section anchors, Markdown rendering and image
references are checked. It includes all features, worked examples and a symptom-based
troubleshooting reference. UI research and evidence boundaries are recorded in
[docs/UX.md](docs/UX.md).

Guide completion was checked on 2026-11-05: 55 heading anchors, 30 links and seven
local figures passed structural validation, and Markdown was rendered to HTML
with MarkdownIt. A browser visual preview could not be completed: the in-app
browser failed to initialize and the isolated Edge headless renderer exited with
an access-violation crash. The actual native Blender captures and assembled guide
figures were inspected separately. Browser-specific guide layout is unverified.

The native float-precision limitation described below remains. This UI revision
does not claim new precision, renderer or cross-platform certification.

## 1.0.0 audited release, 2026-11-04

The release number is 1.0.0 as requested. The 2.0.0 section below records earlier
development verification and does not identify the current download.

Current coverage on Windows x64, Blender 4.2.23 LTS and 5.2.3 LTS:

* Eighteen original integration groups, thirteen advanced groups, and fifteen
  audit regression groups per version: **46 groups per version**.
* Four formula methods, three motion methods and one package-failure method.
* Seven native panel states per version and actual Create/Undo/Redo.
* Actual native ZIP installation and version/source verification on both versions.
* GLB and FBX export/import, fifteen pose comparisons per format per version.
* Source and native-expression checks, fresh-process reopen with auto-run disabled,
  Ruff and both Blender/standard-library package builders.

An additional Blender 5.2 load check created a 10,000-frame speed ramp with 10,002
keys in 0.042 seconds and paused it, including its rollback snapshot, in 0.312
seconds on this machine. These measurements are local evidence, not timing guarantees.

The supplied `watch 2.blend` is verified in Blender
5.2.3. All three hands have local Z as their spindle. Preview matches Blender's
native Local Z transform; thirty animated poses keep their normals in the dial
plane. A separate corrected copy reopens and seeks without the add-on and with
auto-run disabled. The original file is not overwritten.

Blender 4.2 reports that this newer asset cannot be read. Its generated spindle,
mirrored-object, delta-rotation and restoration tests pass instead. Octane is not
installed in the isolated test environment; its other scene reports an unavailable
engine on load. Rendering verification uses Workbench and isolated real hand meshes
with a temporary dial guide, not the original materials or a claimed Octane render.

The first Blender 5.2 GUI run did not draw the panel before its timeout. Delayed
startup-dialog dismissal was added to the test harness; a separate rerun passed.
This change is confined to the harness. Full results are retained in
`tests/output/final-validation.log`, with individual logs alongside it.

The strict ideal 1e-6-radian unwrapped precision requirement still fails at the
known Blender float boundary; measured maximum ideal error remains
0.000352825161826 radians. This is not described as a production accuracy pass.

See [AUDIT_REPORT.md](AUDIT_REPORT.md) for the concrete defects and fixes.

## 2.0.0 full animation tools and progressive UI

Test date: 2026-11-04. Windows x64. Tested binaries: Blender 4.2.23 LTS and
Blender 5.2.3 LTS. Distribution is extension-only.

### Requested feature coverage

| # | Feature | Delivered behavior | Evidence |
| --- | --- | --- | --- |
| 1 | Animate between times | From/to clock time, frame range, extra days, linear or eased keys | Shot endpoints, midpoint, eased quarter-point, seek order and re-apply tested |
| 2 | Speed ramps and pause/resume | Integrated linear/smoothstep speed, terminal continuation and frame-based timing decisions | Analytic integral checks at both FPS bases, pause and resume tested |
| 3 | Movement presets | Quartz, 6-step, 8-step and continuous motion | Driver angles checked at a fractional clock second |
| 4 | Crown controls | Quarter/full/custom signed turns, current-pose keys and readable gearing | Actual operators invoked; crown action and geared time checked |
| 5 | Live display | Current HH:MM:SS separately from starting time | Pure formatting tests and actual panel draws |
| 6 | Date wheel | Existing object or generated static-number mesh, instant/smooth midnight change, backward crown input | Mesh generation, positive/negative day changes, transition midpoint and crown midnight crossing tested |
| 7 | Setup helpers | Axles and 15-degree wireframe previews; source objects stay intact | Object counts, hidden-render flags, original matrices and safe helper cleanup tested |
| 8 | Clock manager | Named picker, restored hands/crown/axes/presets/tool settings, new-clock workflow | Same controller/action survives updates; selecting independent clocks restores assignments |
| 9 | Export copy | Parent-free animation copies, sampling, matching NLA tracks, source rig retained | Sample verification, rejected-shear cleanup, real GLB and FBX export/import tests |
| 10 | Tick rebound | Optional damped second-hand motion with zero default | Nonzero fractional response, exact step boundary and native validity checked |
| 11 | Additional gears | Tooth ratios, direction, axes, chains, calibrated reference and safe updates | Chain rates, reverse, full-turn phase, update and dependent-removal refusal tested |
| 12 | Chronograph | Independent second/minute/hour hands and saved Start/Stop/Reset decisions | Elapsed values, hold, resume, reset and main-clock independence tested |
| 13 | Long-rotation precision | Per-hand bounded phases computed before RNA driver-output storage | At frame 1,000,000 the second-hand phase matched within 1e-6; normal native limits remain |

### Final validation

* All 18 original integration groups and all 13 advanced groups passed on each
  Blender version: 31 groups per version.
* Four original math methods and three new motion-math methods passed under
  Python 3.12. Ruff passed.
* Seven actual UI draw states passed per version: first run, playback, shot,
  ramp, gear, stopwatch and damaged-property recovery. Create undo/redo passed.
* Older controller schemas request an update before new tools run and upgrade in
  place without changing the clock ID.
* The controller action and ID remain intact on re-apply. Saved shot/date/phase
  drivers evaluated in a fresh process without enabling the add-on and with
  Auto Run Python Scripts disabled.
* Both ZIP build paths and actual extension installation passed on both versions.
* Export tests baked a range crossing the second-hand full-turn boundary,
  exported actual GLB and FBX files, imported them again, aligned format time
  origins, and compared 15 object/frame poses per format per version.
* Invalid export TRS/shear was rejected while preserving the live rig and
  removing the incomplete copy objects and actions.

The UI follows published progressive disclosure and recognition guidance, with
native Blender controls. [docs/UX.md](docs/UX.md) records sources, the catalog's
fallbacks, decisions, and screenshot review. No novice-user study, screen-reader
certification, or arbitrary theme/OS scaling certification was performed.

### Practical limits

* The date wheel repeats 31 positions; Gregorian month lengths and leap years
  are not simulated. A suitable date window must exist in the watch model.
* Speed profiles and bake copies are sampled at integer frames. Sampling does
  not prove every subframe, motion-blur result or exporter option. Motion above
  half a turn per sample requires a sufficient sampling frame rate.
* The original strict 1e-6 absolute error assumption remains FAIL for native
  single-precision unwrapped outputs. Bounded hand phases improve long playback;
  they cannot remove every input/curve precision limit or Blender 5.2's tiny-value
  clamping. The raw runner still reports that failure explicitly.
* The user's watch .blend and other operating systems were not tested. The
  validation uses synthetic meshes, parents, crowns, gears and date wheels.
* Source geometry and materials are shared by export-object copies, as documented;
  the bake tool changes object transforms/actions, not mesh contents.
* The legacy destructive bake operator remains available for existing scripts;
  the UI defaults to the separate-copy workflow. Controller NLA editing is not
  supported, while export-copy NLA tracks are supported and tested.

### Reproduce

```powershell
& 'C:\Program Files\Python312\python.exe' tests/run_all.py --blender '.tools\blender-4.2.23-windows-x64\blender.exe' --blender 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --ui
```

Actual final runner output:

```text
math: PASS
motion-math: PASS
ruff: PASS
build-fallback: PASS
build-extension: PASS

Blender: .tools\blender-4.2.23-windows-x64\blender.exe
0-probe: PASS
TEST SUMMARY
test_basic                               PASS
test_rates                               PASS
test_axes_parent_and_restore             PASS
test_rotation_modes                      PASS
test_local_axis_rotation                 PASS
test_local_axis_bake_and_upgrade         PASS
test_partial_and_isolation               PASS
test_validation_and_changed_slots        PASS
test_pivots_and_selection                PASS
test_bake_and_realtime                   PASS
test_names_and_unrelated_animation       PASS
test_native_limits_and_bake_fallback     PASS
test_crown_gearing_and_one_way           PASS
test_crown_keyframes_bake_and_isolation  PASS
test_crown_validation_and_missing_input  PASS
test_fresh_process                       PASS
test_crown_fresh_process                 PASS
test_lifecycle                           PASS
Angle samples: 318; max ideal absolute error: 0.000352825161826 rad
VERIFY a-d: PASS if basic/rates passed; e: FAIL strict 1e-6 ideal precision; f: separate UI test
ALL 18 GROUPS PASSED

Blender quit
TBBmalloc: skip allocation functions replacement in ucrtbase.dll: unknown prologue for function _msize
TEST SUMMARY | Advanced tools | Blender 4.2.23 LTS
test_shot_and_manager                        PASS
test_ramp_pause_resume                       PASS
test_movement_and_rebound                    PASS
test_crown_tools                             PASS
test_date_wheel                              PASS
test_gears                                   PASS
test_stopwatch                               PASS
test_alignment_helpers                       PASS
test_precision_and_export_copy               PASS
test_validation_and_independent_clocks       PASS
test_export_failure_preserves_rig            PASS
test_old_controller_upgrade                  PASS
test_reopen                                  PASS
ALL 13 ADVANCED GROUPS PASSED

Blender quit
TBBmalloc: skip allocation functions replacement in ucrtbase.dll: unknown prologue for function _msize
0-export: PASS
UI SMOKE PASS | Blender 4.2.23 LTS | states=[2, 2, 2, 2, 2, 2, 2] | undo/redo=PASS
0-packages: PASS

Blender: C:\Program Files\Blender Foundation\Blender 5.2\blender.exe
1-probe: PASS
TEST SUMMARY
test_basic                               PASS
test_rates                               PASS
test_axes_parent_and_restore             PASS
test_rotation_modes                      PASS
test_local_axis_rotation                 PASS
test_local_axis_bake_and_upgrade         PASS
test_partial_and_isolation               PASS
test_validation_and_changed_slots        PASS
test_pivots_and_selection                PASS
test_bake_and_realtime                   PASS
test_names_and_unrelated_animation       PASS
test_native_limits_and_bake_fallback     PASS
test_crown_gearing_and_one_way           PASS
test_crown_keyframes_bake_and_isolation  PASS
test_crown_validation_and_missing_input  PASS
test_fresh_process                       PASS
test_crown_fresh_process                 PASS
test_lifecycle                           PASS
Angle samples: 318; max ideal absolute error: 0.000352825161826 rad
VERIFY a-d: PASS if basic/rates passed; e: FAIL strict 1e-6 ideal precision; f: separate UI test
ALL 18 GROUPS PASSED

Blender quit
TEST SUMMARY | Advanced tools | Blender 5.2.3 LTS
test_shot_and_manager                        PASS
test_ramp_pause_resume                       PASS
test_movement_and_rebound                    PASS
test_crown_tools                             PASS
test_date_wheel                              PASS
test_gears                                   PASS
test_stopwatch                               PASS
test_alignment_helpers                       PASS
test_precision_and_export_copy               PASS
test_validation_and_independent_clocks       PASS
test_export_failure_preserves_rig            PASS
test_old_controller_upgrade                  PASS
test_reopen                                  PASS
ALL 13 ADVANCED GROUPS PASSED

Blender quit
1-export: PASS
UI SMOKE PASS | Blender 5.2.3 LTS | states=[2, 2, 2, 2, 2, 2, 2] | undo/redo=PASS
1-packages: PASS

ALL IMPLEMENTATION CHECKS PASSED. Spec assumption e remains FAIL. Raw logs: tests/output/
```

Actual export verification output:

```text
EXPORT ROUNDTRIP PASS | 4.2.23 LTS | GLB | samples=15 | max_matrix_error=5.96046448e-08
EXPORT ROUNDTRIP PASS | 4.2.23 LTS | FBX | samples=15 | max_matrix_error=1.94707212e-07
EXPORT ROUNDTRIP PASS | 5.2.3 LTS | GLB | samples=15 | max_matrix_error=5.96046448e-08
EXPORT ROUNDTRIP PASS | 5.2.3 LTS | FBX | samples=15 | max_matrix_error=1.94707212e-07
```

Earlier release records follow. Their statements describe what was tested at the time.

## Extension-only distribution

Updated 2026-11-04: removed the legacy ZIP build path, generated legacy archives,
and legacy installer test. Current installation and build instructions describe
the extension only. Earlier results below record the formats tested at that time.

The standard-library fallback build and Blender's native extension build both
passed. Each produced the extension ZIP without recreating a legacy archive.
Extension install, enable, create, remove, and disable passed on Blender 4.2.23
and 5.2.3 in isolated profiles. Ruff passed. Animation tests were not repeated
for this packaging change. Raw installer logs: `tests/output/extension-only-0.log`
and `tests/output/extension-only-1.log`.

## 1.1.0 crown / rotor input

Test date: 2026-11-04. Host: Windows 11, x64.

Added an optional object rotation input with a separate spindle axis and a live
gear ratio. As requested, this input drives the second hand, and the minute and
hour follow at 1/60 and 1/720 of its rotation. Normal time and crown input add
into the existing native time driver. The crown receives no driver or hand
feedback. Default gearing is 60 second-hand turns per crown turn, equivalent to
one hour of clock time per full crown turn. This is an adjustable animation
ratio, not a manufacturer-specific mechanism calibration.

The source object, axis, attachment angle, and ratio are stored per controller.
Multiple unwrapped turns, negative turns, zero/negative ratios, and reverse hand
direction work. Re-apply retains the source reference and live ratio when the
same crown and axis remain connected. Real Time Start recalibrates the crown at
the current frame. An unanimated input is prepared in the selected local-axis
Euler order without changing its visible pose. Existing incompatible rotation
keys or crown rotation drivers are rejected before rig edits. Removing/baking
the rig leaves the crown's prepared mode, current rotation and action intact.

Actually tested on Blender 4.2.23 LTS and Blender 5.2.3 LTS:

* All 18 integration groups passed on both versions, including the previous
  local-axis regression tests and 318 original/cleanup angle samples per version.
* Crown tests covered X/Y/Z spindle axes, both tick modes, multiple forward and
  backward turns, positive/negative/zero gearing, reverse direction, re-apply,
  Real Time Start, missing input/properties, and invalid feedback connections.
* Normal playback left an unkeyed crown stationary. A crown on one clock did not
  affect a separate clock without that input.
* Keyframed crown rotation survived re-apply. Tick and nonlinear smooth input
  baked into hand keyframes while preserving the crown action and current frame.
* Saved crown-driven rigs evaluated in a fresh Blender process with the add-on
  disabled and Auto Run Python Scripts disabled. All generated drivers remained
  simple and valid on evaluated fixtures.
* Real GUI panel drawing with the crown controls, missing properties, and Create
  undo/redo passed. Both extension and legacy installers passed on both versions.
* Four pure Python test methods and Ruff passed. Both build paths passed.

A separate same-frame dependency-graph probe also passed without calling
scene.frame_set after changing the crown rotation:

```text
LIVE CROWN PASS 4.2.23 LTS same-frame update, no frame_set
LIVE CROWN PASS 5.2.3 LTS same-frame update, no frame_set
```

The user's watch .blend was not supplied or opened. Existing Blender precision
limits still apply to long elapsed times and large geared rotations. No glTF/FBX
round trip or other operating-system check was performed. Physical crown pull
positions, winding energy, date gears, and movement-specific calibration are
outside this animation control.

Run the full checks with:

```powershell
& 'C:\Program Files\Python312\python.exe' tests/run_all.py --blender '.tools\blender-4.2.23-windows-x64\blender.exe' --blender 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --ui
```

Actual final 1.1.0 runner output:

```text
math: PASS
ruff: PASS
build-fallback: PASS
build-extension: PASS

Blender: .tools\blender-4.2.23-windows-x64\blender.exe
0-probe: PASS
TEST SUMMARY
test_basic                               PASS
test_rates                               PASS
test_axes_parent_and_restore             PASS
test_rotation_modes                      PASS
test_local_axis_rotation                 PASS
test_local_axis_bake_and_upgrade         PASS
test_partial_and_isolation               PASS
test_validation_and_changed_slots        PASS
test_pivots_and_selection                PASS
test_bake_and_realtime                   PASS
test_names_and_unrelated_animation       PASS
test_native_limits_and_bake_fallback     PASS
test_crown_gearing_and_one_way           PASS
test_crown_keyframes_bake_and_isolation  PASS
test_crown_validation_and_missing_input  PASS
test_fresh_process                       PASS
test_crown_fresh_process                 PASS
test_lifecycle                           PASS
Angle samples: 318; max ideal absolute error: 0.000352825161826 rad
VERIFY a-d: PASS if basic/rates passed; e: FAIL strict 1e-6 ideal precision; f: separate UI test
ALL 18 GROUPS PASSED

Blender quit
TBBmalloc: skip allocation functions replacement in ucrtbase.dll: unknown prologue for function _msize
UI SMOKE PASS | Blender 4.2.23 LTS | live draws=1 | missing-key draws=2 | undo/redo=PASS
0-packages: PASS

Blender: C:\Program Files\Blender Foundation\Blender 5.2\blender.exe
1-probe: PASS
TEST SUMMARY
test_basic                               PASS
test_rates                               PASS
test_axes_parent_and_restore             PASS
test_rotation_modes                      PASS
test_local_axis_rotation                 PASS
test_local_axis_bake_and_upgrade         PASS
test_partial_and_isolation               PASS
test_validation_and_changed_slots        PASS
test_pivots_and_selection                PASS
test_bake_and_realtime                   PASS
test_names_and_unrelated_animation       PASS
test_native_limits_and_bake_fallback     PASS
test_crown_gearing_and_one_way           PASS
test_crown_keyframes_bake_and_isolation  PASS
test_crown_validation_and_missing_input  PASS
test_fresh_process                       PASS
test_crown_fresh_process                 PASS
test_lifecycle                           PASS
Angle samples: 318; max ideal absolute error: 0.000352825161826 rad
VERIFY a-d: PASS if basic/rates passed; e: FAIL strict 1e-6 ideal precision; f: separate UI test
ALL 18 GROUPS PASSED

Blender quit
UI SMOKE PASS | Blender 5.2.3 LTS | live draws=1 | missing-key draws=2 | undo/redo=PASS
1-packages: PASS

ALL IMPLEMENTATION CHECKS PASSED. Spec assumption e remains FAIL. Raw logs: tests/output/
```

## 1.0.1 local-axis tilt fix

Test date: 2026-11-04. Host: Windows 11, x64.

The 1.0.0 driver changed a Y Euler channel that did not match the hand's current
Local Y axis when its original rotation was nonzero. The new regression failed
before the fix with a maximum world-matrix entry error of 1.380125343799591 on
Blender 5.2.3, compared with Blender's own Local rotation operator.

The fix preserves orientation while choosing XYZ for X, YXZ for Y, or ZXY for Z.
The driven axis is first in the Euler order, so its channel composes a rotation
in the hand's local frame. The time and hand expressions remain native simple
expressions. No geometry transforms, extra objects, handlers, or driver functions
were added. Removal restores the original mode before assigning saved values,
so automatic rotation-mode conversion cannot overwrite a saved quaternion pose.

Actually tested on Blender 4.2.23 LTS and 5.2.3 LTS:

* All 14 integration groups passed on both versions, including the original 312
  angle samples per version.
* 48 manual Local gizmo comparisons per version passed: X/Y/Z, all six Euler
  orders, Quaternion and Axis-Angle, and both directions. Fixtures include a
  rotated parent and nonuniform object scale. Matrix tolerance was 2e-5.
* The same fixtures retained their axle direction through tick and smooth
  playback, re-applied without compounding, and restored their original modes,
  rotation values, parent, and rest matrices on removal.
* A reconstructed 1.0.0 rig reproduced the tilt, then re-apply repaired it.
  Tick and smooth baking preserved the corrected world matrices.
* Both ZIP installers, real panel drawing, Create undo/redo, disable/enable,
  and fresh-process evaluation with auto-run disabled passed on both versions.
* Pure Python tests passed. The default Python 3.14 interpreter lacked Ruff,
  so the runner reported a skip. A separate check using the installed Python
  3.12 Ruff returned `All checks passed!`.

The user's watch .blend was not supplied or opened. The screenshots identify
symptoms; the fix was verified on synthetic pre-rotated fixtures in real Blender.
The original single-precision limit (assumption e) remains unchanged. glTF/FBX
round trips and other operating systems were not tested.

To upgrade an existing rig, install 1.0.1, restart Blender, open the scene, keep
the existing controller selected, and press Create Clock Animation again. The
old rest metadata is compatible; re-apply retains the time controls.

Actual final 1.0.1 runner output:

```text
math: PASS
ruff: SKIP (not installed)
build-fallback: PASS
build-extension: PASS

Blender: .tools\blender-4.2.23-windows-x64\blender.exe
0-probe: PASS
TEST SUMMARY
test_basic                               PASS
test_rates                               PASS
test_axes_parent_and_restore             PASS
test_rotation_modes                      PASS
test_local_axis_rotation                 PASS
test_local_axis_bake_and_upgrade         PASS
test_partial_and_isolation               PASS
test_validation_and_changed_slots        PASS
test_pivots_and_selection                PASS
test_bake_and_realtime                   PASS
test_names_and_unrelated_animation       PASS
test_native_limits_and_bake_fallback     PASS
test_fresh_process                       PASS
test_lifecycle                           PASS
Angle samples: 312; max ideal absolute error: 0.000352825161826 rad
VERIFY a-d: PASS if basic/rates passed; e: FAIL strict 1e-6 ideal precision; f: separate UI test
ALL 14 GROUPS PASSED

Blender quit
TBBmalloc: skip allocation functions replacement in ucrtbase.dll: unknown prologue for function _msize
UI SMOKE PASS | Blender 4.2.23 LTS | live draws=1 | missing-key draws=1 | undo/redo=PASS
0-packages: PASS

Blender: C:\Program Files\Blender Foundation\Blender 5.2\blender.exe
1-probe: PASS
TEST SUMMARY
test_basic                               PASS
test_rates                               PASS
test_axes_parent_and_restore             PASS
test_rotation_modes                      PASS
test_local_axis_rotation                 PASS
test_local_axis_bake_and_upgrade         PASS
test_partial_and_isolation               PASS
test_validation_and_changed_slots        PASS
test_pivots_and_selection                PASS
test_bake_and_realtime                   PASS
test_names_and_unrelated_animation       PASS
test_native_limits_and_bake_fallback     PASS
test_fresh_process                       PASS
test_lifecycle                           PASS
Angle samples: 312; max ideal absolute error: 0.000352825161826 rad
VERIFY a-d: PASS if basic/rates passed; e: FAIL strict 1e-6 ideal precision; f: separate UI test
ALL 14 GROUPS PASSED

Blender quit
UI SMOKE PASS | Blender 5.2.3 LTS | live draws=1 | missing-key draws=1 | undo/redo=PASS
1-packages: PASS

ALL IMPLEMENTATION CHECKS PASSED. Spec assumption e remains FAIL. Raw logs: tests/output/
```

## 1.0.0 baseline report

Test date: 2026-11-03. Host: Windows 11, x64.

## Result

* Blender 4.2.23 LTS: 12 integration groups passed, 312 angle samples checked.
* Blender 5.2.3 LTS: 12 integration groups passed, 312 angle samples checked.
* Pure Python: 3 test methods passed, including the required times, negative
  speed, non-unit fps_base, direction, safe expression evaluation, and naming.
* Ruff 0.15.22: all checks passed.
* Actual GUI panel draw: live controls and missing-property handling passed on
  both Blender versions. Create undo/redo also passed. The harness temporarily
  uses the startup Item category.
* Extension and legacy ZIP installation: passed through Blender's actual
  installers on both versions, using isolated profiles. The legacy test verifies
  that the imported code comes from the installed user scripts directory.
* Native extension build and standard-library ZIP fallback: passed.
* Fresh Blender process, saved .blend, add-on disabled and auto-run disabled:
  driver evaluation passed on both versions.

These passing implementation checks do not make the brief's strict absolute
precision assumption true. That assumption was disproved and is reported below.

## VERIFY FIRST verdicts

| Assumption | 4.2.23 | 5.2.3 | Evidence |
| --- | --- | --- | --- |
| a: all generated drivers are simple and valid | PASS | PASS | Every generated driver checked after frame evaluation; auto-run disabled |
| b: floor() and built-in frame are native | PASS | PASS | Tick, sweep, negative speed, and required frame matrix evaluated |
| c: Empty custom-property driver updates time | PASS | PASS | Time compared with Blender's single-precision output |
| d: Scene fps and fps_base SINGLE_PROP targets resolve | PASS | PASS | 24, 25, 30 fps and 24 / 1.001 tested |
| e: ideal angles always match RNA within 1e-6 radians | FAIL | FAIL | Float32 outputs cannot satisfy this for large unwrapped angles |
| f: UILayout.prop draws controller custom properties | PASS | PASS | Real window redraw with intact and missing keys; no draw exceptions |

The initial probe measured an absolute second-hand error of
`0.0000940494219321` radians at 12h + 1s. The full test matrix measured a maximum
ideal error of `0.000352825161826` radians. Tests separately compare the expected
single-precision result within 1e-6; they do not silently widen the ideal-angle
assertion or label assumption e as passed.

The newest tested engine also zeroed the smooth hour-hand output
`0.00000606017101745` radians near midnight. That limit is covered by a bake
regression test. It is documented as an engine limitation, not fixed by a hidden
handler, driver function, namespace registration, or modified core formula.

## Design decisions

* Retained the exact prescribed native time and hand expressions, fixed literals,
  one Empty, and one time source. No driver namespace changes or handlers.
* Interpreted the time formula as seconds from midnight, rather than the brief's
  conflicting phrase "since 12:00". Noon still produces the correct pose.
* Saved original non-Euler rotation values and mode in addition to `_clock_rest`
  so Remove restores the original representation and pose.
* Reject existing rotation animation, shared pivot geometry, foreign rig hands,
  linked data, and controller animation edits before destructive work.
* Bake samples first, rolls back failed key insertion, and reduces smooth keys
  only when the measured samples are linear. Blender 5.2's small-output behavior
  means two keys are not always enough to preserve integer-frame samples.
* Bake finalizes hand animation and clears ownership; Undo recovers the live rig.
  Existing hand actions/NLA and animated controller settings are rejected.
* Included optional Bake, Real Time Start, and independent clocks. Omitted the
  optional overshoot feature to keep the quartz formula and shared time behavior.

## Reproduce

Run from `M:\Projects\Clock Animator`:

```powershell
python tests/run_all.py --blender '.tools\blender-4.2.23-windows-x64\blender.exe' --blender 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --ui
```

Replace paths if Blender is installed elsewhere. The 4.2.23 portable build is
under `.tools/` in this workspace. The runner stores raw logs in `tests/output/`
and isolates Blender preferences under `.tools/test-profile-*`. It runs the
initial driver probe, both headless suites, actual UI draws, both installers,
formula tests, Ruff when available, and both build paths. `--ui` requires a
desktop session. Headless scripts exit nonzero on an assertion failure.

Direct headless command for either binary:

```powershell
blender -b --factory-startup --python-exit-code 1 --python tests/run_tests.py
```

## Not verified

No glTF/FBX export/import round trip, other operating systems, other Blender
releases, or interactive manual artist review was performed. Undo flags are set
on all operators; actual undo/redo was exercised for Create, not every operator.
The test fixture uses a local parent; complex constraints and externally linked
rigs are outside the tested editing scope. No public repository or release was
published. The strict ideal precision requirement remains unsatisfied because
the tested Blender engines cannot preserve it with the required design.

The raw UI logs include Blender's shutdown message "Cannot change old file
(file saved with @)" after the undo/redo test. The assertions and UI draws had
already passed; this is a recovery-file shutdown message, not a driver or panel
exception. The 4.2 executable also emits a nonfatal TBBmalloc diagnostic. Both
processes exited with code zero.

## Actual final runner output

```text
math: PASS
ruff: PASS
build-fallback: PASS
build-extension: PASS

Blender: .tools\blender-4.2.23-windows-x64\blender.exe
0-probe: PASS
TEST SUMMARY
test_basic                               PASS
test_rates                               PASS
test_axes_parent_and_restore             PASS
test_rotation_modes                      PASS
test_partial_and_isolation               PASS
test_validation_and_changed_slots        PASS
test_pivots_and_selection                PASS
test_bake_and_realtime                   PASS
test_names_and_unrelated_animation       PASS
test_native_limits_and_bake_fallback     PASS
test_fresh_process                       PASS
test_lifecycle                           PASS
Angle samples: 312; max ideal absolute error: 0.000352825161826 rad
VERIFY a-d: PASS if basic/rates passed; e: FAIL strict 1e-6 ideal precision; f: separate UI test
ALL 12 GROUPS PASSED

Blender quit
TBBmalloc: skip allocation functions replacement in ucrtbase.dll: unknown prologue for function _msize
UI SMOKE PASS | Blender 4.2.23 LTS | live draws=1 | missing-key draws=1 | undo/redo=PASS
0-packages: PASS

Blender: C:\Program Files\Blender Foundation\Blender 5.2\blender.exe
1-probe: PASS
TEST SUMMARY
test_basic                               PASS
test_rates                               PASS
test_axes_parent_and_restore             PASS
test_rotation_modes                      PASS
test_partial_and_isolation               PASS
test_validation_and_changed_slots        PASS
test_pivots_and_selection                PASS
test_bake_and_realtime                   PASS
test_names_and_unrelated_animation       PASS
test_native_limits_and_bake_fallback     PASS
test_fresh_process                       PASS
test_lifecycle                           PASS
Angle samples: 312; max ideal absolute error: 0.000352825161826 rad
VERIFY a-d: PASS if basic/rates passed; e: FAIL strict 1e-6 ideal precision; f: separate UI test
ALL 12 GROUPS PASSED

Blender quit
UI SMOKE PASS | Blender 5.2.3 LTS | live draws=1 | missing-key draws=1 | undo/redo=PASS
1-packages: PASS

ALL IMPLEMENTATION CHECKS PASSED. Spec assumption e remains FAIL. Raw logs: tests/output/
```

## Actual pure Python output

```text
test_formulas (__main__.MathTests.test_formulas) ... ok
test_names (__main__.MathTests.test_names) ... ok
test_validation (__main__.MathTests.test_validation) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.018s

OK
```

## Actual initial probe output

```text
VERIFY_FIRST 4.2.23 LTS
a PASS native simple, valid drivers with auto-run disabled
b PASS floor() and built-in frame
c PASS Empty custom property time updates
d PASS Scene fps/fps_base SINGLE_PROP
e FAIL absolute RNA angle error=9.40494219321e-05
f PENDING actual panel redraw test
Blender 4.2.23 LTS (hash d0cbe84903e8 built 2026-07-21 01:34:46)

Blender quit
TBBmalloc: skip allocation functions replacement in ucrtbase.dll: unknown prologue for function _msize
```

```text
VERIFY_FIRST 5.2.3 LTS
a PASS native simple, valid drivers with auto-run disabled
b PASS floor() and built-in frame
c PASS Empty custom property time updates
d PASS Scene fps/fps_base SINGLE_PROP
e FAIL absolute RNA angle error=9.40494219321e-05
f PENDING actual panel redraw test
Blender 5.2.3 LTS (hash e13b728c6880 built 2026-10-22 01:37:16)

Blender quit
```

The probe marks f pending because it is headless; the subsequent actual UI tests supply its PASS verdict. Full installer, fresh-process and UI logs remain in `tests/output/`.
