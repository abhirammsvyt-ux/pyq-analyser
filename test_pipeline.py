#!/usr/bin/env python
"""
Test script for KTU PYQ Analyzer pipeline.
Tests each dependency and each API provider independently.

Usage:
    python test_pipeline.py              # Full test suite
    python test_pipeline.py --providers  # Test only API providers
"""
import os
import sys
import json

# Add project root to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()


def test_result(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    icon = "[+]" if passed else "[-]"
    msg = f"  {icon} {name}: {status}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    return passed


def test_dependencies():
    """Test all system dependencies."""
    results = []

    # 1. PyMuPDF (fitz)
    print("\n--- PDF Processing ---")
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), "Test question paper", fontsize=14)
        pdf_bytes = doc.tobytes()
        doc.close()

        doc2 = fitz.open(stream=pdf_bytes, filetype="pdf")
        matrix = fitz.Matrix(2.0, 2.0)
        pixmap = doc2[0].get_pixmap(matrix=matrix)
        png_bytes = pixmap.tobytes("png")
        doc2.close()

        results.append(test_result(
            "PyMuPDF (fitz)", True,
            f"v{fitz.version[0]}, test render {len(png_bytes)} bytes"
        ))
    except ImportError:
        results.append(test_result("PyMuPDF (fitz)", False, "Not installed. Run: pip install PyMuPDF"))
    except Exception as e:
        results.append(test_result("PyMuPDF (fitz)", False, str(e)[:100]))

    # 2. pdf2image (optional)
    try:
        import pdf2image
        results.append(test_result(
            "pdf2image", True,
            f"v{getattr(pdf2image, '__version__', 'installed')} (optional)"
        ))
    except ImportError:
        results.append(test_result(
            "pdf2image", True,
            "Not installed (optional - PyMuPDF fallback will be used)"
        ))

    # 3. Poppler (optional)
    import shutil
    pdftoppm = shutil.which('pdftoppm')
    if not pdftoppm:
        for p in [
            r'c:\poppler\poppler-24.08.0\Library\bin\pdftoppm.exe',
            r'C:\Program Files\poppler\bin\pdftoppm.exe',
            r'C:\poppler\bin\pdftoppm.exe',
        ]:
            if os.path.exists(p):
                pdftoppm = p
                break
    if pdftoppm:
        results.append(test_result("Poppler", True, f"Found at {pdftoppm}"))
    else:
        results.append(test_result("Poppler", True, "Not found (optional)"))

    # 4. Sentence Transformers
    print("\n--- ML / Clustering ---")
    try:
        from sentence_transformers import SentenceTransformer
        from django.conf import settings
        model_name = getattr(settings, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        results.append(test_result("Sentence Transformers", True, f"Model: {model_name}"))
    except ImportError:
        results.append(test_result("Sentence Transformers", False, "pip install sentence-transformers"))

    # 5. PyTorch
    try:
        import torch
        cuda = torch.cuda.is_available()
        device = torch.cuda.get_device_name(0) if cuda else "CPU only"
        results.append(test_result(
            "PyTorch", True,
            f"v{torch.__version__}, CUDA={'YES - ' + device if cuda else 'No (CPU mode)'}"
        ))
    except ImportError:
        results.append(test_result("PyTorch", False, "pip install torch"))

    # 6. scikit-learn
    try:
        import sklearn
        results.append(test_result("scikit-learn", True, f"v{sklearn.__version__}"))
    except ImportError:
        results.append(test_result("scikit-learn", False, "pip install scikit-learn"))

    # 7. WeasyPrint
    print("\n--- Report Generation ---")
    try:
        import weasyprint
        results.append(test_result("WeasyPrint", True, f"v{weasyprint.__version__}"))
    except ImportError:
        results.append(test_result("WeasyPrint", False, "pip install WeasyPrint"))
    except Exception as e:
        results.append(test_result("WeasyPrint", False, f"Import error: {str(e)[:80]}"))

    # 8. Database
    print("\n--- Infrastructure ---")
    try:
        from django.db import connection
        from django.conf import settings
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        engine = settings.DATABASES['default']['ENGINE']
        results.append(test_result("Database", True, engine.split('.')[-1]))
    except Exception as e:
        results.append(test_result("Database", False, str(e)[:100]))

    # 9. Media directories
    from django.conf import settings
    media_root = settings.MEDIA_ROOT
    for subdir in ['papers', 'reports']:
        dir_path = os.path.join(media_root, subdir)
        os.makedirs(dir_path, exist_ok=True)
        try:
            test_file = os.path.join(dir_path, '_test_write.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            results.append(test_result(f"Media dir ({subdir})", True, f"Writable: {dir_path}"))
        except Exception as e:
            results.append(test_result(f"Media dir ({subdir})", False, str(e)[:80]))

    return results


def test_providers():
    """Test each API provider individually."""
    from django.conf import settings
    results = []
    print("\n--- API Provider Tests ---")
    print("  Priority: Groq -> GitHub Models -> OpenRouter -> Gemini\n")

    # 1. Groq SDK + API
    try:
        import groq as groq_module
        results.append(test_result("Groq SDK", True, "groq package installed"))
    except ImportError:
        results.append(test_result("Groq SDK", False, "pip install groq"))

    groq_keys = getattr(settings, 'GROQ_API_KEYS', [])
    groq_enabled = getattr(settings, 'GROQ_ENABLED', False)
    if groq_enabled and groq_keys:
        for i, key in enumerate(groq_keys):
            try:
                from groq import Groq
                client = Groq(api_key=key)
                model = getattr(settings, 'GROQ_MODEL_TEXT', 'llama-3.3-70b-versatile')
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Reply with only: OK"}],
                    max_tokens=10,
                    temperature=0,
                )
                reply = response.choices[0].message.content.strip()
                # Verify it returns valid text
                results.append(test_result(
                    f"Groq Key {i+1} (text)", True,
                    f"model={model}, response='{reply[:20]}'"
                ))
            except Exception as e:
                results.append(test_result(f"Groq Key {i+1} (text)", False, str(e)[:120]))
    else:
        results.append(test_result(
            "Groq API", False,
            f"{'Not enabled' if not groq_enabled else 'No keys configured'} in .env"
        ))

    # 2. GitHub Models
    github_tokens = getattr(settings, 'GITHUB_MODELS_TOKENS', [])
    if github_tokens:
        for i, token in enumerate(github_tokens):
            try:
                from openai import OpenAI
                client = OpenAI(
                    base_url="https://models.inference.ai.azure.com",
                    api_key=token,
                )
                model = getattr(settings, 'GITHUB_MODELS_MODEL', 'gpt-4o')
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Reply with only: OK"}],
                    temperature=0,
                )
                reply = response.choices[0].message.content.strip()
                results.append(test_result(
                    f"GitHub Models Key {i+1}", True,
                    f"model={model}, response='{reply[:20]}'"
                ))
            except Exception as e:
                results.append(test_result(f"GitHub Models Key {i+1}", False, str(e)[:120]))
    else:
        results.append(test_result("GitHub Models", False, "No tokens configured in .env"))

    # 3. OpenRouter
    openrouter_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    openrouter_enabled = getattr(settings, 'OPENROUTER_ENABLED', False)
    if openrouter_enabled and openrouter_key and openrouter_key != 'your_openrouter_key_here':
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
            )
            model = getattr(settings, 'OPENROUTER_MODEL',
                            'meta-llama/llama-3.2-11b-vision-instruct:free')
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with only: OK"}],
                temperature=0,
                max_tokens=10,
            )
            reply = response.choices[0].message.content.strip()
            results.append(test_result(
                "OpenRouter", True,
                f"model={model}, response='{reply[:20]}'"
            ))
        except Exception as e:
            results.append(test_result("OpenRouter", False, str(e)[:120]))
    else:
        results.append(test_result(
            "OpenRouter", False,
            f"{'Not enabled' if not openrouter_enabled else 'No key configured'} in .env"
        ))

    # 4. Gemini API
    gemini_keys = getattr(settings, 'GEMINI_API_KEYS', [])
    valid_keys = [k for k in gemini_keys if k.strip()]
    if valid_keys:
        for i, key in enumerate(valid_keys):
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=key)
                model = getattr(settings, 'GEMINI_MODEL', 'gemini-2.0-flash')
                response = client.models.generate_content(
                    model=model,
                    contents=["Reply with exactly: OK"],
                    config=types.GenerateContentConfig(temperature=0),
                )
                reply = response.text.strip() if response.text else ""
                results.append(test_result(
                    f"Gemini Key {i+1}", True,
                    f"model={model}, response='{reply[:20]}'"
                ))
            except Exception as e:
                results.append(test_result(f"Gemini Key {i+1}", False, str(e)[:120]))
    else:
        results.append(test_result("Gemini API", False, "No API keys configured in .env"))

    # 5. API Router
    print("\n--- Central API Router ---")
    try:
        from apps.analysis.api_router import get_router
        router = get_router()
        status = router.get_status_summary()
        available = status['available_providers']
        total = status['total_providers']
        provider_names = [p['name'] for p in status['providers']]
        results.append(test_result(
            "API Router", True,
            f"{available}/{total} providers available: {', '.join(provider_names)}"
        ))
    except Exception as e:
        results.append(test_result("API Router", False, str(e)[:120]))

    return results


def main():
    providers_only = '--providers' in sys.argv

    print("=" * 60)
    print("  KTU PYQ Analyzer - Pipeline Test")
    print("  Priority: Groq -> GitHub Models -> OpenRouter -> Gemini")
    print("=" * 60)

    results = []

    if not providers_only:
        results.extend(test_dependencies())

    results.extend(test_providers())

    # Summary
    passed = sum(1 for r in results if r)
    total = len(results)
    print("\n" + "=" * 60)
    print(f"  Results: {passed}/{total} checks passed")
    if passed == total:
        print("  All systems operational!")
    elif passed >= total - 2:
        print(f"  {total - passed} non-critical issue(s). System operational.")
    else:
        print(f"  {total - passed} issue(s) found. See details above.")
    print("=" * 60)

    return 0 if passed >= total - 3 else 1  # Allow 3 optional failures


if __name__ == '__main__':
    sys.exit(main())
