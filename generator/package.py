"""Packaging step (plan §4.1): bump metadata.json to today's UTC date and
zip the shippable contents into a PCM-installable archive.

Usage: python -m generator.package [--version YYYY.MM.DD]
"""
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from generator.package_tools import create_zip_archive, update_version

ROOT = Path(__file__).resolve().parent.parent
METADATA_PATH = ROOT / "metadata.json"

# Matches plan §4.1: 3dmodels, footprints, resources, symbols, metadata.json.
ZIP_CONTENTS = ["3dmodels", "footprints", "resources", "symbols", "metadata.json"]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=None, help="UTC YYYY.MM.DD; defaults to today")
    parser.add_argument("--kicad-version", default="8.0")
    parser.add_argument("--status", default="stable")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    version = args.version or datetime.now(timezone.utc).strftime("%Y.%m.%d")
    update_version(str(METADATA_PATH), version, kicad_version=args.kicad_version, status=args.status)

    output_zip = (args.output or (ROOT / f"es-kicad-lib-{version}.zip")).resolve()

    # create_zip_archive() computes each arcname as os.path.relpath(path, ".")
    # (ported verbatim from CDFER, see package_tools.py), so it must run with
    # the CWD at the repo root or absolute paths leak into the archive.
    previous_cwd = Path.cwd()
    os.chdir(ROOT)
    try:
        existing = [p for p in ZIP_CONTENTS if Path(p).exists()]
        create_zip_archive(str(output_zip), existing)
    finally:
        os.chdir(previous_cwd)

    print(f"Version set to {version}")
    print(f"Wrote {output_zip}")


if __name__ == "__main__":
    main()
