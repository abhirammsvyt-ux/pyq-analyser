"""
Core views - Home, Dashboard, and System Health Check.
"""
import os
import tempfile
import datetime
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.conf import settings

from apps.papers.models import Paper
from apps.questions.models import Question


class HomeView(TemplateView):
    """Landing page view - Public access."""
    template_name = 'pages/home_new.html'  # New 3D animated homepage


class DashboardView(TemplateView):
    """Main dashboard view - Public access enabled."""
    template_name = 'pages/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get user's statistics (if authenticated)
        if user.is_authenticated:
            context['total_subjects'] = user.subjects.count() if hasattr(user, 'subjects') else 0
            context['total_papers'] = Paper.objects.filter(subject__user=user).count()
            context['total_questions'] = Question.objects.filter(paper__subject__user=user).count()

            # Get recent subjects
            context['recent_subjects'] = user.subjects.all()[:5] if hasattr(user, 'subjects') else []
        else:
            # Public view - show general stats
            context['total_subjects'] = 0
            context['total_papers'] = 0
            context['total_questions'] = 0
            context['recent_subjects'] = []

        return context


class HealthCheckView(View):
    """System health check - tests all dependencies and returns status."""

    def get(self, request):
        checks = {}

        # 1. PyMuPDF (fitz)
        try:
            import fitz
            checks['pymupdf'] = {'status': True, 'version': fitz.version[0]}
        except ImportError:
            checks['pymupdf'] = {'status': False, 'error': 'Not installed. Run: pip install PyMuPDF'}

        # 2. pdf2image
        try:
            import pdf2image
            checks['pdf2image'] = {'status': True, 'version': getattr(pdf2image, '__version__', 'installed')}
        except ImportError:
            checks['pdf2image'] = {
                'status': False,
                'error': 'Not installed (optional - PyMuPDF fallback available). Run: pip install pdf2image'
            }

        # 3. Poppler
        import shutil
        pdftoppm_path = shutil.which('pdftoppm')
        if pdftoppm_path:
            checks['poppler'] = {'status': True, 'path': pdftoppm_path}
        else:
            # Check common Windows paths
            poppler_found = False
            for p in [
                r'c:\poppler\poppler-24.08.0\Library\bin\pdftoppm.exe',
                r'C:\Program Files\poppler\bin\pdftoppm.exe',
                r'C:\poppler\bin\pdftoppm.exe',
            ]:
                if os.path.exists(p):
                    checks['poppler'] = {'status': True, 'path': p}
                    poppler_found = True
                    break
            if not poppler_found:
                checks['poppler'] = {
                    'status': False,
                    'error': 'Not found in PATH (optional - PyMuPDF fallback available)'
                }

        # 4. API Router Status
        try:
            from apps.analysis.api_router import get_router
            router = get_router()
            router_status = router.get_status_summary()
            checks['api_router'] = {
                'status': router_status['available_providers'] > 0,
                'total_providers': router_status['total_providers'],
                'available_providers': router_status['available_providers'],
                'total_requests_today': router_status['total_requests_today'],
            }
        except Exception as e:
            checks['api_router'] = {'status': False, 'error': str(e)[:200]}

        # 5. Groq SDK
        try:
            import groq
            groq_keys = getattr(settings, 'GROQ_API_KEYS', [])
            checks['groq'] = {
                'status': bool(groq_keys),
                'key_count': len(groq_keys),
                'enabled': getattr(settings, 'GROQ_ENABLED', False),
            }
        except ImportError:
            checks['groq'] = {'status': False, 'error': 'Not installed. Run: pip install groq'}

        # 6. Google GenAI SDK
        try:
            from google import genai
            gemini_keys = getattr(settings, 'GEMINI_API_KEYS', [])
            checks['google_genai'] = {
                'status': True,
                'key_count': len(gemini_keys),
                'model': getattr(settings, 'GEMINI_MODEL', 'not set'),
            }
        except ImportError:
            checks['google_genai'] = {'status': False, 'error': 'Not installed. Run: pip install google-genai'}

        # 7. Database
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks['database'] = {'status': True, 'engine': settings.DATABASES['default']['ENGINE']}
        except Exception as e:
            checks['database'] = {'status': False, 'error': str(e)[:200]}

        # 8. Media uploads directory
        uploads_dir = os.path.join(settings.MEDIA_ROOT, 'papers')
        os.makedirs(uploads_dir, exist_ok=True)
        try:
            test_file = os.path.join(uploads_dir, '_health_check_test.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            checks['media_uploads'] = {'status': True, 'path': uploads_dir}
        except Exception as e:
            checks['media_uploads'] = {'status': False, 'error': str(e)[:200], 'path': uploads_dir}

        # 9. Media reports directory
        reports_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        try:
            test_file = os.path.join(reports_dir, '_health_check_test.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            checks['media_reports'] = {'status': True, 'path': reports_dir}
        except Exception as e:
            checks['media_reports'] = {'status': False, 'error': str(e)[:200], 'path': reports_dir}

        # 10. Sentence Transformers
        try:
            from sentence_transformers import SentenceTransformer
            checks['sentence_transformers'] = {'status': True, 'model': settings.EMBEDDING_MODEL}
        except ImportError:
            checks['sentence_transformers'] = {
                'status': False,
                'error': 'Not installed. Run: pip install sentence-transformers'
            }

        # 11. xhtml2pdf (PDF generation)
        try:
            import xhtml2pdf
            checks['xhtml2pdf'] = {'status': True, 'version': xhtml2pdf.__version__}
        except ImportError:
            checks['xhtml2pdf'] = {'status': False, 'error': 'Not installed. Run: pip install xhtml2pdf'}
        except Exception as e:
            checks['xhtml2pdf'] = {'status': False, 'error': f'Import error: {str(e)[:100]}'}

        # 12. Torch / CUDA
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            checks['torch'] = {
                'status': True,
                'version': torch.__version__,
                'cuda': cuda_available,
                'cuda_device': torch.cuda.get_device_name(0) if cuda_available else None,
            }
        except ImportError:
            checks['torch'] = {'status': False, 'error': 'Not installed. Run: pip install torch'}

        # Summary
        all_critical = all(
            checks.get(k, {}).get('status', False)
            for k in ['pymupdf', 'api_router', 'database', 'media_uploads']
        )

        return JsonResponse({
            'healthy': all_critical,
            'checks': checks,
        }, json_dumps_params={'indent': 2})


class APIHealthCheckView(View):
    """API provider status dashboard — shows all providers via the central router."""

    def get(self, request):
        from apps.analysis.api_router import get_router

        router = get_router()
        status = router.get_status_summary()
        providers = status['providers']

        # Accept JSON for AJAX polling
        if request.headers.get('Accept') == 'application/json' or request.GET.get('format') == 'json':
            return JsonResponse(status)

        # Build HTML dashboard
        rows = []
        for p in providers:
            if p['available']:
                icon = '<span style="color:#22c55e;font-size:20px;">&#10004;</span>'
                status_text = '<span style="color:#22c55e;">Available</span>'
            else:
                icon = '<span style="color:#ef4444;font-size:20px;">&#10008;</span>'
                status_text = f'<span style="color:#ef4444;">Exhausted</span>'

            ptype = p['type'].capitalize()
            usage = f"{p['requests_today']}/{p['daily_limit']}"
            reset = p['reset_info'] if p['reset_info'] else '-'

            rows.append(f'''
            <tr style="border-bottom:1px solid #333;">
                <td style="padding:12px;text-align:center;">{icon}</td>
                <td style="padding:12px;">{p['name']}</td>
                <td style="padding:12px;"><span style="background:#222;padding:2px 8px;border-radius:4px;font-size:12px;">{ptype}</span></td>
                <td style="padding:12px;">{status_text}</td>
                <td style="padding:12px;text-align:center;">{usage}</td>
                <td style="padding:12px;">{reset}</td>
            </tr>''')

        table_rows = '\n'.join(rows)
        avail = status['available_providers']
        total = status['total_providers']
        total_req = status['total_requests_today']

        html = f'''<!DOCTYPE html>
<html><head><title>API Provider Status</title>
<style>
  body {{ background:#0a0a0a; color:#e5e5e5; font-family:system-ui,-apple-system,sans-serif; margin:0; padding:20px; }}
  .container {{ max-width:900px; margin:0 auto; }}
  h1 {{ color:#fff; font-size:24px; margin-bottom:4px; }}
  .subtitle {{ color:#999; font-size:14px; margin-bottom:24px; }}
  table {{ width:100%; border-collapse:collapse; background:#111; border-radius:8px; overflow:hidden; }}
  th {{ background:#1a1a1a; padding:12px; text-align:left; color:#999; font-size:12px; text-transform:uppercase; }}
  .summary {{ background:#111; border-radius:8px; padding:16px; margin-bottom:24px; display:flex; gap:24px; }}
  .stat {{ text-align:center; }}
  .stat-value {{ font-size:28px; font-weight:bold; color:#fff; }}
  .stat-label {{ font-size:12px; color:#999; text-transform:uppercase; }}
</style>
<script>
  // Auto-refresh every 10 seconds
  setTimeout(function() {{ location.reload(); }}, 10000);
</script>
</head><body>
<div class="container">
  <h1>API Provider Status</h1>
  <div class="subtitle">Priority: Groq → GitHub Models → OpenRouter → Gemini | Auto-refresh every 10s</div>

  <div class="summary">
    <div class="stat">
      <div class="stat-value" style="color:{'#22c55e' if avail > 0 else '#ef4444'}">{avail}/{total}</div>
      <div class="stat-label">Providers Available</div>
    </div>
    <div class="stat">
      <div class="stat-value">{total_req}</div>
      <div class="stat-label">Requests Today</div>
    </div>
  </div>

  <table>
    <tr>
      <th></th><th>Provider</th><th>Type</th><th>Status</th><th>Usage</th><th>Reset</th>
    </tr>
    {table_rows}
  </table>

  <div style="color:#666;font-size:12px;margin-top:16px;">
    Groq: 14400 req/day per key | GitHub Models: 150 req/day | OpenRouter: free tier | Gemini: 1500 req/day per key
  </div>
</div>
</body></html>'''

        return HttpResponse(html, content_type='text/html')


class APIStatusJSONView(View):
    """JSON-only endpoint for AJAX polling from processing status page."""

    def get(self, request):
        from apps.analysis.api_router import get_router
        router = get_router()
        return JsonResponse(router.get_status_summary())
