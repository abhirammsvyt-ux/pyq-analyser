"""
Central API Router for PYQ Analyzer.

Routes all AI API calls through a single point with automatic provider rotation.
Priority order: GitHub Models (primary) → Groq (keys 1-3, fallback) → OpenRouter → Gemini (keys 1-4)

Each provider is tried in order. On rate-limit (429), the provider is marked
temporarily exhausted for 60 seconds and the next provider is tried immediately.
On daily-limit errors, the provider is marked exhausted until midnight.

All exhaustion state is stored in Django's cache framework.
"""
import datetime
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider daily limits (for status display)
# ---------------------------------------------------------------------------
PROVIDER_LIMITS = {
    'groq': 14400,
    'github': 150,
    'openrouter': 200,
    'gemini': 1500,
}


# ---------------------------------------------------------------------------
# Provider Entry
# ---------------------------------------------------------------------------

class ProviderEntry:
    """Describes a single provider slot in the priority list."""

    def __init__(self, provider_type: str, key_index: int, api_key: str,
                 display_name: str, daily_limit: int):
        self.provider_type = provider_type  # groq, github, openrouter, gemini
        self.key_index = key_index          # which key within this type
        self.api_key = api_key
        self.display_name = display_name
        self.daily_limit = daily_limit

    @property
    def cache_exhausted_key(self) -> str:
        return f"api_router:exhausted:{self.provider_type}:{self.key_index}"

    @property
    def cache_requests_key(self) -> str:
        today = datetime.date.today().isoformat()
        return f"api_router:requests:{self.provider_type}:{self.key_index}:{today}"

    def __repr__(self):
        return f"<Provider {self.display_name}>"


# ---------------------------------------------------------------------------
# API Router Singleton
# ---------------------------------------------------------------------------

