import ast
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


class Reviewer:
    def __init__(self, provider, model, review_type, pdf_path, **model_kwargs):
        self.model = MODEL_CLASSES[provider](model, **model_kwargs)
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
            " Nothing may follow the dict literal. Make sure that the dict is in valid Python syntax, with quotes around the keys and string values.",
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

    def generate_review(self, max_tokens=32768):
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
