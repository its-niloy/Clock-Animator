# UI and guide design

## The problem being addressed

The user reported feeling confused and overwhelmed when opening the panel. The
earlier interface hid features inside expandable groups, but still presented
several competing sections, unclear animation states, and extra Apply steps.

This revision organizes the interface around the artist's next task. It keeps
all the animation and mechanism features while reducing the choices shown in
the everyday view. This is a native Blender sidebar, so it uses Blender's own
fonts, colors, keyboard interaction, object pickers, numeric fields and Undo.

## Research and skill guidance

- [NN/G: Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)
  supports deferring less frequent features until requested. The main animation
  view now has three page choices; optional tools appear one at a time under More.
- [NN/G: Recognition and Recall](https://www.nngroup.com/articles/recognition-and-recall/)
  supports visible cues rather than requiring users to remember commands. Setup
  names its current step, exposes preview before Create, and explains where to pick objects.
- [NN/G: Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)
  informs readable status, user control, consistent labels, and error recovery.
  Back is available during setup, preview is optional, and existing clocks open
  without forcing users through onboarding again.
- UI/UX Pro Max's desktop-onboarding search returned relevant guidance about
  allowing Back and avoiding forced tutorials. Its navigation/progressive-disclosure
  searches mostly returned web-specific typography or navigation rules, including
  on the narrower retry. Those are not treated as verified Blender recommendations.
  Native controls and the primary NN/G guidance above are the explicit fallback.
- The skill's app checklist is used for visible labels, feedback and consistent
  controls. Mobile safe areas, touch sizes and Dynamic Type do not apply to this
  desktop host. Custom theme contrast and screen-reader certification remain unverified.

These sources inform design choices. They do not establish that this particular
add-on is now easy for every novice, or support a numerical claim about reduced
cognitive load. The user's original feedback remains the motivation for the change.

## Interaction structure

```text
No active clock
  1. Choose hands
       pickers, optional name matching, Next
  2. Check rotation
       automatic/manual axle, direction, preview, Back, Create

Active clock
  Animate
       live time and the selected animation task
       Run the clock / Move between two times / Gradually change speed
  Setup
       hand reassignment, alignment, pivot helpers, Update
  More
       Crown / Date / Gears / Stopwatch / Export / Manage clocks
       exactly one selected tool
```

## Decisions and their purpose

| Before | Now | Purpose |
| --- | --- | --- |
| All setup choices shown together | Two short steps, with Back and an optional preview | Make the next action explicit |
| Several expandable feature sections | Animate / Setup / More, with one extra tool selected | Prevent optional sections accumulating in the common view |
| Playback/Build labels | Run the clock, Create Time Animation, Play Animation | Distinguish authoring a time curve from playing Blender's timeline |
| Speed editable during a custom time curve | Explain the saved animation and offer Use a Running Clock | Hide an ineffective control until its mode is active |
| Generic starting time | Time at frame followed by the actual anchor frame | Explain why a later playhead can show a different current time |
| Movement dropdown plus Apply | A native preset menu that applies its choice immediately | Remove an easy-to-miss second action |
| Controller picker always visible | Main picker only when multiple rigs exist | Keep a rig implementation detail out of the first everyday view |
| Preview could remain after setup | Clear generated preview on Create and Back | Avoid mistaking wireframe copies for broken hands |
| Old open sections could follow a new clock | Reset task, step and disclosure state on New Clock | Make the next setup predictable |
| Long object labels clipped | Short hand labels; gear labels above their fields | Keep input/output meanings readable at native sidebar width |
| Pivot action could reject a connected rig after clicking | Disable it and explain the need to remove the rig first | Prevent an avoidable error |
| Export result required Outliner navigation | Select Export Objects, then a short File > Export instruction | Make the next practical step available |
| Generic needs-update status | Specific status and Review Setup | Give a recovery path near the problem |

Existing operator IDs, mechanism behavior, saved time curves and native-driver
evaluation are preserved. No runtime dependency, frame handler, custom rendering
layer, automatic tour or user-data migration service was added.

## README information design

The guide starts with a real three-panel overview and a short reader-path table.
It gives new users one quick-start route before listing the whole feature set.

Each feature chapter follows the same pattern: **location → purpose → steps →
worked example → expected result → limits that affect the task**. Familiar labels
match the shipped UI. The clock-time hold is distinguished from stopping the
timeline, and crown turn buttons explain the need for keys at different frames.

Worked recipes cover ticking, sweeping, time-lapse, midnight changes, crown-only
adjustments and export. A symptom/action troubleshooting table follows them.
Implementation formulas and detailed limits sit at the end, with the long
reference sections inside expandable details blocks.

The seven local image assets use real native Blender 5.2 sidebar captures,
cropped without changing the control content. Caption color and spacing organize
the guide figures; these graphics do not redesign Blender's actual theme.
No remote badge, font, screenshot or image service is required to read the guide.

## Verification

- Three task-flow integration groups check the first-use surface, duplicate
  assignments, Back, preview cleanup, pose restoration, immediate movement presets,
  custom-time control visibility, optional-tool isolation, export selection and
  new-clock reset.
- Twenty native GUI states are captured per Blender version: empty and assigned
  first step, check, preview, everyday, playing, shot, saved animation, ramp,
  advanced timing, crown, empty/connected date, gears, stopwatch, empty/ready
  export, clocks, setup and damaged-controller recovery.
- Create and movement-preset Undo/Redo, plus native timeline Play/Stop, are
  executed in real windows.
- The harness selects the actual Clock category after the sidebar is initialized.
  Blender can temporarily mark category selection read-only during startup;
  the harness waits rather than treating that initialization state as a product error.
- Default-width first-use and feature captures are inspected for clipped labels
  and missing primary actions. A separate Blender 5.2 run uses 125% UI scaling.
- The existing rig, feature, audit, fresh-file, exporter and installer checks are
  retained to catch accidental behavior changes.

Captures and raw logs are under `tests/output/`. Guide images are in `docs/images/`.
Human novice-user sessions, every DPI/theme combination, Blender's own accessibility
behavior and other operating systems were not evaluated.

The README's 55 heading anchors, 30 links, seven figures, tables and expandable
details passed parser/file checks, and an HTML preview was generated. Full browser
visual review remained unavailable after in-app-browser initialization failed and
the isolated Edge renderer crashed. Guide figures were inspected directly; no
browser-specific layout certification is claimed.
