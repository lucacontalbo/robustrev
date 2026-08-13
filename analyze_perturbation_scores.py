"""Aggregate statistics on how perturbations move review scores.

Layout this script expects (see tests/):

    tests/reviews/<venue>/<model>/<paper_id>/review.json      # original review
    tests/reviews_<perturbation>/<venue>/<model>/<paper_id>/review.json

A paper directory that has no usable review (missing review.json, an
error.txt instead, or unparsable JSON) is skipped. A perturbation is skipped
for a given paper if *that* perturbation has no usable review for it, even
though the original review exists.

For every "score" field defined in the venue's rubric (rubrics/<venue>_rubric.yaml)
we compute, per perturbation, the distribution of (perturbed - original) deltas:
  - overall (across all papers with a usable pair)
  - broken down by the paper's *original* overall_assessment score, bucketed
    into low / mid / high, to see whether a perturbation behaves differently
    depending on how the paper was scored to begin with.

Usage:
    python analyze_perturbation_scores.py
    python analyze_perturbation_scores.py --output analysis.json --raw-csv raw_deltas.csv
"""

import argparse
import csv
import json
import statistics as stats
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
TESTS_DIR = ROOT / "tests"
RUBRIC_DIR = ROOT / "rubrics"
BASELINE_DIR_NAME = "reviews"

# Default bucketing of the original overall_assessment score (1-5 scale, 0.5
# steps, see rubrics/acl_rubric.yaml). Edges are inclusive on the lower bound
# and exclusive on the upper bound, matching the ARR acceptance semantics:
# <=2 "resubmit", 2.5-3.5 "findings/borderline", >=4 "conference or better".
DEFAULT_BINS = [
    ("low (<=2)", float("-inf"), 2.0),
    ("mid (2.5-3.5)", 2.0, 4.0),
    ("high (>=4)", 4.0, float("inf")),
]

OVERALL_FIELD = "overall_assessment"


