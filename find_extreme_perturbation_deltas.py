"""Find the papers whose score moved the most under each perturbation.

For every perturbation directory (tests/reviews_<perturbation>/) this finds,
on a chosen attribute (default: overall_assessment), the paper(s) with the
biggest increase and the biggest decrease relative to the original review in
tests/reviews/. Useful for spot-checking *why* a perturbation shifted a score
so much, by pointing you straight at the most extreme before/after pair.

Reuses the discovery/loading logic from analyze_perturbation_scores.py so the
two scripts stay consistent about what counts as a "usable" review.

Usage:
    python find_extreme_perturbation_deltas.py
    python find_extreme_perturbation_deltas.py --model gpt-5-mini --top 3
    python find_extreme_perturbation_deltas.py --attribute soundness --output extremes.json
"""

import argparse
import json
from pathlib import Path

from analyze_perturbation_scores import (
    BASELINE_DIR_NAME,
    OVERALL_FIELD,
    TESTS_DIR,
    available_models,
    available_perturbing_models,
    discover_baseline,
    is_number,
    load_review,
    resolve_model_choice,
)

SUMMARY_FIELD = "paper_summary"
SUMMARY_EXCERPT_LEN = 200


def collect_attribute_deltas(baseline_reviews, perturbation_dirs, attribute, perturbing_model):
    """Return {perturbation: [record, ...]} for every usable (base, pert) pair,
    where record = {venue, model, perturbing_model, paper_id, base, pert, delta, summary}."""
    by_pert = {}
    for pert_dir in perturbation_dirs:
        pert_name = pert_dir.name[len(f"{BASELINE_DIR_NAME}_"):]
        records = []
        for (venue, model, paper_id), base_review in baseline_reviews.items():
            base_val = base_review.get(attribute)
            if not is_number(base_val):
                continue
            pert_review = load_review(pert_dir / venue / perturbing_model / model / paper_id)
            if pert_review is None:
                continue
            pert_val = pert_review.get(attribute)
            if not is_number(pert_val):
                continue
            summary = base_review.get(SUMMARY_FIELD)
            summary_excerpt = summary[:SUMMARY_EXCERPT_LEN] if isinstance(summary, str) else ""
            records.append({
                "perturbation": pert_name,
                "venue": venue,
                "model": model,
                "perturbing_model": perturbing_model,
                "paper_id": paper_id,
                "base": base_val,
                "pert": pert_val,
                "delta": pert_val - base_val,
                "summary_excerpt": summary_excerpt,
            })
        by_pert[pert_name] = records
    return by_pert


def top_extremes(records, top_n):
    """Return (top_increases, top_decreases), each a list of up to top_n
    records sorted from most extreme to least. Ties broken by paper_id for
    determinism."""
    by_increase = sorted(records, key=lambda r: (-r["delta"], r["paper_id"]))
    by_decrease = sorted(records, key=lambda r: (r["delta"], r["paper_id"]))
    increases = [r for r in by_increase if r["delta"] > 0][:top_n]
    decreases = [r for r in by_decrease if r["delta"] < 0][:top_n]
    return increases, decreases


def fmt_record(r):
    return (f"{r['paper_id']} ({r['venue']}, perturbed by {r['perturbing_model']}, reviewed by {r['model']})  "
            f"{r['base']:g} -> {r['pert']:g}  (delta={r['delta']:+g})")


def print_report(by_pert, attribute, top_n):
    print("=" * 100)
    print(f"EXTREME PERTURBATION DELTAS — attribute: {attribute}")
    print("=" * 100)

    for pert_name in sorted(by_pert):
        records = by_pert[pert_name]
        print("-" * 100)
        print(f"Perturbation: {pert_name}  (usable pairs: {len(records)})")
        print("-" * 100)
        if not records:
            print("  (no usable pairs)\n")
            continue

        increases, decreases = top_extremes(records, top_n)

        print(f"  Biggest increase(s) (top {top_n}):")
        if not increases:
            print("    (none — no positive deltas)")
        for r in increases:
            print(f"    {fmt_record(r)}")
            if r["summary_excerpt"]:
                print(f"      \"{r['summary_excerpt']}...\"")

        print(f"  Biggest decrease(s) (top {top_n}):")
        if not decreases:
            print("    (none — no negative deltas)")
        for r in decreases:
            print(f"    {fmt_record(r)}")
            if r["summary_excerpt"]:
                print(f"      \"{r['summary_excerpt']}...\"")
        print()


