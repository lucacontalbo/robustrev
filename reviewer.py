import ast
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pypdf import PdfReader

import models

RUBRIC_DIR = Path(__file__).parent / "rubrics"
LOG_PATH = Path(__file__).parent / "log.txt"
MODEL_CLASSES = {
    "anthropic": models.AnthropicModel,
    "openai": models.OpenAIModel,
    "vllm": models.VLLMModel,
    "deepreviewer": models.DeepReviewerModel,
    "cyclereviewer": models.CycleReviewerModel,
}
FINAL_KEYWORD = "FINAL ANSWER:"
# Models for which a direct-PDF submission has already failed once and been
# logged to LOG_PATH in this process. A batch run reviews many papers with
# the same model (a fresh Reviewer per paper), so this is keyed by model
# identity, not by call, to log the fallback once per model rather than once
# per paper.
_pdf_fallback_logged = set()


def _log_pdf_fallback(model_key, error, prompt):
    if model_key in _pdf_fallback_logged:
        return
    _pdf_fallback_logged.add(model_key)
    entry = (
        f"[{datetime.now(timezone.utc).isoformat()}] {model_key}: direct PDF submission failed "
        f"({error!r}); falling back to extracted text for the rest of this run.\n"
        f"--- prompt sent after falling back to text ---\n{prompt}\n"
        f"{'-' * 80}\n"
    )
    with LOG_PATH.open("a") as f:
        f.write(entry)


def _extract_braces(text):
    """Return the first balanced {...} block in text, ignoring braces inside quoted strings."""
    start = text.index("{")
    depth, quote, esc = 0, None, False
    for i, ch in enumerate(text[start:], start):
        if quote:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError("no balanced dict literal found in model output")


def _first_number(text):
    m = re.search(r"\d+(?:\.\d+)?", text or "")
    return float(m.group()) if m else None


def _deepreviewer_sections(raw):
    """Split DeepReviewer's final review into {section name: text}.

    The final review (the meta-review, in standard mode) is wrapped in
    \\boxed_review{...}; per-reviewer drafts in \\boxed_simreviewers{...}
    precede it and are ignored here. If the box is missing (e.g. generation
    was cut off), fall back to the text after the last simulated reviewer."""
    m = re.search(r"\\boxed_review\{(.*?)\n\}", raw, re.DOTALL)
    body = m.group(1) if m else raw.rpartition("\\boxed_simreviewers")[2]
    return {
        name.strip().lower(): text.strip()
        for name, text in re.findall(r"^##\s*([A-Za-z ]+):\s*(.*?)(?=^##\s|\Z)", body, re.DOTALL | re.MULTILINE)
    }


def _deepreviewer_review(raw):
    sec = _deepreviewer_sections(raw)
    return {
        **{k: sec.get(k) for k in ("summary", "strengths", "weaknesses", "suggestions", "questions")},
        **{k: _first_number(sec.get(k)) for k in ("soundness", "presentation", "contribution", "rating", "confidence")},
    }


def _cyclereviewer_review(raw):
    """Combine CycleReviewer's reviews into one.

    It writes several independent reviews (4, as its prompt asks), then a
    meta review and a decision, but no aggregated scores, so each score is
    the mean over the reviews that gave one (as the authors' avg_rating
    does for the rating) and each text field lists every reviewer's text.
    The authors' parser accepts two layouts, depending on the checkpoint:
    reviews separated by "**********" with "## <Section>" headers, or
    started by "## Reviewer" with "### <Section>" headers. Both are
    handled here, with or without a colon after the section name."""
    body = re.split(r"^#{2,3} *Meta Review\b", raw, flags=re.MULTILINE)[0]
    reviews = []
    for block in re.split(r"^\*{5,}\s*$|^#{1,3} *Reviewer\b.*$", body, flags=re.MULTILINE):
        sec = {
            name.strip().lower(): text.strip()
            for name, text in re.findall(
                r"^#{2,3} *([A-Za-z ]+?) *:?[ \t]*\n(.*?)(?=^#{2,3} |\Z)", block, re.DOTALL | re.MULTILINE
            )
        }
        if _first_number(sec.get("rating")) is not None:
            reviews.append(sec)

    def mean(key):
        vals = [v for v in (_first_number(r.get(key)) for r in reviews) if v is not None]
        return sum(vals) / len(vals) if vals else None

    def joined(key):
        return "\n\n".join(f"Reviewer {i}:\n{r[key]}" for i, r in enumerate(reviews, 1) if r.get(key)) or None

    return {
        **{k: joined(k) for k in ("summary", "strengths", "weaknesses", "questions")},
        "suggestions": None,  # not part of CycleReviewer's review format
        **{k: mean(k) for k in ("soundness", "presentation", "contribution", "rating", "confidence")},
    }


