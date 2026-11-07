"""Offline self-test for the roomplan-dxf package.

Generates two *synthetic* RoomPlan inputs in a fresh temporary directory
(raw CapturedStructure, optimized format_version 1), runs the real Node
converter, audits the resulting DXF with ezdxf, and checks the safety rules:

* the input file is never modified,
* existing outputs are refused without --force,
* the retired --jev option (and any Jev/TypeSafe code path) is gone.

No fixture files are shipped with the package and nothing is written outside
the temporary directory. Requires Node.js and python3 + ezdxf.
"""
import hashlib
import json
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


def synthetic_optimized():
    """format_version 1 with a source-provided 90 deg alignment_transform."""
    align = rotated_y(90)
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
        "latLonAlt": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0},
        "orientation": {"orientation_degrees": 0.0, "confidence": 0.9},
        "joints": [],
    }


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_converter(*args):
    return subprocess.run(
        ["node", str(CONVERTER), *map(str, args)],
        capture_output=True, text=True,
    )


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
            actual = {}
            for entity in entities:
                actual[entity.dxftype()] = actual.get(entity.dxftype(), 0) + 1
            self.assertEqual(actual, expected_counts)
        summary = inspect(dxf_path)
        self.assertEqual(summary["audit"]["errors"], 0)
        self.assertEqual(summary["insunits"], 6)
        self.assertEqual(sum(summary["entities"].values()), len(entities))
        return manifest, doc, summary

    def test_raw_conversion(self):
        src, digest, out = self._convert("synthetic-raw", synthetic_raw())
        original = src.read_bytes()
        manifest, doc, _ = self._check_drawing(
            out, "synthetic-raw",
            expected_counts={"LWPOLYLINE": 8, "LINE": 3},
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
            expected_counts={"LWPOLYLINE": 5, "LINE": 2, "TEXT": 1},
        )
        self.assertEqual(manifest["sourceFormat"], "optimized")
        self.assertEqual(manifest["sourceSHA256"], digest)
        self.assertEqual(manifest["storyCount"], 1)
        self.assertEqual(manifest["architecturalAlignment"]["method"],
                         "source-provided alignment_transform")
        labels = [e for e in doc.modelspace().query("TEXT")]
        self.assertEqual(len(labels), 1)
        self.assertIn("Living Room", labels[0].dxf.text)
        self.assertIn("m2", labels[0].dxf.text)
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
        self.assertEqual(geo["latitude"], 0.0)
        self.assertEqual(geo["longitude"], 0.0)
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


if __name__ == "__main__":
    unittest.main()
