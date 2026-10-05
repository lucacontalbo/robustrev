"""Review papers with ReviewerToo (Sahu et al., 2025, "ReviewerToo: Should AI
Join The Program Committee?", https://arxiv.org/abs/2510.08867).

The authors' code is vendored unmodified in rtoo/ (from their supplementary
material). For each paper this script calls their own
main.process_single_paper(), i.e. their full pipeline minus the LitLLM
literature search (it needs live internet access to Semantic Scholar /
OpenAlex / arXiv / Serper, which compute nodes don't have):

    13 persona reviews -> one author rebuttal per review -> 7-stage metareview

with gpt-oss-120b (served by vLLM) as the backbone for every agent.

It is otherwise a drop-in counterpart of `robustrev.py review`, and
deliberately doesn't import anything from it: same CLI, same paper discovery
(papers/ projects or the perturbed_papers/ tree), same resumability, and the
same output layout -- review.json with the rubric's field ids, the compiled
PDF, and raw_response.txt (here: the final metareview) -- plus a reviewertoo/
directory with every intermediate ReviewerToo output (markdown paper,
persona reviews, rebuttals, metareview stages).

ReviewerToo produces no sub-scores and its final decision is categorical, so
the numeric score is the mean of the persona reviews' ratings (out of 10,
ICLR scale), mapped onto the ACL scale the same way as for the other native
review formats in robustrev.

Compute nodes have no internet access, so `review` runs fully offline (see
go_offline()): only the vLLM server can be reached, and every model docling
needs must already be on disk (setup_reviewertoo.sh downloads them).
"""
import argparse
import asyncio
import contextlib
import functools
import ipaddress
import json
import math
import os
import re
import shutil
import socket
import sys
import tempfile
import traceback
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from tqdm import tqdm

HERE = Path(__file__).resolve().parent
ROBUSTREV_DIR = HERE.parent
RTOO_DIR = HERE / "rtoo"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(RTOO_DIR))

from latex_compile import LatexCompiler  # noqa: E402  (verbatim copy of robustrev's)

# Shared with robustrev.py: where papers are read from and reviews written to,
# and the rubrics whose field ids review.json uses.
OUTPUT_DIR = ROBUSTREV_DIR / "tests" / "reviews"
PERTURBED_DIR = ROBUSTREV_DIR / "perturbed_papers"
RUBRIC_DIR = ROBUSTREV_DIR / "rubrics"

# model_id (CLI / output directory name) -> ReviewerToo model string. The
# "vllm/" prefix routes requests to $VLLM_BASE_URL (see
# rtoo/src/services/llm_service_router.py); the rest is the model name vLLM
# must serve it under (--served-model-name).
MODEL_IDS = {
    "ReviewerToo-gpt-oss-120b": "vllm/openai/gpt-oss-120b",
}

PAPER_ID = "paper"  # name of the single paper in each per-paper ReviewerToo run
WORK_DIRNAME = "reviewertoo"  # per-paper ReviewerToo run, next to review.json
# Number of persona reviews main.process_single_paper() runs (its
# review_configs list).
N_PERSONAS = 13


# ---------------------------------------------------------------------------
# Paper discovery and compilation: same logic as robustrev.py.

def compiles(compiler, project_dir):
    """Whether `project_dir` has a working LaTeX root, checked on a scratch
    copy so concurrent runs over the same shared tree can't race."""
    with tempfile.TemporaryDirectory(prefix="robustrev_discover_") as tmp:
        work_dir = Path(tmp) / project_dir.name
        shutil.copytree(project_dir, work_dir)
        try:
            compiler.find_root(work_dir)
            return True
        except FileNotFoundError:
            return False


def find_projects(directory, compiler):
    """A `directory` is either one LaTeX project itself, or a directory of them."""
    directory = Path(directory)
    projects = [
        sub for sub in tqdm(sorted(directory.iterdir()), desc="finding latex projects", unit="project")
        if sub.is_dir() and compiles(compiler, sub)
    ]
    if projects:
        return projects
    compiler.find_root(directory)  # raises FileNotFoundError if not a project either
    return [directory]


