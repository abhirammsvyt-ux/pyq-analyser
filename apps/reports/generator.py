"""
PDF report generator using xhtml2pdf.
"""
import logging
from pathlib import Path
from typing import Optional
from django.template.loader import render_to_string
from django.conf import settings

from apps.subjects.models import Subject
from apps.analytics.calculator import StatsCalculator

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates PDF reports for subjects using xhtml2pdf."""

    def __init__(self, subject: Subject):
        self.subject = subject
        self.calculator = StatsCalculator(subject)

    def generate_module_report(self) -> Optional[str]:
        """
        Generate module-wise question report.

        Returns:
            Path to generated PDF file, or None on failure
        """
        try:
            from xhtml2pdf import pisa

            # Gather data
            stats = self.calculator.get_complete_stats()
            modules = self.subject.modules.all().prefetch_related('questions')

            # Prepare module data with questions
            module_data = []
            for module in modules:
                questions = module.questions.select_related('paper').order_by('paper__year')
                module_data.append({
                    'module': module,
                    'questions': questions,
                    'count': questions.count(),
                })

            # Render HTML template
            html_content = render_to_string('reports/module_report.html', {
                'subject': self.subject,
                'stats': stats,
                'modules': module_data,
            })

            # Generate PDF
            output_dir = Path(settings.MEDIA_ROOT) / 'reports'
            output_dir.mkdir(parents=True, exist_ok=True)

            filename = f"module_report_{self.subject.id}.pdf"
            output_path = output_dir / filename

            with open(str(output_path), 'wb') as pdf_file:
                result = pisa.CreatePDF(html_content, dest=pdf_file)
            if result.err:
                logger.error(f"xhtml2pdf errors in module report: {result.err}")
                return None

            return str(output_path)

        except ImportError:
            logger.error("xhtml2pdf is not installed. Install it with: pip install xhtml2pdf")
            return None
        except Exception as e:
            logger.error(f"Module report generation failed: {e}", exc_info=True)
            return None

    def generate_analytics_report(self) -> Optional[str]:
        """Generate analytics summary report using WeasyPrint.

        Returns:
            Path to generated PDF file, or None on failure.
        """
        try:
            from xhtml2pdf import pisa

            stats = self.calculator.get_complete_stats()

            # Common output folder
            output_dir = Path(settings.MEDIA_ROOT) / 'reports'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"analytics_report_{self.subject.id}.pdf"

            html_content = render_to_string('reports/analytics_report.html', {
                'subject': self.subject,
                'stats': stats,
            })
            with open(str(output_path), 'wb') as pdf_file:
                result = pisa.CreatePDF(html_content, dest=pdf_file)
            if result.err:
                logger.error(f"xhtml2pdf errors in analytics report: {result.err}")
                return None
            return str(output_path)

        except ImportError:
            logger.error("xhtml2pdf is not installed. Install it with: pip install xhtml2pdf")
            return None
        except Exception as e:
            logger.error(f"Analytics report generation failed: {e}", exc_info=True)
            return None
