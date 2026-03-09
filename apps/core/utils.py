"""
Helper utilities for the PYQ Analyzer application.
"""
import hashlib
import re
from typing import Optional


def generate_file_hash(file_content: bytes) -> str:
    """Generate SHA-256 hash of file content for duplicate detection."""
    return hashlib.sha256(file_content).hexdigest()


def clean_text(text: str) -> str:
    """Clean and normalize text for processing."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters except punctuation
    text = re.sub(r'[^\w\s.,;:?!()-]', '', text)
    return text.strip()


def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate text to a maximum length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_question_number(text: str) -> Optional[str]:
    """Extract question number from text (e.g., 'Q1', '1.', '1a)')."""
    patterns = [
        r'^[Qq]\.?\s*(\d+[a-zA-Z]?)',
        r'^(\d+)\s*[.)]\s*',
        r'^(\d+[a-zA-Z]?)\s*[.)]\s*',
    ]
    for pattern in patterns:
        match = re.match(pattern, text.strip())
        if match:
            return match.group(1)
    return None


def safe_filename(filename: str) -> str:
    """Convert a string to a safe filename."""
    # Remove or replace unsafe characters
    filename = re.sub(r'[^\w\s.-]', '', filename)
    filename = re.sub(r'\s+', '_', filename)
    return filename[:255]  # Max filename length