def write_json(path, by_pert, attribute, top_n):
    payload = {"attribute": attribute, "top_n": top_n, "perturbations": {}}
    for pert_name, records in by_pert.items():
        increases, decreases = top_extremes(records, top_n)
        payload["perturbations"][pert_name] = {
            "n_usable_pairs": len(records),
            "top_increases": increases,
            "top_decreases": decreases,
        }
    path.write_text(json.dumps(payload, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tests-dir", type=Path, default=TESTS_DIR, help="directory containing reviews*/ folders")
    parser.add_argument("--model", type=str, default=None,
                         help="only consider reviews written by this reviewing model (the <model> "
                              "path component under tests/reviews/<venue>/<model>/<paper_id>, and the "
                              "second/<reviewing_model> component under tests/reviews_<perturbation>/"
                              "<venue>/<perturbing_model>/<reviewing_model>/<paper_id>); if omitted "
                              "and multiple models are present, you will be prompted to pick one")
    parser.add_argument("--perturbing-model", type=str, default=None,
                         help="only consider perturbed reviews whose LaTeX was perturbed by this "
                              "model (the <perturbing_model> path component under tests/reviews_"
                              "<perturbation>/<venue>/<perturbing_model>/<reviewing_model>/<paper_id>); "
                              "if omitted, defaults to --model (a model reviewing its own "
                              "perturbations, the common case) when that's available, else you'll "
                              "be prompted")
    parser.add_argument("--attribute", type=str, default=OVERALL_FIELD,
                         help=f"score field to rank deltas on (default: {OVERALL_FIELD})")
    parser.add_argument("--top", type=int, default=1, help="how many extreme samples to show per side (default: 1)")
    parser.add_argument("--output", type=Path, default=None, help="write full results as JSON here")
    parser.add_argument("--quiet", action="store_true", help="skip the console report")
    args = parser.parse_args()

    baseline_root = args.tests_dir / BASELINE_DIR_NAME
    if not baseline_root.is_dir():
        parser.error(f"baseline directory not found: {baseline_root}")

    models = available_models(baseline_root)
    if not models:
        parser.error(f"no <venue>/<model>/<paper_id> reviews found under {baseline_root}")
    args.model = resolve_model_choice(parser, args.model, models, "reviewing model", "--model")

    baseline_reviews, baseline_skipped = discover_baseline(baseline_root, args.model)

    perturbation_dirs = sorted(
        d for d in args.tests_dir.glob(f"{BASELINE_DIR_NAME}_*") if d.is_dir()
    )
    if not perturbation_dirs:
        parser.error(f"no {BASELINE_DIR_NAME}_* perturbation directories found under {args.tests_dir}")

    perturbing_models = available_perturbing_models(args.tests_dir, args.model)
    if not perturbing_models:
        parser.error(f"no perturbed reviews found for reviewing model {args.model!r} under {args.tests_dir}")
    if args.perturbing_model is None and args.model in perturbing_models:
        # Default: a model reviewing its own perturbations (the common
        # case). Only falls through to resolve_model_choice() below when
        # that's not available.
        args.perturbing_model = args.model
    else:
        args.perturbing_model = resolve_model_choice(
            parser, args.perturbing_model, perturbing_models, "perturbing model", "--perturbing-model"
        )

    by_pert = collect_attribute_deltas(baseline_reviews, perturbation_dirs, args.attribute, args.perturbing_model)

    if not args.quiet:
        print_report(by_pert, args.attribute, args.top)

    if args.output:
        write_json(args.output, by_pert, args.attribute, args.top)
        print(f"Wrote extreme deltas to {args.output}")


if __name__ == "__main__":
    main()
