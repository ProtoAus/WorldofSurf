#!/usr/bin/env python3
"""Controlled v1 angle-cause reader tests. No native/hardware/capture claim.

Positive input must actually need its bound server operation; removing authority
or adding an unrelated rewrite must not become clean. Reuses the existing HID
fixture, encoded wire bytes, and REC reader, without a new runner or deployment
framework. All identities below are synthetic public test values.
"""
import struct
import unittest

import hidcheck
import reccheck
from test_hidcheck import Journal
from test_reccheck import build as rec_fixture

NONCE = "0" * 32
TARGET = (30.0, 80.0, 0.0)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def bits(pose):
    return " ".join(struct.pack(">f", value).hex() for value in pose)


def wire(fmt="qwabs4n", pose=(30.0, 80.0, 0.0)):
    if fmt == "qwdel2n":  # P1865: svcfte_setangledelta (85), three angle16, from TARGET minus lastcmd 0
        return hidcheck.delta_wire(TARGET, (0, 0, 0))
    if fmt == "qwabs4n":
        payload = struct.pack("<fff", *pose)
    elif fmt == "qwabs1n":
        payload = struct.pack("<bbb", 21, 56, 0)
    else:
        payload = struct.pack("<hhh", 5000, 9000, 0)
    return "0a" + payload.hex()


def target_hex(target):
    return "".join(struct.pack(">f", t).hex() for t in target)


def server(fmt, raw, opid=1, context=""):
    return hidcheck.angle_server_row(
        ("angleop 0 0 0 %s %d 7 %s %s%s" % (NONCE, opid, fmt, raw, context)).split())


def fixture(fmt="qwabs4n", disposition="direct", rewrite=0.0, with_op=True,
            serial=2, close_zero=False, wrong_input=False, no_op=False,
            start=(0.0, 0.0), absolute_post=False):
    raw = wire(fmt, pose=(0, 0, 0)) if no_op else wire(fmt)
    pre = (f32(start[0]), f32(start[1]), 0.0)
    if fmt == "qwdel2n":  # the client's own float32 add, computed here, not by the reader under test
        delta = tuple(f32(v * (360.0 / 65536)) for v in struct.unpack("<hhh", bytes.fromhex(raw[2:])))
        target = delta if absolute_post else tuple(f32(d + p) for d, p in zip(delta, pre))
    else:
        target = hidcheck.angle_wire(fmt, raw)
    j = Journal(p293=True)
    j.lines.insert(1, "anglecause 1")
    j.view(0, 0, pre[0], pre[1])
    j.lines += ["anglebaseline 0 1 " + bits(pre),
                "angleend 0 1 " + bits(pre) + " 1"]
    if with_op:
        j.lines.append("angleop 0 %s 1 7 %s %s %s %s %s %d" % (
            NONCE, fmt, raw, disposition, bits(pre), bits(target), serial))
    base = (target[0] + rewrite, target[1] + rewrite, 0.0)
    if close_zero:
        j.lines += ["anglebaseline 0 %d %s" % (serial, bits(base)),
                    "angleend 0 %d %s 0" % (serial, bits(base))]
        serial += 1
    sign = -1 if wrong_input else 1
    output = (f32(base[0] - sign * j.k * 20),
              f32(base[1] + sign * j.k * 10), 0.0)
    j.frame(1)  # an acting nonempty drain precedes its raw mouse event
    j.mouse(10, 20)
    j.view(10, 20, output[0], output[1])
    j.lines += ["anglebaseline 0 %d %s" % (serial, bits(base)),
                "angleend 0 %d %s 2" % (serial, bits(output))]
    scope = {"nonce": NONCE, "operations": {(NONCE, 1): server(fmt, raw)}}
    return j.end(), scope


def read(text, scope=None):
    return hidcheck.check_hid("_anglecause_synthetic.hid", data=text.encode(),
                              angle_authority=scope)


def rec_bytes(fmt="qwabs4n"):
    lines = rec_fixture(ver=10)
    index = lines.index("begin")
    lines[index:index] = ["nonce " + NONCE, "anglecause 1"]
    index = next(i for i, line in enumerate(lines) if line.startswith("seed ")) + 1
    row = "angleop 0 0 0 %s 1 7 %s %s" % (NONCE, fmt, wire(fmt))
    if fmt == "qwdel2n":
        row += " %s %s 76 77" % (target_hex(TARGET), struct.pack(">hhh", 0, 0, 0).hex())
        lines.insert(index + 1, "angleack 0 0 0 %s 1 78 %s" % (NONCE, struct.pack(">hhh", 0, 0, 0).hex()))
    lines.insert(index, row)
    return ("\n".join(lines) + "\n").encode(), row


