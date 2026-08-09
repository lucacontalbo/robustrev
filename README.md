# robustrev

A toolkit for studying how robust LLM-as-reviewer systems are to
visible-text adversarial framing in academic papers (see
`attacks_on_reviewers.txt`). It has three parts:

1. **Review** a LaTeX paper: compile it to PDF and ask a language model
   (Claude, GPT, or a local vLLM model) to fill out a conference review
   form (e.g. ICLR, ACL).
2. **Perturb** a paper: apply one of a catalog of adversarial-framing edits
   (citation padding, boosting language, verbosity, rubric capture, ...) to
   its LaTeX source, producing a modified copy that still compiles.
3. **Scrape** a dataset of real arXiv papers with compilable LaTeX source,
   to have material to run (1) and (2) against at scale.

## How it works

1. **`latex_compile.py`** finds the `\documentclass` root of a LaTeX
   project — trying every candidate root and keeping the first that
   actually compiles, rather than guessing from the filename — and
   compiles it to PDF with `latexmk`. Shared by everything below.
2. **`reviewer.py`** loads a review rubric from `rubrics/` (e.g.
   `iclr_rubric.yaml`, `acl_rubric.yaml`), builds a prompt from its fields,
   sends the PDF (or extracted text, if the model doesn't accept PDFs) to
   the model, and parses the model's response into a `{field_id: answer}`
   dict.
3. **`perturber.py`** loads the perturbation catalog from
   `perturbations_config.yaml`, picks a random eligible section of a paper
   for a given perturbation, and calls a model once to rewrite it (or, for
   the two review-based perturbations, to rewrite it *using a baseline
   review of the unperturbed paper as context*). Writes a
   `PERTURBATION_CHANGES.md` next to the paper recording exactly what
   changed, no extra model call needed.
4. **`models.py`** wraps the supported model backends: `AnthropicModel`,
   `OpenAIModel`, and `VLLMModel` (for OpenAI-compatible local servers).
5. **`robustrev.py`** is the CLI entry point (`review` / `perturb`
   subcommands) that ties the above together.
6. **`scrape_papers.py`** is a standalone script (no model calls) that
   pulls papers from arXiv, keeping only ones whose LaTeX source actually
   compiles with `latex_compile.py`.

## Setup

Requires Python >= 3.9 and a LaTeX distribution providing `latexmk` (e.g.
TeX Live) installed and on your `PATH` — the `latexmk` line in
`requirements.txt` is the system binary, not a pip package, so install it
via your OS package manager. Note that a base/partial TeX Live install
(e.g. `texlive-base`, `texlive-latex-recommended`) does **not** include it:

```bash
sudo apt install latexmk          # Debian/Ubuntu
tlmgr install latexmk             # any TeX Live via tlmgr
```

A partial TeX Live install will also fail to compile most real papers with
missing font/package errors (e.g. `phvb.tfm not found`, `tcolorbox.sty not
found`). Rather than chasing individual missing files, install the common
bundles up front:

```bash
sudo apt-get install -y texlive-fonts-recommended texlive-latex-extra texlive-pictures texlive-science texlive-fonts-extra
```

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

or install the project itself (registers the `robustrev` command via
`pyproject.toml`):

```bash
pip install -e .
```

Set API keys for whichever model backend(s) you plan to use — either as
environment variables, or in a `.env` file in the repo root (auto-loaded
via `python-dotenv`):

```bash
export ANTHROPIC_API_KEY=...   # for model_class: anthropic
export OPENAI_API_KEY=...      # for model_class: openai
```

A local `vllm` model needs no API key by default; it talks to an
OpenAI-compatible server (default `http://localhost:8000/v1`).

## Running a review

```bash
python robustrev.py review <model_id> <conference> <directory>
# or, if installed via `pip install -e .`:
robustrev review <model_id> <conference> <directory>
```

- `model_id` — one of the entries in `models_config.yaml`
  (e.g. `claude-opus-4-8`, `gpt-4o-mini`, `gpt-5-mini`, `llama-3-70b`).
- `conference` — which rubric to grade against: the name of a
  `rubrics/<conference>_rubric.yaml` file, e.g. `iclr` or `acl`.
- `directory` — a single LaTeX project directory, a directory of several
  such projects, or `perturbed_papers/` itself (see below) to review every
  perturbed variant of every paper in one go.

Example:

```bash
robustrev review claude-opus-4-8 iclr papers/my-submission
```

For each project reviewed, the compiled PDF and the resulting
`review.json` are written to:

```
tests/reviews/<conference>/<model_id>/<project_name>/
```

...except when reviewing something under `perturbed_papers/`, where the
perturbation's id is folded into the output directory name instead, so
different variants of the same paper don't overwrite each other:

```
tests/reviews_<perturbation_id>/<conference>/<model_id>/<project_name>/
```

If compiling or reviewing a given paper/perturbation fails, `review`
doesn't abort the whole batch — it records the traceback in `error.txt`
in the directory `review.json` would have gone to, prints a one-line
summary, and moves on to the next one.

## Perturbing papers

```bash
robustrev perturb <model_id> [--papers NAME ...] [--perturbations ID ...] [--conference CONF] [--review-model-id MODEL_ID]
```

Applies adversarial-framing perturbations (see `attacks_on_reviewers.txt`
and `perturbations_config.yaml`) to every paper under `papers/`, writing
each `(paper, perturbation)` combination to its own directory:

```
perturbed_papers/<paper_name>/<perturbation_id>/<complete perturbed LaTeX project>
PERTURBATION_CHANGES.md   # inside that directory: what changed and why, no extra model call
```

- `model_id` — the model used to generate the perturbed text.
- `--papers` — only perturb these paper names (default: every project
  under `papers/`).
- `--perturbations` — only apply these perturbation ids (default: all of
  them — see `perturbations_config.yaml` for the full catalog, or run
  `python -c "import perturber,yaml; print(sorted(p['id'] for p in yaml.safe_load(perturber.CONFIG_PATH.read_text())['perturbations']))"`).
- `--conference` / `--review-model-id` — two of the thirteen perturbations,
  `rubric_capture` and `disarming_framing`, are *review-based*: they first
  need a baseline review of the **unperturbed** paper (e.g. to know which
  rubric axis to lean on, or which weakness to pre-empt), generated once
  per paper and reused across both. `--conference` picks the rubric for
  that baseline review (required if either is among the perturbations run);
  `--review-model-id` picks the model that generates it, independently of
  `model_id` (defaults to `model_id` if not given).

If a perturbation doesn't apply to a given paper (no matching section, or
its precondition wasn't met — e.g. `resource_overweighting` on a paper
that releases nothing) or produced no change, nothing is written for that
combination — `perturbed_papers/` only ever contains directories that are
actually different from the source.