def find_perturbed_projects(directory):
    """Yield (project_dir, paper_name, perturbation_id, perturbing_model_id)
    for every perturbed_papers/<perturbing_model_id>/<paper>/<perturbation_id>/
    leaf under `directory`, which can be anchored at any level of that tree."""
    directory = Path(directory).resolve()
    root = PERTURBED_DIR.resolve()
    depth_here = 0 if directory == root else len(directory.relative_to(root).parts)
    remaining = max(0, 3 - depth_here)  # levels left to reach <model>/<paper>/<pert>
    candidates = [directory] if remaining == 0 else sorted(directory.glob("/".join(["*"] * remaining)))
    for project_dir in candidates:
        if not project_dir.is_dir():
            continue
        perturbing_model_id, paper_name, pert_id = project_dir.relative_to(root).parts
        yield project_dir, paper_name, pert_id, perturbing_model_id


@contextlib.contextmanager
def isolated_compile(compiler, project_dir):
    """Compile `project_dir` in a private scratch copy rather than in place,
    so concurrent compiles of the same shared project can't race."""
    with tempfile.TemporaryDirectory(prefix="robustrev_compile_") as tmp:
        work_dir = Path(tmp) / project_dir.name
        shutil.copytree(project_dir, work_dir)
        yield compiler.compile_pdf(work_dir)


# ---------------------------------------------------------------------------
# Running ReviewerToo on one paper.

@functools.cache
def docling_converter():
    """ReviewerToo's docling converter (rtoo/src/utils/file_utils.py: a
    default DocumentConverter()), with its OCR engine fixed rather than
    picked at runtime.

    By default docling's OCR is "auto" (OcrAutoModel): it takes the first
    engine that imports, normally RapidOCR on onnxruntime, but silently
    falls back to RapidOCR on torch, whose weights are different files that
    RapidOCR then tries to download. Asking for RapidOCR on onnxruntime with
    exactly the options auto mode would give it yields the same OCR as the
    default converter, always with the models setup_reviewertoo.sh
    downloaded; if onnxruntime can't be used, conversion fails instead."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import OcrAutoOptions, PdfPipelineOptions, RapidOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    auto = OcrAutoOptions()
    ocr_options = RapidOcrOptions(backend="onnxruntime", mode=auto.mode, lang=auto.lang)
    pipeline_options = PdfPipelineOptions(ocr_options=ocr_options)
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)})


def pdf_to_markdown(pdf_path):
    """The paper as markdown, converted as ReviewerToo does, as its reviewers
    expect."""
    return docling_converter().convert(str(pdf_path)).document.export_to_markdown()


def reviewertoo_config(work_dir, model):
    """The config main.process_single_paper() reads (the repo's
    configs/reviewertoo_configs.yml isn't part of the supplementary
    material): every stage but LitLLM, every agent on `model`."""
    return {
        # process_single_paper() reads the paper from
        # <dirname(input_data_path)>/markdown/<paper_id>.md.
        "input_data_path": str(work_dir / "input.json"),
        "base_output_dir": str(work_dir / "output"),
        "cache_dir": str(work_dir / "cache"),
        "models": {"litllm": model, "reviewer": model, "author": model, "metareviewer": model},
        "pipeline_stages": {
            "run_litllm": False,
            "run_review_gauntlet": True,
            "run_rebuttal": True,
            "run_metareview": True,
        },
        "reviewer_config": {"concurrency_limit": N_PERSONAS, "force_rerun": False, "papers_per_category": None},
        "author_config": {"concurrency_limit": N_PERSONAS},
        "ingest_reviews_of": None,
        "api_settings": {"email": None},
        "litllm_config": {"deep_research": False, "selection_mode": None, "enable_llm_fallback": False},
    }


def safify(name):
    """ReviewerToo's directory-name sanitiser (main.safify)."""
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)


def run_reviewertoo(pdf_path, work_dir, model):
    """Run the pipeline on `pdf_path` in the new directory `work_dir`.

    `work_dir` should be a fresh scratch directory: ReviewerToo decides
    which review file its author agent reads by looking for "composite" /
    "monolithic" anywhere in the path (rtoo/src/agents/author/types/
    composite.py), so a paper or perturbation name containing either word
    would break it; and process_single_paper() reuses any persona review
    already on disk, which must not happen with one left by a failed run."""
    import main as rtoo_main  # rtoo/main.py

    (work_dir / "markdown").mkdir(parents=True)
    (work_dir / "markdown" / f"{PAPER_ID}.md").write_text(pdf_to_markdown(pdf_path), encoding="utf-8")
    config = reviewertoo_config(work_dir, model)
    (work_dir / "reviewertoo_config.yml").write_text(yaml.safe_dump(config, sort_keys=False))
    asyncio.run(rtoo_main.process_single_paper(config, "robustrev", PAPER_ID, {"title": "N/A"}))