class AngleCauseTests(unittest.TestCase):
    def assert_unbound(self, report):
        self.assertEqual(report.info.get("identity_unresolved"), 1, report.info)
        self.assertEqual(report.info.get("anglecause_accounted_operations"), 0)
        self.assertEqual(report.info.get("anglecause_unbound_frames"), 1)

    def test_float_word_endianness(self):
        self.assertEqual(hidcheck._angle_pose("3f800000 c0000000 00000000".split()),
                         (1.0, -2.0, 0.0))

    def test_supported_wire_and_acting_controls(self):
        for fmt in ("qwabs1n", "qwabs2n", "qwabs4n"):
            with self.subTest(fmt=fmt):
                text, scope = fixture(fmt)
                report = read(text, scope)
                self.assertFalse(report.faults, report.faults)
                self.assertEqual(report.info.get("identity_judged"), 1)
                self.assertEqual(report.info.get("identity_unresolved"), 0)
                self.assertEqual(report.info.get("anglecause_accounted_operations"), 1)
                self.assertEqual(report.info.get("anglecause_accounted_frames"), 1)
                self.assert_unbound(read(text))
                old = "\n".join(line for line in text.splitlines()
                                if not line.startswith("angle")) + "\n"
                control = read(old)
                self.assertEqual(control.info.get("identity_unresolved"), 1,
                                 "the reset must ACT, not just add harmless annotations")
                self.assertNotIn("anglecause_accounted_operations", control.info)

    def test_wrong_authority_never_licenses(self):
        text, scope = fixture()
        for changed in ({}, {"nonce": "1" * 32, "operations": scope["operations"]},
                        {"nonce": NONCE, "operations": {(NONCE, 2): server("qwabs4n", wire())}},
                        {"nonce": NONCE, "operations": {(NONCE, 1): server(
                            "qwabs4n", wire(pose=(31, 80, 0)))}}):
            with self.subTest(scope=changed):
                self.assert_unbound(read(text, changed))

    def test_non_direct_dispositions_abstain(self):
        for disposition in ("predicted", "consumed", "interleaved"):
            text, scope = fixture(disposition=disposition)
            report = read(text, scope)
            self.assertFalse(report.faults, report.faults)
            self.assert_unbound(report)

    def test_unrelated_whole_rewrite_is_not_excused(self):
        for with_op in (True, False):
            text, scope = fixture(rewrite=1.0, with_op=with_op)
            self.assert_unbound(read(text, scope))

    def test_bound_operation_is_not_a_blanket_input_exemption(self):
        text, scope = fixture(wrong_input=True)
        report = read(text, scope)
        self.assertEqual(report.info.get("anglecause_accounted_operations"), 1)
        self.assertEqual(report.info.get("anglecause_unbound_frames"), 0)
        self.assertEqual(report.info.get("identity_unresolved"), 1)

    def test_target_coincidence_without_operation_is_not_authority(self):
        text, scope = fixture(with_op=False)
        self.assert_unbound(read(text, scope))

    def test_no_v_closure_cannot_license_next_v(self):
        text, scope = fixture(close_zero=True)
        report = read(text, scope)
        self.assertFalse(report.faults, report.faults)
        self.assert_unbound(report)

    def test_interval_ids_may_have_gaps(self):
        text, scope = fixture(serial=100)
        report = read(text, scope)
        self.assertFalse(report.faults, report.faults)
        self.assertEqual(report.info.get("anglecause_accounted_operations"), 1)

    def test_malformed_annotations_withhold_totals(self):
        text, scope = fixture()
        op = next(line for line in text.splitlines() if line.startswith("angleop "))
        baseline = next(line for line in text.splitlines() if line.startswith("anglebaseline 0 2 "))
        end = next(line for line in text.splitlines() if line.startswith("angleend 0 2 "))
        for bad in (text.replace(op, op + "\n" + op),
                    text.replace(op, op.replace("angleop 0 ", "angleop 1 ")),
                    text.replace(baseline, baseline + "\n" + baseline),
                    text.replace(end, end[:-1] + "1"),
                    text.replace(baseline, baseline.replace(bits((30, 80, 0)),
                                                          "7fc00000 42a00000 00000000")),
                    text + end + "\n"):
            with self.subTest(bad=bad[-150:]):
                report = read(bad, scope)
                self.assertTrue(report.faults)
                self.assertFalse(report.info.get("anglecause_observations_complete"))
                self.assertIsNone(report.info.get("anglecause_accounted_operations"))
                self.assertIsNone(report.info.get("anglecause_unbound_frames"))

    def test_missing_baseline_or_end_is_malformed(self):
        text, scope = fixture()
        for prefix in ("anglebaseline 0 2 ", "angleend 0 2 "):
            bad = "\n".join(s for s in text.splitlines() if not s.startswith(prefix)) + "\n"
            self.assertTrue(read(bad, scope).faults)

    def test_pending_operation_cannot_silently_lose_its_recorded_input_closure(self):
        text, scope = fixture(no_op=True)
        positive = read(text, scope)
        self.assertFalse(positive.faults, positive.faults)
        self.assertEqual(positive.info.get("identity_unresolved"), 0)
        bad = "\n".join(s for s in text.splitlines()
                        if not s.startswith(("anglebaseline 0 2 ", "angleend 0 2 "))) + "\n"
        report = read(bad, scope)
        self.assertTrue(report.faults, "known pending metadata cannot silently disappear")
        self.assertIsNone(report.info.get("anglecause_operations"))

    def test_future_schema_is_unavailable_not_legacy_clean(self):
        text, scope = fixture()
        report = read(text.replace("anglecause 1", "anglecause 2"), scope)
        self.assertEqual(report.info.get("identity_blind"), "unsupported anglecause schema")
        self.assertNotIn("anglecause_accounted_operations", report.info)

    def test_server_schema_is_canonical(self):
        row = "angleop 0 0 0 %s 1 7 qwabs4n %s" % (NONCE, wire())
        self.assertEqual(server("qwabs4n", wire())["opid"], 1)
        variants = [row + " extra", row.replace(" 1 7 ", " 0 7 "),
                    row.replace(" 1 7 ", " 01 7 "),
                    row.replace(" 1 7 ", " 18446744073709551616 7 "),
                    row.replace(" 1 7 ", " 1 4294967296 "),
                    row.replace("angleop 0 ", "angleop -1 "),
                    row.replace("qwabs4n", "qwabs4b"),
                    row.replace("0a", "0b", 1),
                    row.replace(wire(), "0a0000c07f0000a04200000000")]
        for bad in variants:
            with self.subTest(bad=bad):
                self.assertRaises(ValueError, hidcheck.angle_server_row, bad.split())

    def test_duplicate_capabilities_never_select_supported_last_value(self):
        text, scope = fixture()
        data, _ = rec_bytes()
        for declarations in ("anglecause 1\nanglecause 1", "anglecause 2\nanglecause 1",
                             "anglecause 1\nanglecause 2", "anglecause  1", "anglecause\t1",
                             " anglecause 1", "anglecause 1 "):
            with self.subTest(declarations=declarations):
                h = read(text.replace("anglecause 1", declarations), scope)
                self.assertTrue(h.faults)
                self.assertIsNone(h.info.get("anglecause_accounted_operations"))
                r = reccheck.check_rec("_anglecause_synthetic.rec", data=data.replace(
                    b"anglecause 1", declarations.encode()))
                self.assertTrue(r.faults)
                self.assertFalse(getattr(r, "angle_ops", {}))

    def test_known_rec_row_preserves_canonical_physical_spelling(self):
        data, row = rec_bytes()
        for newline in (b"\n", b"\r\n"):
            positive = reccheck.check_rec("_anglecause_synthetic.rec", data=data.replace(b"\n", newline))
            self.assertFalse(positive.faults, positive.faults)
            self.assertEqual(positive.info.get("anglecause_operations"), 1)
        for changed in (row + " ", " " + row, row.replace(" ", "  ", 1),
                        row.replace(" ", "\t", 1)):
            with self.subTest(changed=changed):
                r = reccheck.check_rec("_anglecause_synthetic.rec", data=data.replace(
                    row.encode(), changed.encode()))
                self.assertTrue(r.faults)
                self.assertFalse(getattr(r, "angle_ops", {}))
                self.assertIsNone(r.info.get("anglecause_operations"))

    def test_rec_reader_declares_and_binds_active_nonce(self):
        data, row = rec_bytes()
        report = reccheck.check_rec("_anglecause_synthetic.rec", data=data)
        self.assertFalse(report.faults, report.faults)
        self.assertEqual(report.info.get("anglecause_operations"), 1)
        self.assertIn((NONCE, 1), report.angle_ops)
        for bad in (data.replace(b"anglecause 1\n", b""),
                    data.replace(row.encode(), (row + "\n" + row).encode()),
                    data.replace(row.encode(), row.replace(NONCE, "1" * 32).encode())):
            self.assertTrue(reccheck.check_rec("_anglecause_synthetic.rec", data=bad).faults)


