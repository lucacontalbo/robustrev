import base64
import os
import re
from pathlib import Path

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
_DISABLE_THINKING_MODELS = re.compile(r"qwen3\.5", re.IGNORECASE)


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
