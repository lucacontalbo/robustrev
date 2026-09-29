import re
import os
import base64
from pdfminer.high_level import extract_text as pdfminer_extract_text

from docling.document_converter import DocumentConverter

import logging

logging.getLogger("pdfminer").setLevel(logging.ERROR)
docling_converter = DocumentConverter()


def save_md(content, save_path):
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(content)


def docling_pdf_to_md(pdf_path):
    "converts pdf to md and saves in the appropriate directory as well"
    md_path = pdf_path.replace("pdfs", "mds").replace(".pdf", ".md")
    # check if the md file already exists
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as md_file:
            return md_file.read()

    result = docling_converter.convert(pdf_path)
    md = result.document.export_to_markdown()
    save_md(md, md_path)
    return md


def encode_file_to_base64(file_path: str) -> str:
    """Encode a file to base64 format."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")


def get_mime_type(filename: str) -> str:
    """Get MIME type based on file extension."""
    ext = os.path.splitext(filename)[1].lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".pdf": "application/pdf",
        ".md": "text/plain",
        ".json": "application/json",
        ".jsonl": "application/jsonl",
        ".html": "text/html",
        ".xml": "application/xml",
        ".csv": "text/csv",
        ".md": "text/markdown",
    }
    return mime_types.get(ext, "application/octet-stream")


def extract_text_from_pdf(pdf_path: str, converter: str = "pdfminer") -> str:
    """Extracts text content from a PDF file."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    try:
        if converter == "pdfminer":
            return pdfminer_extract_text(pdf_path)
        elif converter == "docling":
            return docling_pdf_to_md(pdf_path)
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        raise


def clean_markdown(markdown_text: str) -> str:
    """
    Cleans markdown text converted from a PDF by removing artifacts.

    This function specifically targets and removes:
    1. Lines that contain only a number (e.g., page or line numbers like '040').
    2. Entire lines containing markdown-formatted embedded images with a data URI
       (e.g., '![Image](data:image/png;base64,...)').

    Args:
        markdown_text: A string containing the raw markdown text.

    Returns:
        A string with the unwanted artifacts removed, ready for LLM processing.
    """
    # Split the text into individual lines
    lines = markdown_text.split("\n")
    cleaned_lines = []

    # Compile a regular expression to detect embedded image data URIs
    # This looks for ![...](data:image/...)
    image_pattern = re.compile(r"^\s*!\[.*?\]\(data:image/.*?\)\s*$")

    for line in lines:
        # 1. Check for lines that are just numbers (ignoring whitespace)
        stripped_line = line.strip()
        if stripped_line.isdigit():
            continue  # Skip this line

        # 2. Check for embedded image data URI lines
        if image_pattern.match(line):
            continue  # Skip this line

        # If the line is not an artifact, add it to our cleaned list
        cleaned_lines.append(line)

    # Join the cleaned lines back into a single string
    return re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines).strip())