def short(angle):
    v = int(angle * 65536 / 360.0)
    return ((v + 32768) % 65536) - 32768


class DJ:
    """The engine's order, frame by frame (cl_main.c CL_Frame). Packets are parsed first: an angle operation lands
    there and P396 turns the angle history with it. IN_Commands then writes `f <cl.movesequence>` -- the command
    being BUILT, since cl.movesequence is incremented right after each send (cl_input.c:3750) -- and only when it
    drained input (in_generic.c:1764-1779); a keyboard turn drains nothing. CL_SendCmd accumulates the view, writes
    `v` when it moved, and every `per` frames sends the command with P136's resample, the view `lag` of a frame back
    (cl_input.c:2161-2165). What the server received is kept, so its rows are the real ones: lastcmd is command
    lastseq, and the ack is the first command sent after the packet."""

    def __init__(self, start=(3.0, 40.0), per=1, lag=0.0):
        self.j = Journal(p293=True)
        self.j.lines.insert(1, "anglecause 1")
        self.pose = self.sample = (f32(start[0]), f32(start[1]), 0.0)
        self.j.view(0, 0, self.pose[0], self.pose[1])
        self.vcount, self.sent, self.cmds = 1, 0, {}
        self.per, self.lag, self.n, self.serial = per, lag, 0, 0

    def frame(self, dx=0, dy=0, kyaw=0.0, n=1, label=None):
        for _ in range(n):
            self._frame(dx, dy, kyaw, label)

    def _frame(self, dx, dy, kyaw, label=None, moved=False, jump=(0.0, 0.0)):
        if dx or dy:                       # a drained mouse event: the frame marker, then the event
            self.j.frame(self.sent + 1 if label is None else label)
            self.j.mouse(dx, dy)
        p = self.pose
        self.pose = (f32(p[0] + self.j.kp * dy + jump[0]), f32(p[1] + self.j.k * dx + kyaw + jump[1]), 0.0)
        if moved or self.pose != p:
            self.j.view(dx, dy, self.pose[0], self.pose[1], kyaw=kyaw)
            self.vcount += 1
        prev = self.sample
        self.sample = self.pose if not any(jump) else self.pose
        if any(jump):                      # a predicted snap turns the history too (pr_csqc.c, P396)
            prev = (f32(prev[0] + jump[0]), f32(prev[1] + jump[1]), 0.0)
        self.n += 1
        if self.n % self.per == 0:
            self.sent += 1
            self.cmds[self.sent] = tuple(short(a + (b - a) * (1.0 - self.lag))
                                         for a, b in zip(prev[:2], self.sample[:2])) + (0,)

    def snap(self, rot, dx=0):
        """CSQC's locally predicted snap: the view turns by rot on a frame with no operation."""
        self._frame(dx, 0, 0.0, jump=rot[:2])

    def server(self, target=TARGET, back=0, lastcmd=None, seq=77, opid=1):
        lastseq = self.sent - back
        lc = self.cmds[lastseq] if lastcmd is None else tuple(short(a) for a in lastcmd[:2]) + (0,)
        t = tuple(f32(v) for v in target)
        raw = hidcheck.delta_wire(t, lc)
        row = server("qwdel2n", raw, opid, " %s %s %d %d" % (target_hex(t), struct.pack(">hhh", *lc).hex(),
                                                              lastseq, seq))
        return row, raw

    def apply(self, row, raw, packet=77, disposition="direct", dx=0, dy=0, kyaw=0.0, applied=None, label=None):
        """The packet is parsed at the start of the next frame. -> the first command sent after it (the ack)."""
        self.serial += 1
        wired = tuple(f32(v * (360.0 / 65536)) for v in struct.unpack("<hhh", bytes.fromhex(raw[2:])))
        pre = self.pose
        post = tuple(f32(d + p) for d, p in zip(wired if applied is None else applied, pre))
        self.j.lines.append("angleop 0 %s %d 7 qwdel2n %s %s %s %s %d %d" % (
            NONCE, row["opid"], raw, disposition, bits(pre), bits(post), self.serial, packet))
        self.sample = tuple(f32(s + b - a) for s, a, b in zip(self.sample, pre, post))   # P396
        self.pose = post
        self._frame(dx, dy, kyaw, label, moved=post != pre)
        self.j.lines += ["anglebaseline 0 %d %s" % (self.serial, bits(post)),
                         "angleend 0 %d %s %d" % (self.serial, bits(self.pose), self.vcount)]
        return self.sent if self.n % self.per == 0 else self.sent + 1

    def ack(self, row, cmdseq, angles=None):
        return dict(row, ack={"cmdseq": cmdseq, "angles": angles or self.cmds[cmdseq]})

    def read(self, ops):
        return hidcheck.check_hid("_anglecause_synthetic.hid", data=self.j.end().encode(),
                                  angle_authority={"nonce": NONCE, "operations": ops})


