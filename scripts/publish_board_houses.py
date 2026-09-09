#!/usr/bin/env python3
"""Publish `board-houses/board-houses.json` to the docs site as downloads.

`SPEC-342` section 2.3 settled that real houses are distributed as a file rather
than bundled with the app, which means the numbers now exist in two places: the
source of truth in `board-houses/`, and whatever the docs site serves. Two
copies of the same numbers drift, and the failure is silent and bad -- a user
downloads a house, orders against it, and it is a revision behind what the
vendor's page said when someone last read it.

So the published set is generated, never hand-edited, and `--check` fails CI if
it has fallen behind. Per-house files exist because a user quoting one vendor
should not have to import four.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(REPO_ROOT, "board-houses", "board-houses.json")
PUBLISHED = os.path.join(REPO_ROOT, "docs", "site", "public", "board-houses")


def _render(source: dict) -> dict[str, str]:
    """Filename -> file contents. One file per house, plus the whole set.

    Each per-house file is a complete importable library with one house in it,
    not a bare house record: the importer takes a `houses` list, and handing a
    user a file it will refuse is worse than handing them nothing."""
    files = {"board-houses.json": json.dumps(source, indent=2) + "\n"}
    for house in source["houses"]:
        one = {
            "schema_version": source["schema_version"],
            "exported_at": source["exported_at"],
            "houses": [house],
        }
        files[f"{house['house_id']}.json"] = json.dumps(one, indent=2) + "\n"
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the published files are missing, stale or extra. Writes nothing.",
    )
    args = parser.parse_args(argv)

    with open(SOURCE, encoding="utf-8") as fh:
        source = json.load(fh)
    files = _render(source)

    if args.check:
        stale = []
        for name, body in files.items():
            path = os.path.join(PUBLISHED, name)
            if not os.path.exists(path):
                stale.append(f"missing: {name}")
                continue
            with open(path, encoding="utf-8") as fh:
                if fh.read() != body:
                    stale.append(f"stale:   {name}")
        if os.path.isdir(PUBLISHED):
            for name in sorted(os.listdir(PUBLISHED)):
                if name.endswith(".json") and name not in files:
                    # A house removed from the source but still downloadable is
                    # the worst of the drift cases: nothing points at it and it
                    # still works.
                    stale.append(f"orphan:  {name}")
        if stale:
            print(
                "docs/site/public/board-houses is out of date with "
                "board-houses/board-houses.json:",
                file=sys.stderr,
            )
            for line in stale:
                print(f"  {line}", file=sys.stderr)
            print(
                "\nRun: python3 scripts/publish_board_houses.py",
                file=sys.stderr,
            )
            return 1
        print(f"OK ({len(files)} published files match the source)")
        return 0

    os.makedirs(PUBLISHED, exist_ok=True)
    for name, body in files.items():
        with open(os.path.join(PUBLISHED, name), "w", encoding="utf-8") as fh:
            fh.write(body)
    for name in sorted(os.listdir(PUBLISHED)):
        if name.endswith(".json") and name not in files:
            os.remove(os.path.join(PUBLISHED, name))
            print(f"removed orphan {name}")
    print(f"Published {len(files)} files to docs/site/public/board-houses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
