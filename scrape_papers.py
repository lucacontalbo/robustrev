"""Scrapes arXiv for papers that ship LaTeX source which actually compiles,
and assembles them into scraped_papers/ using the same <name>/latex/ layout
as papers/ (here <name> is the arXiv id, since it's the natural unique key
for scraped content, unlike a title).

No model calls: eligibility is purely "has a LaTeX source" + "it compiles
with LatexCompiler" (the same compiler review/perturb already use). Network
access is stdlib-only (urllib + arXiv's public Atom API) — no new deps.

Resumable: progress (arXiv pagination cursor, ids already attempted, ids
already accepted) is checkpointed to --state-file after every paper, so a
long run can be killed and restarted without losing work or re-downloading
what it already has.

Usage:
    python scrape_papers.py --target 1000
    python scrape_papers.py --target 5   # smoke-test on a handful first
"""
import argparse
import gzip
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from latex_compile import LatexCompiler

ARXIV_API = "https://export.arxiv.org/api/query"
EPRINT_URL = "https://export.arxiv.org/e-print/{id}"
USER_AGENT = "robustrev-scraper/1.0 (research use; see repo README)"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

DEFAULT_CATEGORIES = ["cs.CL", "cs.LG", "stat.ML", "cs.AI", "cs.NE"]
OUTPUT_DIR = Path(__file__).parent / "scraped_papers"
STATE_PATH = Path(__file__).parent / "scraped_papers_state.json"
LOG_PATH = Path(__file__).parent / "scraped_papers_log.jsonl"


# -- arXiv API -----------------------------------------------------------

def build_search_query(categories, start_year):
    cats = " OR ".join(f"cat:{c}" for c in categories)
    return f"({cats}) AND submittedDate:[{start_year}01010000 TO 209912312359]"