def honest(start=(3.0, 40.0), per=1, lag=0.0, pre_frames=12, after=8, back=0, dx=0, kyaw=0.0, **apply_kw):
    """Steady play, a teleport whose lastcmd is the command `back` commands before the newest, acked right away."""
    d = DJ(start, per, lag)
    d.frame(dx=dx, kyaw=kyaw, n=pre_frames)
    row, raw = d.server(back=back)
    c = d.apply(row, raw, dx=dx, kyaw=kyaw, **apply_kw)
    d.frame(dx=dx, kyaw=kyaw, n=after)
    return d, d.ack(row, c)


class NonFiniteTests(unittest.TestCase):
    """P1869: inf in a 'v' line raised in the angle trace, so rcptcheck stored the journal as "" (not checked)."""

    def _mutated(self, text, value):
        lines = text.splitlines()
        idx = max(i for i, line in enumerate(lines) if line.startswith("v "))
        out = []
        for field in (5, 6):
            tok = lines[idx].split(" ")
            tok[field] = value
            out.append("\n".join(lines[:idx] + [" ".join(tok)] + lines[idx + 1:]) + "\n")
        return out

    def test_non_finite_view_faults_and_never_raises(self):
        text, scope = fixture()
        d, op = honest()
        for value in ("inf", "-inf", "nan"):
            for bad in self._mutated(text, value):
                report = read(bad, scope)
                self.assertTrue(any("non-finite view observation" in f for f in report.faults), report.faults)
            for bad in self._mutated(d.j.end(), value):
                report = hidcheck.check_hid("_anglecause_synthetic.hid", data=bad.encode(),
                                            angle_authority={"nonce": NONCE, "operations": {(NONCE, 1): op}})
                self.assertTrue(any("non-finite view observation" in f for f in report.faults), report.faults)


