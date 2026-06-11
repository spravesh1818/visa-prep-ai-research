"""Build app/knowledge/universities.json from authoritative registries.

Sources:
  - US: IPEDS "Directory" (HD) file from NCES - every active US institution.
        We keep currently-active, 4-year (degree-granting) institutions.
        https://nces.ed.gov/ipeds/datacenter/data/HD2023.zip
  - UK: Hipolabs university list, filtered to the United Kingdom.
        https://raw.githubusercontent.com/Hipo/university-domains-list/master/world_universities_and_domains.json
        (The official UK "register of licensed student sponsors" CSV can be
        substituted here; its download URL changes by publication date.)

Every imported school gets the neutral tier "recognized". The hand-curated tiers
in curated_overrides.json (top/high/mid/low/diploma_mill) are then overlaid, so
well-known schools keep their ranking-based tier and abbreviations.

Usage:
  uv run python scripts/build_universities.py            # download fresh
  uv run python scripts/build_universities.py \
      --ipeds /tmp/HD2023.csv --hipolabs /tmp/world.json # use local copies
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.knowledge.university_service import normalize_name as _norm  # noqa: E402

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "app" / "knowledge"
OVERRIDES_PATH = KNOWLEDGE_DIR / "curated_overrides.json"
OUTPUT_PATH = KNOWLEDGE_DIR / "universities.json"

IPEDS_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD2023.zip"
HIPOLABS_URL = (
    "https://raw.githubusercontent.com/Hipo/university-domains-list/"
    "master/world_universities_and_domains.json"
)

DEFAULT_TIER = "recognized"


# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #
def _read_ipeds_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    # The first column header may carry a BOM (e.g. "\ufeffUNITID").
    rows: list[dict] = []
    for row in reader:
        # CYACTIVE == 1 -> currently active; ICLEVEL == 1 -> 4-year institution.
        if row.get("CYACTIVE") != "1" or row.get("ICLEVEL") != "1":
            continue
        name = (row.get("INSTNM") or "").strip()
        if not name:
            continue
        aliases = []
        raw_alias = (row.get("IALIAS") or "").strip()
        if raw_alias:
            for part in re.split(r"[|;]", raw_alias):
                part = part.strip()
                if 2 <= len(part) <= 60 and _norm(part) != _norm(name):
                    aliases.append(part)
        rows.append({"name": name, "country": "US", "aliases": aliases})
    return rows


def load_ipeds(local: str | None) -> list[dict]:
    if local:
        text = Path(local).read_text(encoding="latin-1")
        return _read_ipeds_csv(text)
    print(f"Downloading IPEDS: {IPEDS_URL}")
    with urllib.request.urlopen(IPEDS_URL, timeout=120) as resp:
        blob = resp.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        text = zf.read(csv_name).decode("latin-1")
    return _read_ipeds_csv(text)


def load_hipolabs(local: str | None, countries: set[str]) -> list[dict]:
    if local:
        data = json.loads(Path(local).read_text(encoding="utf-8"))
    else:
        print(f"Downloading Hipolabs: {HIPOLABS_URL}")
        with urllib.request.urlopen(HIPOLABS_URL, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))

    country_to_code = {"United Kingdom": "UK", "United States": "US"}
    out: list[dict] = []
    for item in data:
        country = item.get("country")
        if country not in countries:
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "country": country_to_code.get(country, country),
                "aliases": [],
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #
def build(ipeds_local: str | None, hipolabs_local: str | None) -> dict:
    bulk = load_ipeds(ipeds_local) + load_hipolabs(
        hipolabs_local, countries={"United Kingdom"}
    )

    # Deduplicate by (country, normalized name); merge aliases.
    registry: dict[tuple[str, str], dict] = {}
    for entry in bulk:
        key = (entry["country"], _norm(entry["name"]))
        if key in registry:
            existing = registry[key]
            existing_aliases = set(existing["aliases"]) | set(entry["aliases"])
            existing["aliases"] = sorted(existing_aliases)
        else:
            registry[key] = {
                "name": entry["name"],
                "country": entry["country"],
                "tier": DEFAULT_TIER,
                "aliases": sorted(set(entry["aliases"])),
            }

    # Overlay curated tier overrides via exact normalized match. When no exact
    # match exists (e.g. IPEDS uses a campus-specific name), the override is added
    # as its own clean entry; the runtime matcher resolves it via exact-normalized
    # lookup and tier priority.
    overrides = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))["overrides"]
    applied, added = 0, 0
    for ov in overrides:
        key = (ov["country"], _norm(ov["name"]))
        if key in registry:
            target = registry[key]
            target["tier"] = ov["tier"]
            target["aliases"] = sorted(set(target["aliases"]) | set(ov.get("aliases", [])))
            applied += 1
        else:
            registry[key] = {
                "name": ov["name"],
                "country": ov["country"],
                "tier": ov["tier"],
                "aliases": sorted(set(ov.get("aliases", []))),
            }
            added += 1

    universities = sorted(
        registry.values(), key=lambda e: (e["country"], e["name"].lower())
    )

    print(
        f"Built {len(universities)} universities "
        f"(overrides applied: {applied}, added: {added})."
    )
    return {
        "_meta": {
            "description": (
                "Auto-generated by scripts/build_universities.py from IPEDS (US) "
                "and Hipolabs (UK), with curated tier overrides. Illustrative for "
                "a mock/prep tool; NOT an official accreditation source."
            ),
            "tiers": ["top", "high", "mid", "low", "recognized", "diploma_mill"],
            "count": len(universities),
        },
        "universities": universities,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipeds", help="Local IPEDS HD CSV path (skip download).")
    parser.add_argument("--hipolabs", help="Local Hipolabs JSON path (skip download).")
    args = parser.parse_args()

    result = build(args.ipeds, args.hipolabs)
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
