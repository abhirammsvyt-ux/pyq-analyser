"""
PDF extraction pipeline for KTU Question Papers.
Routes ALL API calls through the central api_router for automatic provider rotation.
Priority: GitHub Models (primary) → Groq (keys 1-3, fallback) → OpenRouter → Gemini (keys 1-4)
"""
import json
import re
import os
import hashlib
import base64
import logging
import threading
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

# KTU Module Assignment Rules (fixed, never changes)
KTU_MODULE_MAP = {
    1: 1, 2: 1,
    3: 2, 4: 2,
    5: 3, 6: 3,
    7: 4, 8: 4,
    9: 5, 10: 5,
    11: 1, 12: 1,
    13: 2, 14: 2,
    15: 3, 16: 3,
    17: 4, 18: 4,
    19: 5, 20: 5,
}


class DailyQuotaExhaustedError(Exception):
    """Raised when ALL API providers have hit their daily limits."""
    pass


def get_module_for_question(q_number: int) -> int:
    """Return the correct module number (1-5) based on fixed KTU rules."""
    return KTU_MODULE_MAP.get(q_number, 1)


# ---------------------------------------------------------------------------
# Backward-compatible quota helper delegates
# ---------------------------------------------------------------------------

def check_quota_available() -> bool:
    """Check if any API provider has capacity. Delegates to api_router."""
    from .api_router import check_quota_available as _check
    return _check()


def should_stop_proactively() -> bool:
    """Check if all providers are exhausted. Delegates to api_router."""
    from .api_router import should_stop_proactively as _stop
    return _stop()


def record_usage(key_index: int, tokens: int):
    """Record API usage. Kept for backward compatibility but now a no-op
    since the api_router tracks its own request counts via Django cache."""
    pass


# ---------------------------------------------------------------------------
# PDF Detection
# ---------------------------------------------------------------------------

