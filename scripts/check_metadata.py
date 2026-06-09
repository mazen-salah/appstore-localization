#!/usr/bin/env python3
"""
Validate localized App Store metadata against Apple's field limits.

Scans a fastlane metadata tree (the `<locale>/*.txt` layout used by
`fastlane deliver`) and flags fields that exceed App Store Connect limits or
waste characters — the kind of thing that gets a `deliver` run rejected or
silently truncated after you have translated 12 locales.

Checks per locale:
  * name.txt            <= 30 chars
  * subtitle.txt        <= 30 chars
  * keywords.txt        <= 100 chars; warns on leading/trailing spaces, spaces
                          after commas (wasted chars), duplicate keywords, and
                          words already present in name/subtitle (redundant, since
                          App Store indexes name + subtitle + keywords as one bag)
  * promotional_text.txt <= 170 chars
  * description.txt      <= 4000 chars
  * release_notes.txt    <= 4000 chars

Pure standard library, no dependencies, no network, no credentials.

Usage:
    python check_metadata.py path/to/ios/fastlane/metadata
    python check_metadata.py path/to/metadata --locale en-US
"""
from __future__ import annotations

import argparse
import os
import sys

LIMITS = {
    "name": 30,
    "subtitle": 30,
    "keywords": 100,
    "promotional_text": 170,
    "description": 4000,
    "release_notes": 4000,
}

GREEN, YELLOW, RED, DIM, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().strip("\n")


def check_locale(locale_dir: str, locale: str) -> tuple[int, int]:
    errors = warnings = 0
    name = subtitle = ""
    print(f"\n{locale}")

    for field, limit in LIMITS.items():
        path = os.path.join(locale_dir, f"{field}.txt")
        if not os.path.exists(path):
            if field in ("name", "subtitle", "keywords", "description"):
                print(f"  {DIM}- {field:<17} (absent){RESET}")
            continue
        value = _read(path)
        n = len(value)
        over = n > limit
        tag = f"{RED}OVER{RESET}" if over else f"{GREEN}ok{RESET}"
        print(f"  {field:<17} {n:>4}/{limit}  {tag}")
        if over:
            errors += 1

        if field == "name":
            name = value
        elif field == "subtitle":
            subtitle = value
        elif field == "keywords":
            if value != value.strip():
                print(f"      {YELLOW}warn: leading/trailing whitespace{RESET}")
                warnings += 1
            if ", " in value:
                print(f"      {YELLOW}warn: spaces after commas waste characters "
                      f"(use 'a,b,c' not 'a, b, c'){RESET}")
                warnings += 1
            kws = [k.strip().lower() for k in value.split(",") if k.strip()]
            dups = {k for k in kws if kws.count(k) > 1}
            if dups:
                print(f"      {YELLOW}warn: duplicate keywords: {', '.join(sorted(dups))}{RESET}")
                warnings += 1
            bag = (name + " " + subtitle).lower().split()
            redundant = sorted({k for k in kws if k in bag})
            if redundant:
                print(f"      {YELLOW}warn: already in name/subtitle (redundant): "
                      f"{', '.join(redundant)}{RESET}")
                warnings += 1

    return errors, warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate App Store metadata field limits.")
    ap.add_argument("metadata_dir", help="fastlane metadata directory")
    ap.add_argument("--locale", help="check a single locale only")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.metadata_dir):
        sys.exit(f"not a directory: {args.metadata_dir}")

    locales = (
        [args.locale]
        if args.locale
        else sorted(
            d for d in os.listdir(args.metadata_dir)
            if os.path.isdir(os.path.join(args.metadata_dir, d))
            and d != "review_information"
        )
    )

    total_e = total_w = 0
    for loc in locales:
        d = os.path.join(args.metadata_dir, loc)
        if not os.path.isdir(d):
            print(f"{RED}missing locale dir: {loc}{RESET}")
            total_e += 1
            continue
        e, w = check_locale(d, loc)
        total_e += e
        total_w += w

    print(f"\n{'-' * 40}")
    status = f"{RED}{total_e} error(s){RESET}" if total_e else f"{GREEN}no errors{RESET}"
    print(f"{status}, {total_w} warning(s) across {len(locales)} locale(s)")
    return 1 if total_e else 0


if __name__ == "__main__":
    raise SystemExit(main())