def load_review(paper_dir):
    """Return the review dict for a paper directory, or None if unusable."""
    review_file = paper_dir / "review.json"
    if not review_file.exists():
        # tolerate the plural spelling too
        alt = paper_dir / "reviews.json"
        if alt.exists():
            review_file = alt
        else:
            return None
    try:
        data = json.loads(review_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def score_fields_for_venue(venue):
    """Score-type field ids from the venue's rubric, falling back to type
    sniffing if no rubric is found."""
    rubric_path = RUBRIC_DIR / f"{venue}_rubric.yaml"
    if not rubric_path.exists():
        return None
    rubric = yaml.safe_load(rubric_path.read_text())
    return [f["id"] for f in rubric.get("fields", []) if f.get("type") == "score"]


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def bin_for(score, bins):
    for label, lo, hi in bins:
        if lo <= score < hi:
            return label
    return None


def discover_baseline(baseline_root):
    """paper dirs are baseline_root/<venue>/<model>/<paper_id>."""
    reviews = {}  # (venue, model, paper_id) -> review dict
    skipped = 0
    for paper_dir in sorted(baseline_root.glob("*/*/*")):
        if not paper_dir.is_dir():
            continue
        venue, model, paper_id = paper_dir.parts[-3:]
        review = load_review(paper_dir)
        if review is None:
            skipped += 1
            continue
        reviews[(venue, model, paper_id)] = review
    return reviews, skipped


def collect_deltas(baseline_reviews, perturbation_dirs, score_fields_cache):
    """Return a list of delta records:
    {perturbation, venue, model, paper_id, attribute, base, pert, delta, base_overall}
    """
    records = []
    per_perturbation_skipped = {}

    for pert_dir in perturbation_dirs:
        pert_name = pert_dir.name[len(f"{BASELINE_DIR_NAME}_"):]
        skipped = 0
        for (venue, model, paper_id), base_review in baseline_reviews.items():
            paper_dir = pert_dir / venue / model / paper_id
            pert_review = load_review(paper_dir)
            if pert_review is None:
                skipped += 1
                continue

            if venue not in score_fields_cache:
                score_fields_cache[venue] = score_fields_for_venue(venue)
            score_fields = score_fields_cache[venue]
            if score_fields is None:
                # no rubric available: fall back to keys numeric in the baseline
                score_fields = [k for k, v in base_review.items() if is_number(v)]

            base_overall = base_review.get(OVERALL_FIELD)
            if not is_number(base_overall):
                base_overall = None

            for attr in score_fields:
                base_val = base_review.get(attr)
                pert_val = pert_review.get(attr)
                if not is_number(base_val) or not is_number(pert_val):
                    continue
                records.append({
                    "perturbation": pert_name,
                    "venue": venue,
                    "model": model,
                    "paper_id": paper_id,
                    "attribute": attr,
                    "base": base_val,
                    "pert": pert_val,
                    "delta": pert_val - base_val,
                    "base_overall": base_overall,
                })
        per_perturbation_skipped[pert_name] = skipped

    return records, per_perturbation_skipped


def summarize(deltas, bases, perts):
    n = len(deltas)
    if n == 0:
        return None
    increased = sum(1 for d in deltas if d > 0)
    decreased = sum(1 for d in deltas if d < 0)
    unchanged = n - increased - decreased
    return {
        "n": n,
        "mean_delta": stats.mean(deltas),
        "std_delta": stats.stdev(deltas) if n > 1 else 0.0,
        "median_delta": stats.median(deltas),
        "min_delta": min(deltas),
        "max_delta": max(deltas),
        "mean_base": stats.mean(bases),
        "mean_pert": stats.mean(perts),
        "frac_increased": increased / n,
        "frac_decreased": decreased / n,
        "frac_unchanged": unchanged / n,
    }


def aggregate(records, bins):
    by_pert_attr = {}
    by_pert_attr_bin = {}

    grouped = {}
    for r in records:
        grouped.setdefault((r["perturbation"], r["attribute"]), []).append(r)

    for (pert, attr), rs in grouped.items():
        deltas = [r["delta"] for r in rs]
        bases = [r["base"] for r in rs]
        perts = [r["pert"] for r in rs]
        by_pert_attr.setdefault(pert, {})[attr] = summarize(deltas, bases, perts)

        binned = {}
        for r in rs:
            if r["base_overall"] is None:
                continue
            label = bin_for(r["base_overall"], bins)
            if label is None:
                continue
            binned.setdefault(label, []).append(r)
        bin_summary = {}
        for label, _, _ in bins:
            rs_bin = binned.get(label, [])
            bin_summary[label] = summarize(
                [r["delta"] for r in rs_bin],
                [r["base"] for r in rs_bin],
                [r["pert"] for r in rs_bin],
            )
        by_pert_attr_bin.setdefault(pert, {})[attr] = bin_summary

    return by_pert_attr, by_pert_attr_bin


def fmt(x, width=7, prec=3):
    return f"{x:{width}.{prec}f}" if isinstance(x, float) else f"{x:{width}}"


def print_report(by_pert_attr, by_pert_attr_bin, bins, baseline_skipped, per_pert_skipped, n_baseline):
    print("=" * 100)
    print("PERTURBATION SCORE-CHANGE ANALYSIS")
    print("=" * 100)
    print(f"Original reviews usable: {n_baseline} (skipped, no usable review: {baseline_skipped})\n")

    for pert in sorted(by_pert_attr):
        print("-" * 100)
        print(f"Perturbation: {pert}  "
              f"(papers skipped for this perturbation: {per_pert_skipped.get(pert, 0)})")
        print("-" * 100)
        attrs = by_pert_attr[pert]
        header = f"{'attribute':<20}{'n':>5}{'mean Δ':>9}{'std Δ':>9}{'median Δ':>10}{'min Δ':>8}{'max Δ':>8}{'%up':>7}{'%down':>7}{'%same':>7}"
        print(header)
        for attr in sorted(attrs):
            s = attrs[attr]
            if s is None:
                print(f"{attr:<20}{'(no usable pairs)':>76}")
                continue
            print(f"{attr:<20}{s['n']:>5}{s['mean_delta']:>9.3f}{s['std_delta']:>9.3f}"
                  f"{s['median_delta']:>10.3f}{s['min_delta']:>8.2f}{s['max_delta']:>8.2f}"
                  f"{100*s['frac_increased']:>6.0f}%{100*s['frac_decreased']:>6.0f}%{100*s['frac_unchanged']:>6.0f}%")

        print(f"\n  By original {OVERALL_FIELD} bucket:")
        for attr in sorted(by_pert_attr_bin[pert]):
            bin_summary = by_pert_attr_bin[pert][attr]
            print(f"  {attr}:")
            for label, _, _ in bins:
                s = bin_summary.get(label)
                if s is None or s["n"] == 0:
                    print(f"    {label:<16} n=0")
                    continue
                print(f"    {label:<16} n={s['n']:<4} mean Δ={s['mean_delta']:>7.3f}  "
                      f"std Δ={s['std_delta']:>6.3f}  %up={100*s['frac_increased']:>5.0f}%  "
                      f"%down={100*s['frac_decreased']:>5.0f}%  %same={100*s['frac_unchanged']:>5.0f}%")
        print()


def write_json(path, by_pert_attr, by_pert_attr_bin, bins, baseline_skipped, per_pert_skipped, n_baseline):
    payload = {
        "n_baseline_reviews": n_baseline,
        "baseline_skipped": baseline_skipped,
        "bins": [{"label": l, "lo": lo, "hi": hi} for l, lo, hi in bins],
        "per_perturbation_skipped_papers": per_pert_skipped,
        "overall": by_pert_attr,
        "by_original_overall_assessment_bucket": by_pert_attr_bin,
    }
    path.write_text(json.dumps(payload, indent=2))


def write_raw_csv(path, records):
    fields = ["perturbation", "venue", "model", "paper_id", "attribute", "base", "pert", "delta", "base_overall"]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tests-dir", type=Path, default=TESTS_DIR, help="directory containing reviews*/ folders")
    parser.add_argument("--output", type=Path, default=None, help="write full aggregate stats as JSON here")
    parser.add_argument("--raw-csv", type=Path, default=None, help="write every individual (paper, attribute) delta as CSV here")
    parser.add_argument("--quiet", action="store_true", help="skip the console report")
    args = parser.parse_args()

    baseline_root = args.tests_dir / BASELINE_DIR_NAME
    if not baseline_root.is_dir():
        parser.error(f"baseline directory not found: {baseline_root}")

    baseline_reviews, baseline_skipped = discover_baseline(baseline_root)

    perturbation_dirs = sorted(
        d for d in args.tests_dir.glob(f"{BASELINE_DIR_NAME}_*") if d.is_dir()
    )
    if not perturbation_dirs:
        parser.error(f"no {BASELINE_DIR_NAME}_* perturbation directories found under {args.tests_dir}")

    score_fields_cache = {}
    records, per_pert_skipped = collect_deltas(baseline_reviews, perturbation_dirs, score_fields_cache)

    by_pert_attr, by_pert_attr_bin = aggregate(records, DEFAULT_BINS)

    if not args.quiet:
        print_report(by_pert_attr, by_pert_attr_bin, DEFAULT_BINS, baseline_skipped, per_pert_skipped, len(baseline_reviews))

    if args.output:
        write_json(args.output, by_pert_attr, by_pert_attr_bin, DEFAULT_BINS, baseline_skipped, per_pert_skipped, len(baseline_reviews))
        print(f"Wrote aggregate stats to {args.output}")

    if args.raw_csv:
        write_raw_csv(args.raw_csv, records)
        print(f"Wrote raw deltas to {args.raw_csv}")


if __name__ == "__main__":
    main()