def _interp(x, points, step=0.5):
    """Piecewise-linear map of x through (src, dst) anchor points, clamped to
    the ends and rounded to the target scale's step."""
    if x is None:
        return None
    x = min(max(x, points[0][0]), points[-1][0])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            y = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
            return math.floor(y / step + 0.5) * step  # half-up, unlike round()
    return points[-1][1]


# ICLR 1-4 (poor/fair/good/excellent) -> ACL 1-5, spread linearly end to end.
_ICLR4_TO_ACL5 = [(1, 1), (4, 5)]
# ICLR rating 1-10 -> ACL overall_assessment 1-5, anchored on the labels:
# 1 strong reject -> 1 do not resubmit; 3 reject -> 2 resubmit next cycle;
# 5 marginally below -> 3 findings; 6 marginally above -> 3.5 borderline
# conference; 8 accept -> 4 conference; 10 strong accept -> 5 award.
_ICLR_RATING_TO_ACL_OVERALL = [(1, 1), (3, 2), (5, 3), (6, 3.5), (8, 4), (10, 5)]


# model class -> (name used in errors, parser of its raw output into one
# normalised ICLR-style review: see _deepreviewer_review for the keys)
_NATIVE_REVIEWERS = {
    models.DeepReviewerModel: ("DeepReviewer", _deepreviewer_review),
    models.CycleReviewerModel: ("CycleReviewer", _cyclereviewer_review),
}


def _native_to_rubric(name, review, conference, raw):
    """Map a normalised ICLR-style review (from one of _NATIVE_REVIEWERS'
    parsers) onto the iclr or acl rubric's field ids."""
    rating = review["rating"]
    if rating is None:
        raise ValueError(f"no rating found in {name} output\n--- original model response ---\n{raw}")
    if conference == "iclr":
        return {k: review[k] for k in (
            "summary", "soundness", "presentation", "contribution", "strengths", "weaknesses", "questions",
            "rating", "confidence",
        )}
    if conference == "acl":
        overall = _interp(rating, _ICLR_RATING_TO_ACL_OVERALL)
        comments = "\n\n".join(filter(None, [review["suggestions"], review["questions"]]))
        return {
            "paper_summary": review["summary"],
            "summary_of_strengths": review["strengths"],
            "summary_of_weaknesses": review["weaknesses"],
            "comments_suggestions_typos": comments or None,
            "soundness": _interp(review["soundness"], _ICLR4_TO_ACL5),
            # ACL's excitement is about impact/novelty: closest ICLR field
            # is contribution.
            "excitement": _interp(review["contribution"], _ICLR4_TO_ACL5),
            "overall_assessment": overall,
            "best_paper": "yes" if overall >= 4.5 else "no",
            "confidence": review["confidence"],  # same 1-5 scale in both forms
        }
    raise ValueError(f"no {name} mapping for rubric '{conference}' (supported: iclr, acl)")


