import re
import subprocess
from pathlib import Path

SEC_CMDS = r"part|chapter|section|subsection|subsubsection|paragraph"
# Unescaped "%" starts a LaTeX comment running to end of line.
_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")


def _strip_comments(text):
    """Blank out unescaped LaTeX comments (replacing them with spaces, not
    removing them) so structural regexes below don't fire on commented-out
    commands like `%\\input{...}`, while keeping every other character at
    its original offset so positions found in the result stay valid against
    the original text."""
    return _COMMENT_RE.sub(lambda m: " " * len(m.group()), text)


class LatexCompiler:
    def __init__(self, timeout=None):
        # find_root() is expensive now (it trial-compiles candidates) but is
        # called repeatedly for the same project (find_structure(), Perturber,
        # ...); cache the winning candidate per project so only the first
        # call per project actually invokes latexmk.
        self._root_cache = {}
        # Optional wall-clock budget (seconds) per latexmk invocation, for
        # callers processing many untrusted/unknown documents (e.g. a paper
        # scraper) where one pathological source (huge, or an accidental
        # infinite expansion) shouldn't be able to hang the whole run.
        # None (the default) means no timeout, unchanged from before this
        # was added.
        self.timeout = timeout

    def find_root(self, project_dir):
        project_dir = Path(project_dir).resolve()
        if project_dir in self._root_cache:
            return self._root_cache[project_dir]

        candidates = [
            tex for tex in project_dir.rglob("*.tex")
            if r"\documentclass" in _strip_comments(tex.read_text(errors="ignore"))
        ]
        if not candidates:
            raise FileNotFoundError("no \\documentclass found in project")
        # Projects sometimes ship multiple entry points (e.g. ACL's
        # acl_latex.tex vs acl_lualatex.tex for different engines). Rather
        # than guess which one is right from its name, actually try
        # compiling each candidate — trying the ones not named after a
        # different engine first, since we only ever compile with plain
        # pdflatex — and keep the first one that actually works.
        engine_named = re.compile(r"lualatex|xelatex", re.I)
        ordered = sorted(candidates, key=lambda c: (bool(engine_named.search(c.stem)), str(c)))

        last_error = None
        for candidate in ordered:
            try:
                self._trial_compile(candidate)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                last_error = e
                continue
            self._root_cache[project_dir] = candidate
            return candidate
        raise FileNotFoundError(
            f"none of {[c.name for c in candidates]} in {project_dir} compiled successfully"
        ) from last_error

    def _trial_compile(self, root):
        """Quietly try compiling `root`; raises CalledProcessError if it
        doesn't work. Output is captured (not streamed) since candidates
        expected to fail (e.g. the wrong engine) shouldn't spam the console —
        see compile_pdf() for the real, visible build.

        -outdir is root.parent (same as cwd) rather than some enclosing
        project_dir: pdflatex honors -outdir for its own output, but bibtex
        doesn't — it runs relative to cwd and writes .bbl/.blg there
        regardless. If -outdir pointed elsewhere, bibtex would read
        whatever stale .aux happens to already be sitting in root.parent
        (e.g. copied in from an earlier build) instead of the fresh one
        pdflatex just wrote to -outdir, silently producing a bibliography
        that's missing anything newly cited — undefined-citation `[?]`s in
        the PDF with no error to flag it.
        """
        subprocess.run(
            ["latexmk", "-C", f"-outdir={root.parent}", root.name],
            cwd=root.parent, capture_output=True, timeout=self.timeout,
        )

        subprocess.run(
            ["latexmk", "-g", "-pdf", "-interaction=nonstopmode", "-halt-on-error", f"-outdir={root.parent}", root.name],
            cwd=root.parent, check=True, capture_output=True, timeout=self.timeout,
        )

    def compile_pdf(self, project_dir):
        project_dir = Path(project_dir).resolve()
        root = self.find_root(project_dir)
        try:
            subprocess.run(
                ["latexmk", "-C", f"-outdir={root.parent}", root.name],
                cwd=root.parent, capture_output=True, timeout=self.timeout,
            )

            subprocess.run(
                # -g forces a full rebuild even if latexmk's cache thinks
                # nothing changed; without it, a previously *failed* run
                # (e.g. due to a missing font that's since been installed)
                # leaves stale state that makes latexmk refuse to retry.
                # -outdir=root.parent, not project_dir: see
                # _trial_compile()'s docstring for why outdir and cwd must
                # match.
                # capture_output: this is the real, full build (unlike the
                # quiet trial compiles in find_root()), so without this its
                # entire pdflatex/bibtex log would stream straight to
                # stdout on every call — capture it instead so callers doing
                # many compiles in a row (review/perturb) stay quiet, and
                # attach it to the exception below so a failure isn't silent.
                ["latexmk", "-g", "-pdf", "-interaction=nonstopmode", "-halt-on-error", f"-outdir={root.parent}", root.name],
                cwd=root.parent, check=True, capture_output=True, timeout=self.timeout,
            )
        except subprocess.CalledProcessError as e:
            log = (e.stdout.decode(errors="ignore") + e.stderr.decode(errors="ignore")).strip()
            raise RuntimeError(f"latexmk failed for {root.name}:\n{log}") from e
        return root.with_suffix(".pdf")


    def walk_files(self, tex_path, seen=None):
        seen = seen if seen is not None else set()
        tex_path = Path(tex_path)
        if tex_path in seen:
            return
        seen.add(tex_path)
        text = tex_path.read_text(errors="ignore")
        yield tex_path, text
        for m in re.finditer(r"\\(?:input|include)\{([^}]+)\}", _strip_comments(text)):
            path = tex_path.parent / m.group(1)
            path = path if path.suffix else path.with_suffix(".tex")
            if path.exists():
                yield from self.walk_files(path, seen)


    def find_structure(self, project_dir):
        items = []
        for path, text in self.walk_files(self.find_root(project_dir)):
            clean = _strip_comments(text)
            for m in re.finditer(rf"\\({SEC_CMDS})\*?\{{([^}}]*)\}}", clean):
                items.append({"type": m[1], "title": m[2], "file": path, "search": m[0]})
            for _ in re.finditer(r"\\begin\{abstract\}", clean):
                items.append({"type": "abstract", "title": "", "file": path, "search": r"\begin{abstract}"})
            if re.search(r"\\appendix\b", clean):
                items.append({"type": "appendix", "title": "", "file": path, "search": r"\appendix"})
        return items
