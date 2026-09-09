import argparse
import contextlib
import json
import shutil
import tempfile
import traceback
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import yaml
from tqdm import tqdm

from latex_compile import LatexCompiler
from perturber import Perturber
from reviewer import Reviewer

"""from phoenix.otel import register

tracer_provider = register(
    auto_instrument=True,
    batch=True,
    project_name="robustrev",
)"""

CONFIG_PATH = Path(__file__).parent / "models_config.yaml"
OUTPUT_DIR = Path(__file__).parent / "tests" / "reviews"
PAPERS_DIR = Path(__file__).parent / "papers"
PERTURBED_DIR = Path(__file__).parent / "perturbed_papers"


def load_model(model_id):
    for cfg in yaml.safe_load(CONFIG_PATH.read_text()):
        if cfg["model_id"] == model_id:
            return cfg
    raise ValueError(f"unknown model_id '{model_id}' in {CONFIG_PATH}")


def model_kwargs(cfg):
    """Extra models_config.yaml keys beyond the id/name/class routing
    fields (e.g. base_url/api_key/pdf_capable on a vllm entry), forwarded
    straight through to the model class's constructor."""
    return {k: v for k, v in cfg.items() if k not in ("model_id", "model_name", "model_class")}


def find_projects(directory, compiler):
    """A `directory` is either one LaTeX project itself, or a directory of them."""
    directory = Path(directory)
    projects = []
    for sub in tqdm(sorted(directory.iterdir()), desc="finding latex projects", unit="project"):
        if sub.is_dir():
            try:
                compiler.find_root(sub)
                projects.append(sub)
            except FileNotFoundError:
                pass
    if projects:
        return projects
    compiler.find_root(directory)  # raises FileNotFoundError if not a project either
    return [directory]


def perturbation_name(project_dir):
    """If `project_dir` sits under perturbed_papers/<paper>/<perturbation_id>/,
    return <perturbation_id>; else None. Based on path position (2 levels
    below PERTURBED_DIR), not on project_dir's own name, so it works whether
    `review` was pointed at one specific perturbed_papers/<paper>/<pert_id>/
    directory or at perturbed_papers/<paper>/ as a whole (each perturbation
    subdirectory then becomes its own "project" via find_projects())."""
    parts = Path(project_dir).resolve().parts
    if PERTURBED_DIR.name in parts:
        idx = parts.index(PERTURBED_DIR.name)
        if len(parts) > idx + 2:
            return parts[idx + 2]
    return None


def find_perturbed_projects(directory):
    """Walk `directory` (perturbed_papers/) as <paper>/<perturbation_id>/ two
    levels deep, yielding (project_dir, paper_name, perturbation_id) for each
    perturbation variant. Needed because find_projects() only looks one level
    deep: pointed at perturbed_papers/<paper>/, it would find *some*
    compilable root somewhere in that whole multi-perturbation subtree and
    treat the paper dir as a single project, silently ignoring the rest."""
    directory = Path(directory)
    for paper_dir in sorted(directory.iterdir()):
        if not paper_dir.is_dir():
            continue
        for pert_dir in sorted(paper_dir.iterdir()):
            if pert_dir.is_dir():
                yield pert_dir, paper_dir.name, pert_dir.name


@contextlib.contextmanager
def isolated_compile(compiler, project_dir):
    """Compile `project_dir` in a private scratch copy rather than in place.

    LatexCompiler builds inside the project directory itself (required so
    bibtex's cwd-relative .aux/.bbl output matches pdflatex's -outdir; see
    latex_compile.py), and starts every build with `latexmk -C` (a full
    clean). Two review/perturb processes compiling the *same* shared
    papers/ or scraped_papers/ project concurrently (e.g. one process per
    model, on a shared cluster filesystem) can then race: one process's
    clean step deletes the PDF another process just finished building,
    right before it's copied or read out — surfacing as a FileNotFoundError
    on a file that existed a moment earlier. Isolating each compile into
    its own throwaway copy makes concurrent compiles of the same source
    project fully independent, at the cost of one extra copytree per call
    (negligible next to the model call that follows)."""
    with tempfile.TemporaryDirectory(prefix="robustrev_compile_") as tmp:
        work_dir = Path(tmp) / project_dir.name
        shutil.copytree(project_dir, work_dir)
        yield compiler.compile_pdf(work_dir)


def review(args):
    cfg = load_model(args.model_id)
    compiler = LatexCompiler()

    directory = Path(args.directory).resolve()
    if directory == PERTURBED_DIR.resolve():
        jobs = list(find_perturbed_projects(directory))
    else:
        jobs = [(p, p.name, perturbation_name(p)) for p in find_projects(directory, compiler)]

    #jobs = jobs[7890:] # TODO: remove this line when done testing
    bar = tqdm(jobs, desc="reviewing", unit="paper")
    for project_dir, paper_name, pert_name in bar:
        base_dir = OUTPUT_DIR if pert_name is None else OUTPUT_DIR.parent / f"{OUTPUT_DIR.name}_{pert_name}"
        out_dir = base_dir / args.conference / args.model_id / paper_name
        label = f"{paper_name}/{pert_name}" if pert_name else paper_name
        bar.set_postfix_str(label)

        # Resumable: a completed review.json means this exact (paper,
        # perturbation, model, conference) was already reviewed by a
        # previous run — skip it instead of spending another model call.
        # A leftover error.txt from a *failed* attempt doesn't count, so a
        # rerun still retries those (e.g. after fixing the race condition
        # that produced them). --force re-reviews everything regardless.
        if not args.force and (out_dir / "review.json").exists():
            tqdm.write(f"already reviewed, skipping {label} (pass --force to redo)")
            continue

        try:
            with isolated_compile(compiler, project_dir) as pdf_path:
                result = Reviewer(
                    cfg["model_class"], cfg["model_name"], args.conference, pdf_path, **model_kwargs(cfg)
                ).generate_review()
                out_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(pdf_path, out_dir / pdf_path.name)
        except Exception:
            # Compilation, review, or the copy above can fail per
            # paper/perturbation (e.g. a perturbation broke LaTeX syntax);
            # don't let one bad one abort the whole batch. Record the raw
            # traceback (no model call) where the review would have gone,
            # and move on to the next job.
            tb = traceback.format_exc()
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "error.txt").write_text(tb)
            tqdm.write(f"skipped {label}: {tb.rstrip().splitlines()[-1]} (see {out_dir / 'error.txt'})")
            continue

        (out_dir / "review.json").write_text(json.dumps(result, indent=2))
        tqdm.write(f"reviewed {label} -> {out_dir}")


