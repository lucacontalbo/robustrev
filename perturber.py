import json
import random
import re
from pathlib import Path

import yaml

import models
from latex_compile import LatexCompiler, SEC_CMDS, _strip_comments

CONFIG_PATH = Path(__file__).parent / "perturbations_config.yaml"
MODEL_CLASSES = {
    "anthropic": models.AnthropicModel,
    "openai": models.OpenAIModel,
    "vllm": models.VLLMModel,
}
FINAL_KEYWORD = "PERTURBED TEXT:"
# Delimiter separating the rewritten excerpt from an optional new BibTeX
# entry, for perturbations with requires_citation: true in the config.
CITATION_KEYWORD = "NEW CITATION:"
# Sentinel the model returns instead of rewritten text when a perturbation's
# `precondition` (see perturbations_config.yaml) isn't met by the excerpt it
# was given, e.g. resource_overweighting on a paper that releases nothing.
UNCHANGED_TOKEN = "UNCHANGED"
# mechanism values apply_one() knows how to run.
SUPPORTED_MECHANISMS = {"zero_shot", "review_based"}
# Perturbations applied to every matching role (not just the first hit).
# self_preference_rewrite explicitly rewrites abstract + introduction +
# conclusion together (see its description in the config); everything else
# targets a single, highest-priority section.
MULTI_TARGET_PERTURBATIONS = {"self_preference_rewrite"}
# part < chapter < section < subsection < subsubsection < paragraph, in
# nesting order — used to tell a heading's children (deeper level) apart
# from its siblings/ancestors (same or shallower level) when computing how
# far a chosen section's body extends.
_HEADING_LEVELS = {name: i for i, name in enumerate(SEC_CMDS.split("|"))}
# Written into project_dir by every apply_one() call that actually changes
# something, recording what changed — no extra model call, just the
# before/after text (and any citation) already produced while applying it.
LOG_FILENAME = "PERTURBATION_CHANGES.md"


def _strip_code_fence(text):
    """Models sometimes wrap the requested raw-LaTeX answer in a ```...``` fence
    despite instructions not to; drop it if present."""
    m = re.match(r"^```[\w-]*\n(.*)\n```$", text, re.S)
    return m.group(1) if m else text


_PROMPT_COMMENT_RE = re.compile(r"(?<!\\)%.*")


def _strip_comments_for_prompt(text):
    """Drop LaTeX comments (unescaped % to end of line) and the now-empty
    lines they leave behind, before LaTeX text goes into a prompt — fewer
    tokens sent for no loss (the model never needs to see them). Unlike
    latex_compile._strip_comments, which blanks comments in place to
    preserve character offsets for later splicing, this is only ever used
    for prompt text, so the comments are deleted outright rather than
    padded with spaces."""
    lines = (_PROMPT_COMMENT_RE.sub("", line) for line in text.splitlines())
    return "\n".join(line for line in lines if line.strip())


