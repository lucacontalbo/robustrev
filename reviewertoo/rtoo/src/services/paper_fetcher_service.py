# src/services/paper_fetcher_service.py

import os
import re
import tqdm

import numpy as np
import requests
import logging
import time
import random
import json
from dotenv import load_dotenv
from urllib.parse import quote
import http.client
import concurrent.futures
import semanticscholar, arxiv
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from xml.etree import ElementTree

from src.utils.file_utils import extract_text_from_pdf
from src.utils.parser_utils import parse_llm_json_response
from src.services.llm_service_router import LLMServiceRouter
from src.agents.litllm.components.bibliography_locator_agent import (
    BibliographyLocatorAgent,
)
from src.agents.litllm.components.bibliography_extraction_agent import (
    BibliographyExtractionAgent,
)

logger = logging.getLogger(__name__)
load_dotenv()


def _search_with_semanticscholar(
    queries: List[str], limit_per_query: int
) -> List[Dict[str, Any]]:
    """
    Searches for papers using the official Semantic Scholar API.
    """
    # NOTE: This is a basic implementation. The semanticscholar library has more options.
    # The API is also less permissive than others, so rate limiting is important.
    # See: https://github.com/danielnsilva/semanticscholar
    api_key = os.getenv("S2_API_KEY")
    s2 = semanticscholar.SemanticScholar(api_key=api_key, timeout=30, retry=False)
    all_results = []
    logger.info(
        "Searching with Semantic Scholar API. This may be slow due to rate limits."
    )
    for query in tqdm.tqdm(queries, desc="Searching Semantic Scholar"):
        for _ in range(5):
            try:
                # The library handles searching and returns a list of Paper objects
                results = s2.search_paper(query, limit=limit_per_query)
                for ix, item in enumerate(results):
                    if ix > limit_per_query:
                        break
                    # Convert the Paper object to our standard dictionary format
                    item = dict(item)
                    all_results.append(
                        {
                            "title": item["title"],
                            "arxiv_id": item.get("externalIds").get("ArXiv"),
                            "doi": item.get("externalIds").get("DOI"),
                            "abstract": item.get("abstract"),
                            "openalex_id": None,  # S2 does not provide this
                            "publication_date": str(item.get("publicationDate")),
                        }
                    )
                time.sleep(2)  # Respect rate limits
                break
            except Exception as e:
                logger.warning(
                    f"Semantic Scholar search for query '{query}' failed: {e}. Retrying..."
                )
                time.sleep(5)
    return all_results


