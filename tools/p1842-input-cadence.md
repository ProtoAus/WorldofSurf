# P1842: ordinary REC14 input cadence (structural only)

## What changes

The legacy measured sample-rate expression, 2% upper threshold and fallback
fault text are unchanged. Only an otherwise fault-free, finished **ordinary
REC14** file that would hit that upper-rate fault may replace it with a complete
input-boundary chronology witness. Typed held-metadata formats, other versions,
low-density files and existing faults do not enter this path.

`structural_input_cadence` reports pose/input/join counts. The accompanying note
explicitly says **structural chronology only; native verification still
required**. This is not NativePASS, a physics verdict, receipt, signature,
eligibility decision or badge. No API consumer receives an automatic trust upgrade.

## Supported witness

The initial subset requires a fresh equal `instart`, counted clock, `holdclock 1`
and `viewclock 1`, Source version-17 pin, complete Source seed, positive actual
mover divisor and matching float32 header/pin rate. Every active `pm` ticrate
must match that divisor, as must every supported PMS1 snapshot. Header
capabilities alone do not prove body chronology.

With `Q` denoting a QC float32 rounding:

```
Clock(mt, carry) = Q(Q(Q(mt) * Q(actualRate)) + Q(carry))
Elapsed = Q(Clock - fineOrigin)
```

The fresh fine origin is derived from the first native input horizon and seed,
not fitted to visual samples. Native exact replay seeds directly before its
post-input comparisons: the first pose must therefore restate all six fresh
seed position/velocity values at the writer's `%.2f` precision. A zero timestamp
alone is not a physical bootstrap join. Every running pose must have exactly the
native `%.4f` spelling of its consumed elapsed clock. A pose pending before an input
consumes that input's pre-move boundary; outgoing PMS1 and final `inend` can
close the last pending pose. There is at most one pose per distinct boundary.
Poses are optional, not in one-to-one correspondence with all input rows.
Positive-duration inputs with zero whole ticks still advance fine time; a real
zero-duration input may own its own truthful same-time boundary.

Every input duration is checked against its successor or outgoing/final native
horizon. Carries must be finite and within the actual divisor; counters must be
bounded exact nonnegative QC float32 integers. The native RunCmdPart bound is
`max(0.05f, actualRate + 0.00001f)` advanced by two float ULPs. There is no learned
clock tolerance or density multiplier.

A matched `savejoin -> pause -> resume/retry -> session -> seed -> input`
sequence derives saved fine elapsed from the **outgoing PMS1 endpoint**, not the
older legacy pause pre-move horizon or the rounded visual timestamp. Saved
counted ticks, snapshot rate/carry, incoming session and restored seed must agree.
The new fine origin is `Q(Clock(session) - savedFineElapsed)`; counted origin and
carried ticks remain independently checked at `clockend`.

**Cross-join ownership:** the outgoing endpoint and the first resumed pre-input
are the same logical boundary. This subset prohibits any running numeric pose
between the restored seed and first resumed input, even if the outgoing endpoint
had no pose. Rebasing does not issue a new pose owner. A subsequent real input,
including a zero-duration one, can create the next boundary normally.

P1675 `startlag` is optional untimed pre-origin metadata, not elapsed time. A
single writer-shaped row is accepted only after the fresh seed/all padding and
before running poses/inputs. Its exact nonnegative tick count and canonical
`%.4f` seconds must agree at the actual rate; its cached maximum must be finite
(a nonpositive maximum disables that separate policy). It is never added to or
subtracted from the run clock. Late/restored/duplicate/malformed rows refuse.

## Deliberate limits

Actual `hold`, `fzin`, `spec`, `ghost`, body `viewclock` or `parkclock`, nonzero
closing frozen/viewing accumulators, unknown clock context, ambiguous negative
zero padding, missing bootstrap or unsupported/old restore witnesses retain the
old rate fault. Malformed attempted witnesses refuse rather than silently
retrying a looser proof. This is **not** full view/freeze/park feature support.
Existing board, ranked, input, seed, count and closing-clock checks remain in
force. Known non-clock finish records `plat` and `pad` do not change chronology;
their existing diagnostics and display-only semantics remain unchanged. Native
replay must still independently establish world/pin/movement and retained-endpoint
equivalence against the exact bytes.

## Validation and rollout

`python3 -B tools/test_reccheck.py` runs the registered behavioral cases, including
synthetic high-frequency, optional pose, zero-tick/zero-duration, cold/chained
join, ownership, rate, seed, horizon, closing, startlag and excluded-context
controls. Synthetic chronology is not a native capture or a physics proof.
The checked revision completed **1,196 checks, zero failures**. Four immutable
ordinary recordings were separately regraded without changing input bytes; the
three previous density-only refusals became structural successes and the sparse
control remained unchanged. A genuine restored-seam duplicate with a truthful
incremented sample count refused for lack of a new pose owner. Mutating the
first pose without changing its seed refused, while truthful rounded bootstrap
values and known finish metadata passed.

A paired captured-byte comparison of **306 canonical recordings and 34 sidecars**
against the pre-change reader, using the same helper modules, introduced **zero
faults**. The existing 76 recording and 8 sidecar faults remained unchanged; they
were not repaired or hidden by this change. Independent diff review,
installed-caller integration, exact reader/module revision binding,
actual-root/platform qualification and any native/deployment gates remain
separate. No live activation, publication, build-number bump or runtime rollout
is authorized by these reader results.