class Perturber:
    """Applies visible-text adversarial-framing perturbations (see
    attacks_on_reviewers.txt and perturbations_config.yaml) to a LaTeX
    project's source files.

    Holds only the model — a single instance can be reused across different
    papers, since `project_dir` and which perturbation to run are passed
    per call, not fixed at construction. Each call mutates the .tex files
    under the given `project_dir` in place, the same way
    LatexCompiler.compile_pdf() writes its build output directly into
    project_dir — copy the project first if you want to keep an
    unperturbed original around for a baseline review.
    """

    def __init__(self, provider, model, max_tokens=32768, **model_kwargs):
        self.model = MODEL_CLASSES[provider](model, **model_kwargs)
        self.max_tokens = max_tokens
        self.compiler = LatexCompiler()
        cfg = yaml.safe_load(CONFIG_PATH.read_text())
        self.role_detection = cfg["role_detection"]
        self.perturbations = {p["id"]: p for p in cfg["perturbations"]}

    def apply(self, project_dir, perturbation_ids, baseline_review=None):
        """Apply each perturbation id, in order, to `project_dir`. Returns
        {id: result}, where result is True/False (whether it actually
        changed something) or, for an id this class can't run (unknown /
        precondition never met), a string explaining why. `baseline_review`
        (a Reviewer.generate_review() dict) is required by review_based
        perturbations (rubric_capture, disarming_framing) and ignored by
        the rest."""
        project_dir = Path(project_dir)
        results = {}
        for pid in perturbation_ids:
            try:
                results[pid] = self.apply_one(project_dir, pid, baseline_review)
            except NotImplementedError as e:
                results[pid] = str(e)
        return results

    def apply_one(self, project_dir, pert_id, baseline_review=None):
        project_dir = Path(project_dir)
        if pert_id not in self.perturbations:
            raise ValueError(f"unknown perturbation_id '{pert_id}' in {CONFIG_PATH}")
        pert = self.perturbations[pert_id]
        if pert["mechanism"] not in SUPPORTED_MECHANISMS:
            raise NotImplementedError(
                f"'{pert_id}' has mechanism '{pert['mechanism']}', which apply_one() doesn't support"
            )
        if pert["mechanism"] == "review_based" and baseline_review is None:
            raise ValueError(f"'{pert_id}' is review-based and requires a baseline_review")
        if pert["inputs"] == ["full_paper_text"]:
            return self._apply_addition(project_dir, pert, baseline_review)
        return self._apply_rewrite(project_dir, pert, baseline_review)

    # -- section discovery --------------------------------------------------

    def _matches_role(self, item, role):
        spec = self.role_detection[role]
        if spec["match"] == "structure_type":
            return item["type"] == role
        if spec["match"] == "title_keywords":
            title = item["title"].lower()
            return any(kw in title for kw in spec["title_keywords"])
        if spec["match"] == "any":
            return item["type"] not in ("abstract", "appendix")
        return False

    def _resolve_targets(self, project_dir, pert):
        """Structural items matching pert's applies_to.roles (pooled across
        all of them, not kept separate by role priority). Single-target
        perturbations get one item picked at random from that pool, not
        deterministically the first one found; MULTI_TARGET_PERTURBATIONS
        still get every distinct hit across all roles."""
        structure = self.compiler.find_structure(project_dir)
        matches = [
            item for role in pert["applies_to"]["roles"]
            for item in structure if self._matches_role(item, role)
        ]
        if pert["id"] not in MULTI_TARGET_PERTURBATIONS:
            return [random.choice(matches)] if matches else []
        seen, targets = set(), []
        for item in matches:
            key = (item["file"], item["search"])
            if key not in seen:
                seen.add(key)
                targets.append(item)
        return targets

    def _section_body_span(self, item):
        """Return (file_text, start, end): the character span of `item`'s body
        within its own file, i.e. everything after its heading up to the next
        heading at the same or a shallower level (or EOF) — so a chosen
        section's own subsections stay part of its body rather than cutting
        it off at the first child heading. Content pulled in via a further
        \\input inside that span isn't followed."""
        text = item["file"].read_text(errors="ignore")
        start = text.index(item["search"]) + len(item["search"])
        if item["type"] == "abstract":
            m = re.search(r"\\end\{abstract\}", text[start:])
            end = start + m.start() if m else len(text)
            return text, start, end

        own_level = _HEADING_LEVELS.get(item["type"], -1)
        end = len(text)
        for m in re.finditer(rf"\\({SEC_CMDS})\*?\{{|\\begin\{{abstract\}}|\\appendix\b", text[start:]):
            # abstract/appendix always terminate (level -1); a heading only
            # terminates if it's not a descendant (deeper level) of `item`.
            level = _HEADING_LEVELS.get(m.group(1), -1)
            if level <= own_level:
                end = start + m.start()
                break
        return text, start, end

    def _full_text(self, project_dir):
        root = self.compiler.find_root(project_dir)
        return "\n\n".join(text for _, text in self.compiler.walk_files(root))

    # -- generation -----------------------------------------------------------

    def _extract_output(self, raw):
        _, kw, tail = raw.rpartition(FINAL_KEYWORD)
        return _strip_code_fence((tail if kw else raw).strip())

    def _split_citation(self, text):
        """Split "<replacement text> NEW CITATION: <bibtex entry>" into
        (text, bibtex_entry); (text, None) if there's no citation block."""
        body, kw, bib = text.rpartition(CITATION_KEYWORD)
        if not kw:
            return text.strip(), None
        return body.strip(), _strip_code_fence(bib.strip())

    def _build_rewrite_prompt(self, pert, section_text, baseline_review=None):
        # All edit-specific detail (what to change, any precondition on when
        # it applies) lives in pert["description"] itself, not here — this
        # template only supplies what's needed to run the edit and parse the
        # result back out.
        lines = [
            "Apply the following "
            f'edit to the LaTeX excerpt below: {pert["description"].strip()}',
        ]
        if baseline_review is not None:
            lines.append(f"Baseline review of this paper to work from (don't reproduce it verbatim): {json.dumps(baseline_review)}")
        lines += [
            "",
            "Keep every LaTeX command, citation key, label, and macro syntactically valid.",
            "Change only what the edit requires; leave the rest of the excerpt unchanged.",
            "Do not write the instruction given here, just modify the excerpt itself as requested.",
        ]
        if pert.get("requires_citation"):
            lines.append(
                f'If the edit needs one or more citations not already in the excerpt, add \\cite{{key}} for '
                f"each, each with its own new, unique BibTeX key, and after the replacement text write the "
                f'line "{CITATION_KEYWORD}" followed by one complete BibTeX entry per new key (each starting '
                "with @type{key, on its own line), concatenated one after another, and nothing else."
            )
        lines += [
            f'If the edit does not apply to this excerpt, write "{FINAL_KEYWORD}" followed by exactly '
            f"the word {UNCHANGED_TOKEN} and nothing else.",
            f'Otherwise, write "{FINAL_KEYWORD}" followed immediately by the complete replacement for '
            "the excerpt below" + (f", then the optional {CITATION_KEYWORD} block" if pert.get("requires_citation") else "")
            + " — nothing else, no markdown fences, no commentary.",
            "",
            "# LaTeX excerpt",
            _strip_comments_for_prompt(section_text),
        ]
        return "\n".join(lines)

    def _build_addition_prompt(self, pert, full_text, baseline_review=None):
        lines = [
            "Apply the following "
            f'edit to the paper below: {pert["description"].strip()}',
        ]
        if baseline_review is not None:
            lines.append(f"Baseline review of this paper to work from (don't reproduce it verbatim): {json.dumps(baseline_review)}")
        lines += [
            "The paper below is for context only — do not repeat or rewrite it.",
            "Keep every LaTeX command, citation key, label, and macro syntactically valid.",
            f'If the edit does not apply to this paper, write "{FINAL_KEYWORD}" followed by exactly the '
            f"word {UNCHANGED_TOKEN} and nothing else.",
            f'Otherwise, write "{FINAL_KEYWORD}" followed immediately by the new LaTeX content only — '
            "nothing else, no markdown fences, no commentary.",
            "",
            "# Full paper",
            _strip_comments_for_prompt(full_text),
        ]
        return "\n".join(lines)

    def _perturb_text(self, pert, section_text, baseline_review=None):
        """Returns (replacement_text, bib_entry_or_None); (None, None) if the
        edit doesn't apply to this excerpt."""
        raw = self.model.generate(
            self._build_rewrite_prompt(pert, section_text, baseline_review), max_tokens=self.max_tokens
        )
        result = self._extract_output(raw)
        if result.upper() == UNCHANGED_TOKEN:
            return None, None
        if pert.get("requires_citation"):
            return self._split_citation(result)
        return result, None

    # -- citations ----------------------------------------------------------

    def _bib_path(self, project_dir):
        """The .bib file backing the project's \\bibliography{...}, or None
        if it declares none. Uses the first declared name if more than one."""
        root = self.compiler.find_root(project_dir)
        m = re.search(r"\\bibliography\{([^}]+)\}", _strip_comments(root.read_text(errors="ignore")))
        if not m:
            return None
        name = m.group(1).split(",")[0].strip()
        return (root.parent / name).with_suffix(".bib")

    def _split_bib_entries(self, blob):
        """Split a blob of one or more concatenated BibTeX entries into
        individual entry strings. Entries are assumed to each start with
        "@type{" at the beginning of a line, as the prompt asks for and as
        holds for any well-formed .bib file."""
        parts = re.split(r"(?=^@\w+\{)", blob.strip(), flags=re.M)
        return [p.strip() for p in parts if p.strip()]

    def _add_citation(self, project_dir, bib_blob, text):
        """Appends one or more BibTeX entries (from `bib_blob`, which may be
        several concatenated @type{key,...} entries) to the project's .bib
        file, renaming any key that collides with an existing one — or with
        another new entry in this same batch — and updating `text` to
        match. Returns (text, [bib_entry, ...], bib_path); if there's no
        .bib file to attach to, or nothing in `bib_blob` parses, returns
        (text, [], None) unchanged (any \\cite{} left dangling in `text`
        ends up undefined — a LaTeX warning, not a fatal compile error)."""
        bib_path = self._bib_path(project_dir)
        entries = self._split_bib_entries(bib_blob)
        if bib_path is None or not entries:
            return text, [], None

        existing = bib_path.read_text(errors="ignore") if bib_path.exists() else ""
        used_keys = set(re.findall(r"@\w+\{\s*([^,\s]+)\s*,", existing))
        added = []
        for entry in entries:
            key_match = re.match(r"\s*@\w+\{\s*([^,\s]+)\s*,", entry)
            if not key_match:
                continue
            key = key_match.group(1)
            new_key, n = key, 2
            while new_key in used_keys:
                new_key, n = f"{key}{n}", n + 1
            used_keys.add(new_key)
            if new_key != key:
                entry = re.sub(rf"\b{re.escape(key)}\b", new_key, entry, count=1)
                text = re.sub(rf"\b{re.escape(key)}\b", new_key, text)
            added.append(entry.strip())

        if not added:
            return text, [], None
        sep = "\n\n" if existing.strip() else ""
        bib_path.write_text(existing.rstrip() + sep + "\n\n".join(added) + "\n")
        return text, added, bib_path

    # -- application ------------------------------------------------------

    def _apply_rewrite(self, project_dir, pert, baseline_review=None):
        targets = self._resolve_targets(project_dir, pert)
        if not targets:
            if pert["applies_to"]["fallback"] == "create":
                return self._create_section(project_dir, pert, baseline_review)
            return False
        changes = []
        for target in targets:
            text, start, end = self._section_body_span(target)
            result, bib_entry = self._perturb_text(pert, text[start:end], baseline_review)
            if result is None:  # precondition wasn't met for this section
                continue
            before = text[start:end].strip()
            citation = None
            if bib_entry:
                result, added_entries, bib_path = self._add_citation(project_dir, bib_entry, result)
                if added_entries:
                    citation = {"file": bib_path.relative_to(project_dir), "entries": added_entries}
            target["file"].write_text(text[:start] + " \n" + result.strip() + " \n" + text[end:])
            changes.append({
                "file": target["file"].relative_to(project_dir), "before": before,
                "after": result.strip(), "citation": citation,
            })
        if changes:
            self._write_change_log(project_dir, pert, changes)
        return bool(changes)

    def _apply_addition(self, project_dir, pert, baseline_review=None):
        raw = self.model.generate(
            self._build_addition_prompt(pert, self._full_text(project_dir), baseline_review), max_tokens=self.max_tokens
        )
        new_content = self._extract_output(raw)
        if not new_content or new_content.upper() == UNCHANGED_TOKEN:
            return False

        root = self.compiler.find_root(project_dir)
        text = root.read_text(errors="ignore")
        end_doc = re.search(r"\\end\{document\}", text)
        if not end_doc:
            raise ValueError(f"no \\end{{document}} found in {root}")
        has_appendix = any(i["type"] == "appendix" for i in self.compiler.find_structure(project_dir))
        insertion = ("" if has_appendix else "\\appendix\n\n") + new_content.strip() + "\n\n"
        root.write_text(text[:end_doc.start()] + insertion + text[end_doc.start():])
        self._write_change_log(project_dir, pert, [{
            "file": root.relative_to(project_dir), "before": None, "after": new_content.strip(), "citation": None,
        }])
        return True

    def _create_section(self, project_dir, pert, baseline_review=None):
        """For perturbations whose applies_to.fallback is "create": when no
        matching section exists, generate its body and insert a new section
        for it at the end of the paper's main content — right before the
        references (\\bibliography{}/\\begin{thebibliography}) or \\appendix,
        whichever comes first in the root file, or right before
        \\end{document} if neither exists. The heading itself (e.g.
        "\\section{Limitations}") is added by code, from the role name, not
        left to the model — so later perturbations' role_detection title
        matching reliably finds it, and so the model only ever writes body
        content, same as the rewrite path above."""
        root = self.compiler.find_root(project_dir)
        text = root.read_text(errors="ignore")
        clean = _strip_comments(text)
        markers = (r"\\bibliography\{", r"\\begin\{thebibliography\}", r"\\appendix\b", r"\\end\{document\}")
        positions = [m.start() for pat in markers for m in [re.search(pat, clean)] if m]
        if not positions:
            raise ValueError(f"no \\end{{document}} found in {root}")
        insert_at = min(positions)

        raw = self.model.generate(
            self._build_addition_prompt(pert, self._full_text(project_dir), baseline_review), max_tokens=self.max_tokens
        )
        new_content = self._extract_output(raw)
        if not new_content or new_content.upper() == UNCHANGED_TOKEN:
            return False

        title = pert["applies_to"]["roles"][0].replace("_", " ").title()
        section = f"\\section{{{title}}}\n{new_content.strip()}\n\n"
        root.write_text(text[:insert_at] + section + text[insert_at:])
        self._write_change_log(project_dir, pert, [{
            "file": root.relative_to(project_dir), "before": None, "after": new_content.strip(), "citation": None,
        }])
        return True

    def _write_change_log(self, project_dir, pert, changes):
        lines = [f"# Perturbation applied: {pert['name']} (`{pert['id']}`)", "", pert["description"].strip()]
        for c in changes:
            lines += ["", f"## `{c['file']}`"]
            if c["before"] is not None:
                lines += ["", "**Before:**", "```latex", c["before"], "```", "", "**After:**", "```latex", c["after"], "```"]
            else:
                lines += ["", "**Added:**", "```latex", c["after"], "```"]
            if c["citation"]:
                plural = "s" if len(c["citation"]["entries"]) > 1 else ""
                lines += [
                    "", f"**New citation{plural} added to `{c['citation']['file']}`:**",
                    "```bibtex", "\n\n".join(c["citation"]["entries"]), "```",
                ]
        (project_dir / LOG_FILENAME).write_text("\n".join(lines) + "\n")
