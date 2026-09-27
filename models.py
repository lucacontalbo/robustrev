import base64
import os
import re
from pathlib import Path

import httpx
from anthropic import Anthropic
from openai import OpenAI


class AnthropicModel:
    def __init__(self, model="claude-opus-4-8", api_key=None):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def supports_pdf(self):
        # All current Claude models accept documents; ask the Models API so
        # a future text-only/no-vision model is detected automatically.
        try:
            caps = self.client.models.retrieve(self.model).capabilities
            return caps.get("image_input", {}).get("supported", True)
        except Exception:
            return True

    def generate(self, prompt, pdf_path=None, max_tokens=16384):
        content = [{"type": "text", "text": prompt}]
        if pdf_path:
            data = base64.standard_b64encode(Path(pdf_path).read_bytes()).decode()
            content.insert(0, {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": data},
            })
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        return next(b.text for b in msg.content if b.type == "text")


# OpenAI exposes no capabilities endpoint, so model behavior is keyed off the
# model name instead. Update these as OpenAI ships new families.
# Reasoning models (gpt-5*, o1/o3/o4*) require `max_completion_tokens`
# instead of `max_tokens` in Chat Completions.
_REASONING_RE = re.compile(r"^(gpt-5|o1|o3|o4)")
# Vision-capable models that can take a PDF as a `file` content part
# (gpt-4o and later). o-series support varies by variant, so it's left off
# this allowlist by default.
_PDF_CAPABLE_RE = re.compile(r"^(gpt-4o|gpt-4\.1|gpt-4\.5|gpt-5)")
_DISABLE_THINKING_MODELS = re.compile(r"qwen3\.5|nemotron-3", re.IGNORECASE)


class OpenAIModel:
    def __init__(self, model="gpt-4o-mini", api_key=None):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def supports_pdf(self):
        return bool(_PDF_CAPABLE_RE.match(self.model))

    def generate(self, prompt, pdf_path=None, max_tokens=16384):
        content = [{"type": "text", "text": prompt}]
        if pdf_path:
            data = base64.standard_b64encode(Path(pdf_path).read_bytes()).decode()
            content.insert(0, {
                "type": "file",
                "file": {"filename": Path(pdf_path).name, "file_data": f"data:application/pdf;base64,{data}"},
            })
        token_kwarg = "max_completion_tokens" if _REASONING_RE.match(self.model) else "max_tokens"
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            # max_tokens=max_tokens,
            temperature=0 if not _REASONING_RE.match(self.model) else 1,
            extra_body={} if not _DISABLE_THINKING_MODELS.search(self.model) else {
                "chat_template_kwargs": {
                    "enable_thinking": False
                }
            },
            **{token_kwarg: max_tokens},
        )
        return resp.choices[0].message.content


class VLLMModel(OpenAIModel):
    """Talks to a vLLM server exposing the OpenAI-compatible API.

    base_url/api_key default to the OPENAI_BASE_URL/OPENAI_API_KEY env vars
    (falling back to a plain local server if those aren't set either),
    rather than being hardcoded — so e.g. a Slurm array job that starts one
    vLLM server per task on a per-task port can just
    `export OPENAI_BASE_URL=http://127.0.0.1:$PORT/v1` before invoking
    robustrev.py instead of needing a separate models_config.yaml entry per
    task. An explicit base_url/api_key in models_config.yaml still wins over
    both."""

    def __init__(self, model, base_url=None, api_key=None, pdf_capable=False):
        base_url = base_url or os.environ.get("OPENAI_BASE_URL") or "http://localhost:8000/v1"
        api_key = api_key or os.environ.get("OPENAI_API_KEY") or "EMPTY"
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        # vLLM serves arbitrary open models, so PDF/vision support can't be
        # inferred from the name — caller states it explicitly.
        self._pdf_capable = pdf_capable

    def supports_pdf(self):
        return self._pdf_capable


class _NativeReviewerModel(VLLMModel):
    """A reviewer fine-tune served by vLLM that is trained to answer a fixed
    system prompt with its own review format, not an arbitrary instruction —
    so it gets its own entry point (review()) instead of generate(), and
    reviewer.py maps its native review onto our rubric.

    Each request is given the model's whole context (MAX_MODEL_LEN, which
    must match --max-model-len in its sbatch script): vLLM rejects
    prompt + max_tokens > --max-model-len, so generation gets whatever the
    prompt leaves."""

    MAX_MODEL_LEN = None

    def system_prompt(self):
        raise NotImplementedError

    def _count_prompt_tokens(self, messages):
        """Prompt length in tokens, chat template included, via vLLM's
        /tokenize endpoint (served at the server root, not under /v1)."""
        root = str(self.client.base_url).rstrip("/").removesuffix("/v1")
        resp = httpx.post(
            f"{root}/tokenize",
            json={"model": self.model, "messages": messages, "add_generation_prompt": True},
            headers={"Authorization": f"Bearer {self.client.api_key}"},
            timeout=600,
        )
        resp.raise_for_status()
        return resp.json()["count"]

    def review(self, paper_text, max_model_len=None):
        max_model_len = max_model_len or self.MAX_MODEL_LEN
        messages = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": paper_text},
        ]
        prompt_tokens = self._count_prompt_tokens(messages)
        max_tokens = max_model_len - prompt_tokens
        if max_tokens <= 0:
            raise ValueError(
                f"paper is {prompt_tokens} tokens, which fills {type(self).__name__}'s {max_model_len}-token context"
            )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.4,
            top_p=0.95,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content