class APIRouter:
    """Central API router that manages provider selection and rotation."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._call_lock = threading.Lock()
        self._build_provider_list()

    def _build_provider_list(self):
        """Build the ordered list of all configured providers."""
        self.providers: List[ProviderEntry] = []

        # 1. GitHub Models tokens (PRIMARY — 150 req/day each)
        for i, token in enumerate(getattr(settings, 'GITHUB_MODELS_TOKENS', [])):
            if token and token != 'your-github-token-here':
                self.providers.append(ProviderEntry(
                    provider_type='github',
                    key_index=i,
                    api_key=token,
                    display_name=f'GitHub Models Key {i + 1}',
                    daily_limit=150,
                ))

        # 2. Groq keys (FALLBACK — 14400 req/day each)
        if getattr(settings, 'GROQ_ENABLED', False):
            for i, key in enumerate(getattr(settings, 'GROQ_API_KEYS', [])):
                if key and key != 'your_groq_key_here':
                    self.providers.append(ProviderEntry(
                        provider_type='groq',
                        key_index=i,
                        api_key=key,
                        display_name=f'Groq Key {i + 1}',
                        daily_limit=14400,
                    ))

        # 3. OpenRouter (free models)
        if getattr(settings, 'OPENROUTER_ENABLED', False):
            api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
            if api_key and api_key != 'your_openrouter_key_here':
                self.providers.append(ProviderEntry(
                    provider_type='openrouter',
                    key_index=0,
                    api_key=api_key,
                    display_name='OpenRouter Free',
                    daily_limit=200,
                ))

        # 4. Gemini keys (1500 req/day each)
        for i, key in enumerate(getattr(settings, 'GEMINI_API_KEYS', [])):
            if key and key.strip():
                self.providers.append(ProviderEntry(
                    provider_type='gemini',
                    key_index=i,
                    api_key=key,
                    display_name=f'Gemini Key {i + 1}',
                    daily_limit=1500,
                ))

        provider_names = [p.display_name for p in self.providers]
        logger.info(f"API Router initialized with {len(self.providers)} providers: {provider_names}")

    # ------------------------------------------------------------------
    # Exhaustion management (cache-based)
    # ------------------------------------------------------------------

    def mark_exhausted(self, provider: ProviderEntry, duration_seconds: int):
        """Mark a provider as temporarily exhausted."""
        cache.set(provider.cache_exhausted_key, True, timeout=duration_seconds)
        logger.warning(
            f"Provider {provider.display_name} marked exhausted for {duration_seconds}s"
        )

    def mark_exhausted_until_midnight(self, provider: ProviderEntry):
        """Mark a provider as exhausted until midnight (daily limit hit)."""
        now = datetime.datetime.now()
        midnight = (now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        seconds_until_midnight = int((midnight - now).total_seconds())
        cache.set(provider.cache_exhausted_key, True, timeout=seconds_until_midnight)
        logger.warning(
            f"Provider {provider.display_name} marked exhausted until midnight "
            f"({seconds_until_midnight}s)"
        )

    def is_exhausted(self, provider: ProviderEntry) -> bool:
        """Check if a provider is currently marked as exhausted."""
        return cache.get(provider.cache_exhausted_key, False)

    def _increment_request_count(self, provider: ProviderEntry):
        """Increment the daily request counter for a provider."""
        key = provider.cache_requests_key
        count = cache.get(key, 0)
        # Cache expires at end of day (max 24h)
        cache.set(key, count + 1, timeout=86400)

    def _get_request_count(self, provider: ProviderEntry) -> int:
        """Get today's request count for a provider."""
        return cache.get(provider.cache_requests_key, 0)

    # ------------------------------------------------------------------
    # Provider selection
    # ------------------------------------------------------------------

    def get_available_provider(self) -> Optional[ProviderEntry]:
        """Return the first non-exhausted provider from the priority list."""
        for provider in self.providers:
            if not self.is_exhausted(provider):
                return provider
        return None

    def has_any_provider(self) -> bool:
        """Check if any provider is available (for quota checks)."""
        return self.get_available_provider() is not None

    # ------------------------------------------------------------------
    # Actual API call dispatch
    # ------------------------------------------------------------------

    def call_api(self, prompt: str, image_b64: Optional[str] = None,
                 page_images_b64: Optional[List[str]] = None) -> Tuple[str, str]:
        """Call the best available API provider.

        Args:
            prompt: The text prompt to send.
            image_b64: Single base64-encoded image (for single-page vision).
            page_images_b64: List of base64 images (for multi-page vision).
                If provided, calls are made one page at a time and results merged.

        Returns:
            Tuple of (response_text, provider_display_name).

        Raises:
            RuntimeError: If all providers are exhausted.
        """
        # Multi-page vision: process one page at a time, merge results
        if page_images_b64 and len(page_images_b64) > 0:
            return self._call_api_multipage(prompt, page_images_b64)

        # Single call (text or single image)
        tried_providers = set()
        last_error = None

        for provider in self.providers:
            if self.is_exhausted(provider):
                continue
            if id(provider) in tried_providers:
                continue
            tried_providers.add(id(provider))

            try:
                logger.info(f"Trying provider: {provider.display_name}")
                response_text = self._dispatch_call(provider, prompt, image_b64)
                self._increment_request_count(provider)
                logger.info(f"Success from {provider.display_name}")
                return response_text, provider.display_name

            except Exception as e:
                last_error = e
                self._handle_provider_error(provider, e)
                continue

        raise RuntimeError(
            f"All API providers exhausted or failed. Last error: {last_error}"
        )

    def _call_api_multipage(self, prompt: str,
                            page_images_b64: List[str]) -> Tuple[str, str]:
        """Handle multi-page vision by calling one page at a time."""
        # Limit to first 2 pages (KTU optimization)
        if len(page_images_b64) > 2:
            logger.info(
                f"Limiting from {len(page_images_b64)} pages to 2 (KTU optimization)"
            )
            page_images_b64 = page_images_b64[:2]

        all_questions = []
        metadata = {}
        provider_used = ''

        for page_idx, b64_str in enumerate(page_images_b64):
            page_prompt = (
                f"This is page {page_idx + 1} of {len(page_images_b64)} "
                f"of a KTU exam paper. " + prompt
            )
            raw_response, provider_name = self.call_api(
                page_prompt, image_b64=b64_str
            )
            provider_used = provider_name

            try:
                from .gemini_pipeline import parse_gemini_response
                page_data = parse_gemini_response(raw_response)
                page_questions = page_data.get('questions', [])
                all_questions.extend(page_questions)

                if not metadata and page_data.get('subject_code'):
                    metadata = {
                        'subject_code': page_data.get('subject_code', ''),
                        'subject_name': page_data.get('subject_name', ''),
                        'exam_year': page_data.get('exam_year'),
                        'exam_month': page_data.get('exam_month', ''),
                    }
                logger.info(
                    f"Page {page_idx + 1}: extracted {len(page_questions)} questions "
                    f"via {provider_name}"
                )
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(
                    f"Page {page_idx + 1}: JSON parse failed ({e}), skipping"
                )
                continue

        # Deduplicate by (q_number, sub)
        seen = set()
        deduped = []
        for q in all_questions:
            key = (q.get('q_number', 0), q.get('sub', ''))
            if key not in seen:
                seen.add(key)
                deduped.append(q)

        merged = {
            'subject_code': metadata.get('subject_code', ''),
            'subject_name': metadata.get('subject_name', ''),
            'exam_year': metadata.get('exam_year'),
            'exam_month': metadata.get('exam_month', ''),
            'questions': deduped,
        }

        logger.info(
            f"Merged {len(deduped)} unique questions from "
            f"{len(page_images_b64)} pages"
        )
        return json.dumps(merged), provider_used

    # ------------------------------------------------------------------
    # Provider-specific dispatch
    # ------------------------------------------------------------------

    def _dispatch_call(self, provider: ProviderEntry, prompt: str,
                       image_b64: Optional[str] = None) -> str:
        """Dispatch a single API call to the appropriate provider backend."""
        if provider.provider_type == 'groq':
            return self._call_groq(provider, prompt, image_b64)
        elif provider.provider_type == 'github':
            return self._call_github(provider, prompt, image_b64)
        elif provider.provider_type == 'openrouter':
            return self._call_openrouter(provider, prompt, image_b64)
        elif provider.provider_type == 'gemini':
            return self._call_gemini(provider, prompt, image_b64)
        else:
            raise ValueError(f"Unknown provider type: {provider.provider_type}")

    def _call_groq(self, provider: ProviderEntry, prompt: str,
                   image_b64: Optional[str] = None) -> str:
        """Call Groq API for text or vision."""
        from groq import Groq

        client = Groq(api_key=provider.api_key)

        if image_b64:
            # Vision model
            model = settings.GROQ_MODEL_VISION
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        },
                    },
                ],
            }]
        else:
            # Text model
            model = settings.GROQ_MODEL_TEXT
            messages = [{"role": "user", "content": prompt}]

        logger.info(f"Groq API call: model={model}, key_index={provider.key_index}")
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000,
            temperature=0.1,
        )
        text = response.choices[0].message.content
        if not text or not text.strip():
            raise RuntimeError("Groq returned empty response")
        return text

    def _call_github(self, provider: ProviderEntry, prompt: str,
                     image_b64: Optional[str] = None) -> str:
        """Call GitHub Models API (OpenAI-compatible)."""
        from openai import OpenAI

        client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=provider.api_key,
        )
        model = settings.GITHUB_MODELS_MODEL

        if image_b64:
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}",
                    },
                },
            ]
        else:
            content = prompt

        logger.info(
            f"GitHub Models API call: model={model}, "
            f"token_index={provider.key_index}"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            temperature=0,
        )
        text = response.choices[0].message.content
        if not text or not text.strip():
            raise RuntimeError("GitHub Models returned empty response")
        return text

    def _call_openrouter(self, provider: ProviderEntry, prompt: str,
                         image_b64: Optional[str] = None) -> str:
        """Call OpenRouter API (OpenAI-compatible with different base_url)."""
        from openai import OpenAI

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=provider.api_key,
        )
        model = settings.OPENROUTER_MODEL

        if image_b64:
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}",
                    },
                },
            ]
        else:
            content = prompt

        logger.info(f"OpenRouter API call: model={model}")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            temperature=0.1,
            max_tokens=2000,
        )
        text = response.choices[0].message.content
        if not text or not text.strip():
            raise RuntimeError("OpenRouter returned empty response")
        return text

    def _call_gemini(self, provider: ProviderEntry, prompt: str,
                     image_b64: Optional[str] = None) -> str:
        """Call Google Gemini API."""
        import base64
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=provider.api_key)
        model = settings.GEMINI_MODEL

        if image_b64:
            image_bytes = base64.b64decode(image_b64)
            image_part = types.Part.from_bytes(
                data=image_bytes, mime_type='image/jpeg'
            )
            content_parts = [prompt, image_part]
        else:
            content_parts = [prompt]

        logger.info(
            f"Gemini API call: model={model}, key_index={provider.key_index}"
        )
        response = client.models.generate_content(
            model=model,
            contents=content_parts,
            config=types.GenerateContentConfig(temperature=0),
        )
        text = response.text
        if not text or not text.strip():
            raise RuntimeError("Gemini returned empty response")
        return text

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _handle_provider_error(self, provider: ProviderEntry, error: Exception):
        """Handle provider errors — mark exhausted as appropriate."""
        error_str = str(error).lower()

        # Check for rate limit / quota errors
        rate_limit_keywords = [
            '429', 'rate_limit', 'rate limit', 'too many requests',
            'resource_exhausted', 'resourceexhausted', 'quota',
        ]
        daily_limit_keywords = [
            'daily', 'free_tier_input_token_count', 'quota_exceeded',
            'limit exceeded', 'tokens_limit',
        ]

        is_rate_limit = any(kw in error_str for kw in rate_limit_keywords)
        is_daily_limit = any(kw in error_str for kw in daily_limit_keywords)

        if is_daily_limit:
            logger.warning(
                f"Provider {provider.display_name} hit DAILY limit: {error}"
            )
            self.mark_exhausted_until_midnight(provider)
        elif is_rate_limit:
            logger.warning(
                f"Provider {provider.display_name} hit rate limit: {error}"
            )
            self.mark_exhausted(provider, duration_seconds=60)
        else:
            # Non-rate-limit error — mark briefly exhausted to avoid hammering
            logger.error(
                f"Provider {provider.display_name} error (non-rate-limit): {error}"
            )
            self.mark_exhausted(provider, duration_seconds=30)

    # ------------------------------------------------------------------
    # Status reporting
    # ------------------------------------------------------------------

    def get_status(self) -> List[Dict[str, Any]]:
        """Return status of all providers for the dashboard."""
        status_list = []
        for provider in self.providers:
            exhausted = self.is_exhausted(provider)
            requests_today = self._get_request_count(provider)

            # Estimate when provider becomes available again
            reset_info = ''
            if exhausted:
                # Check if it's a daily exhaustion (close to midnight reset)
                now = datetime.datetime.now()
                midnight = (now + datetime.timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                seconds_until_midnight = int((midnight - now).total_seconds())
                hours = seconds_until_midnight // 3600
                minutes = (seconds_until_midnight % 3600) // 60
                reset_info = f"{hours}h {minutes}m (midnight)"

            status_list.append({
                'name': provider.display_name,
                'type': provider.provider_type,
                'key_index': provider.key_index,
                'available': not exhausted,
                'requests_today': requests_today,
                'daily_limit': provider.daily_limit,
                'reset_info': reset_info,
            })

        return status_list

    def get_status_summary(self) -> Dict[str, Any]:
        """Return a summary of the entire router status."""
        statuses = self.get_status()
        available_count = sum(1 for s in statuses if s['available'])
        total_requests = sum(s['requests_today'] for s in statuses)

        return {
            'providers': statuses,
            'total_providers': len(statuses),
            'available_providers': available_count,
            'total_requests_today': total_requests,
            'all_exhausted': available_count == 0,
        }


# ---------------------------------------------------------------------------
# Module-level helper functions (backward-compatible interface)
# ---------------------------------------------------------------------------

def get_router() -> APIRouter:
    """Get the singleton APIRouter instance."""
    return APIRouter()


def check_quota_available() -> bool:
    """Check if any API provider has capacity to process papers."""
    return get_router().has_any_provider()


def should_stop_proactively() -> bool:
    """Check if all providers are approaching limits.

    Returns True only if all providers are exhausted.
    """
    return not get_router().has_any_provider()