def perturb(args):
    cfg = load_model(args.model_id)
    compiler = LatexCompiler()
    perturber = Perturber(cfg["model_class"], cfg["model_name"], **model_kwargs(cfg))

    projects = find_projects(PAPERS_DIR, compiler)
    if args.papers:
        wanted, have = set(args.papers), {p.name for p in projects}
        if wanted - have:
            raise ValueError(f"unknown paper(s) {sorted(wanted - have)} in {PAPERS_DIR}; choices are {sorted(have)}")
        projects = [p for p in projects if p.name in wanted]

    #projects = projects[640:] # TODO: remove this line when done testing

    pert_ids = args.perturbations or list(perturber.perturbations)
    unknown = set(pert_ids) - set(perturber.perturbations)
    if unknown:
        raise ValueError(f"unknown perturbation id(s) {sorted(unknown)}; choices are {sorted(perturber.perturbations)}")

    # rubric_capture / disarming_framing need a baseline review of the
    # *unperturbed* paper (to know which axis/weakness to target) from a
    # reviewing model — possibly a different one than the perturbing model,
    # hence its own CLI flag.
    review_based = [pid for pid in pert_ids if perturber.perturbations[pid]["mechanism"] == "review_based"]
    if review_based and not args.conference:
        raise ValueError(f"--conference is required to run review-based perturbation(s) {review_based}")
    review_cfg = load_model(args.review_model_id or args.model_id) if review_based else None

    outer = tqdm(projects, desc="perturbing", unit="paper")
    for project_dir in outer:
        outer.set_postfix_str(project_dir.name)
        try:
            baseline_review = None
            if review_based:
                with isolated_compile(compiler, project_dir) as pdf_path:
                    baseline_review = Reviewer(
                        review_cfg["model_class"], review_cfg["model_name"], args.conference, pdf_path,
                        **model_kwargs(review_cfg)
                    ).generate_review()

            inner = tqdm(pert_ids, desc=project_dir.name, unit="perturbation", leave=False)
            for pert_id in inner:
                inner.set_postfix_str(pert_id)
                out_dir = PERTURBED_DIR / args.model_id / project_dir.name / pert_id
                if out_dir.exists():
                    shutil.rmtree(out_dir)
                shutil.copytree(project_dir, out_dir)

                try:
                    changed = perturber.apply_one(out_dir, pert_id, baseline_review)
                except Exception as e:
                    changed = str(e)

                if changed is True:
                    tqdm.write(f"perturbed {project_dir.name}/{pert_id} -> {out_dir}")
                else:
                    shutil.rmtree(out_dir)  # nothing changed; don't leave a copy identical to the original
                    reason = changed if isinstance(changed, str) else "no matching section, or its precondition wasn't met"
                    tqdm.write(f"skipped {project_dir.name}/{pert_id}: {reason}")
        except Exception as e:
            tb = traceback.format_exc()
            tqdm.write(f"skipped {project_dir.name}: {e} (see traceback below)\n{tb}")

def main():
    parser = argparse.ArgumentParser(prog="robustrev")
    subcommands = parser.add_subparsers(dest="command", required=True)

    p_review = subcommands.add_parser("review", help="compile LaTeX paper(s) and review them with an LLM")
    p_review.add_argument("model_id", help="model_id from models_config.yaml")
    p_review.add_argument("conference", help="rubric to review against, e.g. iclr or acl")
    p_review.add_argument("directory", help="a LaTeX project directory, or a directory of such projects")
    p_review.add_argument("--force", action="store_true",
                           help="re-review papers that already have a review.json in the output "
                                "directory (default: skip them)")
    p_review.set_defaults(func=review)

    p_perturb = subcommands.add_parser(
        "perturb", help="apply adversarial-framing perturbations to papers under papers/"
    )
    p_perturb.add_argument("model_id", help="model_id from models_config.yaml, used to generate the perturbed text")
    p_perturb.add_argument(
        "--papers", nargs="+", metavar="NAME",
        help="only perturb these paper project names (default: every project under papers/)",
    )
    p_perturb.add_argument(
        "--perturbations", nargs="+", metavar="ID",
        help="only apply these perturbation ids from perturbations_config.yaml (default: all of them)",
    )
    p_perturb.add_argument(
        "--conference",
        help="rubric to generate the baseline review against, e.g. iclr or acl; required for "
             "review-based perturbations (rubric_capture, disarming_framing)",
    )
    p_perturb.add_argument(
        "--review-model-id",
        help="model_id from models_config.yaml used to generate the baseline review for review-based "
             "perturbations; defaults to model_id (the perturbing model) if not given",
    )
    p_perturb.set_defaults(func=perturb)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