class OutOfRangeTests(unittest.TestCase):
    """P1869 review 1: a huge finite yaw widened the identity tolerance (|yaw| x 2^-22) until no-count turns passed;
    a pitch past the clamp gate turned accusations into unresolved frames; a huge angle overflowed _short_span."""

    def test_out_of_range_view_is_unusable_not_clean_and_not_a_fault(self):
        text, scope = fixture()
        lines = text.splitlines()
        idx = max(i for i, line in enumerate(lines) if line.startswith("v "))
        for field, value, bad in ((6, "720.500000", True), (6, "-1e8", True), (5, "95.000000", True),
                                  (5, "-90.500000", True), (6, "359.999786", False), (5, "89.000000", False)):
            tok = lines[idx].split(" ")
            tok[field] = value
            report = read("\n".join(lines[:idx] + [" ".join(tok)] + lines[idx + 1:]) + "\n", scope)
            self.assertEqual(any("view angle out of range" in n for n in report.notes), bad, (value, report.notes))
            self.assertFalse(any("out of range" in f for f in report.faults), report.faults)
            if bad:
                self.assertEqual(report.info.get("identity_blind"), "unusable view observation", report.info)

    def test_short_span_never_raises(self):
        self.assertFalse(hidcheck._short_span([1e305, 2e305], 0))
        self.assertFalse(hidcheck._short_span([float("inf")], 0))
        self.assertTrue(hidcheck._short_span([10.0], int(10.0 * 65536 / 360.0)))


