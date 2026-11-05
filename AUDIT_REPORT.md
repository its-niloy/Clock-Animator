What this repo does: Clock Animator rigs watch hands and optional crowns, date
wheels, gears and stopwatch hands using Blender's native drivers. It also builds
time animations and export copies. This audit assumes one artist, a few clocks,
and ordinary shot ranges up to roughly 10,000 frames.

Audited release: **1.0.0**, 2026-11-04. The user explicitly authorized fixes,
overriding ponytail-audit's report-only default. All findings below are fixed.

## Must fix

1. **The default axle tilted this watch** (`clock_animator/core.py:93`, `features.py:548`).
   - **What this is:** Preview and animation need the spindle perpendicular to the hand faces.
   - **Problem:** The supplied Circle.028, Circle.029 and Circle.030 meshes lie in local XY. The previous fixed Y default rotated through their faces.
   - **Fix:** Detect the thin mesh dimension, Z for this asset, and use it for both operations. Ambiguous meshes require a manual axis.
   - **If skipped:** The supplied watch continues to tilt in preview and animation.

2. **Changing rotation order changed the rest pose** (`clock_animator/core.py:283`).
   - **What this is:** The driven Euler axis is put first so the channel spins locally.
   - **Problem:** Existing delta rotation was interpreted using the new order. A rotated test hand changed its rest matrix by 0.196 before any clock motion.
   - **Fix:** Preserve the combined rotation, including delta rotation, during conversion and save the original delta values for removal. Test Euler, quaternion and axis-angle objects.
   - **If skipped:** Imported objects can tilt even with the correct spindle selected.

   Blender evaluates delta rotation using the active rotation representation:
   [native object transform implementation](https://projects.blender.org/blender/blender/src/branch/main/source/blender/blenkernel/intern/object.cc).

3. **Preview used a different transform path** (`clock_animator/features.py:548`).
   - **What this is:** The wireframe should demonstrate the turn the rig will perform.
   - **Problem:** Matrix decomposition of a mirrored object can place the reflection into different axes. The old preview disagreed with a local channel turn.
   - **Fix:** Convert and rotate the preview through the same local-axis function as the rig. The supplied watch also matches Blender's native Local Z operator.
   - **If skipped:** A preview can mislead the artist about the actual rig.

4. **Failed edits could destroy a working rig** (`clock_animator/state.py:81`, `core.py:361`, `core.py:460`).
   - **What this is:** Rebuild, animation, mechanism and bake operations change several objects together.
   - **Problem:** Injecting a failure on the second hand removed the previous drivers. The destructive bake rollback also reconstructed only two variables, losing advanced movement inputs.
   - **Fix:** Restore native drivers, all their variables, rotations, custom properties, bound action curves and UI assignments on failure. Remove newly created objects and unused actions.
   - **If skipped:** A cancelled operation can leave a partly disconnected clock or changed animation.

5. **Shared action slots could edit another object** (`clock_animator/core.py:69`).
   - **What this is:** A layered Blender Action can hold separate animation slots for multiple objects.
   - **Problem:** Curve lookup scanned every slot. Building a shot on the second controller cleared the first slot's elapsed-time keys.
   - **Fix:** Read only the slot bound to the object or its NLA strip; preserve the legacy Action path on Blender 4.2.
   - **If skipped:** Editing one clock can overwrite another object's animation.

6. **Duplicated clock IDs crossed ownership boundaries** (`clock_animator/core.py:51`).
   - **What this is:** Managed outputs must belong to one controller.
   - **Problem:** UUID strings survive duplication. Two controllers with the same copied ID could both collect the same hands during removal.
   - **Fix:** Record the controller object pointer and use native driver targets to identify older rigs. Also reject controllers outside the current scene.
   - **If skipped:** Removing one duplicated clock can disconnect another.

7. **Pausing an eased shot changed its past** (`clock_animator/features.py:177`).
   - **What this is:** Pause replaces future motion with a hold.
   - **Problem:** Deleting the future Bezier key changed its automatic handles, altering earlier frames. A keyed-time mode without a curve also crashed.
   - **Fix:** Split the current Bezier segment, freeze the preserved handles, and create a hold curve when necessary. Check fractional frames before the pause.
   - **If skipped:** Previously approved shot timing changes when the artist pauses later.

8. **Stopped playback lost whole days** (`clock_animator/features.py:246`).
   - **What this is:** Switching from a saved shot to playback should preserve the current time.
   - **Problem:** At speed zero, 174034 seconds became 1234 seconds because day preservation depended on dividing by speed.
   - **Fix:** Keep elapsed time in a separate native playback anchor. Older controllers request an update before using these tools.
   - **If skipped:** Date wheels and gear phases jump when switching modes.

9. **Gear updates failed to propagate offsets** (`clock_animator/features.py:444`).
   - **What this is:** A gear chain must follow both the speed and position of its driving gear.
   - **Problem:** Changing the parent ratio recalculated downstream rates but discarded the parent's changed phase offset.
   - **Fix:** Propagate each source's rate and angle offset in dependency order, with calibrated reference angles. Keep global reverse behavior and migrate old references.
   - **If skipped:** Visible teeth no longer stay aligned after a gearing edit.

10. **Stopwatch update and reset could damage motion** (`clock_animator/features.py:497`).
    - **What this is:** The panel reloads connected stopwatch hands into its pickers.
    - **Problem:** Connect rejected already connected hands and could leave partial setups on failure. Reset merged adjacent keys and rewrote the preceding motion, even at frame 121.
    - **Fix:** Permit same-role updates and roll back group failures. Preserve the past curve and use distinct native keys for reset, including at frame 1,000,000.
    - **If skipped:** Routine reconnection fails and resetting the stopwatch changes earlier shots.

11. **A failed build could replace a usable release** (`build.py:15`).
    - **What this is:** Packaging creates the extension ZIP used by the native installer.
    - **Problem:** Generic "not found" validation errors triggered the fallback builder. The output was written directly over the existing release.
    - **Fix:** Recognize only missing-command errors as fallback cases. Build and inspect a temporary ZIP, then replace the release atomically.
    - **If skipped:** A failed build can leave the advertised download incomplete or invalid.

## Should fix

12. **Export copies shared editable geometry** (`clock_animator/features.py:595`).
    - **What this is:** Baking should preserve the editable original rig.
    - **Problem:** A copied object's mesh still belonged to the source. Editing export vertices also edited the original.
    - **Fix:** Copy the geometry data and clean it up if export verification fails. Materials and image resources retain Blender's normal shared-data behavior.
    - **If skipped:** Preparing an export can inadvertently alter the source model.

13. **Saved UI preferences could replace object assignments** (`clock_animator/features.py:39`).
    - **What this is:** Selecting a clock restores its saved tool preferences.
    - **Problem:** The loader accepted any setting name, including controller and hand pointers, from the custom-property dictionary.
    - **Fix:** Restore only the known tool fields and ignore invalid stored preference values.
    - **If skipped:** Damaged or edited metadata can switch the selected controller or hand unexpectedly.

14. **Ready status hid missing or muted hands** (`clock_animator/core.py:430`).
    - **What this is:** The sidebar reports whether the clock is ready.
    - **Problem:** Optional mechanisms counted as primary hands. A single hand plus two mechanisms was reported complete; muted drivers were also missed.
    - **Fix:** Count distinct second/minute/hour roles and check driver mute and validity flags.
    - **If skipped:** The artist receives a ready message for a clock that does not animate correctly.

Additional hardening: finite animation values and native frame limits are checked
before edits. Ramp creation allocates keys in bulk. Installed-package checks
verify the actual source and manifest version rather than merely finding a module.

## Evidence

- `tests/output/audit-before.log`: all eight initial regression groups failed on
  the previous implementation. `audit-gears-before.log` reproduces the chain issue.
- `tests/audit_tests.py`: fifteen regression groups, including deliberate failures
  during rebuild, curve replacement, stopwatch attachment and destructive bake.
- `tests/test_build.py`: simulated validation failure keeps the last archive intact.
- Full runtime coverage includes eighteen original and thirteen advanced groups,
  actual GUI draws and undo/redo, native extension installation, saved-file native
  evaluation, and actual GLB/FBX export/import checks on both tested versions.
- `tests/watch_regression.py`: the actual supplied watch, native Local Z comparison,
  three preview copies and thirty sampled animated poses in Blender 5.2.3.
- The corrected asset reopens and seeks with the add-on absent and auto-run disabled.
- A 10,000-frame ramp created 10,002 keys in 0.042 seconds on Blender 5.2; pausing
  with a rollback snapshot took 0.312 seconds on this machine.

Verdict: The reproduced defects are fixed. Native verification covers the tested
Windows workflows; this is not a claim that every Blender release or renderer is certified.

Not checked: macOS/Linux, Blender versions besides 4.2.23 and 5.2.3, Octane rendering,
and long interactive artist sessions. Blender 4.2 cannot read the supplied newer
watch file, so its spindle tests use synthetic assets. Uneven parent scale or
shear can distort world-space motion; the preview uses the rig's local channel,
and unsupported sheared export transforms are rejected. Blender's documented
single-precision output limit remains; ideal unwrapped 1e-6-radian accuracy is not met.
