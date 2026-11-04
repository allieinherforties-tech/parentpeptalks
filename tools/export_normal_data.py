"""Export the Milestones sheet to the client-side JSON the /normal tool serves.

Input is a verbatim CSV export of the Milestones sheet (11 columns, original
headers) — the same pull the data-layer review was built from. Output is
assets/normal-data.json, shaped per the /normal MVP spec (art_OFGP554H):

  meta   — provenance, never hand-edited
  bands  — the eight age bands, in start-month order
  items  — every banded row, verbatim, in sheet order

The three cross-cutting editorial rows (M-156/M-157/M-158, Age Band
"All bands (cross-cutting)") are excluded from items: the tool never renders
them — their content anchors the register rules in normal-editorial.json and
the render templates in normal.js instead.

Usage:
  python3 tools/export_normal_data.py <verbatim.csv> \
      [--out assets/normal-data.json] [--exported YYYY-MM-DD]

Rerun after any Milestones edit; hand changes to the output get overwritten.
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

# The 11 columns the tool consumes, verbatim from the sheet. Anything else in
# the CSV (editorial-calendar fields) is ignored.
COLUMNS = {
    "Item ID": "id",
    "Age Band": "band",
    "Band Start (months)": "bandStart",
    "Band End (months)": "bandEnd",
    "Category": "category",
    "Milestone or Concern": "concern",
    "Trigger Moments": "triggerMoments",
    "Normalization Guidance": "guidance",
    "Confidence Label": "confidence",
    "Source": "source",
    "Geography": "geography",
}

CROSS_CUTTING_BAND = "All bands (cross-cutting)"
EXPECTED_CROSS_CUTTING_IDS = {"M-156", "M-157", "M-158"}

# Stable band ids keyed by (start, end) months. A new or changed band is a
# schema change — this map fails loudly rather than inventing an id.
BAND_IDS = {
    (0, 3): "nb-3m",
    (4, 9): "4-9m",
    (9, 18): "9-18m",
    (18, 36): "18m-3y",
    (36, 60): "3-5y",
    (60, 84): "5-7y",
    (84, 120): "7-10y",
    (120, 156): "10-13y",
}


def fail(message):
    sys.exit(f"export_normal_data: {message}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="verbatim Milestones CSV export")
    parser.add_argument("--out", default="assets/normal-data.json")
    parser.add_argument(
        "--exported", default=date.today().isoformat(),
        help="date of the underlying sheet export (YYYY-MM-DD)")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.is_file():
        fail(f"input CSV not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            fail(f"input CSV is missing columns: {missing}")
        rows = list(reader)

    problems = []
    items = []
    band_rows = {}
    band_labels = {}
    for index, row in enumerate(rows, start=2):  # header is line 1
        item_id = (row.get("Item ID") or "").strip()
        label = row.get("Age Band", "")

        if label == CROSS_CUTTING_BAND:
            continue  # counted separately below
        for column in COLUMNS:
            if not (row.get(column) or "").strip():
                problems.append(f"line {index} ({item_id or '?'}): empty {column}")
        try:
            start, end = int(row["Band Start (months)"]), int(row["Band End (months)"])
        except ValueError:
            problems.append(f"line {index} ({item_id}): non-numeric band months")
            continue
        band_id = BAND_IDS.get((start, end))
        if band_id is None:
            problems.append(
                f"line {index} ({item_id}): band ({start}, {end}) has no id — "
                "update BAND_IDS in this script")
            continue

        items.append({
            "id": item_id,
            "band": label,
            "bandStart": start,
            "bandEnd": end,
            "category": row["Category"],
            "concern": row["Milestone or Concern"],
            "triggerMoments": row["Trigger Moments"],
            "guidance": row["Normalization Guidance"],
            "confidence": row["Confidence Label"],
            "source": row["Source"],
            "geography": row["Geography"],
        })
        band_rows[band_id] = band_rows.get(band_id, 0) + 1
        band_labels[band_id] = label

    excluded_ids = {
        (row.get("Item ID") or "").strip()
        for row in rows if row.get("Age Band") == CROSS_CUTTING_BAND
    }
    # The exclusion set is only checked when the input still carries the
    # cross-cutting rows: a full-sheet export must exclude exactly the three
    # known editorial rows, and a pre-filtered export (like the reviewed
    # data-layer CSV) must not smuggle them in as banded rows.
    if excluded_ids and excluded_ids != EXPECTED_CROSS_CUTTING_IDS:
        fail(
            "cross-cutting exclusion set drifted: expected "
            f"{sorted(EXPECTED_CROSS_CUTTING_IDS)}, found {sorted(excluded_ids)}"
        )
    smuggled = sorted(EXPECTED_CROSS_CUTTING_IDS & {item["id"] for item in items})
    if smuggled:
        fail(f"cross-cutting editorial rows must not be items: {smuggled}")
    if problems:
        fail(f"{len(problems)} row problem(s):\n  " + "\n  ".join(problems))

    bands = [
        {
            "id": band_id,
            "label": band_labels[band_id],
            "start": start,
            "end": end,
            "rows": band_rows[band_id],
        }
        for (start, end), band_id in sorted(BAND_IDS.items())
        if band_id in band_rows
    ]

    data = {
        "meta": {
            "source": (
                "Milestones sheet sh_aq4ocQyf, workbook wb_MWwXShaC "
                "(Parent Pep Talks — Content Library)"
            ),
            "exported": args.exported,
            "rowCount": len(items),
            "note": "Generated file. Edit the sheet, rerun the export — never edit this.",
        },
        "bands": bands,
        "items": items,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(
        f"export_normal_data: wrote {out_path} — {len(items)} items, "
        f"{len(bands)} bands, {len(rows) - len(items)} cross-cutting rows excluded"
    )


if __name__ == "__main__":
    main()