# DeepReviewer (WestlakeNLP/DeepReviewer-7B/-14B). The prompts, sampling
# parameters and context length are copied verbatim from the authors'
# reference implementation:
# https://github.com/zhu-minjun/Researcher/blob/main/ai_researcher/deep_reviewer.py
# Must match --max-model-len in sbatch_review_deepreviewer.sh.
DEEPREVIEWER_MAX_MODEL_LEN = 90000
_DEEPREVIEWER_BASE_PROMPT = (
    "You are an expert academic reviewer tasked with providing a thorough and balanced evaluation of research papers."
)
_DEEPREVIEWER_SIMREVIEWER_PROMPT = (
    "When you simulate different reviewers, write the sections in this order: Summary, Soundness, Presentation, "
    "Contribution, Strengths, Weaknesses, Suggestions, Questions, Rating and Confidence."
)


class DeepReviewerModel(_NativeReviewerModel):
    """A DeepReviewer checkpoint served by vLLM.

    mode:         "fast" (a single review straight away) or "standard"
                  (simulates `reviewer_num` reviewers, self-verifies, then
                  writes a meta-review). The paper's "Best Mode" needs an
                  OpenScholar retrieval server and isn't supported.
    reviewer_num: reviewers simulated in standard mode (default 3)."""

    MODES = ("fast", "standard")
    MAX_MODEL_LEN = DEEPREVIEWER_MAX_MODEL_LEN

    def __init__(self, model, mode="standard", reviewer_num=3, **kwargs):
        super().__init__(model, **kwargs)
        if mode not in self.MODES:
            raise ValueError(f"unknown DeepReviewer mode {mode!r}; choices are {self.MODES}")
        self.mode = mode
        self.reviewer_num = reviewer_num

    def system_prompt(self):
        if self.mode == "fast":
            return (f"{_DEEPREVIEWER_BASE_PROMPT} Your thinking mode is Fast Mode. "
                    "In this mode, you should quickly provide the review results.")
        return (f"{_DEEPREVIEWER_BASE_PROMPT} Your thinking mode is Standard Mode. In this mode, you should review by "
                f"simulating {self.reviewer_num} different reviewers, and use self-verification to double-check any "
                f"paper deficiencies identified. Finally, provide complete review results."
                + _DEEPREVIEWER_SIMREVIEWER_PROMPT)


# CycleReviewer (WestlakeNLP/CycleReviewer-ML-Llama-3.1-8B,
# WestlakeNLP/CycleReviewer-Llama-3.1-70B). It has a single mode: 4
# reviews, then a meta review and an Accept/Reject decision. The system
# prompt (stray indentation included, as the authors' code sends it),
# sampling parameters and context length are copied from:
# https://github.com/zhu-minjun/Researcher/blob/main/ai_researcher/cycle_reviewer.py
# Must match --max-model-len in sbatch_review_cyclereviewer_{8b,70b}.sh.
CYCLEREVIEWER_MAX_MODEL_LEN = 50000
_CYCLEREVIEWER_PROMPT = (
    'You are an expert academic reviewer tasked with providing a thorough and balanced evaluation of research papers. For each paper submitted, conduct a comprehensive review addressing the following aspects:' "\n"
    '    ' "\n"
    '            1. Summary: Briefly outline main points and objectives.' "\n"
    '            2. Soundness: Assess methodology and logical consistency.' "\n"
    '            3. Presentation: Evaluate clarity, organization, and visual aids.' "\n"
    '            4. Contribution: Analyze significance and novelty in the field.' "\n"
    "            5. Strengths: Identify the paper's strongest aspects." "\n"
    '            6. Weaknesses: Point out areas for improvement.' "\n"
    '            7. Questions: Pose questions for the authors.' "\n"
    '            8. Rating: Score 1-10, justify your rating.' "\n"
    '            9. Meta Review: Provide overall assessment and recommendation (Accept/Reject).' "\n"
    '    ' "\n"
    '            Maintain objectivity and provide specific examples from the paper to support your evaluation.' "\n"
    '    ' "\n"
    '            You need to fill out **4** review opinions.'
)


class CycleReviewerModel(_NativeReviewerModel):
    """A CycleReviewer checkpoint served by vLLM."""

    MAX_MODEL_LEN = CYCLEREVIEWER_MAX_MODEL_LEN

    def system_prompt(self):
        return _CYCLEREVIEWER_PROMPT