## Scraping papers

```bash
python scrape_papers.py --target 1000
```

Pulls papers from arXiv (`cs.CL`/`cs.LG`/`stat.ML`/`cs.AI`/`cs.NE` by
default, 2025 onward) and keeps only ones with a LaTeX source that
actually compiles with `latex_compile.py` — no model calls involved.
Output mirrors `papers/`'s layout, keyed by arXiv id instead of a title:

```
scraped_papers/<arxiv_id>/latex/<source + compiled PDF>
scraped_papers/<arxiv_id>/metadata.json   # title, year, categories, source URL
```

Resumable and rate-limited (see `--api-delay`/`--download-delay`; arXiv
discourages large-scale scripted pulls from the `/e-print/` endpoint, so
this is deliberately polite rather than fast) — progress is checkpointed
to `scraped_papers_state.json` after every paper, so it's safe to kill and
rerun the same command; per-attempt outcomes are logged to
`scraped_papers_log.jsonl`. Run `python scrape_papers.py --help` for all
options (categories, start year, page size, compile timeout, ...).

## Configuring models

Models available to `robustrev review`/`perturb` are declared in
`models_config.yaml`. Each entry has:

- `model_id` — the identifier passed on the command line.
- `model_name` — the actual model name/path passed to the backend client.
- `model_class` — one of `anthropic`, `openai`, or `vllm` (must match a key
  in `MODEL_CLASSES` in `reviewer.py`/`perturber.py`).

Add a new entry there to make another model available.

## Adding a rubric

Rubrics live in `rubrics/<conference>_rubric.yaml` and define the
`conference`, `edition`, and a list of `fields` (each with an `id`,
`question`, `type`, and optionally `scale`/`options`). Fields marked
`applies_to: human_reviewer_only` are skipped for LLM reviews. See
`rubrics/iclr_rubric.yaml` and `rubrics/acl_rubric.yaml` for examples.

## Adding a perturbation

Perturbations live in `perturbations_config.yaml`. Each entry declares
which structural `roles` (introduction, related_work, limitations, ...) it
can target — resolved generically via `LatexCompiler.find_structure()`,
not per-paper — whether it needs a baseline review (`mechanism:
review_based`) or just the paper text (`zero_shot`), and what to do if no
matching section exists (`fallback: create` or `skip`). All the
perturbation-specific instruction text lives in each entry's `description`
— the prompt template in `perturber.py` stays generic across all of them.

## Call logging with Phoenix (optional)

`robustrev.py` auto-instruments model calls via
[Arize Phoenix](https://github.com/Arize-ai/phoenix) if a collector is
reachable at `localhost:4317`/`localhost:6006`. To run one locally:

```bash
docker pull arizephoenix/phoenix:latest
docker run -d -p 6006:6006 -p 4317:4317 -i -t arizephoenix/phoenix:latest
```

View traces at `http://localhost:6006`. Without a collector running,
tracing calls just fail silently in the background — everything else
still works.
