"""Generate a synthetic 100 x 50 mm rectangle DXF; refuses existing destinations.

Used by the self-test to exercise inspect_dxf without shipping fixture files.
"""
import argparse
from pathlib import Path

import ezdxf
from ezdxf import units


def generate(path):
    doc = ezdxf.new("R2010")
    doc.units = units.MM
    doc.layers.new("OUTLINE", dxfattribs={"color": 7})
    points = [(0, 0), (100, 0), (100, 50), (0, 50)]
    for start, end in zip(points, points[1:] + points[:1]):
        doc.modelspace().add_line(start, end, dxfattribs={"layer": "OUTLINE"})
    audit = doc.audit()
    if audit.errors or audit.fixes:
        raise ValueError("synthetic document failed pre-write audit")
    # Exclusive open also refuses symlinks to existing files; never truncate input.
    # On later write/readback failure, leave the new file for explicit inspection.
    with Path(path).open("x", encoding=doc.output_encoding, newline="") as stream:
        doc.write(stream)
    reopened = ezdxf.readfile(path)
    audit = reopened.audit()
    if audit.errors or audit.fixes:
        raise ValueError("synthetic document failed readback audit")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    generate(args.output)


if __name__ == "__main__":
    main()
