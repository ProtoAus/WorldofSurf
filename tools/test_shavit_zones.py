#!/usr/bin/env python3
"""Bounded exporter tests. Require a fresh owned --test-root; no default /tmp."""
import argparse
import copy
import json
from pathlib import Path
import unittest

import shavit_zones as sz

ROOT = None


def region(points=None, **extra):
    return dict(points=points or [[0, 0], [128, 0], [128, 128], [0, 128]],
                bottom=0, height=128, **extra)


def group(*regions):
    return {"regions": list(regions) or [region()]}


def track(*segments):
    return {"zones": {"segments": list(segments) or [{"checkpoints": [group()]}], "end": group()}}


def native(main=None, bonuses=None):
    return {"formatVersion": 1, "tracks": {"main": main or track(), "bonuses": bonuses or []}}


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT/self._testMethodName
        self.root.mkdir()

    def source(self, obj=None, name="surf_fixture", folder="source"):
        path = self.root/folder
        path.mkdir(exist_ok=True)
        (path/(name+".json")).write_text(json.dumps(obj or native())+"\n")
        return path

    def test_box_and_review_warning(self):
        zones, warnings = sz.candidates(native())
        self.assertEqual([z["type"] for z in zones], ["start", "end"])
        self.assertEqual(zones[0], dict(id=1, type="start", track=0, point_a=[0., 0., 0.], point_b=[128., 128., 128.]))
        self.assertIn("not calibrated", warnings[0])

    def test_clockwise_and_collinear_rectangle(self):
        points = [[0, 0], [0, 128], [64, 128], [128, 128], [128, 0]]
        a, b, approximate = sz.box(region(points), "test", False)
        self.assertEqual((a, b, approximate), ([0., 0., 0.], [128., 128., 128.], False))

    def test_staged_main(self):
        main = track(*[{"checkpoints": [group()]} for _ in range(3)])
        zones, _ = sz.candidates(native(main))
        self.assertEqual([z["type"] for z in zones], ["start", "stage", "stage", "end"])
        self.assertEqual([z.get("data") for z in zones], [None, 2, 3, None])

    def test_linear_checkpoints_and_multiple_regions(self):
        main = track({"checkpoints": [group(), group(region(), region()), group()]})
        zones, _ = sz.candidates(native(main))
        self.assertEqual([z.get("data") for z in zones], [None, 1, 1, 2, None])
        self.assertEqual([z["id"] for z in zones], list(range(1, 6)))

    def test_bonus_start_end(self):
        zones, _ = sz.candidates(native(bonuses=[track(), track()]))
        self.assertEqual([z["track"] for z in zones], [0, 0, 1, 1, 2, 2])

    def test_mixed_stage_checkpoint_rejected(self):
        main = track({"checkpoints": [group(), group()]}, {"checkpoints": [group()]})
        with self.assertRaisesRegex(sz.Unsupported, "mixed"):
            sz.candidates(native(main))

    def test_staged_and_checkpoint_bonuses_rejected(self):
        for bonus in (track({"checkpoints": [group()]}, {"checkpoints": [group()]}),
                      track({"checkpoints": [group(), group()]})):
            with self.subTest(bonus=bonus), self.assertRaises(sz.Unsupported):
                sz.candidates(native(bonuses=[bonus]))

    def test_target_caps(self):
        with self.assertRaisesRegex(sz.Unsupported, "12 bonus"):
            sz.candidates(native(bonuses=[track() for _ in range(13)]))
        with self.assertRaisesRegex(sz.Unsupported, "zone cap"):
            sz.candidates(native(track({"checkpoints": [group(*[region() for _ in range(128)])]})))
        with self.assertRaisesRegex(sz.Unsupported, "index limit"):
            sz.candidates(native(track(*[{"checkpoints": [group()]} for _ in range(64)])))

    def test_polygon_not_silently_boxed(self):
        diamond = region([[0, 64], [64, 0], [128, 64], [64, 128]])
        obj = native(track({"checkpoints": [group(diamond)]}))
        before = copy.deepcopy(obj)
        with self.assertRaisesRegex(sz.Unsupported, "not replaced"):
            sz.candidates(obj)
        zones, warnings = sz.candidates(obj, approximate=True)
        self.assertEqual(zones[0]["point_a"], [0., 0., 0.])
        self.assertTrue(any("APPROXIMATION" in w for w in warnings))
        self.assertEqual(obj, before)

    def test_tiny_slanted_edges_require_explicit_approximation(self):
        for x, y, scale in ((0, 0, 1), (10000, -20000, 1), (-1000, 5000, 10)):
            points = [[x, y], [x+128*scale, y+0.00005*scale],
                      [x+128*scale, y+128*scale], [x, y+128*scale]]
            r = region(points)
            with self.subTest(position=(x, y, scale)):
                with self.assertRaisesRegex(sz.Unsupported, "not replaced"):
                    sz.box(r, "tiny slant", False)
                self.assertTrue(sz.box(r, "tiny slant", True)[2])

    def test_unknown_track_route_is_blocked(self):
        obj = native(); obj["tracks"]["otherTrack"] = track()
        with self.assertRaisesRegex(sz.Unsupported, "additional entries"):
            sz.candidates(obj)

    def test_unknown_zone_and_group_fields_are_reported(self):
        obj = native()
        z = obj["tracks"]["main"]["zones"]
        z["customRule"] = True
        z["segments"][0]["checkpoints"][0]["customCheckpointRule"] = 2
        z["end"]["customEndRule"] = 3
        _, warnings = sz.candidates(obj)
        for key in ("customRule", "customCheckpointRule", "customEndRule"):
            self.assertTrue(any(key in w and "tracks.main.zones" in w for w in warnings), key)

    def test_target_boundaries_are_accepted_then_refused(self):
        # 127 start regions plus one end = exactly 128 physical zones.
        self.assertEqual(len(sz.candidates(native(track({"checkpoints": [group(*[region() for _ in range(127)])]})))[0]), 128)
        staged = track(*[{"checkpoints": [group()]} for _ in range(63)])
        self.assertEqual(sz.candidates(native(staged))[0][-2]["data"], 63)
        linear = track({"checkpoints": [group() for _ in range(64)]})
        self.assertEqual(sz.candidates(native(linear))[0][-2]["data"], 63)
        linear["zones"]["segments"][0]["checkpoints"].append(group())
        with self.assertRaisesRegex(sz.Unsupported, "index limit"):
            sz.candidates(native(linear))

    def test_huge_integer_blocks_one_map_not_the_batch(self):
        for sign in (-1, 1):
            huge = sign*10**400
            for field in ("coordinate", "height", "yaw"):
                r = region()
                if field == "coordinate": r["points"][0][0] = huge
                elif field == "height": r["height"] = huge
                else: r["teleDestYaw"] = huge
                with self.subTest(sign=sign, field=field), self.assertRaises(sz.Unsupported):
                    sz.candidates(native(track({"checkpoints": [group(r)]})))
        bad = native(); bad["tracks"]["main"]["zones"]["segments"][0]["checkpoints"][0]["regions"][0]["bottom"] = 10**400
        source = self.source(bad, name="bhop_bad")
        self.source(native(), name="surf_good")
        report = sz.export([source], self.root/"out")
        self.assertEqual(report["counts"]["blocked-no-partial-map"], 1)
        self.assertEqual(report["counts"]["review-candidate"], 1)
        self.assertTrue((self.root/"out/report.json").exists())

    def test_invalid_geometry_even_when_approximation_allowed(self):
        for points in ([[0, 0], [128, 128], [0, 128], [128, 0]],
                       [[0, 0], [128, 0], [64, 64], [128, 128], [0, 128]],
                       [[0, 100], [59, -81], [-95, 31], [95, 31], [-59, -81]]):
            with self.subTest(points=points), self.assertRaises(sz.Unsupported):
                sz.box(region(points), "bad", True)

    def test_numeric_validation(self):
        for value in (True, float("inf"), float("nan"), "10", 1_000_001):
            with self.subTest(value=value), self.assertRaises(sz.Unsupported):
                sz.number(value, "x")
        for h in (0, -1, 62, 72):
            r = region(); r["height"] = h
            with self.subTest(height=h), self.assertRaises(sz.Unsupported):
                sz.box(r, "height", False)

    def test_geometry_candidates_accept_rings_without_weakening_old_modes(self):
        rings = (
            [[0, 0], [128, 0], [64, 64], [128, 128], [0, 128]],  # concave
            [[0, 0], [128, 128], [0, 128], [128, 0]],  # self-crossing, zero signed area
            [[0, 0], [64, 64.0000000001], [128, 128]],  # nearly collinear
        )
        for points in rings:
            r = region(points)
            with self.subTest(points=points):
                with self.assertRaises(sz.Unsupported):
                    sz.box(r, "ring", False)
                # The old approximate mode already accepts the nearly collinear
                # convex triangle, but still refuses concave/crossed rings.
                if points != rings[-1]:
                    with self.assertRaises(sz.Unsupported):
                        sz.box(r, "ring", True)
                else:
                    self.assertTrue(sz.box(r, "ring", True)[2])
                obj = native(track({"checkpoints": [group(r)]}))
                before = copy.deepcopy(obj)
                changes = []
                zones, warnings = sz.candidates(obj, geometry_candidates=True, transformations=changes)
                self.assertEqual(zones[0]["point_a"], [0., 0., 0.])
                self.assertEqual(zones[0]["point_b"], [128., 128., 128.])
                self.assertEqual(changes[0]["added_z_above"], 0)
                self.assertTrue(any("MATERIAL TIMING DIFFERENCE" in w for w in warnings))
                self.assertEqual(obj, before)
        # Strict-compatible candidates remain byte-for-byte identical zone arrays.
        self.assertEqual(sz.candidates(native()), sz.candidates(native(), geometry_candidates=True))

    def test_geometry_candidates_pad_short_heights_and_report_exact_bounds(self):
        for bottom, height in ((0, 0.00001), (-999999, 1), (999990, 1), (0, 62), (0, 72)):
            r = region(); r.update(bottom=bottom, height=height)
            obj = native(track({"checkpoints": [group(r)]}))
            with self.subTest(bottom=bottom, height=height):
                for approximate in (False, True):
                    with self.assertRaises(sz.Unsupported):
                        sz.candidates(obj, approximate=approximate)
                changes = []
                zones, warnings = sz.candidates(obj, geometry_candidates=True, transformations=changes)
                a, b = zones[0]["point_a"], zones[0]["point_b"]
                self.assertEqual(b[2]-a[2], 73)
                self.assertGreaterEqual(bottom, a[2])
                self.assertLessEqual(bottom+height, b[2])
                self.assertLessEqual(b[2], 1_000_000)
                self.assertEqual(changes[0]["added_z_below"], bottom-a[2])
                self.assertEqual(changes[0]["added_z_above"], b[2]-(bottom+height))
                for shrink in (31, 36):
                    self.assertGreater((b[2]-shrink)-(a[2]+shrink), 0)
                self.assertTrue(any("not calibrated" in w and "native_height" in w for w in warnings))

    def test_geometry_candidates_still_block_malformed_and_zero_ranges(self):
        bad = []
        for height in (0, -1, float("inf"), float("nan")):
            r = region(); r["height"] = height; bad.append(r)
        bad.extend([region([[0, 0], [0, 10], [0, 20]]),
                    region([[0, 0], [10, 0], [20, 0]]),
                    region([[0, 0], [10, 1]]),
                    region([[0, 0]]*65), region([[0, 0], [10, 1], [True, 2]])])
        r = region(); r.update(bottom=1_000_000, height=1); bad.append(r)
        for r in bad:
            with self.subTest(region=r), self.assertRaises(sz.Unsupported):
                sz.candidates(native(track({"checkpoints": [group(r)]})), geometry_candidates=True)

    def test_geometry_candidates_no_route_or_cap_fallback(self):
        cases = [native(track({"checkpoints": [group(), group()]}, {"checkpoints": [group()]})),
                 native(bonuses=[track({"checkpoints": [group()]}, {"checkpoints": [group()]})]),
                 native(bonuses=[track({"checkpoints": [group(), group()]})]),
                 native(track({"checkpoints": [group(*[region() for _ in range(128)])]})),
                 native(track({"checkpoints": [group() for _ in range(65)]})),
                 native(track(*[{"checkpoints": [group()]} for _ in range(64)]))]
        unknown = native(); unknown["tracks"]["other"] = track(); cases.append(unknown)
        missing = native(); del missing["tracks"]["main"]; cases.append(missing)
        missing = native(); del missing["tracks"]["main"]["zones"]["end"]; cases.append(missing)
        for i, obj in enumerate(cases):
            source = self.source(obj, name=f"surf_bad_{i}")
        report = sz.export([source], self.root/"out", geometry_candidates=True)
        self.assertEqual(report["counts"]["blocked-no-partial-map"], len(cases))
        self.assertEqual(list((self.root/"out/z").iterdir()), [])
        for row in report["maps"]:
            self.assertEqual((self.root/"out/native"/row["source_filename"]).read_bytes(),
                             (source/row["source_filename"]).read_bytes())

    def test_geometry_export_counts_preserves_existing_and_backups(self):
        r = region([[0, 0], [128, 128], [0, 128], [128, 0]])
        r["height"] = 1
        source = self.source(native(track({"checkpoints": [group(r)]})), name="surf_ring")
        self.source(name="surf_strict")
        self.source(name="surf_existing")
        existing = self.root/"existing"; existing.mkdir()
        upstream = existing/"surf_existing.json"; upstream.write_bytes(b"keep")
        report = sz.export([source], self.root/"out", existing=existing, geometry_candidates=True)
        self.assertEqual(report["candidate_counts"], {"strict": 1, "geometry-proposal": 1, "approximate-proposal": 0})
        self.assertEqual(upstream.read_bytes(), b"keep")
        self.assertFalse((self.root/"out/z/surf_existing.json").exists())
        for row in report["maps"]:
            self.assertEqual((self.root/"out/native"/row["source_filename"]).read_bytes(),
                             (source/row["source_filename"]).read_bytes())
        ring = next(row for row in report["maps"] if row["map"] == "surf_ring")
        self.assertEqual(ring["source_index"], 0)
        self.assertEqual(len(ring["transformations"]), 1)
        self.assertEqual(ring["transformations"][0]["added_z_above"], 72)

    def catalogue(self, rows):
        path = self.root/"catalogue.txt"
        path.write_text("FTESURF-MAPDL 1\n# of zoned enabled\n"+"".join(
            f"dl {name} {mode} m 1 100 2026-11-25 0 1 1 {base} 0 {enabled}\n"
            for name, mode, base, enabled in rows), encoding="ascii")
        return path

    def test_catalogue_nonprefix_modes_original_case_and_no_of_alias(self):
        source = self.source(name="Ab_Baume")
        self.source(name="agtricks")
        self.source(name="surf_regular")
        catalogue = self.catalogue([("ab_baume", "bhop", "surf_base", 0),
                                    ("agtricks", "bhop", "-", 1),
                                    ("surf_regular", "surf", "-", 1)])
        before = (source/"Ab_Baume.json").read_bytes()
        existing = self.root/"existing"; existing.mkdir()
        upstream = existing/"AGTRICKS.json"; upstream.write_bytes(b"keep")
        report = sz.export([source], self.root/"out", catalogue=catalogue, existing=existing)
        rows = {row["map"]: row for row in report["maps"]}
        self.assertEqual(set(rows), {"ab_baume", "agtricks", "surf_regular"})
        self.assertEqual(rows["ab_baume"]["mode"], "bhop")
        self.assertEqual(rows["surf_regular"]["mode"], "surf")
        self.assertEqual(rows["ab_baume"]["catalogue_of"], "surf_base")
        self.assertEqual(rows["ab_baume"]["source_filename"], "Ab_Baume.json")
        self.assertEqual(rows["ab_baume"]["catalogue_map"], "ab_baume")
        self.assertEqual(rows["ab_baume"]["source_index"], 0)
        self.assertEqual((self.root/"out/native/Ab_Baume.json").read_bytes(), before)
        self.assertEqual(rows["ab_baume"]["native_sha256"], sz.hashlib.sha256(before).hexdigest())
        self.assertTrue((self.root/"out/z/ab_baume.json").exists())
        self.assertFalse((self.root/"out/z/surf_base.json").exists())
        self.assertFalse((self.root/"out/z/agtricks.json").exists())
        self.assertEqual(upstream.read_bytes(), b"keep")
        self.assertEqual(report["input_selection"], "catalogue")
        self.assertEqual(report["catalogue_sha256"], sz.hashlib.sha256(catalogue.read_bytes()).hexdigest())
        # Without the explicit catalogue, the inherited prefix selection remains.
        default = sz.export([source], self.root/"default")
        self.assertEqual([row["map"] for row in default["maps"]], ["surf_regular"])

    def test_catalogue_unlisted_inputs_not_copied_named_or_aliased(self):
        source = self.source(name="surf_public")
        self.source(name="surf_private_draft")
        self.source(name="private.draft")
        catalogue = self.catalogue([("surf_public", "surf", "-", 1),
                                    ("public_missing", "bhop", "-", 0)])
        report = sz.export([source], self.root/"out", catalogue=catalogue, geometry_candidates=True)
        self.assertEqual(report["ignored_inputs"], {"unlisted_stem": 1, "unsafe_stem": 1})
        self.assertEqual(report["catalogue_entries_without_input"], ["public_missing"])
        for folder in ("native", "z"):
            self.assertEqual([p.name for p in (self.root/"out"/folder).iterdir()], ["surf_public.json"])
        text = (self.root/"out/report.json").read_text()
        self.assertNotIn("surf_private_draft", text)
        self.assertNotIn("private.draft", text)
        # An all-ignored input still gets a useful, non-disclosing catalogue report.
        catalogue = self.catalogue([("public_missing", "bhop", "-", 0)])
        empty = sz.export([source], self.root/"all-ignored", catalogue=catalogue)
        self.assertEqual(empty["maps"], [])
        self.assertEqual(empty["ignored_inputs"], {"unlisted_stem": 2, "unsafe_stem": 1})
        self.assertEqual(list((self.root/"all-ignored/native").iterdir()), [])

    def test_catalogue_malformed_and_colliding_rows_refused_before_output(self):
        catalogue = self.catalogue([("ab_baume", "bhop", "-", 1)])
        raw = catalogue.read_bytes()
        bad = [b"FTESURF-MAPDL1\n", raw.replace(b"MAPDL 1", b"MAPDL 2"),
               raw.replace(b"bhop", b"other"), raw.replace(b"ab_baume", b"../secret"),
               raw.replace(b"ab_baume", b"a"*101), raw.replace(b"ab_baume", b"a/b"),
               raw.replace(b"ab_baume", "nonascii_é".encode()),
               raw.replace(b" - 0 1", b" - 0"), raw.replace(b" - 0 1", b" - 0 1 extra"),
               raw+raw.splitlines()[-1]+b"\n", raw+raw.splitlines()[-1].replace(b"ab_baume", b"AB_BAUME")+b"\n"]
        source = self.source(name="ab_baume")
        for value in bad:
            with self.subTest(raw=value):
                catalogue.write_bytes(value)
                with self.assertRaises(ValueError):
                    sz.export([source], self.root/"out", catalogue=catalogue)
                self.assertFalse((self.root/"out").exists())

    def test_json_duplicate_and_nonfinite_rejected(self):
        for raw in (b'{"formatVersion":1,"formatVersion":1}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e9999}', b'\xff', b'{' ):
            with self.subTest(raw=raw), self.assertRaises(sz.Unsupported):
                sz.load_native(raw)
        with self.assertRaisesRegex(sz.Unsupported, "2 MiB"):
            sz.load_native(b' '*(sz.MAX_BYTES+1))
        with self.assertRaises(sz.Unsupported):
            sz.candidates(dict(formatVersion=True, tracks={}))

    def test_restart_name_never_becomes_trigger_filter(self):
        r = region(teleDestTargetname="stage_destination", teleDestYaw=90, safeHeight=0)
        obj = native(track({"checkpoints": [group(r)]}))
        obj.update(maxVelocity=10000, globalRegions={"cancel": [region()]})
        zones, warnings = sz.candidates(obj)
        self.assertNotIn("target", zones[0])
        self.assertNotIn("dest", zones[0])
        self.assertTrue(any("named restart" in w for w in warnings))
        self.assertTrue(any("restart yaw" in w for w in warnings))
        self.assertTrue(any("globalRegions" in w and "maxVelocity" in w for w in warnings))

    def test_explicit_stage_dest_only(self):
        r = region(teleDestPos=[1, 2, 3])
        zones, warnings = sz.candidates(native(track({"checkpoints": [group(r)]}, {"checkpoints": [group(r)]})))
        self.assertNotIn("dest", zones[0])
        self.assertEqual(zones[1]["dest"], [1., 2., 3.])
        self.assertTrue(any("not carried" in w for w in warnings))

    def test_export_preserves_native_and_is_deterministic(self):
        source = self.source()
        before = (source/"surf_fixture.json").read_bytes()
        for output in (self.root/"a", self.root/"b"):
            report = sz.export([source], output)
            self.assertEqual(report["counts"]["review-candidate"], 1)
            self.assertEqual((output/"native/surf_fixture.json").read_bytes(), before)
            self.assertTrue((output/"REVIEW-REQUIRED.txt").is_file())
        self.assertEqual((source/"surf_fixture.json").read_bytes(), before)
        self.assertEqual((self.root/"a/z/surf_fixture.json").read_bytes(), (self.root/"b/z/surf_fixture.json").read_bytes())
        self.assertEqual((self.root/"a/report.json").read_bytes(), (self.root/"b/report.json").read_bytes())

    def test_existing_upstream_casefolded_and_not_modified(self):
        source = self.source()
        existing = self.root/"existing"; existing.mkdir()
        upstream = existing/"Surf_Fixture.json"; upstream.write_bytes(b'[{"upstream":"keep"}]')
        report = sz.export([source], self.root/"out", existing=existing)
        self.assertEqual(report["counts"]["existing-upstream-untouched"], 1)
        self.assertEqual(upstream.read_bytes(), b'[{"upstream":"keep"}]')
        self.assertFalse((self.root/"out/z/surf_fixture.json").exists())

    def test_first_source_wins_and_no_suffix_alias(self):
        first = self.source(name="surf_fixture_ksf", folder="first")
        second = self.source(name="surf_fixture_ksf", folder="second")
        (second/"surf_fixture_ksf.json").write_bytes(b'invalid shadowed bytes')
        report = sz.export([first, second], self.root/"out")
        self.assertEqual(report["shadowed_inputs"], [{"map": "surf_fixture_ksf", "source_index": 1}])
        self.assertTrue((self.root/"out/z/surf_fixture_ksf.json").exists())
        self.assertFalse((self.root/"out/z/surf_fixture.json").exists())

    def test_output_refuses_overwrite_and_symlinks(self):
        source = self.source()
        out = self.root/"out"; out.mkdir(); (out/"keep").write_text("keep")
        with self.assertRaisesRegex(ValueError, "never overwritten"):
            sz.export([source], out)
        self.assertEqual((out/"keep").read_text(), "keep")
        link = self.root/"link"; link.symlink_to(out, target_is_directory=True)
        with self.assertRaises(ValueError): sz.export([source], link)
        linked_source = self.root/"linked-source"; linked_source.mkdir()
        (linked_source/"surf_fixture.json").symlink_to(source/"surf_fixture.json")
        with self.assertRaisesRegex(ValueError, "regular source"):
            sz.export([linked_source], self.root/"other")

    def test_case_collision_and_empty_inventory_refused(self):
        source = self.source()
        (source/"Surf_Fixture.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "case-colliding"):
            sz.export([source], self.root/"out")
        empty = self.root/"empty"; empty.mkdir()
        with self.assertRaisesRegex(ValueError, "nothing exported"):
            sz.export([empty], self.root/"out")
        self.assertFalse((self.root/"out").exists())

    def test_oversized_source_is_not_copied_or_partially_hashed(self):
        source = self.source()
        (source/"surf_fixture.json").write_bytes(b' '*(sz.MAX_BYTES+10))
        report = sz.export([source], self.root/"out")
        row = report["maps"][0]
        self.assertEqual(row["status"], "blocked-no-partial-map")
        self.assertIsNone(row["native_sha256"])
        self.assertFalse(row["native_copy_written"])
        self.assertFalse((self.root/"out/native/surf_fixture.json").exists())

    def test_bad_map_emits_no_partial_target_file(self):
        obj = native(); obj["tracks"]["main"]["zones"]["end"] = {"regions": []}
        source = self.source(obj)
        report = sz.export([source], self.root/"out")
        self.assertEqual(report["counts"]["blocked-no-partial-map"], 1)
        self.assertFalse((self.root/"out/z/surf_fixture.json").exists())
        self.assertEqual((self.root/"out/native/surf_fixture.json").read_bytes(), (source/"surf_fixture.json").read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-root", required=True, type=Path)
    args = parser.parse_args()
    ROOT = args.test_root.absolute()
    if ROOT.exists() or ROOT.is_symlink() or not ROOT.parent.is_dir():
        parser.error("test-root must be a fresh absent path under an existing owned directory")
    ROOT.mkdir()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExportTests))
    (ROOT/"result.json").write_text(json.dumps(dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors)))+"\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