def detect_pdf_type(pdf_path: str) -> Dict[str, Any]:
    """Detect whether a PDF is text-based or requires image processing.

    Opens the PDF with PyMuPDF, extracts text from pages 1 and 2,
    checks character count and garbled patterns.

    Returns dict with keys: pdf_type, char_count, has_garbled, extracted_text
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    page_count = len(doc)

    # Extract text from first two pages for detection
    sample_text = ""
    for i in range(min(2, page_count)):
        page = doc[i]
        sample_text += page.get_text() or ""

    char_count = len(sample_text)

    # Check for garbled character patterns
    garbled_patterns = [
        r'[`~][a-zA-Z]',           # backtick/tilde followed by letters
        r'[{}][a-zA-Z]',           # curly braces mixed with letters
        r'\u20ac',                  # euro sign
        r'[^\x00-\x7F]{3,}',      # 3+ non-ASCII chars in sequence
        r'(?:[^a-zA-Z0-9\s.,;:!?()\'"-]{2,})',  # sequences of unusual chars
    ]

    has_garbled = False
    for pattern in garbled_patterns:
        if re.search(pattern, sample_text):
            has_garbled = True
            break

    # Extract full text if it's a clean text PDF
    full_text = ""
    if char_count >= 300 and not has_garbled:
        for page in doc:
            full_text += (page.get_text() or "") + "\n"
        pdf_type = 'text'
    else:
        pdf_type = 'image'

    doc.close()

    logger.info(
        f"PDF detection: type={pdf_type}, chars={char_count}, "
        f"garbled={has_garbled}, pages={page_count}"
    )

    return {
        'pdf_type': pdf_type,
        'char_count': char_count,
        'has_garbled': has_garbled,
        'extracted_text': full_text,
        'page_count': page_count,
    }


# ---------------------------------------------------------------------------
# Image Extraction
# ---------------------------------------------------------------------------

def _extract_images_pymupdf(pdf_path: str) -> List[str]:
    """Fallback: Convert PDF pages to images using PyMuPDF native rendering.

    Uses fitz.Matrix(1.5, 1.5) for 1.5x resolution (~108 DPI).
    Saves as JPEG quality 85 for ~10x smaller files vs PNG at 2x.
    """
    import fitz  # PyMuPDF
    from PIL import Image

    logger.info("Using PyMuPDF fallback for image extraction (no Poppler needed)")
    doc = fitz.open(pdf_path)
    base64_images = []

    # 1.5x zoom matrix (~108 DPI) — sufficient for text extraction
    zoom_matrix = fitz.Matrix(1.5, 1.5)

    for i, page in enumerate(doc):
        pixmap = page.get_pixmap(matrix=zoom_matrix)
        # Convert to JPEG via PIL for better compression
        img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

        # Resize if wider than 900px
        if img.width > 900:
            img.thumbnail((900, int(img.height * 900 / img.width)), Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format='JPEG', quality=85)
        b64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
        base64_images.append(b64_str)
        logger.debug(f"Page {i+1}: PyMuPDF rendered as JPEG ({len(buf.getvalue())} bytes)")

    doc.close()
    logger.info(f"PyMuPDF rendered {len(base64_images)} pages to JPEG images")
    return base64_images


def _extract_images_pdf2image(pdf_path: str) -> List[str]:
    """Primary: Convert PDF pages to 150 DPI JPEG images using pdf2image + Poppler.

    150 DPI JPEG quality 85 gives ~80-120KB per page vs ~800-1200KB at 300 DPI PNG.
    Returns list of base64-encoded JPEG strings.
    Raises ImportError if pdf2image is not installed.
    Raises Exception if Poppler is not found.
    """
    import os
    from pdf2image import convert_from_path
    from PIL import Image

    # Find poppler on Windows
    poppler_path = None
    possible_poppler = [
        r'c:\poppler\poppler-24.08.0\Library\bin',
        r'C:\Program Files\poppler\bin',
        r'C:\poppler\bin',
        r'C:\poppler\poppler-24.08.0\bin',
    ]
    for path in possible_poppler:
        if os.path.exists(path):
            poppler_path = path
            break

    logger.info(f"Converting PDF to 150 DPI JPEG images (poppler: {poppler_path or 'system PATH'})")

    if poppler_path:
        images = convert_from_path(pdf_path, dpi=150, poppler_path=poppler_path)
    else:
        images = convert_from_path(pdf_path, dpi=150)

    logger.info(f"Converted {len(images)} pages to images")

    base64_images = []
    for i, img in enumerate(images):
        # Resize if wider than 900px
        if img.width > 900:
            img.thumbnail((900, int(img.height * 900 / img.width)), Image.LANCZOS)

        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        base64_images.append(b64_str)
        logger.debug(f"Page {i+1}: encoded as base64 JPEG ({len(buffer.getvalue())} bytes)")

    return base64_images


def extract_page_images(pdf_path: str) -> List[str]:
    """Convert PDF pages to JPEG images as base64 strings.

    Tries pdf2image (Poppler) first for 150 DPI quality.
    Falls back to PyMuPDF native rendering if pdf2image/Poppler is unavailable.
    All images are JPEG quality 85, max 900px wide.
    """
    # Try pdf2image first (higher quality, 300 DPI)
    try:
        return _extract_images_pdf2image(pdf_path)
    except ImportError:
        logger.warning(
            "pdf2image is not installed. Falling back to PyMuPDF rendering. "
            "Install pdf2image and Poppler for 300 DPI quality: pip install pdf2image"
        )
    except Exception as e:
        error_msg = str(e).lower()
        if 'poppler' in error_msg or 'pdftoppm' in error_msg:
            logger.warning(
                f"Poppler not found ({e}). Falling back to PyMuPDF rendering. "
                "Install Poppler for 300 DPI quality."
            )
        else:
            logger.warning(f"pdf2image failed ({e}). Falling back to PyMuPDF rendering.")

    # Fallback to PyMuPDF native rendering
    return _extract_images_pymupdf(pdf_path)


def _resize_image_if_needed(b64_str: str, max_width: int = 900) -> str:
    """Resize a base64 image to max_width if it's wider.

    Maintains aspect ratio. Converts to JPEG quality 85.
    Returns base64 string (resized or original).
    """
    from PIL import Image

    image_bytes = base64.b64decode(b64_str)
    img = Image.open(BytesIO(image_bytes))

    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)
        logger.debug(f"Resized image from {img.width}x{img.height} to {max_width}x{new_height}")

    # Always output as JPEG for compression
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# ---------------------------------------------------------------------------
# Extraction Prompts (used by all providers via the router)
# ---------------------------------------------------------------------------

UNIVERSAL_GEMINI_PROMPT = (
    "You are reading a KTU APJ Abdul Kalam Technological University exam question paper. "
    "This paper may be from any subject, any semester, any year between 2019 and 2026. "
    "The paper format may vary slightly between years but always follows the same core structure. "
    "\n\n"
    "PART A always has exactly 10 questions numbered 1 through 10 each worth 3 marks. "
    "PART B always has questions numbered 11 through 20 each worth 14 marks total. "
    "Use ONLY the question number to determine module assignment. Never use printed module headings. "
    "Questions 1 and 2 are Module 1. Questions 3 and 4 are Module 2. Questions 5 and 6 are Module 3. "
    "Questions 7 and 8 are Module 4. Questions 9 and 10 are Module 5. "
    "Questions 11 and 12 are Module 1. Questions 13 and 14 are Module 2. "
    "Questions 15 and 16 are Module 3. Questions 17 and 18 are Module 4. "
    "Questions 19 and 20 are Module 5. "
    "\n\n"
    "For each question you must extract the complete untruncated question text exactly as written "
    "in the paper. Copy every word. Do not summarize. Do not paraphrase. Do not shorten. "
    "Include all numerical values, all conditions, all sub-clauses within the question text itself. "
    "The minimum acceptable text length is 15 characters. If a question text is shorter than "
    "15 characters something is wrong. "
    "\n\n"
    "Some Part B questions have sub-parts labeled a and b. Some Part B questions are single "
    "questions with no sub-parts. Handle both cases. For questions with sub-parts create two "
    "separate question objects, one for sub a and one for sub b, each with their own marks. "
    "For single Part B questions with no sub-parts create one question object with sub as "
    "empty string and marks as 14. "
    "\n\n"
    "If the paper has a stamp, watermark, college logo, or other overlay partially obscuring "
    "text, read around it and extract what is visible. Never skip a question because of overlays. "
    "\n\n"
    "Read the paper header carefully to extract subject code, subject name, exam year as a "
    "4-digit integer, and exam month as a word. If the header is unclear, make your best "
    "inference from any visible text. "
    "\n\n"
    "Return ONLY a raw JSON object. The very first character must be an opening curly brace. "
    "No markdown. No code blocks. No backticks. No explanation text before or after the JSON. "
    "The JSON schema must have these exact top-level keys: "
    "subject_code as string, subject_name as string, exam_year as integer, exam_month as string, "
    "questions as array. Each question object must have these exact keys: "
    "q_number as integer between 1 and 20, "
    "sub as string which is empty string or a or b, "
    "part as string which is A or B, "
    "marks as integer, "
    "module as integer between 1 and 5, "
    "text as string containing complete non-empty question text. "
    "\n\n"
    "Before returning the JSON, verify it internally. Check that no text field is empty. "
    "Check that all q_numbers are between 1 and 20. Check that the questions array has at least "
    "15 items for a complete paper. If any check fails, re-read the paper and fix the issue "
    "before returning."
)

GEMINI_IMAGE_PROMPT = UNIVERSAL_GEMINI_PROMPT

GEMINI_TEXT_PROMPT = (
    "You are reading extracted text from a KTU university exam question paper. The text may have "
    "minor formatting artifacts from PDF extraction. Your job is to identify and extract every "
    "question following the rules below. "
    "\n\n" + UNIVERSAL_GEMINI_PROMPT
)

GEMINI_RETRY_PROMPT = (
    "CRITICAL RETRY: The previous extraction attempt returned questions with empty text or "
    "missing data. This time you MUST extract the COMPLETE text for EVERY question. "
    "Do not return any question with an empty text field. Read the paper more carefully. "
    "\n\n" + UNIVERSAL_GEMINI_PROMPT
)


# ---------------------------------------------------------------------------
# JSON Parsing with Triple Fallback
# ---------------------------------------------------------------------------

def parse_gemini_response(raw_text: str, paper_id: str = '') -> dict:
    """Parse API response text as JSON with triple fallback and universal key mapping.

    Attempt 1: Strip markdown code blocks, then json.loads
    Attempt 2: Extract substring between first { and last }
    Attempt 3: Regex to find JSON object pattern

    After parsing, normalize question keys using universal key mapper.
    If all parsing attempts fail, save raw response to failed_responses/ and raise.
    """
    import datetime

    # Step 1: Strip whitespace
    raw_stripped = raw_text.strip()

    # Step 2: Remove markdown code block markers
    lines = raw_stripped.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped_line = line.strip()
        if stripped_line in ('```', '```json', '```JSON'):
            continue
        cleaned_lines.append(line)
    cleaned = '\n'.join(cleaned_lines).strip()

    parsed = None

    # Attempt 1: Direct parse
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 2: Find first { and last }
    if parsed is None:
        try:
            first_brace = cleaned.index('{')
            last_brace = cleaned.rindex('}')
            if first_brace < last_brace:
                substring = cleaned[first_brace:last_brace + 1]
                parsed = json.loads(substring)
        except (ValueError, json.JSONDecodeError):
            pass

    # Attempt 3: Regex to find JSON object
    if parsed is None:
        try:
            match = re.search(r'\{[\s\S]*\}', cleaned)
            if match:
                parsed = json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass

    # All three failed - save raw response and raise
    if parsed is None:
        failed_dir = Path(settings.BASE_DIR) / 'failed_responses'
        failed_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"paper_{paper_id}_{timestamp}.txt" if paper_id else f"unknown_{timestamp}.txt"
        failed_path = failed_dir / filename
        with open(failed_path, 'w', encoding='utf-8') as f:
            f.write(raw_text)
        logger.error(f"JSON parsing failed. Raw response saved to {failed_path}")

        raise ValueError(
            f"JSON parsing failed after 3 attempts. Raw response saved to {failed_path}. "
            f"First 200 chars: {raw_text[:200]}"
        )

    # Normalize question keys using universal key mapper
    if 'questions' in parsed and isinstance(parsed['questions'], list):
        parsed['questions'] = [_normalize_question_keys(q) for q in parsed['questions']]

    return parsed


def _normalize_question_keys(q: dict) -> dict:
    """Normalize question dict keys using universal key mapper.

    Tries multiple key variations for each required field and uses
    the first non-empty value found.
    """
    def _get_first(d, keys, default=None):
        for key in keys:
            val = d.get(key)
            if val is not None and val != '':
                return val
        return default

    text = _get_first(q, ['text', 'question_text', 'question', 'content',
                          'q_text', 'description', 'body'], default='')
    q_number = _get_first(q, ['q_number', 'question_number', 'number', 'qno',
                               'num', 'question_no', 'no'], default=0)
    sub = _get_first(q, ['sub', 'sub_question', 'subpart', 'part_label',
                          'sub_part', 'label'], default='')
    marks = _get_first(q, ['marks', 'mark', 'score', 'weightage', 'points'], default=0)
    module = _get_first(q, ['module', 'module_number', 'mod', 'module_no'], default=0)
    part = _get_first(q, ['part', 'section', 'part_type'], default='')

    # Type coercion
    try:
        q_number = int(q_number)
    except (TypeError, ValueError):
        q_number = 0
    try:
        marks = int(marks)
    except (TypeError, ValueError):
        marks = 0
    try:
        module = int(module)
    except (TypeError, ValueError):
        module = 0

    if sub is None:
        sub = ''
    sub = str(sub).strip()

    if part is None:
        part = ''
    part = str(part).strip().upper()

    text = str(text).strip() if text else ''

    return {
        'q_number': q_number,
        'text': text,
        'sub': sub,
        'marks': marks,
        'module': module,
        'part': part,
    }


# ---------------------------------------------------------------------------
# Universal Question Validator
# ---------------------------------------------------------------------------

def validate_and_clean_questions(questions: list, paper_metadata: dict = None) -> Tuple[list, dict]:
    """Validate parsed questions and return cleaned list with validation report.

    Applies universal KTU rules regardless of subject or year:
    - Removes questions with empty text
    - Corrects q_number using position inference
    - Recomputes module from q_number (always correct for KTU)
    - Infers marks from part and sub
    - Infers part from q_number
    - Normalizes sub field (never None)

    Returns (cleaned_questions, validation_report).
    """
    report = {
        'valid_count': 0,
        'invalid_count': 0,
        'corrections_made': 0,
        'warnings': [],
        'corrections_detail': [],
        'removed_questions': [],
    }

    cleaned = []

    for idx, q in enumerate(questions):
        q_number = q.get('q_number', 0)
        text = q.get('text', '')
        sub = q.get('sub')
        marks = q.get('marks', 0)
        part = q.get('part', '')

        # Rule 1: Reject empty text
        if text is None or not str(text).strip():
            report['invalid_count'] += 1
            report['removed_questions'].append({
                'index': idx, 'q_number': q_number, 'reason': 'empty text'
            })
            report['warnings'].append(f"Q{q_number} (index {idx}): removed - empty text")
            logger.warning(f"Validator: Removed Q{q_number} at index {idx} - empty text")
            continue

        text = str(text).strip()

        # Rule 2: Validate/infer q_number
        if q_number is None or q_number == 0 or not (1 <= q_number <= 20):
            # Attempt to infer from position
            inferred = _infer_q_number(questions, idx)
            if inferred:
                report['corrections_detail'].append(
                    f"Q at index {idx}: q_number {q_number} -> {inferred} (inferred)"
                )
                report['corrections_made'] += 1
                q_number = inferred
            else:
                report['invalid_count'] += 1
                report['removed_questions'].append({
                    'index': idx, 'q_number': q_number, 'reason': 'invalid question number'
                })
                report['warnings'].append(
                    f"Index {idx}: removed - invalid q_number={q_number}, cannot infer"
                )
                logger.warning(f"Validator: Removed index {idx} - invalid q_number={q_number}")
                continue

        # Rule 5: Infer part from q_number
        correct_part = 'A' if 1 <= q_number <= 10 else 'B'
        if part != correct_part:
            if part:
                report['corrections_detail'].append(
                    f"Q{q_number}: part '{part}' -> '{correct_part}'"
                )
                report['corrections_made'] += 1
            part = correct_part

        # Rule 3: Recompute module from q_number (always correct for KTU)
        correct_module = get_module_for_question(q_number)
        gemini_module = q.get('module', 0)
        if gemini_module != correct_module:
            if gemini_module:
                report['corrections_detail'].append(
                    f"Q{q_number}: module {gemini_module} -> {correct_module}"
                )
                report['corrections_made'] += 1

        # Rule 4: Infer marks if missing
        if marks is None or marks <= 0:
            if part == 'A':
                marks = 3
            elif sub in ('a',):
                marks = 8
            elif sub in ('b',):
                marks = 6
            else:
                marks = 14
            report['corrections_detail'].append(
                f"Q{q_number}: marks inferred as {marks}"
            )
            report['corrections_made'] += 1

        # Rule 6: Normalize sub
        if sub is None:
            sub = ''
        sub = str(sub).strip()

        # Check text length warning (not rejection)
        if len(text) < 15:
            report['warnings'].append(
                f"Q{q_number}: text suspiciously short ({len(text)} chars)"
            )

        cleaned.append({
            'q_number': q_number,
            'text': text,
            'sub': sub,
            'marks': marks,
            'module': correct_module,
            'part': part,
            'needs_review': len(text) < 15,
        })
        report['valid_count'] += 1

    # Check minimum question count
    if len(cleaned) < 15:
        report['warnings'].append(
            f"Only {len(cleaned)} valid questions (expected at least 15 for a complete paper)"
        )

    return cleaned, report


def _infer_q_number(questions: list, idx: int) -> Optional[int]:
    """Try to infer q_number from surrounding questions in the array."""
    # Look at previous valid q_number
    prev_qn = None
    for i in range(idx - 1, -1, -1):
        qn = questions[i].get('q_number', 0)
        if qn and 1 <= qn <= 20:
            prev_qn = qn
            break

    # Look at next valid q_number
    next_qn = None
    for i in range(idx + 1, len(questions)):
        qn = questions[i].get('q_number', 0)
        if qn and 1 <= qn <= 20:
            next_qn = qn
            break

    if prev_qn is not None and next_qn is not None:
        # If consecutive, the gap gives us the answer
        if next_qn - prev_qn == 2:
            return prev_qn + 1
    elif prev_qn is not None:
        candidate = prev_qn + 1
        if 1 <= candidate <= 20:
            return candidate
    elif next_qn is not None:
        candidate = next_qn - 1
        if 1 <= candidate <= 20:
            return candidate

    return None


# ---------------------------------------------------------------------------
# Quality Score Calculator
# ---------------------------------------------------------------------------

def compute_quality_score(questions: list, parsed_data: dict) -> int:
    """Compute a universal quality score for extraction results.

    Score starts at 100 and adjusts based on quality indicators.
    Returns integer score 0-110.
    """
    score = 100

    for q in questions:
        text = q.get('text', '')
        if not text or not str(text).strip():
            score -= 5
        elif len(str(text).strip()) < 15:
            score -= 3
        if q.get('q_number', 0) == 0:
            score -= 2

    if len(questions) < 15:
        score -= 10
    if not parsed_data.get('subject_code'):
        score -= 5

    # Bonuses
    if len(questions) >= 20:
        score += 5
    if all(len(str(q.get('text', '')).strip()) > 20 for q in questions if q.get('text')):
        score += 5

    return max(0, min(110, score))


# ---------------------------------------------------------------------------
# API Response Cache (file-based, MD5-keyed)
# ---------------------------------------------------------------------------

_CACHE_DIR = Path(settings.BASE_DIR) / 'gemini_cache'


def _get_pdf_hash(pdf_path: str) -> str:
    """Compute MD5 hash of a PDF file for cache keying."""
    h = hashlib.md5()
    with open(pdf_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def _get_cached_response(pdf_hash: str) -> Optional[str]:
    """Check if a cached API response exists for this PDF hash.
    Returns the raw JSON string if found, None otherwise.
    """
    cache_file = _CACHE_DIR / f"{pdf_hash}.json"
    if cache_file.exists():
        try:
            return cache_file.read_text(encoding='utf-8')
        except Exception:
            return None
    return None


def _save_cached_response(pdf_hash: str, raw_response: str):
    """Save an API response to the file cache."""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    cache_file = _CACHE_DIR / f"{pdf_hash}.json"
    try:
        cache_file.write_text(raw_response, encoding='utf-8')
        logger.info(f"Cached API response: {cache_file}")
    except Exception as e:
        logger.warning(f"Failed to cache response: {e}")


# ---------------------------------------------------------------------------
# Main Pipeline — routes ALL API calls through api_router
# ---------------------------------------------------------------------------

def process_paper(pdf_path: str, paper_id: str = '') -> Tuple[dict, dict]:
    """Process a single PDF paper through the central API router.

    Priority: Groq (keys 1-3) → GitHub Models → OpenRouter → Gemini (keys 1-4)
    The router handles all provider selection, rotation, and rate-limit recovery.

    Includes quality scoring and automatic retry on low quality.

    Returns (validated_data, processing_log).

    validated_data has keys: subject_code, subject_name, exam_year, exam_month, questions
    processing_log has keys: pdf_type, char_count, has_garbled, pipeline_used,
                            correction_count, warnings, page_count, quality_score, timings
    """
    import time as _time
    from .api_router import get_router

    timings = {}
    pipeline_start = _time.perf_counter()
    router = get_router()
    processing_log = {}

    # Step 1: Detect PDF type
    t0 = _time.perf_counter()
    detection = detect_pdf_type(pdf_path)
    timings['pdf_detection'] = round(_time.perf_counter() - t0, 3)
    processing_log['pdf_type'] = detection['pdf_type']
    processing_log['char_count'] = detection['char_count']
    processing_log['has_garbled'] = detection['has_garbled']
    processing_log['page_count'] = detection['page_count']

    # Step 1b: Check file cache (MD5 hash of PDF) — works for ALL providers
    t0 = _time.perf_counter()
    pdf_hash = _get_pdf_hash(pdf_path)
    cached_response = _get_cached_response(pdf_hash)
    timings['cache_check'] = round(_time.perf_counter() - t0, 3)

    if cached_response is not None:
        logger.info(f"Cache HIT for paper {paper_id} (hash={pdf_hash[:12]}...)")
        processing_log['pipeline_used'] = 'cache_hit'
        raw_response = cached_response

        # Skip directly to JSON parsing
        t0 = _time.perf_counter()
        parsed_data = parse_gemini_response(raw_response, paper_id=paper_id)
        timings['json_parsing'] = round(_time.perf_counter() - t0, 3)

        t0 = _time.perf_counter()
        raw_questions = parsed_data.get('questions', [])
        cleaned_questions, validation_report = validate_and_clean_questions(
            raw_questions, paper_metadata=parsed_data
        )
        quality_score = compute_quality_score(cleaned_questions, parsed_data)
        timings['validation'] = round(_time.perf_counter() - t0, 3)

        processing_log['quality_score'] = quality_score

        validated_data = {
            'subject_code': parsed_data.get('subject_code', ''),
            'subject_name': parsed_data.get('subject_name', ''),
            'exam_year': parsed_data.get('exam_year'),
            'exam_month': parsed_data.get('exam_month', ''),
            'questions': cleaned_questions,
        }

        processing_log['correction_count'] = validation_report.get('corrections_made', 0)
        processing_log.setdefault('warnings', [])
        processing_log['warnings'].extend(validation_report.get('warnings', []))
        processing_log['corrections_detail'] = validation_report.get('corrections_detail', [])
        processing_log['questions_extracted'] = len(cleaned_questions)
        processing_log['questions_removed'] = validation_report.get('invalid_count', 0)
        processing_log['validation_report'] = validation_report
        processing_log['needs_review'] = quality_score < 60

        timings['total'] = round(_time.perf_counter() - pipeline_start, 3)
        processing_log['timings'] = timings

        logger.info(
            f"=== TIMING TABLE (paper_id={paper_id}, CACHED) ===\n"
            + "\n".join(f"  {stage:20s}: {secs:7.3f}s" for stage, secs in timings.items())
        )

        return validated_data, processing_log

    # Step 2: Extract via API router (handles all provider rotation automatically)
    raw_response = None
    provider_used = 'unknown'

    # Prepare image data if needed (shared between all providers)
    page_images = None
    if detection['pdf_type'] == 'image':
        t0 = _time.perf_counter()
        page_images = extract_page_images(pdf_path)
        # Limit to first 2 pages — KTU papers fit on 2 pages
        if len(page_images) > 2:
            logger.info(f"Limiting from {len(page_images)} pages to 2 (KTU optimization)")
            page_images = page_images[:2]
        # Resize all images for token reduction
        page_images = [_resize_image_if_needed(img, max_width=900) for img in page_images]
        timings['image_conversion'] = round(_time.perf_counter() - t0, 3)

    t0 = _time.perf_counter()
    try:
        if detection['pdf_type'] == 'image':
            # IMAGE pipeline: send pages through router (one at a time)
            logger.info("Using IMAGE pipeline via API router")
            raw_response, provider_used = router.call_api(
                GEMINI_IMAGE_PROMPT, page_images_b64=page_images
            )
            processing_log['pipeline_used'] = f'{provider_used}_image'
        else:
            # TEXT pipeline: send extracted text through router
            logger.info("Using TEXT pipeline via API router")
            extracted_text = detection['extracted_text']

            # Trim to PART A section to reduce tokens by 40-60%
            part_a_idx = extracted_text.upper().find('PART A')
            if part_a_idx > 0:
                extracted_text = extracted_text[part_a_idx:]
                logger.info(f"Trimmed text to PART A section ({len(extracted_text)} chars)")

            # Truncate to 2500 chars — KTU papers fit within this
            if len(extracted_text) > 2500:
                logger.warning(
                    f"Truncating text from {len(extracted_text)} to 2500 chars"
                )
                extracted_text = extracted_text[:2500]

            full_prompt = (
                GEMINI_TEXT_PROMPT
                + "\n\nHere is the extracted text:\n\n"
                + extracted_text
            )
            raw_response, provider_used = router.call_api(full_prompt)
            processing_log['pipeline_used'] = f'{provider_used}_text'

    except RuntimeError as e:
        # All providers exhausted
        raise DailyQuotaExhaustedError(str(e)) from e

    timings['api_call'] = round(_time.perf_counter() - t0, 3)
    processing_log['provider_used'] = provider_used

    # Cache the successful API response for future use
    _save_cached_response(pdf_hash, raw_response)

    # Step 3: Parse JSON response
    t0 = _time.perf_counter()
    parsed_data = parse_gemini_response(raw_response, paper_id=paper_id)
    timings['json_parsing'] = round(_time.perf_counter() - t0, 3)

    # Step 4: Validate and clean questions
    t0 = _time.perf_counter()
    raw_questions = parsed_data.get('questions', [])
    cleaned_questions, validation_report = validate_and_clean_questions(
        raw_questions, paper_metadata=parsed_data
    )

    # Step 5: Compute quality score
    quality_score = compute_quality_score(cleaned_questions, parsed_data)
    timings['validation'] = round(_time.perf_counter() - t0, 3)
    processing_log['quality_score'] = quality_score

    # Step 6: If quality is low, retry once with aggressive prompt via router
    if quality_score < 60 and raw_response:
        logger.warning(
            f"Quality score {quality_score} is below 60. Retrying with aggressive prompt..."
        )
        processing_log.setdefault('warnings', [])
        processing_log['warnings'].append(
            f"First attempt quality score: {quality_score}/100. Retrying..."
        )

        try:
            if detection['pdf_type'] == 'image' and page_images:
                # Retry with vision — send first page with retry prompt
                retry_response, retry_provider = router.call_api(
                    GEMINI_RETRY_PROMPT, page_images_b64=page_images
                )
            else:
                retry_prompt = (
                    GEMINI_RETRY_PROMPT
                    + "\n\nHere is the extracted text:\n\n"
                    + detection['extracted_text']
                )
                retry_response, retry_provider = router.call_api(retry_prompt)

            retry_parsed = parse_gemini_response(retry_response, paper_id=paper_id)
            retry_questions = retry_parsed.get('questions', [])
            retry_cleaned, retry_report = validate_and_clean_questions(
                retry_questions, paper_metadata=retry_parsed
            )
            retry_score = compute_quality_score(retry_cleaned, retry_parsed)

            if retry_score > quality_score:
                logger.info(f"Retry improved quality: {quality_score} -> {retry_score}")
                cleaned_questions = retry_cleaned
                validation_report = retry_report
                quality_score = retry_score
                parsed_data = retry_parsed
                processing_log['quality_score'] = retry_score
                processing_log['pipeline_used'] += '_retry'
                provider_used = retry_provider
            else:
                logger.info(f"Retry did not improve quality: {retry_score} vs {quality_score}")

        except Exception as retry_err:
            logger.warning(f"Retry attempt failed: {retry_err}")

    # Build validated_data with cleaned questions
    validated_data = {
        'subject_code': parsed_data.get('subject_code', ''),
        'subject_name': parsed_data.get('subject_name', ''),
        'exam_year': parsed_data.get('exam_year'),
        'exam_month': parsed_data.get('exam_month', ''),
        'questions': cleaned_questions,
    }

    processing_log['correction_count'] = validation_report.get('corrections_made', 0)
    processing_log.setdefault('warnings', [])
    processing_log['warnings'].extend(validation_report.get('warnings', []))
    processing_log['corrections_detail'] = validation_report.get('corrections_detail', [])
    processing_log['questions_extracted'] = len(cleaned_questions)
    processing_log['questions_removed'] = validation_report.get('invalid_count', 0)
    processing_log['validation_report'] = validation_report
    processing_log['needs_review'] = quality_score < 60

    # Record total pipeline time and timing breakdown
    timings['total'] = round(_time.perf_counter() - pipeline_start, 3)
    processing_log['timings'] = timings

    # Print timing table
    logger.info(
        f"=== TIMING TABLE (paper_id={paper_id}) ===\n"
        + "\n".join(f"  {stage:20s}: {secs:7.3f}s" for stage, secs in timings.items())
    )

    logger.info(
        f"Pipeline complete: {processing_log['questions_extracted']} questions, "
        f"{processing_log['correction_count']} corrections, "
        f"quality={quality_score}, pipeline={processing_log['pipeline_used']}, "
        f"provider={provider_used}, total_time={timings['total']}s"
    )

    return validated_data, processing_log