def run_output_dir(work_dir):
    """Where a run in `work_dir` leaves its reviews/, rebuttals/ and
    metareviews/."""
    return work_dir / "output" / safify(PAPER_ID)


# ---------------------------------------------------------------------------
# Reading ReviewerToo's outputs.

_RATING_RE = re.compile(r"<rating>(.*?)</rating>", re.DOTALL | re.IGNORECASE)
_DECISION_RE = re.compile(r"<final_decision>(.*?)</final_decision>", re.DOTALL | re.IGNORECASE)
# The sections the persona prompts ask for ("ICLR Review Structure" in
# rtoo/src/prompts/reviewer/*.py), plus the closing ones that end them.
_SECTIONS = {
    "summary of contributions": "summary",
    "strengths": "strengths",
    "weaknesses": "weaknesses",
    "questions for the authors": "questions",
    "suggestions for improvement": "suggestions",
}
_HEADING_RE = re.compile(
    r"^[ \t>]*(?:#{1,6}[ \t]*)?(?:\d+[.)][ \t]*)?(?:\*\*|__)?[ \t]*"
    r"(Summary of Contributions|Strengths|Weaknesses|Questions for the Authors|Suggestions for Improvement"
    r"|Final Recommendation|Overall Recommendation|Final Evaluation)\b([^\n]*)$",
    re.IGNORECASE | re.MULTILINE,
)


def _first_number(text):
    m = re.search(r"\d+(?:\.\d+)?", text or "")
    return float(m.group()) if m else None


def parse_persona_review(text):
    """{"rating": float | None, <section>: str} from one persona review.
    Headings may be markdown headings or bold lines, optionally numbered,
    with the section's text either below or on the same line."""
    review = {"rating": None}
    ratings = _RATING_RE.findall(text)
    if ratings:
        review["rating"] = _first_number(ratings[-1])
    headings = list(_HEADING_RE.finditer(text))
    for h, nxt in zip(headings, headings[1:] + [None]):
        key = _SECTIONS.get(h.group(1).lower())
        if key is None or key in review:
            continue
        inline = re.sub(r"^[\s:*_]*", "", h.group(2)).rstrip("*_ \t")
        body = text[h.end():nxt.start() if nxt else len(text)]
        body = _RATING_RE.sub("", _DECISION_RE.sub("", body))
        section = "\n".join(filter(None, [inline, body.strip().strip("-").strip()])).strip()
        if section:
            review[key] = section
    return review


def collect_outputs(output_dir, model):
    """The persona reviews and final metareview of a finished run, checked
    for completeness. ReviewerToo swallows most LLM errors (saving an error
    string as the review, or skipping a rebuttal) and carries on, so a run
    only counts if every persona review has a rating, every review got a
    rebuttal, and the metareview reached its final decision."""
    reviews_root = output_dir / "reviews" / safify(model) / "monolithic"
    persona_reviews, problems = {}, []
    for path in sorted(reviews_root.glob("*/monolithic_review.md")):
        review = parse_persona_review(path.read_text(encoding="utf-8"))
        if review["rating"] is None:
            problems.append(f"persona '{path.parent.name}' review has no <rating>")
        persona_reviews[path.parent.name] = review
    if len(persona_reviews) != N_PERSONAS:
        problems.append(f"{len(persona_reviews)}/{N_PERSONAS} persona reviews were written")

    rebuttals = [p for p in (output_dir / "rebuttals").glob("*/*/*/*/rebuttal.md") if p.read_text(encoding="utf-8").strip()]
    if len(rebuttals) != N_PERSONAS:
        problems.append(f"{len(rebuttals)}/{N_PERSONAS} rebuttals were written")

    meta_dir = output_dir / "metareviews" / safify(model) / "composite" / "default"
    for stage in ("1_initial_stance", "2_key_points", "3_rebuttal_analysis", "7_final_synthesis"):
        path = meta_dir / f"{stage}.md"
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            problems.append(f"metareview stage {stage} is missing or empty")
    final_path = meta_dir / "7_final_synthesis.md"
    metareview = final_path.read_text(encoding="utf-8") if final_path.exists() else ""
    if metareview.strip() and not _DECISION_RE.search(metareview):
        problems.append("final metareview has no <final_decision>")

    if problems:
        raise RuntimeError("incomplete ReviewerToo run: " + "; ".join(problems))
    return persona_reviews, metareview