class DeltaAngleCauseTests(unittest.TestCase):
    """P1865: most server angle sets reach FTE clients as svcfte_setangledelta. Round 3: a delta is never accounted
    on the client's own `f` labels; a server-matched one is HELD (unresolved) and its labels only say "framed"."""
    assert_unbound = AngleCauseTests.assert_unbound

    def assert_held(self, report, framed):
        self.assertFalse(report.faults, report.faults)
        self.assertEqual(report.info.get("anglecause_accounted_operations"), 0, report.info)
        self.assertEqual(report.info.get("identity_unresolved"), 1, report.info)
        self.assertEqual(report.info.get("anglecause_delta_held_frames"), 1, report.info)
        self.assertEqual(report.info.get("anglecause_delta_framed_frames"), framed, report.info)

    def test_honest_turning_players_are_framed_in_the_real_order(self):
        # f labelled with the LAST SENT command, commands every `per` frames, P136 resampled `lag` of a frame back
        for per, lag, dx, start in ((1, 0.0, -15, (3.0, 40.0)), (2, 0.5, -15, (3.0, 40.0)), (1, 0.2, 1, (3.0, 40.0)),
                                    (3, 0.9, 25, (-7.75, 171.0)), (2, 0.3, 40, (3.0, 179.9)), (1, 0.7, -60, (3.0, 40.0))):
            with self.subTest(per=per, lag=lag, dx=dx):
                d, row = honest(start=start, per=per, lag=lag, dx=dx)
                self.assert_held(d.read({(NONCE, 1): row}), framed=1)

    def test_honest_high_ping_is_framed_however_far_back_lastcmd_is(self):
        for back in (20, 60, 150):
            with self.subTest(back=back):
                d, row = honest(per=2, lag=0.5, pre_frames=2 * back + 20, back=back, dx=-15)
                self.assert_held(d.read({(NONCE, 1): row}), framed=1)

    def test_sparse_labels_are_unknown_never_agreement(self):
        # a still player or a keyboard turner drains no input, so writes no `f`: held, not framed, no fault
        for kyaw in (0.0, 0.4):
            with self.subTest(kyaw=kyaw):
                d, row = honest(per=2, lag=0.5, kyaw=kyaw)
                self.assertFalse(any(line.startswith("f ") for line in d.j.lines))
                self.assert_held(d.read({(NONCE, 1): row}), framed=0)

    def test_no_ack_or_no_custody(self):
        d, row = honest(dx=-15)
        bare = {k: v for k, v in row.items() if k != "ack"}
        self.assert_held(d.read({(NONCE, 1): bare}), framed=0)
        report = d.read({})
        self.assert_unbound(report)
        self.assertEqual(report.info.get("anglecause_delta_held_frames"), 0)

    def test_steered_lastcmd_is_not_framed(self):
        # R1/R2: the command the server subtracted is not what the journal's frames could have sent
        for swing, off in ((0, 50.0), (91, 50.0), (9, 5.0)):
            with self.subTest(swing=swing, off=off):
                d = DJ()
                d.frame(dx=-3, n=50)
                if swing:
                    d.frame(dx=-swing, n=100 if swing > 9 else 10)
                    d.frame(dx=swing, n=100 if swing > 9 else 10)
                d.cmds[d.sent] = (short(d.pose[0]), short(d.pose[1] - off), 0)
                row, raw = d.server()
                c = d.apply(row, raw, dx=-3)
                d.frame(dx=-3, n=4)
                self.assert_held(d.read({(NONCE, 1): d.ack(row, c)}), framed=0)

    def test_mirror_image_lastcmd_is_not_framed(self):
        d = DJ((3.0, 40.0))
        d.frame(dx=-30, n=20)
        d.frame(dx=30, n=20)                          # back where it started
        d.cmds[d.sent] = (short(d.pose[0]), short(2 * 40.0 - d.pose[1] + 16.5), 0)
        row, raw = d.server()
        c = d.apply(row, raw, dx=5)
        d.frame(dx=5, n=4)
        self.assert_held(d.read({(NONCE, 1): d.ack(row, c)}), framed=0)

    def test_banked_delta_is_not_framed(self):
        # R3: the packet arrives and is acked by a command built from the unturned view; applied later or never
        for turning, delay in ((True, 100), (False, 2000), (True, 0)):
            with self.subTest(turning=turning, delay=delay):
                d = DJ()
                d.frame(dx=-3, n=8)
                row, raw = d.server()
                d.frame(dx=5 if turning else 0, n=1)      # the packet's frame: hidden, its command acks it
                c = d.sent
                unturned = d.cmds[c]
                if delay:
                    d.frame(dx=5 if turning else 0, n=delay)
                    d.frame(dx=-3, n=2)
                d.apply(row, raw, dx=-3)
                d.frame(dx=-3, n=4)
                self.assert_held(d.read({(NONCE, 1): d.ack(row, c, unturned)}), framed=0)

    def test_relabelled_frames_can_agree_and_still_account_nothing(self):
        # R6: a lie the journal's view passed through earlier, and `f` labels rewritten to put command lastseq
        # there. The labels then agree -- which is exactly why they cannot license: held, unresolved, 0 accounted.
        d = DJ((3.0, 40.0))
        d.frame(dx=-3, n=20)
        d.frame(dx=300, n=10)                            # a swing out ...
        lie = d.pose
        d.frame(dx=-300, n=10)                           # ... and back
        d.frame(dx=-3, n=10)
        s = d.sent
        d.cmds[s] = (short(lie[0]), short(lie[1]), 0)
        row, raw = d.server()
        c = d.apply(row, raw, dx=-3)
        d.frame(dx=-3, n=4)
        text = d.j.end().split("\n")
        fs = [i for i, l in enumerate(text) if l.startswith("f ")]
        for k, i in enumerate(fs):                       # frames 0..29: built up to `lie`; 30..49: "after" s
            w = text[i].split()
            w[3] = str(s - 2 if k < 29 else s - 1 if k == 29 else s if k < 50 else int(w[3]))
            text[i] = " ".join(w)
        report = hidcheck.check_hid("_anglecause_synthetic.hid", data="\n".join(text).encode(),
                                    angle_authority={"nonce": NONCE, "operations": {(NONCE, 1): d.ack(row, c)}})
        self.assertFalse(report.faults, report.faults)
        self.assertEqual(report.info.get("anglecause_delta_framed_frames"), 1, report.info)
        self.assertEqual(report.info.get("anglecause_accounted_operations"), 0)
        self.assertEqual(report.info.get("identity_unresolved"), 1)

    def test_packet_word_or_later_reliable_packet_is_not_custody(self):
        for packet in (78, 76):
            with self.subTest(packet=packet):
                d, row = honest(dx=-15, packet=packet)
                report = d.read({(NONCE, 1): row})
                self.assertFalse(report.faults, report.faults)
                self.assert_unbound(report)
                self.assertEqual(report.info.get("anglecause_delta_held_frames"), 0)

    def predicted(self, snap=None, applied=(0.0, 0.0, 0.0), ops=True, gap_op=False):
        d = DJ()
        d.frame(dx=-3, n=12)
        row, raw = d.server(seq=99, opid=2)
        wired = hidcheck.angle_delta("qwdel2n", raw)
        if gap_op:
            prow, praw = d.server(target=(3.0, 10.0, 0.0), seq=98, opid=1)
        if snap is not None:
            d.snap(tuple(w + e for w, e in zip(wired, snap)))
        d.frame(dx=-3, n=3)
        if gap_op:
            d.apply(prow, praw, packet=98, dx=-3)
            d.frame(dx=-3, n=2)
        c = d.apply(row, raw, packet=99, disposition="predicted", dx=-3, applied=applied)
        d.frame(dx=-3, n=4)
        scope = {}
        if ops:
            scope[(NONCE, 2)] = d.ack(row, c)
            if gap_op:
                scope[(NONCE, 1)] = prow
        return d.read(scope)

    def test_predicted_needs_near_zero_correction_and_an_earlier_snap(self):
        report = self.predicted(snap=(0.0, 0.0))
        self.assertFalse(report.faults, report.faults)
        self.assertEqual(report.info.get("anglecause_predicted_frames"), 1, report.info)
        self.assertEqual(self.predicted(snap=(0.1, -0.2), applied=(0.0, 0.02, 0.0)).info.get(
            "anglecause_predicted_frames"), 1)
        for label, kw in (("no custody", dict(snap=(0.0, 0.0), ops=False)),
                          ("no snap", dict()),
                          ("snap of another size", dict(snap=(0.0, 3.0))),
                          ("the whole delta still applied", dict(snap=(0.0, 0.0), applied=None)),
                          ("a correction of a degree", dict(snap=(0.0, 0.0), applied=(0.0, 1.0, 0.0))),
                          ("the snap is before another operation", dict(snap=(0.0, 0.0), gap_op=True))):
            with self.subTest(label):
                self.assertEqual(self.predicted(**kw).info.get("anglecause_predicted_frames"), 0)

    def test_unapplied_counter_needs_a_server_matched_operation(self):
        for disposition in ("consumed", "interleaved"):
            with self.subTest(disposition=disposition):
                d, row = honest(dx=-15, disposition=disposition)
                report = d.read({(NONCE, 1): row})
                self.assert_unbound(report)
                self.assertEqual(report.info.get("anglecause_unapplied_frames"), 1)
                self.assertEqual(d.read({}).info.get("anglecause_unapplied_frames"), 0)

    def test_same_operation_cited_twice_is_malformed(self):
        d = DJ()
        d.frame(dx=-3, n=5)
        row, raw = d.server()
        c = d.apply(row, raw, dx=-3)
        d.frame(dx=-3, n=2)
        d.apply(row, raw, dx=-3)
        self.assertTrue(d.read({(NONCE, 1): d.ack(row, c)}).faults)

    def test_inconsistent_or_out_of_range_rows_abstain_never_crash(self):
        good = wire("qwdel2n")
        for label, ctx, raw in (
                ("wire is not target-lastcmd", " %s 000100000000 1 77" % target_hex(TARGET), good),
                ("FLT_MAX target", " 00000000%s00000000 000000000000 1 77" % struct.pack(">f", 3.4028234e38).hex(), good),
                ("out of range", " 00000000%s00000000 000000000000 1 77" % struct.pack(">f", 2.0e6).hex(), good)):
            with self.subTest(label=label):
                row = server("qwdel2n", raw, 1, ctx)
                self.assertFalse(row["consistent"])
        self.assertIsNone(hidcheck.delta_wire((0.0, 3.4028234e38, 0.0), (0, 0, 0)))
        data, row = rec_bytes("qwdel2n")
        bad = data.replace(row.encode(), row.replace(target_hex(TARGET), "00000000%s00000000" % struct.pack(">f", 3.4028234e38).hex()).encode())
        report = reccheck.check_rec("_anglecause_synthetic.rec", data=bad)
        self.assertFalse(report.faults, report.faults)
        self.assertFalse(report.angle_ops[(NONCE, 1)]["consistent"])

    def test_delta_server_schema_is_canonical(self):
        good, ctx = wire("qwdel2n"), " %s %s 76 77" % (target_hex(TARGET), "000000000000")
        self.assertEqual(server("qwdel2n", good, context=ctx)["lastseq"], 76)
        for fmt, raw, c in (("qwdel2n", good, ""), ("qwdel2n", good, " %s 000000000000 77" % target_hex(TARGET)),
                            ("qwdel2n", "0a" + good[2:], ctx), ("qwdel2n", good[:-2], ctx), ("qwdel2n", good + "00", ctx),
                            ("qwdel2n", good, ctx + " 1"), ("qwdel2n", good, " 7fc00000%s 000000000000 76 77" % target_hex(TARGET)[8:]),
                            ("qwdel2n", good, " %s 000000000000 76 077" % target_hex(TARGET)),
                            ("qwabs2n", wire("qwabs2n"), ctx), ("qwdel4n", good, ctx), ("qwabs2n", good, "")):
            with self.subTest(fmt=fmt, raw=raw, c=c):
                self.assertRaises(ValueError, server, fmt, raw, 1, c)
        for bad in ("angleack 0 0 0 %s 0 78 000000000000" % NONCE, "angleack 0 0 0 %s 1 078 000000000000" % NONCE,
                    "angleack 0 0 0 %s 1 78 00000000000" % NONCE, "angleack 0 0 0 %s 1 78 000000000000 x" % NONCE):
            with self.subTest(bad=bad):
                self.assertRaises(ValueError, hidcheck.angle_ack_row, bad.split())

    def test_row_integers_take_the_native_u32_range(self):
        # codec #5: pk/mt/row are AC_U32 in the native readers; the Python ones took 31 bits
        good = wire("qwdel2n")
        ctx = " %s 000000000000 76 77" % target_hex(TARGET)
        for value, ok in (("2147483648", True), ("4294967295", True), ("4294967296", False)):
            with self.subTest(value=value):
                op = ("angleop %s 0 0 %s 1 7 qwdel2n %s%s" % (value, NONCE, good, ctx)).split()
                ack = ("angleack 0 %s 0 %s 1 78 000000000000" % (value, NONCE)).split()
                if ok:
                    hidcheck.angle_server_row(op)
                    hidcheck.angle_ack_row(ack)
                else:
                    self.assertRaises(ValueError, hidcheck.angle_server_row, op)
                    self.assertRaises(ValueError, hidcheck.angle_ack_row, ack)

    def test_python_delta_wire_matches_the_engine(self):
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anglecause_delta_golden.txt")
        rows = [line.split() for line in open(path) if not line.startswith("#")]
        self.assertEqual(len(rows), 300)
        for t, l, w in rows:
            target = tuple(struct.unpack(">f", bytes.fromhex(t[i:i + 8]))[0] for i in (0, 8, 16))
            self.assertEqual(hidcheck.delta_wire(target, struct.unpack(">hhh", bytes.fromhex(l))), w, (t, l))

    def test_rec_reader_accepts_a_delta_row_and_its_ack(self):
        data, row = rec_bytes("qwdel2n")
        report = reccheck.check_rec("_anglecause_synthetic.rec", data=data)
        self.assertFalse(report.faults, report.faults)
        op = report.angle_ops[(NONCE, 1)]
        self.assertEqual((op["lastseq"], op["seq"], op["ack"]["cmdseq"]), (76, 77, 78))
        self.assertEqual(report.info.get("anglecause_acks_ignored"), 0)

    def test_odd_acks_license_nothing_and_never_fault(self):
        # round 3: only an ack's shape can fault; the native verifier and held ledger accept these rows too
        data, row = rec_bytes("qwdel2n")
        ack = "angleack 0 0 0 %s 1 78 000000000000" % NONCE
        text = data.decode()
        abs_data, abs_row = rec_bytes("qwabs2n")
        cases = (("duplicate", text.replace(ack, ack + "\n" + ack)),
                 ("orphan", text.replace(ack, ack.replace(" 1 78 ", " 2 78 "))),
                 ("another nonce", text.replace(ack, ack.replace(NONCE, "1" * 32))),
                 ("before its operation", text.replace(ack + "\n", "").replace(row, ack + "\n" + row)),
                 ("names an ABS operation", abs_data.decode().replace(abs_row, abs_row + "\n" + ack)))
        for label, bad in cases:
            with self.subTest(label):
                report = reccheck.check_rec("_anglecause_synthetic.rec", data=bad.encode())
                self.assertFalse(report.faults, report.faults)
                self.assertNotIn("ack", report.angle_ops.get((NONCE, 1), {}))
                self.assertGreaterEqual(report.info.get("anglecause_acks_ignored"), 1)
        lines = rec_fixture(ver=10, sessions=[(15, 3, "drop")])
        index = lines.index("begin")
        lines[index:index] = ["nonce " + NONCE, "anglecause 1"]
        seed = next(i for i, line in enumerate(lines) if line.startswith("seed "))
        lines.insert(seed + 1, row)
        pause = next(i for i, line in enumerate(lines) if line.startswith("pause "))
        lines.insert(pause + 1, ack)
        report = reccheck.check_rec("_anglecause_synthetic.rec", data=("\n".join(lines) + "\n").encode())
        self.assertFalse(report.faults, report.faults)
        self.assertNotIn("ack", report.angle_ops[(NONCE, 1)])
        self.assertEqual(report.info.get("anglecause_acks_ignored"), 1)
        for bad in (text.replace(ack, ack + " 1"), text.replace(ack, ack.replace(" 78 ", " 078 "))):
            with self.subTest(bad=bad[-60:]):
                self.assertTrue(reccheck.check_rec("_anglecause_synthetic.rec", data=bad.encode()).faults)

    def test_header_angle_rows_fault_as_in_the_native_readers(self):
        data, row = rec_bytes("qwdel2n")
        ack = "angleack 0 0 0 %s 1 78 000000000000" % NONCE
        for line in (ack, row):
            with self.subTest(line=line[:9]):
                bad = data.decode().replace("anglecause 1\n", "anglecause 1\n" + line + "\n", 1)
                report = reccheck.check_rec("_anglecause_synthetic.rec", data=bad.encode())
                self.assertTrue(any("outside body" in f for f in report.faults), report.faults)

    def test_exponent_looking_hex_is_not_a_rounded_number(self):
        # a target whose float bits read like 3e800000 (0.25 deg) must not trip the %g exponent check
        target = (0.25, 0.25, 0.0)
        raw = hidcheck.delta_wire(target, (0, 0, 0))
        data, row = rec_bytes("qwdel2n")
        new = row.replace(wire("qwdel2n"), raw).replace(target_hex(TARGET), target_hex(target))
        report = reccheck.check_rec("_anglecause_synthetic.rec", data=data.replace(row.encode(), new.encode()))
        self.assertFalse(report.faults, report.faults)

    def test_abs_lines_are_unchanged_v1(self):
        text, scope = fixture("qwabs2n")
        op = next(l for l in text.splitlines() if l.startswith("angleop "))
        self.assertEqual(len(op.split()), 15)
        self.assertRaises(ValueError, server, "qwabs2n", wire("qwabs2n"), 1, " 1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