def _search_with_arxiv(
    queries: List[str], limit_per_query: int
) -> List[Dict[str, Any]]:
    """
    Searches for papers using the official arXiv API with translated query strings.
    """
    all_results = []
    logger.info("Searching with arXiv API using translated queries.")
    for query in tqdm.tqdm(queries, desc="Searching arXiv"):
        try:
            search = arxiv.Search(
                query=query,
                max_results=limit_per_query,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            for result in search.results():
                all_results.append(
                    {
                        "title": result.title,
                        "arxiv_id": result.get_short_id(),
                        "doi": result.doi,
                        "abstract": result.summary.replace("\n", " ").strip(),
                        "openalex_id": None,
                        "publication_date": str(result.published),
                        "authors": [a.name for a in result.authors],
                        "pdf_url": result.pdf_url,
                    }
                )
        except Exception as e:
            logger.error(f"arXiv search for query '{query}' failed: {e}")
    return all_results


def _search_google_scholar_with_serper(
    query: str, api_key: str, limit: int = 10
) -> List[Dict[str, Optional[str]]]:
    if not api_key:
        raise ValueError("SERPER_API_KEY not found or provided.")

    payload = json.dumps({"q": query + " site:arxiv.org", "num": limit})
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    parsed_results = []

    try:
        conn = http.client.HTTPSConnection("google.serper.dev")
        conn.request("POST", "/scholar", payload, headers)
        response = conn.getresponse()
        if response.status != 200:
            logger.error(
                f"Error calling Serper API: {response.status} {response.reason}"
            )
            return []
        results = json.loads(response.read().decode("utf-8")).get("organic", [])

        for result in results:
            title = result.get("title")
            link = result.get("link", "")
            pdfUrl = result.get("pdfUrl", "")
            arxiv_id = None
            if "arxiv.org/abs/" in link:
                match = re.search(r"arxiv.org/abs/([\d\.]+[v\d]*)", link)
                if match:
                    arxiv_id = match.group(1)

            if title:
                parsed_results.append(
                    {"title": title, "arxiv_id": arxiv_id, "pdfUrl": pdfUrl}
                )

        return parsed_results

    except Exception as e:
        logger.error(f"Error processing Serper API response for query '{query}': {e}")
        return []


def _parse_arxiv_entry(
    entry_xml: ElementTree.Element, namespace: str
) -> Dict[str, Any]:
    """Parses a single <entry> element from the arXiv API response."""
    # Find elements using the namespace
    entry_id = entry_xml.find(f"{namespace}id").text.split("/abs/")[-1]
    title = entry_xml.find(f"{namespace}title").text.strip()
    abstract = entry_xml.find(f"{namespace}summary").text.replace("\n", " ").strip()
    published_date = entry_xml.find(f"{namespace}published").text.strip()

    return {
        "title": title,
        "arxiv_id": entry_id,
        "abstract": abstract,
        "publication_date": published_date,
        "openalex_id": None,
        "doi": None,
        "cited_by_count": None,
        "relevance_score": None,
    }


def make_request_with_backoff(
    request_func: Callable,
    max_retries: int = 5,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    jitter: float = 0.1,
) -> requests.Response:
    """
    Make an HTTP request with exponential backoff retry logic.

    Args:
        request_func: A callable that makes the HTTP request and returns a Response
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplicative factor for increasing delay
        max_delay: Maximum delay in seconds
        jitter: Random factor to add to delay (0.1 = +/- 10%)

    Returns:
        The HTTP response if successful

    Raises:
        requests.RequestException: If all retry attempts fail
    """
    delay = initial_delay
    last_exception = None

    for retry in range(max_retries + 1):
        try:
            response = request_func()
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            last_exception = e

            # If this was our last retry, raise the exception
            if retry >= max_retries:
                logger.error(f"Request failed after {max_retries} retries: {str(e)}")
                raise

            # If we got a 429 (Too Many Requests), respect Retry-After header if present
            if (
                hasattr(e, "response")
                and e.response is not None
                and e.response.status_code == 429
            ):
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except (ValueError, TypeError):
                        # If Retry-After is not a valid number, use our exponential backoff
                        pass

            # Calculate the next delay with jitter
            jitter_amount = random.uniform(-jitter, jitter) * delay
            actual_delay = min(delay + jitter_amount, max_delay)

            logger.warning(
                f"Request failed (attempt {retry+1}/{max_retries+1}): {str(e)}. "
                f"Retrying in {actual_delay:.2f} seconds..."
            )

            time.sleep(actual_delay)
            # Increase the delay for the next retry
            delay = min(delay * backoff_factor, max_delay)

    # We should never reach here due to the raise in the loop, but just in case
    if last_exception:
        raise last_exception
    return None  # To satisfy the type checker


def sanitize_title(title: str) -> str:
    """
    Sanitize a paper title by removing problematic characters.

    Args:
        title: The title to sanitize

    Returns:
        Sanitized title
    """
    if not title:
        return None
    chars_to_remove = ".:'\",()!?"
    translation_table = str.maketrans("", "", chars_to_remove)
    return title.translate(translation_table)


def fetch_paper_from_arxiv(
    arxiv_id: Optional[str] = None, title: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetches paper metadata from arXiv, prioritizing a direct lookup by ID.
    If ID is not provided or fails, it falls back to searching by title.

    Args:
        arxiv_id: The arXiv ID of the paper.
        title: The title of the paper to search for (used as fallback).

    Returns:
        A dictionary containing paper metadata if found, otherwise None.
    """
    if not arxiv_id and not title:
        raise ValueError(
            "Either arxiv_id or title must be provided to fetch from arXiv."
        )

    try:
        # Priority 1: Search by arXiv ID for a direct hit
        if arxiv_id:
            arxiv_search_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
        # Priority 2: Fallback to searching by title
        else:
            sanitized = sanitize_title(title)
            if not sanitized:
                return None
            arxiv_search_url = f'http://export.arxiv.org/api/query?search_query=all:"{quote(sanitized)}"&max_results=1'

        def make_request():
            return requests.get(arxiv_search_url)

        arxiv_response = make_request_with_backoff(make_request)

        # Use ElementTree for robust XML parsing
        root = ElementTree.fromstring(arxiv_response.content)
        namespace = "{http://www.w3.org/2005/Atom}"
        entry = root.find(f"{namespace}entry")

        if entry is not None:
            return _parse_arxiv_entry(entry, namespace)

    except Exception as e:
        logger.warning(
            f"Failed to fetch or parse from arXiv API for id='{arxiv_id}', title='{title}': {str(e)}"
        )

    return None


def fetch_papers_from_arxiv_in_batch(
    arxiv_ids: list[str], max_workers: int = 5, chunk_size: int = 100
) -> list[dict]:
    """
    Fetches metadata for a list of arXiv IDs concurrently, with retries and rate limiting.

    Args:
        arxiv_ids: A list of arXiv IDs to fetch.
        max_workers: The number of parallel threads to use for fetching.
        chunk_size: The number of IDs to include in each API call.

    Returns:
        A list of dictionaries, each containing paper metadata.
    """
    if not arxiv_ids:
        return []

    all_metadata = []

    def fetch_chunk(chunk: list[str], retry_count: int = 3) -> list[dict] | None:
        """Fetches a single chunk of papers with a retry mechanism."""
        for attempt in range(retry_count):
            try:
                search = arxiv.Search(id_list=chunk, max_results=len(chunk))
                chunk_metadata = []
                for result in search.results():
                    chunk_metadata.append(
                        {
                            "arxiv_id": result.get_short_id(),
                            "title": result.title,
                            "abstract": result.summary.replace("\n", " "),
                            "authors": [a.name for a in result.authors],
                            "publication_date": str(result.published),
                            "pdf_url": result.pdf_url,
                        }
                    )
                    search = arxiv.Search(id_list=chunk, max_results=len(chunk))

                time.sleep(3)  # Respect arXiv API rate limits
                return chunk_metadata
            except Exception as e:
                logging.error(
                    f"Attempt {attempt + 1} failed for chunk starting with {chunk[0]}: {e}"
                )
                if attempt < retry_count - 1:
                    time.sleep(5 * (attempt + 1))  # Exponential backoff
                else:
                    logging.error(
                        f"Failed to fetch chunk starting with {chunk[0]} after {retry_count} attempts."
                    )
                    return None

    chunks = [
        arxiv_ids[i : i + chunk_size] for i in range(0, len(arxiv_ids), chunk_size)
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        with tqdm.tqdm(total=len(chunks), desc="Fetching from arXiv") as pbar:
            future_to_chunk = {
                executor.submit(fetch_chunk, chunk): chunk for chunk in chunks
            }
            for future in concurrent.futures.as_completed(future_to_chunk):
                result = future.result()
                if result:
                    all_metadata.extend(result)
                pbar.update(1)

    return all_metadata


def fetch_paper_from_openalex(
    query: Union[str, Dict],
    email: Optional[str] = None,
    limit: int = 1,
    openalex_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch paper metadata from OpenAlex API by paper query.

    Args:
        query: The query of the paper to search for (can be a string or a translated dict)
        email: Optional email to include in API requests for better rate limits
        limit: The maximum number of papers to return

    Returns:
        A list of dictionaries, each containing paper metadata

    Raises:
        ValueError: If there was an API error
    """

    def process_abstract_inverted_index(abstract_inverted_index):
        """
        Convert the abstract_inverted_index from OpenAlex to a readable abstract text.

        Parameters:
            abstract_inverted_index (dict): The abstract_inverted_index from OpenAlex

        Returns:
            str: The readable abstract text
        """
        if not abstract_inverted_index or not isinstance(abstract_inverted_index, dict):
            return "Abstract not available"

        # Create a list of words with their positions
        word_positions = []
        for word, positions in abstract_inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))

        # Sort by position
        word_positions.sort()

        # Join words to form the abstract
        abstract = " ".join(word for _, word in word_positions)

        return abstract

    # Construct API URL with proper query parameters
    base_url = "https://api.openalex.org/works"
    headers = {}
    ARXIV_SOURCE_ID = "S4393918464|S4306400194"
    #

    # Add polite pool identifier if email is provided
    if email:
        headers["User-Agent"] = f"mailto:{email}"

    if openalex_id:
        base_url += f"/{quote(openalex_id)}"
        params = {}
    elif isinstance(query, dict):
        # Path for pre-translated dict queries
        base_filters = [f"primary_location.source.id:{ARXIV_SOURCE_ID}"]
        llm_filter = query.get("filter")
        if llm_filter and isinstance(llm_filter, str):
            base_filters.append(llm_filter)

        params = {
            "search": query,
            # "filter": ",".join(base_filters),
            "sort": "relevance_score:desc",
            "per_page": limit,
        }
    elif isinstance(query, str):
        # Path for simple string-based queries
        sanitized_q = sanitize_title(query)
        if not sanitized_q:
            return []

        params = {
            "search": sanitized_q,
            # "filter": f"primary_location.source.id:{ARXIV_SOURCE_ID}",
            "sort": "relevance_score:desc",
            "per_page": limit,
        }
    else:
        logger.error(f"Unsupported query type for OpenAlex: {type(query)}")
        return []

    try:
        # Use exponential backoff for the API request
        def make_request():
            return requests.get(base_url, params=params, headers=headers)

        response = make_request_with_backoff(make_request)
        data = response.json()

        if "meta" in data:
            if data["meta"]["count"] == 0:
                logger.warning(f"No papers found with query: {query}")
                return []
            else:
                results = data.get("results", [])
        else:
            # If no meta, we assume a single result was returned
            if data.get("title"):
                # If the result is from arXiv, we can directly return it
                return [
                    {
                        "title": data["title"],
                        "abstract": process_abstract_inverted_index(
                            data.get("abstract_inverted_index", {})
                        ),
                        "arxiv_id": None,
                        "publication_date": data.get("publication_date"),
                        "openalex_id": data.get("id").split("/")[-1],
                        "doi": data.get("doi"),
                        "cited_by_count": data.get("cited_by_count"),
                        "relevance_score": data.get("relevance_score"),
                        "referenced_works": data.get("referenced_works", []),
                        "related_works": data.get("related_works", []),
                    }
                ]
            else:
                logger.warning(
                    f"Paper for {query} found from OpenAlex but not indexed in arXiv: {data.get('title', 'N/A')}"
                )
                results = []

        papers_metadata = []

        for paper in results:
            # Extract arXiv URL if available
            arxiv_id = None

            # First check if the paper is indexed on arXiv
            if "arxiv" in paper.get("indexed_in", []):
                # Try to get arXiv ID from IDs
                if paper.get("ids", {}).get("arxiv"):
                    arxiv_id = paper["ids"]["arxiv"].split("/")[-1]
                # If not found in IDs, check open access links
                elif paper.get("open_access", {}).get(
                    "oa_url"
                ) and "arxiv.org" in paper.get("open_access", {}).get("oa_url", ""):
                    arxiv_url = paper["open_access"]["oa_url"]
                    arxiv_id = arxiv_url.split("/")[-1]

            # If arxiv_url is still not found, try searching arxiv API directly
            paper_title = paper.get("title")
            # if not arxiv_id and paper_title:
            #     data = fetch_paper_from_arxiv(title=paper_title)
            #     if data and data.get("arxiv_id"):
            #         arxiv_id = data["arxiv_id"]

            # NOTE: adding this block makes it really serper expensive
            # so keeping it commented out for now

            # if not arxiv_id and paper_title:
            #     # try searching google scholar with serper to get the arxiv_id
            #     serper_results = _search_google_scholar_with_serper(
            #         paper_title, os.getenv("SERPER_API_KEY", ""), limit=1
            #     )
            #     if serper_results and serper_results[0].get("arxiv_id"):
            #         arxiv_id = serper_results[0]["arxiv_id"]

            # Construct the metadata dictionary
            metadata = {
                "title": paper_title,
                "arxiv_id": arxiv_id,
                "publication_date": paper.get("publication_date"),
                "openalex_id": paper.get("id").split("/")[-1],
                "doi": paper.get("doi"),
                "cited_by_count": paper.get("cited_by_count"),
                "relevance_score": paper.get("relevance_score"),
                "abstract": process_abstract_inverted_index(
                    paper.get("abstract_inverted_index", {})
                ),
                "referenced_works": paper.get("referenced_works", []),
                "related_works": paper.get("related_works", []),
            }
            papers_metadata.append(metadata)

        return papers_metadata

    except requests.RequestException as e:
        logger.error(f"Error fetching data from OpenAlex API: {str(e)}")
        raise ValueError(f"Failed to fetch paper data: {str(e)}")