class Reviewer:
    def __init__(self, provider, model, review_type, pdf_path, **model_kwargs):
        self.model = MODEL_CLASSES[provider](model, **model_kwargs)
        self.review_type = review_type
        # Unparsed model output, set only by models that return a review in
        # their own format (_NATIVE_REVIEWERS); review() saves it next to
        # review.json.
        self.raw_response = None
        self.pdf_path = Path(pdf_path)
        rubric = yaml.safe_load((RUBRIC_DIR / f"{review_type}_rubric.yaml").read_text())
        self.conference, self.edition = rubric["conference"], rubric["edition"]
        # human-only indicators (e.g. "did you guess the authors' identity?")
        # don't make sense for an LLM reviewer, so they're dropped here.
        self.fields = [f for f in rubric["fields"] if f.get("applies_to") != "human_reviewer_only"]

    def build_prompt(self, paper_text=None):
        lines = [
            f"You are an expert reviewer for {self.conference} {self.edition}.",
            "Read the attached paper and fill out the review form." if paper_text is None else
            "Read the paper below and fill out the review form.",
            "First, reason step by step about the paper and about each field of the review form.",
            f'When you are done reasoning, write the line "{FINAL_KEYWORD}" and, immediately after it,'
            " a single Python dict literal whose keys are exactly the field ids listed below (as strings)."
            " Nothing may follow the dict literal. Make sure that the dict is in valid Python syntax, with quotes around the keys and string values."
            "For missing attributes, use \"N/A\", properly enclosed in quotes.",
        ]
        if paper_text is not None:
            lines += ["", "# Paper", paper_text]
        lines += ["", "# Review form"]
        for f in self.fields:
            lines.append(f"- {f['id']} ({f['type']}): {f['question'].strip()}")
            if f.get("scale"):
                opts = ", ".join(f"{o['value']}={o['label']}" for o in f["scale"])
                lines.append(f"  allowed values: {opts}")
            if f.get("options"):
                lines.append(f"  allowed values: {', '.join(f['options'])}")
        lines.append(f"\nAfter \"{FINAL_KEYWORD}\", return only the Python dict literal, no other text.")
        return "\n".join(lines)

    def _extract_text(self):
        return "\n".join(p.extract_text() or "" for p in PdfReader(self.pdf_path).pages)

    def _extract_markdown(self):
        # Imported here so only DeepReviewer/CycleReviewer runs need
        # pymupdf4llm installed.
        import pymupdf4llm
        # Our PDFs are compiled from LaTeX, so they already carry a text
        # layer: OCR isn't needed and would fail wherever Tesseract isn't set up.
        return pymupdf4llm.to_markdown(str(self.pdf_path), use_ocr=False)

    def _generate_native_review(self, name, parse):
        # DeepReviewer/CycleReviewer ignore our review form (see
        # models._NativeReviewerModel), so their native review is mapped
        # onto the rubric instead. Fields with no counterpart are "N/A", as
        # the prompt asks other models to do. They were trained on papers
        # converted to markdown, so they get the PDF as markdown rather than
        # pypdf's plain text. The full output is kept in self.raw_response
        # for the caller to save.
        self.raw_response = self.model.review(self._extract_markdown())
        mapped = _native_to_rubric(name, parse(self.raw_response), self.review_type, self.raw_response)
        return {f["id"]: mapped.get(f["id"]) or "N/A" for f in self.fields}

    def generate_review(self, max_tokens=32768):
        native = _NATIVE_REVIEWERS.get(type(self.model))
        if native:
            return self._generate_native_review(*native)
        # Prefer sending the PDF itself; only fall back to extracted text if
        # the model can't take a document directly, or claims to (e.g. a
        # vision-capable vllm model) but actually rejects it at call time.
        if self.model.supports_pdf():
            try:
                raw = self.model.generate(self.build_prompt(), pdf_path=self.pdf_path, max_tokens=max_tokens)
            except Exception as e:
                prompt = self.build_prompt(self._extract_text())
                _log_pdf_fallback(f"{type(self.model).__name__}:{self.model.model}", e, prompt)
                raw = self.model.generate(prompt, pdf_path=None, max_tokens=max_tokens)
        else:
            raw = self.model.generate(self.build_prompt(self._extract_text()), pdf_path=None, max_tokens=max_tokens)
        _, _, tail = raw.rpartition(FINAL_KEYWORD)  # tail == raw if the keyword is missing
        dict_literal = _extract_braces(tail)
        try:
            answers = ast.literal_eval(dict_literal)
        except (ValueError, SyntaxError) as e:
            # Re-raise with the text that failed to parse and the full model
            # response attached, so the traceback logged by the caller (e.g.
            # review()'s error.txt) is enough to diagnose a malformed dict
            # literal without having to reproduce the model call.
            raise ValueError(
                f"ast.literal_eval failed on model output: {e}\n"
                f"--- text passed to ast.literal_eval ---\n{dict_literal}\n"
                f"--- original model response ---\n{raw}"
            ) from e
        return {f["id"]: answers.get(f["id"]) for f in self.fields}