# ---------------------------------------------------------------------------
# Mapping onto the rubric (same mapping as robustrev's native review formats).

def _interp(x, points, step=0.5):
    """Piecewise-linear map of x through (src, dst) anchor points, clamped to
    the ends and rounded half-up to the target scale's step."""
    if x is None:
        return None
    x = min(max(x, points[0][0]), points[-1][0])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            y = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
            return math.floor(y / step + 0.5) * step
    return points[-1][1]


# ICLR rating 1-10 -> ACL overall_assessment 1-5, anchored on the labels:
# 1 strong reject -> 1 do not resubmit; 3 reject -> 2 resubmit next cycle;
# 5 marginally below -> 3 findings; 6 marginally above -> 3.5 borderline
# conference; 8 accept -> 4 conference; 10 strong accept -> 5 award.
_ICLR_RATING_TO_ACL_OVERALL = [(1, 1), (3, 2), (5, 3), (6, 3.5), (8, 4), (10, 5)]


def to_rubric(persona_reviews, conference):
    """Map the persona reviews onto the iclr or acl rubric's field ids: the
    rating is their mean, each text field lists every persona's text.
    ReviewerToo gives no sub-scores (soundness, confidence, ...), so those
    are left out (and end up "N/A")."""
    ratings = [r["rating"] for r in persona_reviews.values()]
    rating = sum(ratings) / len(ratings)

    def joined(key):
        return "\n\n".join(
            f"Reviewer ({persona}):\n{r[key]}" for persona, r in persona_reviews.items() if r.get(key)
        ) or None

    if conference == "iclr":
        return {
            "summary": joined("summary"),
            "strengths": joined("strengths"),
            "weaknesses": joined("weaknesses"),
            "questions": joined("questions"),
            "rating": rating,
        }
    if conference == "acl":
        overall = _interp(rating, _ICLR_RATING_TO_ACL_OVERALL)
        comments = "\n\n".join(filter(None, [joined("suggestions"), joined("questions")]))
        return {
            "paper_summary": joined("summary"),
            "summary_of_strengths": joined("strengths"),
            "summary_of_weaknesses": joined("weaknesses"),
            "comments_suggestions_typos": comments or None,
            "overall_assessment": overall,
            "best_paper": "yes" if overall >= 4.5 else "no",
        }
    raise ValueError(f"no ReviewerToo mapping for rubric '{conference}' (supported: iclr, acl)")


def rubric_fields(conference):
    rubric = yaml.safe_load((RUBRIC_DIR / f"{conference}_rubric.yaml").read_text())
    return [f["id"] for f in rubric["fields"] if f.get("applies_to") != "human_reviewer_only"]


# ---------------------------------------------------------------------------

class NoInternetError(ConnectionRefusedError):
    """A connection go_offline() blocked."""


def go_offline():
    """Make this process unable to reach anything but the vLLM server.

    Compute nodes have no internet access, and a library trying to download
    something there would only fail after timing out (once per paper). This
    puts the Hugging Face libraries (docling's layout and table models) in
    offline mode, and makes every socket connection to a host other than
    localhost or $VLLM_BASE_URL's fail at once with NoInternetError, naming
    the address. Call it before importing docling or ReviewerToo."""
    for var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        os.environ[var] = "1"

    allowed = set()
    vllm_host = urlsplit(os.environ.get("VLLM_BASE_URL", "")).hostname
    if vllm_host:
        allowed.add(vllm_host)
        with contextlib.suppress(OSError):
            allowed.update(info[4][0] for info in socket.getaddrinfo(vllm_host, None))

    def is_allowed(sock, address):
        if sock.family not in (socket.AF_INET, socket.AF_INET6):
            return True  # e.g. Unix sockets
        host = address[0]
        if host in allowed or host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host.split("%")[0]).is_loopback
        except ValueError:
            return False

    def guarded(method):
        @functools.wraps(method)
        def wrapper(sock, address, *args, **kwargs):
            if not is_allowed(sock, address):
                raise NoInternetError(f"internet access is disabled (blocked connection to {address})")
            return method(sock, address, *args, **kwargs)
        return wrapper

    socket.socket.connect = guarded(socket.socket.connect)
    socket.socket.connect_ex = guarded(socket.socket.connect_ex)


