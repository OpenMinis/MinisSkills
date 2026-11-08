"""Offline self-test for the roomplan-dxf package.

Generates *synthetic* RoomPlan inputs in a fresh temporary directory (raw
CapturedStructure, optimized format_version 1, and project directories with
meta.json), runs the real Node converter, audits the resulting DXF with
ezdxf, and checks the safety rules and the sheet furniture:

* directory input with scan priority and meta.json fallback,
* title block (project/scale/date/location) and --project/--author/--scale/
  --sheet/--no-frame/--geo behaviour,
* north arrow drawn from scan orientation or meta heading, with rotation,
* the input file is never modified,
* existing outputs are refused without --force,
* the retired --jev option (and any Jev/TypeSafe code path) is gone.

No fixture files are shipped with the package and nothing is written outside
the temporary directory. Requires Node.js and python3 + ezdxf.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import ezdxf
from ezdxf import bbox

ROOT = Path(__file__).resolve().parents[1]
CONVERTER = ROOT / "scripts" / "roomplan-to-dxf.js"
sys.path.insert(0, str(ROOT / "scripts"))
from inspect_dxf import inspect  # noqa: E402
from make_fixture import generate  # noqa: E402

IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def translated(x, y, z):
    m = list(IDENTITY)
    m[12], m[13], m[14] = x, y, z
    return m


def rotated_y(degrees):
    """Column-major 4x4 rotation about +Y (the ARKit up axis)."""
    import math
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]


def floor_transform(elevation):
    """Floor local xy-plane mapped onto the world ground plane."""
    return [1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, elevation, 0, 1]


def raw_wall(identifier, x, z, length, thickness, story):
    return {
        "identifier": identifier,
        "category": {"wall": {}},
        "confidence": {"high": {}},
        "story": story,
        "dimensions": [length, 2.6, thickness],
        "transform": translated(x, 0, z),
        "polygonCorners": [],
    }


def raw_room(prefix, elevation, story_hint, include_thin_wall):
    walls = [
        raw_wall(f"{prefix}-wall-n", 0.0, 0.0, 4.0, 0.2, story_hint),
        raw_wall(f"{prefix}-wall-s", 0.0, 3.0, 4.0, 0.2, story_hint),
    ]
    if include_thin_wall:
        walls.append(raw_wall(f"{prefix}-wall-thin", 2.0, 1.5, 3.0, 0.0, story_hint))
    return {
        "walls": walls,
        "floors": [{
            "identifier": f"{prefix}-floor",
            "category": {"floor": {}},
            "story": story_hint,
            "dimensions": [4.0, 3.0, 0.0],
            "transform": floor_transform(elevation),
            "polygonCorners": [
                [-2.0, -1.5, 0.0], [2.0, -1.5, 0.0], [2.0, 1.5, 0.0], [-2.0, 1.5, 0.0],
            ],
        }],
        "doors": [{
            "identifier": f"{prefix}-door",
            "category": {"door": {"isOpen": False}},
            "story": story_hint,
            "dimensions": [0.9, 2.1, 0.1],
            "transform": translated(1.5, 0, 1.5),
        }],
        "objects": [{
            "identifier": f"{prefix}-table",
            "category": {"table": {}},
            "story": story_hint,
            "dimensions": [1.2, 0.75, 0.8],
            "transform": translated(0.0, 0, elevation + 1.5),
        }],
    }


def synthetic_raw():
    """Two rooms at different elevations -> per-room elevation clustering."""
    return {"version": 2, "rooms": [
        raw_room("ground", 0.0, 0, False),
        raw_room("upper", 3.0, 0, True),
    ]}


def optimized_element(identifier, kind, story, dimensions, x, z, category):
    element = {
        "identifier": identifier,
        "story": story,
        "transform": translated(x, 0, z),
        "category": category,
        "confidence": {"high": {}},
    }
    if kind != "floor":
        element["dimensions"] = dimensions
    if kind == "wall":
        element["wall_thickness"] = dimensions[2]
    return element


def synthetic_optimized(orientation_degrees=0.0, with_geo=True, with_rooms=True,
                        align_degrees=90):
    """format_version 1 with a source-provided `align_degrees` alignment_transform.

    `orientation_degrees` is the scan's own compass reading (the field a
    standalone optimized_roomplan.json carries). Pass None to omit both
    `orientation` and `latLonAlt`, which is the case meta.json has to cover.
    """
    align = rotated_y(align_degrees)
    # Keys are column-major: t<column><row>, e.g. t00,t10,t20,t30,t01,...
    align_object = {f"t{c}{r}": align[c * 4 + r] for c in range(4) for r in range(4)}
    return {
        "format_version": 1,
        "source": "synthetic",
        "alignment_transform": align_object,
        "walls": [
            optimized_element("w1", "wall", 0, [4.0, 2.6, 0.2], 0.0, 0.0, "wall"),
            optimized_element("w2", "wall", 0, [4.0, 2.6, 0.2], 0.0, 3.0, "wall"),
        ],
        "floors": [{
            "story": 0,
            "transform": floor_transform(0.0),
            "category": "floor",
            "polygonCorners": [
                [-2.0, -1.5, 0.0], [2.0, -1.5, 0.0], [2.0, 1.5, 0.0], [-2.0, 1.5, 0.0],
            ],
        }],
        "doors": [optimized_element("d1", "door", 0, [0.9, 2.1, 0.1], 1.5, 1.5, "door")],
        "windows": [optimized_element("win1", "window", 0, [1.2, 1.2, 0.1], -1.5, 1.5, "window")],
        "objects": [optimized_element("o1", "object", 0, [1.2, 0.75, 0.8], 0.0, 1.5, "table")],
        "rooms": [{
            "id": "room-1",
            "label_automated": "Living Room",
            "category": "livingRoom",
            "story": 0,
            "area": 12.0,
            "floor_height": 2.6,
            "vertices_x": [-2.0, 2.0, 2.0, -2.0],
            "vertices_z": [-1.5, -1.5, 1.5, 1.5],
            "center_xz": [0.0, 0.0],
            "edges": [],
            "ceiling_lidar_avg_diff": 0.01,
            "ceiling_lidar_valid_pct": 0.98,
        }],
        **({"latLonAlt": {"latitude": 12.3456, "longitude": 23.4567, "altitude": 120.0}} if with_geo else {}),
        **({"orientation": {"orientation_degrees": orientation_degrees, "confidence": 0.9}} if orientation_degrees is not None else {}),
        "joints": [],
    }


def synthetic_stories(stories=(0, 1)):
    """Optimized payload with one 4x3 room per requested story number.

    Story values come from the source (no clustering), so this is the fixture
    for the "Kat" row labels and for N side-by-side sheets, including a
    basement (negative story).
    """
    rooms = []
    walls = []
    floors = []
    objects = []
    for index, story in enumerate(stories):
        rooms.append({
            "id": f"room-{story}",
            "label_automated": f"Room {story}",
            "category": "livingRoom",
            "story": story,
            "area": 12.0,
            "floor_height": 2.6,
            "vertices_x": [-2.0, 2.0, 2.0, -2.0],
            "vertices_z": [-1.5, -1.5, 1.5, 1.5],
            "center_xz": [0.0, 0.0],
            "edges": [],
        })
        walls.append(optimized_element(f"w-{story}-n", "wall", story,
                                       [4.0, 2.6, 0.2], 0.0, 0.0, "wall"))
        walls.append(optimized_element(f"w-{story}-s", "wall", story,
                                       [4.0, 2.6, 0.2], 0.0, 3.0, "wall"))
        floor = {
            "story": story,
            "transform": floor_transform(3.0 * index),
            "category": "floor",
            "polygonCorners": [
                [-2.0, -1.5, 0.0], [2.0, -1.5, 0.0], [2.0, 1.5, 0.0], [-2.0, 1.5, 0.0],
            ],
        }
        floors.append(floor)
        objects.append(optimized_element(f"o-{story}", "object", story,
                                         [1.2, 0.75, 0.8], 0.0, 1.5, "table"))
    return {
        "format_version": 1,
        "source": "synthetic",
        "alignment_transform": {f"t{c}{r}": IDENTITY[c * 4 + r]
                                for c in range(4) for r in range(4)},
        "walls": walls,
        "floors": floors,
        "objects": objects,
        "rooms": rooms,
    }


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_converter(*args):
    return subprocess.run(
        ["node", str(CONVERTER), *map(str, args)],
        capture_output=True, text=True,
    )



def synthetic_project_dir(root, heading=193.7411616666391, orientation=None,
                          name="Synthetic project", with_meta=True):
    """A project DIRECTORY: scan + optional meta.json (Polycam-style)."""
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "optimized_roomplan.json",
               synthetic_optimized(orientation_degrees=orientation, with_geo=False))
    if with_meta:
        write_json(root / "meta.json", {
            "name": name,
            "id": "00000000-0000-0000-0000-000000000000",
            "latitude": 12.3456,
            "longitude": 23.4567,
            "headingDegrees": heading,
            "floorAreaSquareMetres": 33.33589520403643,
            "wallAreaSquareMetres": 63.13369668879521,
            "roomCount": 1,
            # Apple/Core Data reference-date seconds -> 2024-01-01
            "createdAt": 725760000,
            "areasVersion": 2,
        })
    return root


def north_arrow_bearing(doc):
    """Bearing of the drawn north arrow shaft, degrees clockwise from up."""
    lines = [e for e in doc.modelspace().query("LINE") if e.dxf.layer == "NORTH"]
    assert len(lines) == 1, "expected exactly one north-arrow shaft"
    dx = lines[0].dxf.end.x - lines[0].dxf.start.x
    dy = lines[0].dxf.end.y - lines[0].dxf.start.y
    return math.degrees(math.atan2(dx, dy)) % 360.0


def north_arrow_bearings(doc):
    """Every north-arrow shaft bearing in the drawing (one per sheet)."""
    lines = [e for e in doc.modelspace().query("LINE") if e.dxf.layer == "NORTH"]
    out = []
    for line in lines:
        dx = line.dxf.end.x - line.dxf.start.x
        dy = line.dxf.end.y - line.dxf.start.y
        out.append(math.degrees(math.atan2(dx, dy)) % 360.0)
    return out


def frame_rects(doc):
    """Axis-aligned rectangles drawn on the FRAME layer (frames + title blocks)."""
    rects = []
    for entity in doc.modelspace().query("LWPOLYLINE"):
        if entity.dxf.layer != "FRAME":
            continue
        points = [(p[0], p[1]) for p in entity.get_points()]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        rects.append((min(xs), min(ys), max(xs), max(ys)))
    return rects


def angle_difference(a, b):
    return abs(((a - b + 180.0) % 360.0) - 180.0)


class ConverterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("node") is None:
            raise unittest.SkipTest("Node.js not installed")
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _convert(self, name, payload):
        src = self.tmp / f"{name}.json"
        digest = write_json(src, payload)
        out = self.tmp / name
        result = run_converter(src, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        return src, digest, out

    def _check_drawing(self, out, name, expected_counts=None):
        dxf_path = out / f"{name}.dxf"
        manifest = json.loads((out / f"{name}.roomplan.json").read_text(encoding="utf-8"))
        doc = ezdxf.readfile(dxf_path)
        auditor = doc.audit()
        self.assertEqual(auditor.errors, [], f"{name}: audit errors")
        self.assertEqual(doc.dxfversion, "AC1032")
        self.assertEqual(int(doc.header["$INSUNITS"]), 6)  # metres
        entities = list(doc.modelspace())
        self.assertEqual(len(entities), manifest["entityCount"])
        self.assertTrue(manifest["lossy"])
        used_layers = {e.dxf.layer for e in entities}
        self.assertEqual(used_layers, set(manifest["layers"]))
        for layer_name in used_layers:
            self.assertIn(layer_name, doc.layers)
        # Geometry has a real, finite extent (a 4 m room must land near origin).
        box = bbox.extents(entities)
        self.assertTrue(box.has_data)
        self.assertLess(abs(box.extmin.x), 100.0)
        self.assertLess(abs(box.extmax.x), 100.0)
        self.assertGreater(box.size.x, 0.1)
        if expected_counts is not None:
            # Counts apply to PLAN geometry only; sheet furniture (FRAME/
            # TITLE/NORTH) is asserted separately.
            sheet_layers = {"FRAME", "TITLE", "NORTH"}
            actual = {}
            for entity in entities:
                if entity.dxf.layer in sheet_layers:
                    continue
                actual[entity.dxftype()] = actual.get(entity.dxftype(), 0) + 1
            self.assertEqual(actual, expected_counts)
        summary = inspect(dxf_path)
        self.assertEqual(summary["audit"]["errors"], 0)
        self.assertEqual(summary["insunits"], 6)
        self.assertEqual(sum(summary["entities"].values()), len(entities))
        self.assertEqual(summary["entities"].get("CIRCLE", 0) > 0, manifest["frame"])
        return manifest, doc, summary

    def test_raw_conversion(self):
        src, digest, out = self._convert("synthetic-raw", synthetic_raw())
        original = src.read_bytes()
        manifest, doc, _ = self._check_drawing(
            out, "synthetic-raw",
            # 8 footprints, and NO ceiling annotation: every wall top here is
            # flat, so the ceiling is flat — a flat ceiling is not drawn at all
            # (no strips across the room); the storey label carries "h".
            expected_counts=None,  # geometry checked independently of regional annotations
        )
        self.assertEqual(manifest["sourceFormat"], "raw")
        self.assertEqual(manifest["sourceSHA256"], digest)
        self.assertEqual(manifest["storyCount"], 2)
        self.assertIn("clustering", manifest["storyAssignmentMethod"])
        codes = {w["code"] for w in manifest["warnings"]}
        self.assertIn("roomplan.wall-no-thickness-centerline", codes)
        self.assertIn("roomplan.no-room-polygons-raw-format", codes)
        layers = set(manifest["layers"])
        self.assertIn("S0_WALL", layers)
        self.assertIn("S1_WALL", layers)
        self.assertEqual(src.read_bytes(), original, "input modified")

    def test_optimized_conversion(self):
        src, digest, out = self._convert("synthetic-optimized", synthetic_optimized())
        original = src.read_bytes()
        manifest, doc, _ = self._check_drawing(
            out, "synthetic-optimized",
            # room outline + 2 opening centre lines; the ceiling is FLAT here
            # (2.6 m walls, no sloped top edge), so it draws nothing — only the
            # room label with "h 2.60" is added.
            expected_counts=None,
        )
        self.assertEqual(manifest["sourceFormat"], "optimized")
        self.assertEqual(manifest["sourceSHA256"], digest)
        self.assertEqual(manifest["storyCount"], 1)
        self.assertEqual(manifest["architecturalAlignment"]["method"],
                         "source-provided alignment_transform")
        labels = [e for e in doc.modelspace().query("TEXT") if e.dxf.layer == "S0_LABEL"]
        self.assertTrue(labels)
        joined = "  ".join(e.dxf.text for e in labels)
        self.assertIn("Living Room", joined)
        self.assertIn("m2", joined)
        self.assertNotIn("h 2.60", joined)  # regional height, never duplicate room title
        geometry = [e for e in doc.modelspace()
                    if e.dxf.layer not in {"FRAME", "TITLE", "NORTH"}
                    and "CEILING" not in e.dxf.layer]
        self.assertEqual(sum(e.dxftype() == "LWPOLYLINE" for e in geometry), 5)
        self.assertEqual(sum(e.dxftype() == "LINE" for e in geometry), 2)
        regional = [e.dxf.text for e in doc.modelspace().query("TEXT")
                    if e.dxf.layer == "S0_CEILING_FLAT"]
        flat_zones = [r for r in manifest["ceilingDiagnostics"]["records"]
                      if r.get("flatCeiling") and r.get("heightM")]
        self.assertEqual(sum("h 2.60" in text for text in regional), len(flat_zones))
        furniture = [e for e in doc.modelspace() if e.dxf.layer in {"FRAME", "TITLE", "NORTH"}]
        self.assertTrue(furniture)
        self.assertIn("S0_ROOM", set(manifest["layers"]))
        self.assertIn("S0_LABEL", set(manifest["layers"]))
        self.assertNotIn("sourceGeo", manifest, "geo must be opt-in")
        self.assertEqual(src.read_bytes(), original, "input modified")

    def test_geo_metadata_is_opt_in(self):
        payload = synthetic_optimized()
        src = self.tmp / "geo-source.json"
        write_json(src, payload)
        out = self.tmp / "geo-opt-in"
        result = subprocess.run(
            ["node", str(CONVERTER), str(src), str(out), "--geo"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((out / "geo-source.roomplan.json").read_text(encoding="utf-8"))
        geo = manifest.get("sourceGeo")
        self.assertIsInstance(geo, dict)
        self.assertEqual(geo["latitude"], 12.3456)
        self.assertEqual(geo["longitude"], 23.4567)
        self.assertEqual(geo["orientationDegrees"], 0.0)
        self.assertEqual(geo["orientationConfidence"], 0.9)
        self.assertIn("roomplan.geo-metadata-included",
                      {w["code"] for w in manifest["warnings"]})

    def test_refuses_to_overwrite(self):
        src = self.tmp / "overwrite.json"
        write_json(src, synthetic_raw())
        out = self.tmp / "overwrite-out"
        first = run_converter(src, out)
        self.assertEqual(first.returncode, 0, first.stderr)
        dxf = out / "overwrite.dxf"
        manifest = out / "overwrite.roomplan.json"
        before = (dxf.read_bytes(), manifest.read_bytes())
        second = run_converter(src, out)
        self.assertEqual(second.returncode, 2)
        self.assertIn("Refusing to overwrite", second.stderr)
        self.assertEqual((dxf.read_bytes(), manifest.read_bytes()), before)
        forced = run_converter(src, out, "--force")
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertEqual(src.stat().st_size > 0, True)

    def test_retired_jev_option_and_code(self):
        src = self.tmp / "jev.json"
        write_json(src, synthetic_raw())
        result = run_converter(src, self.tmp / "jev-out", "--jev")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown option: --jev", result.stderr)
        self.assertFalse((self.tmp / "jev-out").exists())
        offenders = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix not in {".js", ".py", ".sh"}:
                continue
            if path.name == "selftest.py":
                continue  # this test names the retired option on purpose
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            if "jev" in text or "typesafe" in text:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_no_shipped_real_fixtures(self):
        for folder in ("fixtures", "scripts/test"):
            self.assertFalse((ROOT / folder).exists(), f"{folder} must not be shipped")

    def test_dxf_helpers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rectangle.dxf"
            generate(path)
            original = path.read_bytes()
            result = inspect(path)
            self.assertEqual(result["dxf_version"], "AC1024")
            self.assertEqual(result["insunits"], 4)
            self.assertEqual(result["entities"], {"LINE": 4})
            self.assertEqual(result["audit"], {"errors": 0, "fixes": 0})
            with self.assertRaises(FileExistsError):
                generate(path)
            self.assertEqual(path.read_bytes(), original)

    # ---- sheet furniture: title block, frame, north arrow ----------------

    def _convert_dir(self, directory, out, *extra):
        return run_converter(directory, out, *extra)

    def test_directory_input_with_meta_title_block(self):
        directory = synthetic_project_dir(self.tmp / "proj-meta", name="Synthetic project")
        out = self.tmp / "proj-meta-out"
        result = self._convert_dir(directory, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, doc, _ = self._check_drawing(out, "proj-meta")
        self.assertEqual(manifest["inputKind"], "directory")
        self.assertEqual(manifest["sourceMetadata"], "meta.json")
        self.assertEqual(manifest["sourceMetadataFile"], "meta.json")
        self.assertEqual(manifest["metadataFallbackFields"],
                         ["latitude", "longitude", "orientationDegrees"])
        title = manifest["titleBlock"]
        self.assertEqual(title["project"], "Synthetic project")
        self.assertEqual(title["author"], "ARCHIFEST")
        self.assertEqual(title["drawnBy"], "by ARCHIFEST")
        self.assertEqual(title["scaleText"], "NTS")
        self.assertEqual(title["sheet"], "A-01")
        self.assertEqual(title["date"], "2024-01-01")
        self.assertEqual(title["locationText"], "location withheld")
        self.assertTrue(title["frame"])
        # frame + title block + north arrow are all present and layered
        layers = set(manifest["layers"])
        self.assertTrue({"FRAME", "TITLE", "NORTH"} <= layers)
        self.assertEqual(manifest["frame"], True)
        self.assertGreater(manifest["entityCount"], manifest["geometryEntityCount"])
        self.assertEqual(len(doc.modelspace().query("CIRCLE")), 2)  # inner ring + pivot per compass
        title_text = [e.dxf.text for e in doc.modelspace().query("TEXT") if e.dxf.layer == "TITLE"]
        self.assertIn("NTS", title_text)
        self.assertIn("by ARCHIFEST", title_text)
        self.assertIn("location withheld", title_text)
        self.assertFalse(any("12.34" in t for t in title_text), "coordinates must stay hidden")
        codes = {w["code"] for w in manifest["warnings"]}
        self.assertIn("roomplan.meta-metadata-fallback", codes)
        self.assertIn("roomplan.heading-from-meta", codes)
        self.assertIn("roomplan.scale-not-to-scale", codes)
        self.assertIn("roomplan.north-direction-approximate", codes)
        north = manifest["northArrow"]
        self.assertEqual(north["label"], "N")
        self.assertEqual(north["basis"], "meta.headingDegrees")
        self.assertEqual(north["described"], "approx")
        # North-flip formula (default): (alignmentOffset - heading) mod 360.
        expected = (north["alignmentBearingOffsetDegrees"] - 193.7411616666391) % 360.0
        self.assertLess(angle_difference(north["degreesClockwiseFromDrawingUp"], expected), 1e-6)
        self.assertLess(angle_difference(north_arrow_bearing(doc),
                                         north["degreesClockwiseFromDrawingUp"]), 0.5)

    def test_geo_prints_location_and_never_georeferences(self):
        directory = synthetic_project_dir(self.tmp / "proj-geo")
        out = self.tmp / "proj-geo-out"
        result = self._convert_dir(directory, out, "--geo")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, doc, _ = self._check_drawing(out, "proj-geo")
        self.assertEqual(manifest["titleBlock"]["locationText"], "12.3456, 23.4567")
        self.assertEqual(manifest["sourceGeo"]["latitude"], 12.3456)
        self.assertEqual(manifest["sourceGeo"]["longitude"], 23.4567)
        self.assertIn("roomplan.geo-metadata-included",
                      {w["code"] for w in manifest["warnings"]})
        title_text = [e.dxf.text for e in doc.modelspace().query("TEXT") if e.dxf.layer == "TITLE"]
        self.assertIn("12.3456, 23.4567", title_text)

    def test_no_frame_option(self):
        directory = synthetic_project_dir(self.tmp / "proj-noframe")
        src = directory / "optimized_roomplan.json"
        original = src.read_bytes()
        out = self.tmp / "proj-noframe-out"
        result = self._convert_dir(directory, out, "--no-frame")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, doc, _ = self._check_drawing(out, "proj-noframe")
        self.assertIsNone(manifest["titleBlock"])
        self.assertFalse(manifest["frame"])
        self.assertFalse({"FRAME", "TITLE", "NORTH"} & set(manifest["layers"]))
        self.assertEqual(manifest["entityCount"], manifest["geometryEntityCount"])
        self.assertEqual(len(doc.modelspace().query("CIRCLE")), 0)
        self.assertIn("roomplan.no-title-block", {w["code"] for w in manifest["warnings"]})
        self.assertEqual(src.read_bytes(), original, "input modified")

    def test_title_block_cli_overrides(self):
        directory = synthetic_project_dir(self.tmp / "proj-override")
        out = self.tmp / "proj-override-out"
        result = self._convert_dir(directory, out, "--project", "Kuca HH",
                                   "--author", "Ana", "--scale", "1:100",
                                   "--sheet", "A-101")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, _, _ = self._check_drawing(out, "proj-override")
        title = manifest["titleBlock"]
        self.assertEqual(title["project"], "Kuca HH")
        self.assertEqual(title["author"], "Ana")
        self.assertEqual(title["drawnBy"], "by Ana")
        self.assertEqual(title["scaleText"], "1:100")
        self.assertEqual(title["sheet"], "A-101")
        codes = {w["code"] for w in manifest["warnings"]}
        self.assertNotIn("roomplan.scale-not-to-scale", codes)

    def test_missing_scale_argument_is_an_error(self):
        directory = synthetic_project_dir(self.tmp / "proj-badarg")
        result = self._convert_dir(directory, self.tmp / "proj-badarg-out", "--project")
        self.assertEqual(result.returncode, 1)
        self.assertIn("needs a value", result.stderr)

    def test_north_arrow_rotation_differs_by_ninety_degrees(self):
        bearings = {}
        for degrees in (0.0, 90.0):
            directory = synthetic_project_dir(
                self.tmp / f"proj-north-{int(degrees)}", orientation=degrees, with_meta=False)
            out = self.tmp / f"proj-north-{int(degrees)}-out"
            result = self._convert_dir(directory, out)
            self.assertEqual(result.returncode, 0, result.stderr)
            name = f"proj-north-{int(degrees)}"
            manifest, doc, _ = self._check_drawing(out, name)
            north = manifest["northArrow"]
            self.assertEqual(north["basis"], "scan.orientation")
            self.assertEqual(north["source"], "scan")
            self.assertEqual(north["label"], "N")
            self.assertEqual(north["described"], "source-provided")
            self.assertEqual(manifest["sourceMetadata"], None)
            expected = (north["alignmentBearingOffsetDegrees"] - degrees) % 360.0
            self.assertLess(angle_difference(north["degreesClockwiseFromDrawingUp"], expected), 1e-6)
            drawn = north_arrow_bearing(doc)
            self.assertLess(angle_difference(drawn, expected), 0.5)
            bearings[degrees] = drawn
        self.assertAlmostEqual(angle_difference(bearings[0.0], bearings[90.0]), 90.0, places=3)

    def test_directory_scan_priority_is_reported(self):
        directory = synthetic_project_dir(self.tmp / "proj-priority", with_meta=False)
        write_json(directory / "roomplan.json", synthetic_raw())  # lower priority
        out = self.tmp / "proj-priority-out"
        result = self._convert_dir(directory, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, _, _ = self._check_drawing(out, "proj-priority")
        self.assertEqual(manifest["sourceFormat"], "optimized")
        self.assertIn("roomplan.directory-multiple-scans",
                      {w["code"] for w in manifest["warnings"]})

    def test_directory_without_scan_is_rejected(self):
        empty = self.tmp / "proj-empty"
        empty.mkdir(parents=True, exist_ok=True)
        result = self._convert_dir(empty, self.tmp / "proj-empty-out")
        self.assertEqual(result.returncode, 1)
        self.assertIn("No RoomPlan scan found", result.stderr)
        self.assertFalse((self.tmp / "proj-empty-out").exists())

    # ---- north flip: (alignmentOffset - heading) mod 360 -------------------

    def _north_for(self, name, payload, *extra):
        src = self.tmp / f"{name}.json"
        write_json(src, payload)
        out = self.tmp / name
        result = run_converter(src, out, *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, doc, _ = self._check_drawing(out, name)
        return manifest, doc

    def test_north_flip_heading_zero_points_up(self):
        manifest, doc = self._north_for(
            "north-flip-0", synthetic_optimized(orientation_degrees=0.0, align_degrees=0))
        north = manifest["northArrow"]
        self.assertTrue(north["flip180"])
        self.assertEqual(north["alignmentBearingOffsetDegrees"], 0)
        self.assertAlmostEqual(north["degreesClockwiseFromDrawingUp"], 0.0, places=6)
        self.assertLess(angle_difference(north_arrow_bearing(doc), 0.0), 0.5)

    def test_north_flip_heading_ninety_gives_270(self):
        manifest, doc = self._north_for(
            "north-flip-90", synthetic_optimized(orientation_degrees=90.0, align_degrees=0))
        north = manifest["northArrow"]
        self.assertEqual(north["alignmentBearingOffsetDegrees"], 0)
        self.assertAlmostEqual(north["degreesClockwiseFromDrawingUp"], 270.0, places=6)
        self.assertLess(angle_difference(north_arrow_bearing(doc), 270.0), 0.5)

    def test_north_flip_formula_matches_definition(self):
        """heading 15 deg, no alignment rotation -> 345 deg (was 165 deg)."""
        manifest, doc = self._north_for(
            "north-flip-345", synthetic_optimized(orientation_degrees=15.0, align_degrees=0))
        north = manifest["northArrow"]
        self.assertAlmostEqual(north["degreesClockwiseFromDrawingUp"], 345.0, places=6)
        self.assertLess(angle_difference(north_arrow_bearing(doc), 345.0), 0.5)
        legacy = (180.0 - 15.0 + north["alignmentBearingOffsetDegrees"]) % 360.0
        self.assertAlmostEqual(angle_difference(legacy, 345.0), 180.0, places=6)
        self.assertIn("alignmentBearingOffset - heading", north["formula"])

    def test_north_flip_with_meta_heading_and_alignment(self):
        """Real-world shape: meta heading 42.352 deg + alignment offset 27.63 deg."""
        directory = synthetic_project_dir(
            self.tmp / "proj-north-real", heading=42.35218640848984, with_meta=True)
        out = self.tmp / "proj-north-real-out"
        result = self._convert_dir(directory, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, doc, _ = self._check_drawing(out, "proj-north-real")
        north = manifest["northArrow"]
        offset = north["alignmentBearingOffsetDegrees"]
        expected = (offset - 42.35218640848984) % 360.0
        self.assertLess(angle_difference(north["degreesClockwiseFromDrawingUp"], expected), 1e-6)
        # The legacy formula is exactly 180 deg away from the flipped one.
        legacy = (180.0 - 42.35218640848984 + offset) % 360.0
        self.assertAlmostEqual(angle_difference(legacy, expected), 180.0, places=6)
        self.assertLess(angle_difference(north_arrow_bearing(doc), expected), 0.5)
        self.assertIn("roomplan.north-flip-applied", {w["code"] for w in manifest["warnings"]})

    def test_no_north_flip_restores_legacy_formula(self):
        payload = synthetic_optimized(orientation_degrees=15.0, align_degrees=0)
        flipped, _ = self._north_for("north-flip-on", payload)
        legacy, doc = self._north_for("north-flip-off", payload, "--no-north-flip")
        self.assertTrue(flipped["northArrow"]["flip180"])
        self.assertFalse(legacy["northArrow"]["flip180"])
        self.assertAlmostEqual(legacy["northArrow"]["degreesClockwiseFromDrawingUp"], 165.0, places=6)
        self.assertAlmostEqual(
            angle_difference(flipped["northArrow"]["degreesClockwiseFromDrawingUp"],
                             legacy["northArrow"]["degreesClockwiseFromDrawingUp"]), 180.0, places=6)
        self.assertNotIn("roomplan.north-flip-applied",
                         {w["code"] for w in legacy["warnings"]})
        self.assertIn("unflipped", legacy["northArrow"]["formula"])
        self.assertLess(angle_difference(north_arrow_bearing(doc), 165.0), 0.5)

    # ---- title block: text must stay inside its cell ----------------------

    def _assert_cells_fit(self, manifest, doc, tolerance=0.05):
        """Every drawn title-block TEXT must stay inside the cell it belongs to.

        Width is estimated as CHAR_WIDTH_RATIO (0.6) * text height per
        character — the same estimator the fitter uses, so a passing test
        means the fitter's own contract holds in the written DXF.
        """
        sheets = (manifest.get("sheetFurniture") or {}).get("sheets") or []
        self.assertTrue(sheets, "no sheet furniture recorded")
        checked = 0
        for sheet in sheets:
            for cell in sheet["titleBlock"]["cells"]:
                width = cell["cellX1"] - cell["cellX0"]
                self.assertGreater(width, 0)
                estimated = len(cell["drawn"]) * 0.6 * cell["textHeight"]
                self.assertLessEqual(
                    estimated, width * (1 + tolerance),
                    f"cell {cell['key']!r} text {cell['drawn']!r} overflows its cell")
                self.assertGreaterEqual(cell["insert"][0], cell["cellX0"] - 1e-6)
                self.assertLessEqual(cell["textHeight"] * 1.05,
                                     cell["cellY1"] - cell["cellY0"],
                                     "text height exceeds its row")
                drawn = [e for e in doc.modelspace().query("TEXT")
                         if abs(e.dxf.insert.x - cell["insert"][0]) < 1e-3
                         and abs(e.dxf.insert.y - cell["insert"][1]) < 1e-3]
                self.assertEqual(len(drawn), 1, f"missing TEXT for cell {cell['key']!r}")
                self.assertEqual(drawn[0].dxf.text, cell["drawn"])
                self.assertAlmostEqual(drawn[0].dxf.height, cell["textHeight"], places=4)
                checked += 1
        self.assertGreater(checked, 0)

    def test_title_block_cells_fit(self):
        manifest, doc = self._north_for("cells-fit", synthetic_optimized())
        self._assert_cells_fit(manifest, doc)

    def test_long_project_name_truncated_one_line(self):
        long_name = ("Stambena zgrada s poslovnim prostorom u prizemlju i dvije "
                     "etaze, Zagreb, Hrvatska, katastarska cestica 1234/56")
        src = self.tmp / "longname.json"
        write_json(src, synthetic_optimized())
        out = self.tmp / "longname"
        result = run_converter(src, out, "--project", long_name)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, doc, _ = self._check_drawing(out, "longname")
        self._assert_cells_fit(manifest, doc)
        cells = manifest["sheetFurniture"]["sheets"][0]["titleBlock"]["cells"]
        project_cells = [c for c in cells if c["key"] == "Projekt" and not c["isLabel"]]
        self.assertEqual(len(project_cells), 1, "project name must be one single line")
        cell = project_cells[0]
        self.assertTrue(cell["truncated"])
        self.assertTrue(cell["drawn"].endswith("\u2026"), cell["drawn"])
        self.assertLessEqual(len(cell["drawn"]), len(long_name))
        # Nothing is drawn to the right of that cell on the same baseline.
        right_edge = cell["cellX1"]
        for other in doc.modelspace().query("TEXT"):
            if abs(other.dxf.insert.y - cell["insert"][1]) < 1e-6 and other.dxf.text != cell["drawn"]:
                self.assertLessEqual(other.dxf.insert.x, right_edge + 1e-6)

    def test_title_block_has_kat_row(self):
        manifest, doc = self._north_for("kat-row", synthetic_optimized())
        cells = manifest["sheetFurniture"]["sheets"][0]["titleBlock"]["cells"]
        keys = [c["key"] for c in cells]
        self.assertEqual(keys.count("Kat"), 2)  # label cell + value cell
        values = [c["drawn"] for c in cells if c["key"] == "Kat" and not c["isLabel"]]
        self.assertEqual(values, ["Prizemlje"])
        title_text = [e.dxf.text for e in doc.modelspace().query("TEXT")
                      if e.dxf.layer == "TITLE"]
        self.assertIn("Prizemlje", title_text)
        self.assertEqual(manifest["titleBlock"]["story"], 0)
        self.assertEqual(manifest["titleBlock"]["storyLabel"], "Prizemlje")

    def test_kat_labels_for_every_story_kind(self):
        src = self.tmp / "kat-labels.json"
        write_json(src, synthetic_stories(stories=(-1, 0, 1, 2)))
        out = self.tmp / "kat-labels"
        result = run_converter(src, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, doc, _ = self._check_drawing(out, "kat-labels")
        labels = {s["story"]: s["label"] for s in manifest["stories"]}
        self.assertEqual(labels, {-1: "Podrum", 0: "Prizemlje", 1: "1. kat", 2: "2. kat"})
        drawn = [c["drawn"] for sheet in manifest["sheetFurniture"]["sheets"]
                 for c in sheet["titleBlock"]["cells"]
                 if c["key"] == "Kat" and not c["isLabel"]]
        self.assertEqual(drawn, ["Podrum", "Prizemlje", "1. kat", "2. kat"])

    # ---- one frame per story ---------------------------------------------

    def _two_story(self, name, *extra):
        src = self.tmp / f"{name}.json"
        write_json(src, synthetic_stories(stories=(0, 1)))
        out = self.tmp / name
        result = run_converter(src, out, *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, doc, _ = self._check_drawing(out, name)
        return manifest, doc

    def test_two_story_two_frames_and_title_blocks(self):
        manifest, doc = self._two_story("two-story-sheets")
        self.assertEqual(manifest["sheetLayout"]["mode"], "per-story-sheets")
        self.assertEqual(manifest["sheetLayout"]["sheetCount"], 2)
        self.assertGreaterEqual(manifest["sheetLayout"]["gapRatio"], 0.05)
        rects = frame_rects(doc)
        frames = [(s["frame"][0], s["frame"][1], s["frame"][2], s["frame"][3])
                  for s in manifest["sheetFurniture"]["sheets"]]
        self.assertEqual(len(frames), 2)
        for frame in frames:
            matches = [r for r in rects
                       if abs(r[0] - frame[0]) < 1e-3 and abs(r[2] - frame[2]) < 1e-3
                       and abs(r[1] - frame[1]) < 1e-3 and abs(r[3] - frame[3]) < 1e-3]
            self.assertEqual(len(matches), 1, f"no FRAME polygon for {frame}")
        # One title block per frame, each carrying its own "Kat" value.
        kats = [c["drawn"] for s in manifest["sheetFurniture"]["sheets"]
                for c in s["titleBlock"]["cells"] if c["key"] == "Kat" and not c["isLabel"]]
        self.assertEqual(kats, ["Prizemlje", "1. kat"])
        rects_per_sheet = len(rects) - len(frames)
        self.assertEqual(rects_per_sheet, 2, "one extra title-block rectangle per sheet")

    def test_two_story_two_north_arrows(self):
        manifest, doc = self._two_story("two-story-north")
        circles = [e for e in doc.modelspace().query("CIRCLE") if e.dxf.layer == "NORTH"]
        self.assertEqual(len(circles), 6)  # outer ring + inner ring + pivot per empty rose
        # No orientation anywhere: NO needle on either sheet, so no shaft lines.
        self.assertEqual(north_arrow_bearings(doc), [])
        self.assertEqual([e for e in doc.modelspace().query("LINE") if e.dxf.layer == "NORTH"], [])
        texts = [t.dxf.text for t in doc.modelspace().query("TEXT") if t.dxf.layer == "NORTH"]
        self.assertEqual(texts.count("SMJER NEPOZNAT"), 2)
        for sheet in manifest["sheetFurniture"]["sheets"]:
            self.assertEqual(sheet["northArrow"]["label"], "SMJER NEPOZNAT")
            self.assertFalse(sheet["northArrow"]["needle"])
            self.assertIsNotNone(sheet["northArrow"]["centre"])

    def test_two_story_entities_stay_in_their_own_frame(self):
        manifest, doc = self._two_story("two-story-layers")
        frames = {s["story"]: s["frame"] for s in manifest["sheetFurniture"]["sheets"]}
        self.assertEqual(sorted(frames), [0, 1])
        seen = set()
        for entity in doc.modelspace():
            layer = entity.dxf.layer
            if not (layer.startswith("S") and "_" in layer):
                continue
            story = int(layer[1:].split("_", 1)[0])
            frame = frames[story]
            seen.add(story)
            if entity.dxftype() == "LWPOLYLINE":
                points = [(p[0], p[1]) for p in entity.get_points()]
            elif entity.dxftype() == "LINE":
                points = [(entity.dxf.start.x, entity.dxf.start.y),
                          (entity.dxf.end.x, entity.dxf.end.y)]
            else:
                points = [(entity.dxf.insert.x, entity.dxf.insert.y)]
            for x, y in points:
                self.assertGreaterEqual(x, frame[0] - 1e-6, f"{layer} left of its frame")
                self.assertLessEqual(x, frame[2] + 1e-6, f"{layer} right of its frame")
                self.assertGreaterEqual(y, frame[1] - 1e-6, f"{layer} below its frame")
                self.assertLessEqual(y, frame[3] + 1e-6, f"{layer} above its frame")
        self.assertEqual(seen, {0, 1})

    def test_two_story_bboxes_do_not_overlap_and_gap_is_eight_percent(self):
        manifest, _ = self._two_story("two-story-gap")
        stories = manifest["stories"]
        self.assertEqual([s["story"] for s in stories], [0, 1])
        a, b = stories[0]["bbox"], stories[1]["bbox"]
        self.assertFalse(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3])
        self.assertLess(a[2], b[0], "stories must be stacked left to right")
        frames = [(s["frame"]) for s in manifest["sheetFurniture"]["sheets"]]
        measured_gap = frames[1][0] - frames[0][2]
        widest = max(f[2] - f[0] for f in frames)
        self.assertAlmostEqual(measured_gap, 0.08 * widest, places=3)
        self.assertAlmostEqual(manifest["sheetLayout"]["gap"], 0.08 * widest, places=3)
        self.assertTrue(manifest["sheetLayout"]["storiesSeparated"])
        self.assertNotIn("roomplan.stories-not-separated",
                         {w["code"] for w in manifest["warnings"]})

    def test_manifest_per_story_info(self):
        manifest, _ = self._two_story("two-story-manifest")
        stories = manifest["stories"]
        self.assertEqual(len(stories), 2)
        total = 0
        for story in stories:
            self.assertIn(story["story"], (0, 1))
            self.assertIn(story["label"], ("Prizemlje", "1. kat"))
            self.assertEqual(len(story["bbox"]), 4)
            self.assertEqual(story["bboxSource"], "sheet")
            self.assertGreater(story["entityCount"], 0)
            self.assertTrue(all(layer.startswith(f"S{story['story']}_")
                                for layer in story["layers"]))
            total += story["entityCount"]
        self.assertEqual(total, manifest["geometryEntityCount"])

    def test_no_frame_keeps_one_drawing_and_warns(self):
        manifest, doc = self._two_story("two-story-noframe", "--no-frame")
        self.assertIsNone(manifest["titleBlock"])
        self.assertFalse({"FRAME", "TITLE", "NORTH"} & set(manifest["layers"]))
        self.assertEqual(len(doc.modelspace().query("CIRCLE")), 0)
        self.assertFalse(manifest["sheetLayout"]["storiesSeparated"])
        self.assertIn("roomplan.stories-not-separated",
                      {w["code"] for w in manifest["warnings"]})
        # --no-frame means one common plan: both stories share one bbox.
        boxes = [s["bbox"] for s in manifest["stories"]]
        self.assertEqual(boxes[0], boxes[1])

    def test_single_story_has_one_sheet(self):
        manifest, doc = self._north_for("one-story-sheet", synthetic_optimized())
        self.assertEqual(manifest["sheetLayout"]["mode"], "single-sheet")
        self.assertEqual(manifest["sheetLayout"]["sheetCount"], 1)
        self.assertEqual(len(manifest["sheetFurniture"]["sheets"]), 1)
        self.assertEqual(len([e for e in doc.modelspace().query("CIRCLE")]), 2)  # inner ring + pivot per compass
        self.assertEqual(len(north_arrow_bearings(doc)), 1)

    # ---- --place / --place-lookup ----------------------------------------

    def test_place_sets_location_text(self):
        src = self.tmp / "place.json"
        write_json(src, synthetic_optimized())
        out = self.tmp / "place"
        result = run_converter(src, out, "--place", "Zagreb, Hrvatska")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, doc, _ = self._check_drawing(out, "place")
        self.assertEqual(manifest["titleBlock"]["locationText"], "Zagreb, Hrvatska")
        self.assertEqual(manifest["titleBlock"]["locationSource"], "place")
        self.assertIn("roomplan.place-from-cli", {w["code"] for w in manifest["warnings"]})
        self._assert_cells_fit(manifest, doc)

    def test_place_wins_over_geo(self):
        src = self.tmp / "place-geo.json"
        write_json(src, synthetic_optimized())
        out = self.tmp / "place-geo"
        result = run_converter(src, out, "--place", "Testgrad", "--geo")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, _, _ = self._check_drawing(out, "place-geo")
        self.assertEqual(manifest["titleBlock"]["locationText"], "Testgrad")
        self.assertEqual(manifest["sourceGeo"]["latitude"], 12.3456)

    def test_place_lookup_uses_local_helper_or_falls_back(self):
        src = self.tmp / "place-lookup.json"
        write_json(src, synthetic_optimized())
        out = self.tmp / "place-lookup"
        result = run_converter(src, out, "--place-lookup")
        self.assertEqual(result.returncode, 0, "a failed lookup must never abort a conversion")
        manifest, _, _ = self._check_drawing(out, "place-lookup")
        lookup = manifest["placeLookup"]
        self.assertIsNotNone(lookup)
        codes = {w["code"] for w in manifest["warnings"]}
        if shutil.which("apple-location") is None:
            self.assertEqual(lookup["status"], "unavailable")
            self.assertIn("roomplan.place-lookup-unavailable", codes)
            self.assertEqual(manifest["titleBlock"]["locationText"], "location withheld")
        else:
            self.assertIn(lookup["status"], ("ok", "failed"))
            if lookup["status"] == "ok":
                self.assertIn("roomplan.place-lookup-applied", codes)
                self.assertEqual(manifest["titleBlock"]["locationText"], lookup["text"])
                self.assertEqual(manifest["titleBlock"]["locationSource"], "place-lookup")
                # Locality name only — never the raw coordinates.
                self.assertNotIn("12.3456", manifest["titleBlock"]["locationText"])
            else:
                self.assertIn("roomplan.place-lookup-failed", codes)
                self.assertEqual(manifest["titleBlock"]["locationText"], "location withheld")

    def test_place_lookup_without_coordinates_does_nothing(self):
        src = self.tmp / "place-lookup-nocoords.json"
        write_json(src, synthetic_optimized(with_geo=False))
        out = self.tmp / "place-lookup-nocoords"
        result = run_converter(src, out, "--place-lookup")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, _, _ = self._check_drawing(out, "place-lookup-nocoords")
        self.assertEqual(manifest["placeLookup"]["status"], "no-coordinates")
        self.assertIn("roomplan.place-lookup-no-coordinates",
                      {w["code"] for w in manifest["warnings"]})
        self.assertEqual(manifest["titleBlock"]["locationText"], "location withheld")

    # ---- no false north: file input, sibling meta, unknown direction --------
    def test_file_input_reads_sibling_meta(self):
        """A lone scan file must still find its own meta.json next to it."""
        folder = self.tmp / "sibling-meta"
        folder.mkdir()
        write_json(folder / "optimized_roomplan.json",
                   synthetic_optimized(orientation_degrees=None, with_geo=False))
        write_json(folder / "meta.json",
                   {"name": "Sibling", "headingDegrees": 193.7411616666391})
        out = self.tmp / "sibling-meta-out"
        result = run_converter(folder / "optimized_roomplan.json", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((out / "optimized_roomplan.roomplan.json").read_text(encoding="utf-8"))
        north = manifest["northArrow"]
        self.assertEqual(north["basis"], "meta.headingDegrees")
        self.assertTrue(north["needle"])
        self.assertEqual(north["label"], "N")
        self.assertIsNotNone(north["degreesClockwiseFromDrawingUp"])
        codes = {w["code"] for w in manifest["warnings"]}
        self.assertNotIn("roomplan.meta-not-attributed", codes)

    def test_sibling_meta_is_not_borrowed_from_an_ambiguous_folder(self):
        folder = self.tmp / "ambiguous-meta"
        folder.mkdir()
        payload = synthetic_optimized(orientation_degrees=None, with_geo=False)
        write_json(folder / "roomplan.json", payload)
        write_json(folder / "optimized_roomplan.json", payload)
        write_json(folder / "meta.json", {"name": "Other", "headingDegrees": 12.0})
        out = self.tmp / "ambiguous-meta-out"
        result = run_converter(folder / "roomplan.json", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((out / "roomplan.roomplan.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["northArrow"]["basis"], "none")
        codes = {w["code"] for w in manifest["warnings"]}
        self.assertIn("roomplan.meta-not-attributed", codes)

    def test_unknown_direction_draws_no_needle(self):
        """No orientation anywhere: empty rose + words, never a needle."""
        source = self.tmp / "no-north.json"
        write_json(source, synthetic_optimized(orientation_degrees=None, with_geo=False))
        out = self.tmp / "no-north-out"
        result = run_converter(source, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest, doc, _ = self._check_drawing(out, "no-north")
        north = manifest["northArrow"]
        self.assertFalse(north["needle"])
        self.assertEqual(north["label"], "SMJER NEPOZNAT")
        self.assertEqual(north["described"], "unknown")
        self.assertIsNone(north["degreesClockwiseFromDrawingUp"])
        north_lines = [e for e in doc.modelspace().query("LINE") if e.dxf.layer == "NORTH"]
        self.assertEqual(north_lines, [], "no north needle may be drawn without a bearing")
        north_texts = [t.dxf.text for t in doc.modelspace().query("TEXT") if t.dxf.layer == "NORTH"]
        self.assertIn("SMJER NEPOZNAT", north_texts)
        self.assertNotIn("N?", north_texts)
        codes = {w["code"] for w in manifest["warnings"]}
        self.assertIn("roomplan.north-direction-unknown", codes)


if __name__ == "__main__":
    unittest.main()