class PaperFetcherService:
    """
    A service to find and fetch academic papers from various sources,
    with built-in caching for PDFs.
    """

    def __init__(self, email: Optional[str] = None, cache_dir: str = ".cache"):
        self.email = email
        self.pdf_cache_path = os.path.join(cache_dir, "pdfs")
        self.serper_api_key = os.getenv("SERPER_API_KEY")
        os.makedirs(self.pdf_cache_path, exist_ok=True)
        logger.info(
            f"PaperFetcherService initialized. PDF cache is at: {self.pdf_cache_path}"
        )

    def get_referenced_works_from_semanticscholar(
        self, paper_info: Dict[str, Any]
    ) -> Dict[str, List]:
        """
        Fetches the reference lists for a batch of arXiv IDs using the
        Semantic Scholar API.

        Args:
            paper_info: A list of dicts with arxiv_ids

        Returns:
            A list of dictionaries containing the data returned from the API.
        """
        # The API endpoint for batch paper lookups.
        api_url = "https://api.semanticscholar.org/graph/v1/paper/batch"

        fields = (
            "references.title,references.externalIds,referenceCount,references.abstract"
        )
        params = {"fields": fields}

        # Format the IDs for the API by prepending "ARXIV:".
        arxiv_ids = [o["arxiv_id"] for o in paper_info]
        s2_paper_ids = [f"ARXIV:{id}" for id in arxiv_ids]
        headers = {"x-api-key": os.getenv("S2_API_KEY")}

        # loop with 500 papers at a time, as 500 is the limit for batch request
        s2_results = []
        for i in tqdm.tqdm(
            range(0, len(s2_paper_ids), 50),
            desc="getting references from s2",
            total=int(np.ceil(len(s2_paper_ids) / 50)),
        ):
            s2_ids_batch = s2_paper_ids[i : i + 50]
            try:
                response = requests.post(
                    api_url,
                    params=params,
                    json={"ids": s2_ids_batch},
                    headers=headers,
                )
                response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
                s2_results.extend(response.json())
                # time.sleep(1)
            except requests.exceptions.HTTPError as http_err:
                print(
                    f"HTTP error occurred when fetching references from S2 API: {http_err}"
                )
                print(f"Response content: {response.text}")
                time.sleep(2)
            except Exception as err:
                print(
                    f"An other error occurred when fetching references from S2 API:: {err}"
                )
                time.sleep(2)
        if not s2_results:
            return
        references_dict = {}
        for i, result in enumerate(s2_results):
            if not result:
                continue
            references = result.get("references")
            query_id = arxiv_ids[i]
            _refs = []
            for ref in references:
                if not ref.get("externalIds"):
                    continue
                if not ref["externalIds"].get("ArXiv"):
                    continue
                _refs.append(
                    {
                        "arxiv_id": ref["externalIds"]["ArXiv"],
                        "title": ref.get("title"),
                        "abstract": ref.get("abstract"),
                    }
                )
            if not _refs:
                continue
            references_dict[query_id] = _refs
        return {"references": references_dict}

    def get_referenced_works_from_openalex(
        self, paper_info: Dict[str, Any]
    ) -> Dict[str, List]:
        """
        Gets referenced and related works for a paper from OpenAlex.
        Uses a DOI-first, title-fallback strategy.
        """
        base_url = "https://api.openalex.org/works"
        doi = paper_info.get("doi")
        title = paper_info.get("title")

        # Priority 1: Use DOI for a precise lookup.
        if doi:
            params = {"filter": f"doi:{doi}"}
            try:

                def make_request():
                    return requests.get(base_url, params=params)

                response = make_request_with_backoff(make_request)
                data = response.json()
                if data.get("results"):
                    work = data["results"][0]
                    return {
                        "referenced_works": work.get("referenced_works", []),
                        "related_works": work.get("related_works", []),
                    }
            except Exception as e:
                logger.warning(
                    f"OpenAlex DOI lookup for {doi} failed: {e}. Falling back to title search."
                )

        # Priority 2: Fallback to title search if DOI lookup fails or DOI is missing.
        if title:
            try:
                paper_metadata = fetch_paper_from_openalex(
                    query=title, email=self.email, limit=1
                )
                if paper_metadata:
                    work = paper_metadata[0]
                    return {
                        "referenced_works": work.get("referenced_works", []),
                        "related_works": work.get("related_works", []),
                    }
            except Exception as e:
                logger.error(f"OpenAlex title search for '{title}' failed: {e}")

        return {"referenced_works": [], "related_works": []}

    async def extract_bibliography_with_llm(
        self,
        pdf_path: str,
        llm_router: LLMServiceRouter,
        locator_agent: BibliographyLocatorAgent,
        extractor_agent: BibliographyExtractionAgent,
        pdf_converter: str = "docling",
    ) -> Optional[List[str]]:
        """
        Extracts a list of titles from a PDF's bibliography using a two-phase LLM process.
        """
        if not os.path.exists(pdf_path):
            logger.error(
                f"PDF not found at {pdf_path} for LLM bibliography extraction."
            )
            return None

        try:
            full_text = extract_text_from_pdf(pdf_path, converter=pdf_converter)

            bib_pattern = r"(?im)^\s*#{1,6}\s*(?:\d+\.?\s*)?(?:references|bibliography|works cited)\s*$"

            # Split the text by the pattern
            parts = re.split(bib_pattern, full_text, maxsplit=1)

            if len(parts) > 1:
                marked_text = parts[1].strip()
            else:
                logger.info(
                    "Could not locate a bibliography section for %s. Trying with an LLM..."
                    % pdf_path
                )
                locator_result = await locator_agent.execute(
                    llm_router, {"paper_text": full_text}, []
                )
                marked_text = locator_result.get("response")
                # remove anything between the <think></think> tags
                marked_text = re.sub(
                    r"<think>.*?</think>",
                    "",
                    marked_text,
                    flags=re.DOTALL,
                )

            if not marked_text:
                logger.error(
                    "LLM BibExtraction failed: Could not locate bibliography marker."
                )
                return None

            # Phase 2: Extract titles from the isolated section
            bib_text = marked_text
            # logger.info("Extracting titles from bibliography with LLM...")
            extractor_result = await extractor_agent.execute(
                llm_router, {"bibliography_text": bib_text}, []
            )
            response_json = parse_llm_json_response(
                extractor_result.get("response", "{}")
            )

            if response_json and "references" in response_json:
                extracted_titles = [
                    ref.get("title")
                    for ref in response_json["references"]
                    if ref.get("title")
                ]
                return extracted_titles
            else:
                logger.error(
                    "LLM BibExtraction failed: Could not parse JSON from extractor response."
                )
                return None

        except Exception as e:
            logger.error(
                f"An unexpected error occurred during the LLM BibExtraction process: {e}"
            )
            return None

    def _get_safe_filename(self, paper_id: str) -> str:
        """Creates a filesystem-safe name from a paper ID."""
        if not paper_id:
            return None
        return "".join(c for c in paper_id if c.isalnum() or c in "-_.").strip()

    def _download_pdf_from_arxiv(self, arxiv_id: str, save_path: str) -> bool:
        """Downloads a PDF from an ArXiv ID."""
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        try:
            response = requests.get(pdf_url, stream=True)
            response.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"Successfully downloaded {arxiv_id} to {save_path}")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to download PDF for {arxiv_id}: {e}")
            return False

    def fetch_pdfs(self, paper_ids: List[str]) -> Dict[str, str]:
        """
        Ensures PDFs for a list of paper IDs are available locally, using a cache.
        Returns a dictionary mapping paper_id to its local PDF file path.
        """
        local_pdf_paths = {}
        for paper_id in tqdm.tqdm(paper_ids, desc="Fetching/Verifying PDFs"):
            safe_filename = self._get_safe_filename(paper_id)
            if not safe_filename:
                continue

            pdf_path = os.path.join(self.pdf_cache_path, f"{safe_filename}.pdf")

            # 1. Check cache first
            if os.path.exists(pdf_path):
                logger.info(f"Cache hit for PDF: {paper_id}")
                local_pdf_paths[paper_id] = pdf_path
            else:
                # 2. If not in cache, attempt to download it (currently only from ArXiv)
                # ArXiv IDs are the most reliable for direct PDF downloads.
                # A more robust solution would check DOI resolvers, etc.
                logger.info(
                    f"Cache miss for {paper_id}. Attempting download from ArXiv..."
                )
                try:
                    success = self._download_pdf_from_arxiv(paper_id, pdf_path)
                    if success:
                        local_pdf_paths[paper_id] = pdf_path
                except Exception as e:
                    logger.warning(
                        f"Cannot download PDF for non-ArXiv ID '{paper_id}'. Download logic needs extension."
                    )

        return local_pdf_paths

    def search_papers(
        self,
        queries: List[str],
        api: str,
        limit_per_query: int = 5,
        openalex_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Takes a list of search queries and returns a de-duplicated list of paper metadata
        using a specified search API.

        Args:
            queries: A list of search strings.
            api: The search API to use ('serper', 'openalex', 'arxiv', 'semanticscholar').
            limit_per_query: The number of results to fetch for each query.
            openalex_ids: A list of OpenAlex IDs to fetch directly (bypasses query search).

        Returns:
            A de-duplicated list of paper metadata dictionaries.
        """
        all_papers = []

        if openalex_ids:
            logger.info(
                f"Fetching papers directly for {len(openalex_ids)} OpenAlex IDs."
            )
            for openalex_id in tqdm.tqdm(openalex_ids, desc="Fetching OpenAlex papers"):
                paper_metadata = fetch_paper_from_openalex(
                    query="n/a", email=self.email, openalex_id=openalex_id
                )
                if paper_metadata:
                    all_papers.extend(paper_metadata)

        elif api == "serper":
            logger.info("Searching with Serper API (Google Scholar)...")
            for query in tqdm.tqdm(queries, desc="Searching Serper"):
                serper_results = _search_google_scholar_with_serper(
                    query, self.serper_api_key, limit=limit_per_query
                )
                if serper_results:
                    ids_to_fetch = [
                        res["arxiv_id"] for res in serper_results if res.get("arxiv_id")
                    ]
                    if ids_to_fetch:
                        all_papers.extend(
                            fetch_papers_from_arxiv_in_batch(ids_to_fetch)
                        )

        elif api == "openalex":
            logger.info("Searching with OpenAlex API...")
            for query in tqdm.tqdm(queries, desc="Searching OpenAlex"):
                all_papers.extend(
                    fetch_paper_from_openalex(
                        query, email=self.email, limit=limit_per_query
                    )
                )

        elif api == "arxiv":
            logger.info("Searching with arXiv API...")
            all_papers.extend(_search_with_arxiv(queries, limit_per_query))

        elif api == "semanticscholar":
            all_papers.extend(_search_with_semanticscholar(queries, limit_per_query))

        else:
            raise ValueError(
                f"Unsupported search API specified: '{api}'. Must be one of 'serper', 'openalex', 'arxiv', 'semanticscholar'."
            )

        # Deduplicate results using a more robust key
        unique_papers_dict = {}
        for paper in all_papers:
            # Normalize arXiv IDs by removing versions for better matching
            arxiv_id_base = None
            if paper.get("arxiv_id"):
                arxiv_id_base = re.sub(r"v\d+$", "", paper["arxiv_id"])

            # Use the first available unique identifier in order of preference
            unique_id = arxiv_id_base or paper.get("doi") or paper.get("openalex_id")
            if unique_id:
                if unique_id not in unique_papers_dict:
                    unique_papers_dict[unique_id] = paper
            else:
                # Fallback to title if no standard ID is present
                title = paper.get("title")
                if title and title.lower() not in unique_papers_dict:
                    unique_papers_dict[title.lower()] = paper

        unique_papers = list(unique_papers_dict.values())
        logger.info(
            f"Found {len(unique_papers)} unique papers from {len(all_papers)} total results after de-duplication."
        )
        return unique_papers
