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
    # Sampling parameters from the model authors' reference implementation.
    TEMPERATURE = 0.4
    TOP_P = 0.95

    def system_prompt(self):
        raise NotImplementedError

    def user_prompt(self, paper_text):
        return paper_text

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
            {"role": "user", "content": self.user_prompt(paper_text)},
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
            temperature=self.TEMPERATURE,
            top_p=self.TOP_P,
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


# OpenReviewer (maxidl/Llama-OpenReviewer-8B). Unlike DeepReviewer and
# CycleReviewer it has no fixed review form: its system prompt takes the
# venue's form as "review_fields", but it was trained only on ICLR
# 2022-2025 and NeurIPS 2022-2024 forms, so it's always given the ICLR 2025
# form it was trained on (reviewer.py maps the answer onto our rubric).
# Prompts, form, paper preprocessing and sampling parameters are copied
# from the authors' code (https://github.com/maxidl/openreviewer):
# llm_training/generate.py, llm_training/prepare_data.py and
# openreview_dataset_creation/note_parsers/iclr_2025.py. The context is
# Llama 3.1's native 128k, which the model was fine-tuned at; must match
# --max-model-len in sbatch_review_openreviewer.sh.
OPENREVIEWER_MAX_MODEL_LEN = 131072
_OPENREVIEWER_SYSTEM_PROMPT_TEMPLATE = (
    'You are an expert reviewer for AI conferences. You follow best practices and review papers according to the reviewer guidelines.' "\n"
    '' "\n"
    'Reviewer guidelines:' "\n"
    '1. Read the paper: It’s important to carefully read through the entire paper, and to look up any related work and citations that will help you comprehensively evaluate it. Be sure to give yourself sufficient time for this step.' "\n"
    '2. While reading, consider the following:' "\n"
    '    - Objective of the work: What is the goal of the paper? Is it to better address a known application or problem, draw attention to a new application or problem, or to introduce and/or explain a new theoretical finding? A combination of these? Different objectives will require different considerations as to potential value and impact.' "\n"
    '    - Strong points: is the submission clear, technically correct, experimentally rigorous, reproducible, does it present novel findings (e.g. theoretically, algorithmically, etc.)?' "\n"
    '    - Weak points: is it weak in any of the aspects listed in b.?' "\n"
    '    - Be mindful of potential biases and try to be open-minded about the value and interest a paper can hold for the community, even if it may not be very interesting for you.' "\n"
    '3. Answer four key questions for yourself, to make a recommendation to Accept or Reject:' "\n"
    '    - What is the specific question and/or problem tackled by the paper?' "\n"
    '    - Is the approach well motivated, including being well-placed in the literature?' "\n"
    '    - Does the paper support the claims? This includes determining if results, whether theoretical or empirical, are correct and if they are scientifically rigorous.' "\n"
    '    - What is the significance of the work? Does it contribute new knowledge and sufficient value to the community? Note, this does not necessarily require state-of-the-art results. Submissions bring value to the community when they convincingly demonstrate new, relevant, impactful knowledge (incl., empirical, theoretical, for practitioners, etc).' "\n"
    '4. Write your review including the following information: ' "\n"
    '    - Summarize what the paper claims to contribute. Be positive and constructive.' "\n"
    '    - List strong and weak points of the paper. Be as comprehensive as possible.' "\n"
    '    - Clearly state your initial recommendation (accept or reject) with one or two key reasons for this choice.' "\n"
    '    - Provide supporting arguments for your recommendation.' "\n"
    '    - Ask questions you would like answered by the authors to help you clarify your understanding of the paper and provide the additional evidence you need to be confident in your assessment.' "\n"
    '    - Provide additional feedback with the aim to improve the paper. Make it clear that these points are here to help, and not necessarily part of your decision assessment.' "\n"
    '' "\n"
    'Your write reviews in markdown format. Your reviews contain the following sections:' "\n"
    '' "\n"
    '# Review' "\n"
    '' "\n"
    '{review_fields}' "\n"
    '' "\n"
    'Your response must only contain the review in markdown format with sections as defined above.' "\n"
    ''
)
_OPENREVIEWER_USER_PROMPT_TEMPLATE = (
    'Review the following paper:' "\n"
    '' "\n"
    '{paper_text}' "\n"
    ''
)
# (field id, description) of the ICLR 2025 review form, as in training.
_OPENREVIEWER_ICLR2025_FIELDS = [
    ('summary',
     'Briefly summarize the paper and its contributions. This is not the place to critique the paper; the authors should generally agree with a well-written summary.'),
    ('soundness',
     'Please assign the paper a numerical rating on the following scale to indicate the soundness of the technical claims, experimental and research methodology and on whether the central claims of the paper are adequately supported with evidence. Choose from the following:' "\n"
     '4: excellent' "\n"
     '3: good' "\n"
     '2: fair' "\n"
     '1: poor'),
    ('presentation',
     'Please assign the paper a numerical rating on the following scale to indicate the quality of the presentation. This should take into account the writing style and clarity, as well as contextualization relative to prior work. Choose from the following:' "\n"
     '4: excellent' "\n"
     '3: good' "\n"
     '2: fair' "\n"
     '1: poor'),
    ('contribution',
     'Please assign the paper a numerical rating on the following scale to indicate the quality of the overall contribution this paper makes to the research area being studied. Are the questions being asked important? Does the paper bring a significant originality of ideas and/or execution? Are the results valuable to share with the broader ICLR community? Choose from the following:' "\n"
     '4: excellent' "\n"
     '3: good' "\n"
     '2: fair' "\n"
     '1: poor'),
    ('strengths',
     'A substantive assessment of the strengths of the paper, touching on each of the following dimensions: originality, quality, clarity, and significance. We encourage reviewers to be broad in their definitions of originality and significance. For example, originality may arise from a new definition or problem formulation, creative combinations of existing ideas, application to a new domain, or removing limitations from prior results.'),
    ('weaknesses',
     'A substantive assessment of the weaknesses of the paper. Focus on constructive and actionable insights on how the work could improve towards its stated goals. Be specific, avoid generic remarks. For example, if you believe the contribution lacks novelty, provide references and an explanation as evidence; if you believe experiments are insufficient, explain why and exactly what is missing, etc.'),
    ('questions',
     'Please list up and carefully describe any questions and suggestions for the authors. Think of the things where a response from the author can change your opinion, clarify a confusion or address a limitation. This is important for a productive rebuttal and discussion phase with the authors.'),
    ('flag_for_ethics_review',
     'If there are ethical issues with this paper, please flag the paper for an ethics review and select area of expertise that would be most useful for the ethics reviewer to have. Please select all that apply. Choose from the following:' "\n"
     'No ethics review needed.' "\n"
     'Yes, Discrimination / bias / fairness concerns' "\n"
     'Yes, Privacy, security and safety' "\n"
     'Yes, Legal compliance (e.g., GDPR, copyright, terms of use)' "\n"
     'Yes, Potentially harmful insights, methodologies and applications' "\n"
     'Yes, Responsible research practice (e.g., human subjects, data release)' "\n"
     'Yes, Research integrity issues (e.g., plagiarism, dual submission)' "\n"
     'Yes, Unprofessional behaviors (e.g., unprofessional exchange between authors and reviewers)' "\n"
     'Yes, Other reasons (please specify below)'),
    ('details_of_ethics_concerns',
     'Please provide details of your concerns.'),
    ('rating',
     'Please provide an "overall score" for this submission. Choose from the following:' "\n"
     '1: strong reject' "\n"
     '3: reject, not good enough' "\n"
     '5: marginally below the acceptance threshold' "\n"
     '6: marginally above the acceptance threshold' "\n"
     '8: accept, good paper' "\n"
     '10: strong accept, should be highlighted at the conference'),
    ('confidence',
     'Please provide a "confidence score" for your assessment of this submission to indicate how confident you are in your evaluation. Choose from the following:' "\n"
     '1: You are unable to assess this paper and have alerted the ACs to seek an opinion from different reviewers.' "\n"
     '2: You are willing to defend your assessment, but it is quite likely that you did not understand the central parts of the submission or that you are unfamiliar with some pieces of related work. Math/other details were not carefully checked.' "\n"
     '3: You are fairly confident in your assessment. It is possible that you did not understand some parts of the submission or that you are unfamiliar with some pieces of related work. Math/other details were not carefully checked.' "\n"
     '4: You are confident in your assessment, but not absolutely certain. It is unlikely, but not impossible, that you did not understand some parts of the submission or that you are unfamiliar with some pieces of related work.' "\n"
     '5: You are absolutely certain about your assessment. You are very familiar with the related work and checked the math/other details carefully.'),
]
# Built exactly as prepare_data.py builds it from a venue's form.
_OPENREVIEWER_REVIEW_FIELDS = "\n".join(
    f"## {field.replace('_', ' ').title()}\n{description}\n" for field, description in _OPENREVIEWER_ICLR2025_FIELDS
)
_MD_HEADER_SPLIT = re.compile(r"^#+\ ", re.MULTILINE)
_REFERENCE_MATCHES = ["References", "REFERENCES", "R E F E R E N C E S", "Re F E R E N C E S"]