def fetch_page(search_query, start, page_size, retries=5):
    params = {
        "search_query": search_query, "start": start, "max_results": page_size,
        "sortBy": "submittedDate", "sortOrder": "ascending",
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            wait = min(60, 5 * (attempt + 1))
            print(f"  arXiv API request failed ({e}); retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"arXiv API request failed after {retries} retries: {url}")


def parse_entries(xml_bytes):
    root = ET.fromstring(xml_bytes)
    entries = []
    for entry in root.findall("a:entry", ATOM_NS):
        raw_id = entry.find("a:id", ATOM_NS).text.strip()
        arxiv_id = re.sub(r"v\d+$", "", raw_id.rsplit("/", 1)[-1])
        title = " ".join(entry.find("a:title", ATOM_NS).text.split())
        published = entry.find("a:published", ATOM_NS).text
        categories = [c.get("term") for c in entry.findall("a:category", ATOM_NS)]
        primary = entry.find("arxiv:primary_category", ATOM_NS)
        entries.append({
            "id": arxiv_id,
            "title": title,
            "year": int(published[:4]),
            "categories": categories,
            "primary_category": primary.get("term") if primary is not None else None,
        })
    return entries


# -- source download + eligibility check ----------------------------------

def download_source(arxiv_id, dest_dir, timeout=60):
    """Downloads and extracts the paper's e-print into dest_dir. Returns
    True if a LaTeX source was found (dest_dir now holds it); False if this
    paper has no LaTeX source (arXiv served a bare PDF instead — happens for
    PDF-only submissions) or the archive couldn't be extracted."""
    url = EPRINT_URL.format(id=arxiv_id)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()

    if data[:4] == b"%PDF":
        return False  # PDF-only submission, no source to compile

    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            try:
                tar.extractall(dest_dir, filter="data")
            except TypeError:
                tar.extractall(dest_dir)  # Python < 3.12: no `filter` kwarg
        return True
    except tarfile.ReadError:
        pass  # not a tarball; maybe a single gzipped .tex file, try that

    try:
        text = gzip.decompress(data)
    except OSError:
        return False
    (dest_dir / "main.tex").write_bytes(text)
    return True


def try_compile(source_dir, timeout):
    """Returns the compiled PDF path on success, None on any failure."""
    try:
        return LatexCompiler(timeout=timeout).compile_pdf(source_dir)
    except Exception:
        return None


# -- state / logging -------------------------------------------------------

def load_state(target):
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text())
        state["attempted_ids"] = set(state["attempted_ids"])
        state.setdefault("eligible_titles", [])  # older state files predate this field
        state["target"] = target  # a fresh --target on resume overrides whatever was saved before
        return state
    return {"target": target, "next_start": 0, "attempted_ids": set(), "eligible_ids": [], "eligible_titles": []}


def save_state(state):
    to_write = dict(state, attempted_ids=sorted(state["attempted_ids"]))
    STATE_PATH.write_text(json.dumps(to_write, indent=2))


def log_attempt(arxiv_id, outcome, detail=""):
    with LOG_PATH.open("a") as f:
        f.write(json.dumps({"id": arxiv_id, "outcome": outcome, "detail": detail[:300]}) + "\n")


# -- main scrape loop -------------------------------------------------------

def scrape(target, categories, start_year, page_size, api_delay, download_delay, compile_timeout):
    OUTPUT_DIR.mkdir(exist_ok=True)
    state = load_state(target)
    search_query = build_search_query(categories, start_year)

    print(f"Resuming: {len(state['eligible_ids'])}/{target} eligible so far, "
          f"{len(state['attempted_ids'])} candidates attempted, next_start={state['next_start']}")

    while len(state["eligible_ids"]) < target:
        page = fetch_page(search_query, state["next_start"], page_size)
        entries = parse_entries(page)
        if not entries:
            raise RuntimeError(
                f"arXiv returned no more results at start={state['next_start']} "
                f"but only {len(state['eligible_ids'])}/{target} eligible papers found — "
                "exhausted the candidate pool for this query."
            )
        state["next_start"] += page_size
        time.sleep(api_delay)  # be polite to the API between page fetches

        for entry in entries:
            if len(state["eligible_ids"]) >= target:
                break
            arxiv_id = entry["id"]
            if arxiv_id in state["attempted_ids"]:
                # Same arXiv id seen again (e.g. pagination drift from new
                # papers landing between page fetches) — already covered,
                # whatever the outcome was the first time. Guarantees no
                # arxiv_id is ever downloaded/compiled/counted twice.
                continue
            state["attempted_ids"].add(arxiv_id)

            # Same paper resubmitted under a *different* arxiv_id (rarer,
            # but happens) — catch it by title before spending a download
            # and a compile on a duplicate.
            normalized_title = entry["title"].strip().lower()
            if normalized_title in state["eligible_titles"]:
                log_attempt(arxiv_id, "duplicate_title", entry["title"])
                save_state(state)
                continue

            with tempfile.TemporaryDirectory(prefix="arxiv_scrape_") as tmp:
                staging = Path(tmp) / "latex"
                try:
                    has_source = download_source(arxiv_id, staging)
                except Exception as e:
                    log_attempt(arxiv_id, "download_failed", str(e))
                    save_state(state)
                    time.sleep(download_delay)
                    continue
                time.sleep(download_delay)  # be polite between e-print downloads

                if not has_source:
                    log_attempt(arxiv_id, "no_latex_source")
                    save_state(state)
                    continue

                pdf_path = try_compile(staging, compile_timeout)
                if pdf_path is None:
                    log_attempt(arxiv_id, "compile_failed")
                    save_state(state)
                    continue

                paper_dir = OUTPUT_DIR / arxiv_id
                if paper_dir.exists():
                    shutil.rmtree(paper_dir)
                paper_dir.mkdir(parents=True)
                shutil.copytree(staging, paper_dir / "latex")
                (paper_dir / "metadata.json").write_text(json.dumps({
                    "arxiv_id": arxiv_id,
                    "title": entry["title"],
                    "year": entry["year"],
                    "categories": entry["categories"],
                    "primary_category": entry["primary_category"],
                    "source_url": f"https://arxiv.org/abs/{arxiv_id}",
                }, indent=2))

            # Belt-and-suspenders: both guards above should already make this
            # unreachable. If it ever fires anyway, don't crash an
            # hours-long unattended run over it — drop the copy just
            # written, skip this candidate without counting it, and move on
            # to the next one.
            if arxiv_id in state["eligible_ids"] or normalized_title in state["eligible_titles"]:
                shutil.rmtree(paper_dir, ignore_errors=True)
                log_attempt(arxiv_id, "duplicate_slipped_through")
                save_state(state)
                continue

            state["eligible_ids"].append(arxiv_id)
            state["eligible_titles"].append(normalized_title)
            log_attempt(arxiv_id, "eligible")
            save_state(state)
            print(f"[{len(state['eligible_ids'])}/{target}] eligible: {arxiv_id} — {entry['title'][:80]}")

    print(f"Done: {len(state['eligible_ids'])} eligible papers in {OUTPUT_DIR} "
          f"(attempted {len(state['attempted_ids'])} candidates total).")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", type=int, default=1000, help="number of eligible papers to collect (default: 1000)")
    parser.add_argument("--categories", nargs="+", default=DEFAULT_CATEGORIES, help="arXiv categories (OR'd together)")
    parser.add_argument("--start-year", type=int, default=2025, help="only papers submitted from this year onward")
    parser.add_argument("--page-size", type=int, default=100, help="arXiv API results per page (max 100)")
    parser.add_argument("--api-delay", type=float, default=3.0, help="seconds to sleep between arXiv API calls")
    parser.add_argument("--download-delay", type=float, default=2.0, help="seconds to sleep between e-print downloads")
    parser.add_argument("--compile-timeout", type=float, default=120.0, help="per-candidate latexmk timeout, seconds")
    args = parser.parse_args()

    scrape(
        target=args.target, categories=args.categories, start_year=args.start_year,
        page_size=args.page_size, api_delay=args.api_delay, download_delay=args.download_delay,
        compile_timeout=args.compile_timeout,
    )


if __name__ == "__main__":
    main()