def review(args):
    go_offline()
    if args.model_id not in MODEL_IDS:
        raise ValueError(f"unknown model_id '{args.model_id}'; choices are {sorted(MODEL_IDS)}")
    model = MODEL_IDS[args.model_id]
    field_ids = rubric_fields(args.conference)
    compiler = LatexCompiler()

    directory = Path(args.directory).resolve()
    perturbed_root = PERTURBED_DIR.resolve()
    if directory == perturbed_root or perturbed_root in directory.parents:
        jobs = list(find_perturbed_projects(directory))
    else:
        jobs = [(p, p.name, None, None) for p in find_projects(directory, compiler)]

    bar = tqdm(jobs, desc="reviewing", unit="paper")
    for project_dir, paper_name, pert_name, perturbing_model_id in bar:
        if pert_name is None:
            base_dir, model_path = OUTPUT_DIR, args.model_id
        else:
            base_dir = OUTPUT_DIR.parent / f"{OUTPUT_DIR.name}_{pert_name}"
            model_path = Path(perturbing_model_id) / args.model_id
        out_dir = base_dir / args.conference / model_path / paper_name
        label = f"{paper_name}/{pert_name}" if pert_name else paper_name
        bar.set_postfix_str(label)

        # Resumable: a completed review.json means this exact (paper,
        # perturbation, model, conference) was already reviewed.
        if not args.force and (out_dir / "review.json").exists():
            tqdm.write(f"already reviewed, skipping {label} (pass --force to redo)")
            continue

        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            kept_dir = out_dir / WORK_DIRNAME
            with isolated_compile(compiler, project_dir) as pdf_path, \
                    tempfile.TemporaryDirectory(prefix="reviewertoo_") as tmp:
                shutil.copy(pdf_path, out_dir / pdf_path.name)
                work_dir = Path(tmp) / "run"
                try:
                    run_reviewertoo(pdf_path, work_dir, model)
                finally:
                    # Keep every intermediate output next to review.json,
                    # replacing any left by an earlier attempt (also on
                    # failure, for debugging).
                    if kept_dir.exists():
                        shutil.rmtree(kept_dir)
                    if work_dir.exists():
                        shutil.copytree(work_dir, kept_dir)
            persona_reviews, metareview = collect_outputs(run_output_dir(kept_dir), model)
            mapped = to_rubric(persona_reviews, args.conference)
            result = {fid: mapped.get(fid) or "N/A" for fid in field_ids}
        except Exception:
            # One bad paper (LaTeX error, incomplete run, ...) shouldn't abort
            # the batch: record the traceback where the review would have
            # gone and move on. A rerun starts that paper over from scratch.
            tb = traceback.format_exc()
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "error.txt").write_text(tb)
            tqdm.write(f"skipped {label}: {tb.rstrip().splitlines()[-1]} (see {out_dir / 'error.txt'})")
            continue

        (out_dir / "raw_response.txt").write_text(metareview, encoding="utf-8")
        (out_dir / "review.json").write_text(json.dumps(result, indent=2))
        tqdm.write(f"reviewed {label} -> {out_dir}")


def main():
    parser = argparse.ArgumentParser(prog="run_reviewertoo")
    subcommands = parser.add_subparsers(dest="command", required=True)
    p_review = subcommands.add_parser("review", help="compile LaTeX paper(s) and review them with ReviewerToo")
    p_review.add_argument("model_id", help=f"one of {sorted(MODEL_IDS)}")
    p_review.add_argument("conference", help="rubric to map the review onto: iclr or acl")
    p_review.add_argument("directory", help="a LaTeX project directory, or a directory of such projects")
    p_review.add_argument("--force", action="store_true",
                          help="re-review papers that already have a review.json (default: skip them)")
    p_review.set_defaults(func=review)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