def _openreviewer_main_text(text):
    """Drop the appendix, keeping the references: the paper text ends with
    the first markdown section that mentions references. Same logic as
    get_main_text() in the authors' prepare_data.py, which is how the
    training inputs were cut; the full text is kept if no such section is
    found."""
    sections = re.split(_MD_HEADER_SPLIT, text)
    reference_sections = [i for i, section in enumerate(sections) if any(m in section for m in _REFERENCE_MATCHES)]
    if not reference_sections:
        return text
    reference_section_text = sections[reference_sections[0]]
    return text.split(reference_section_text)[0] + reference_section_text


class OpenReviewerModel(_NativeReviewerModel):
    """An OpenReviewer checkpoint served by vLLM: a single review in the
    ICLR 2025 form."""

    MAX_MODEL_LEN = OPENREVIEWER_MAX_MODEL_LEN
    TEMPERATURE = 0.0
    TOP_P = 0.9

    def system_prompt(self):
        return _OPENREVIEWER_SYSTEM_PROMPT_TEMPLATE.format(review_fields=_OPENREVIEWER_REVIEW_FIELDS)

    def user_prompt(self, paper_text):
        return _OPENREVIEWER_USER_PROMPT_TEMPLATE.format(paper_text=_openreviewer_main_text(paper_text))
