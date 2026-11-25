# Static Source lighting references (P1832)

`client/cl_lightingorigin.qc` supports a bounded static subset of Source prop
lighting references without moving or duplicating the prop. `vbsp_lightingorigin`
defaults to `1`; set it to `0` to retain the previous drawing path.

## Contract, not a renderer-parity claim

Valve's released [`C_InfoLightingRelative::GetLightingOffset`](https://github.com/ValveSoftware/source-sdk-2013/blob/0d8dceea4310fde5706b3ce1c70609d72a38efdf/mp/src/game/client/c_baseanimating.cpp)
constructs `H_world * inverse(L_world)`, including rotation, and returns identity
without a valid landmark. Its draw hook passes lighting inputs separately from
the ordinary model pose. The closed renderer's final input sample centre,
absolute/relative precedence and dynamic-light policy are not established by
that released client code. In particular, do not attribute a
`ComputeLightingOrigin(vecModelLightingCenter)` interface or studio illumination
attachment/bone/scale policy to SDK2013 on this evidence.

Here the relative matrix transforms **this engine's existing `origin + 24Z`
world-light sample**, not the rendered origin. An absolute reference provides
its static world position. Neither path changes physical pose, ordinary baked
lookup or dynamic-light attenuation. This explicit local policy is not proof of
exact Source sampling/appearance parity. No guessed illumination-centre or
brightness adjustment is made to force an attractive screenshot.

Names and matrices resolve once at map load. A per-model delta listener binds a
unique authored model/origin on first sight, then uses that binding without
per-frame name scans. It composes with the existing exact-tint path and retains
ordinary rendering if the optional native call fails. Accepted custom drawing
suppresses precisely one ordinary submission. Hidden entities stay hidden.

## Conservative scope

Supported consumers/references are static, unparented and unanimated; consumers
must have body zero. Authored incoming I/O makes the affected consumer/reference
unsafe even if its initial body is zero. Brush models, ambiguous model/origin
matches, unsafe frames and simultaneous absolute plus relative assignments
retain the prior path. An unavailable relative helper does not invent an
assignment; an existing helper without a landmark supplies identity. Missing
references keep ordinary drawing. Runtime parenting, animation/body changes and
lighting-reference reassignment are not implemented by this static adapter.

The optional native APIs return floats (accepted submission or refusal):

```qc
float(entity e, vector point) addentity_lightingorigin = #0;
float(entity e, vector translation, vector axisX, vector axisY, vector axisZ)
    addentity_lightingoffset = #0;
```

The adapter checks availability before calling. An old engine warns once and
keeps ordinary drawing. A new engine carries a separate pending point to normal
late model lighting; it does not sample prematurely during submission. Internal
render-entity layout changed, so rebuild the complete native engine and matching
plugins, not just one object or the HL2 plugin. Wire and fixed standard QC-edict
layouts are unchanged. Unlit materials are not made vertex-lit by these APIs.

## Diagnostics and acted controls

Run `lightingorigin_info` at a fixed view containing an eligible prop, or execute
`cfg/test/p1832-lightingorigin.cfg`. The command prints:

- authored, resolved, missing and unsupported metadata counts;
- actual bindings/attempts and native API availability;
- cumulative **accepted submissions**, not GPU draw-call counts, and refusals;
- each resolved frame/matrix plus useful model/bounds diagnostics.

A nonzero resolved count with **zero bindings/submissions is vacuous**. First
show a positive visible consumer; then compare off/on, hiding and re-enabling,
`r_drawentities 0/1`, video restart and cold map reload. On an old engine require
positive bindings but zero custom submissions, exactly one missing-API warning,
and the ordinary reference appearance. Do not mislabel an outside-PVS camera or
a warned diagnostic build as a passed positive control.

For the audited map, actual controls found five authored consumers, two supported
relative consumers and three missing references. Both bound and actively
submitted on the new engine, with zero refusals; off submitted none. A private
derived incoming-bodygroup fixture declined that consumer and actively drew the
other (one supported, one unsafe). Original map bytes were preserved. The same
compiled QC on the old engine bound both and used ordinary fallback. Fixed-view
photos and hide/enable/entity-hiding/restart/reload controls were inspected.
These are functional tests, not a whole-map FPS claim or a cross-Source fidelity
comparison.

## Regression tests

```sh
python3 -B tools/test_lightingorigin.py
python3 -B tools/test_lightingorigin.py --bsp /your/local/map.bsp
```

Nine tests cover full rigid matrices, wrong-order/identity controls, wiring and
eligibility including incoming bodygroup I/O. The scalar eligibility oracle is
a **Python translation**, not QC execution; actual native/QC controls above are
separate evidence. `tools/test_model_lighting_point.py` in the engine
checkout compiles production-body O0/O2 tests and rejects eager-lighting,
physical-origin-cache-key and lost-pending-point mutations. Builds/actors must
follow the workspace game lock and quiet-timing coordination rules.
