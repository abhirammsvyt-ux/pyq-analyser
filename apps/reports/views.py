"""Views for report generation and download."""
from django.views.generic import View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from django.contrib import messages
from pathlib import Path
import zipfile
import tempfile

from apps.subjects.models import Subject, Module
from .generator import ReportGenerator
from .ktu_report_generator import KTUModuleReportGenerator


class PublicReportMixin:
    """Mixin for public report generation (no login required)."""
    
    def get_subject(self, subject_pk):
        """Get subject without user requirement."""
        return get_object_or_404(Subject, pk=subject_pk)


class ReportsListView(LoginRequiredMixin, TemplateView):
    """List available reports for a subject."""
    
    template_name = 'reports/reports_list_new.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject = get_object_or_404(
            Subject, pk=self.kwargs['subject_pk'], user=self.request.user
        )
        
        context['subject'] = subject
        context['modules'] = subject.modules.all().order_by('number')
        
        return context


class GenerateModuleReportView(LoginRequiredMixin, View):
    """Generate and download a specific module report using KTU format."""
    
    def get(self, request, subject_pk, module_number):
        subject = get_object_or_404(
            Subject, pk=subject_pk, user=request.user
        )
        module = get_object_or_404(Module, subject=subject, number=module_number)
        
        # Use KTU report generator for proper format
        generator = KTUModuleReportGenerator(subject)
        pdf_path = generator.generate_module_report(module)
        
        if pdf_path and Path(pdf_path).exists():
            filename = f"Module_{module.number}_{subject.code or subject.name.replace(' ', '_')}.pdf"
            return FileResponse(
                open(pdf_path, 'rb'),
                content_type='application/pdf',
                as_attachment=True,
                filename=filename
            )
        
        messages.error(request, f"Failed to generate report for Module {module.number}")
        raise Http404("Report generation failed")


class GenerateAllModuleReportsView(LoginRequiredMixin, View):
    """Generate reports for all modules and return as ZIP."""
    
    def get(self, request, subject_pk):
        subject = get_object_or_404(
            Subject, pk=subject_pk, user=request.user
        )
        
        return self._generate_reports(subject)
    
    def _generate_reports(self, subject):
        """Shared report generation logic."""
        try:
            # Use KTU report generator
            generator = KTUModuleReportGenerator(subject)
            results = generator.generate_all_module_reports()
            
            # Create a ZIP file with all module PDFs
            successful_pdfs = []
            for module_num, pdf_path in results.items():
                if pdf_path and Path(pdf_path).exists():
                    successful_pdfs.append((module_num, pdf_path))
            
            if not successful_pdfs:
                # Log more details about the failure
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"No successful PDFs generated for subject {subject.id}")
                logger.error(f"Results: {results}")
                
                # Check if there are any questions
                from apps.questions.models import Question
                q_count = Question.objects.filter(paper__subject=subject).count()
                logger.error(f"Question count: {q_count}")
                
                raise Http404(f"No reports could be generated. Questions found: {q_count}")
            
            # If only one report, return it directly
            if len(successful_pdfs) == 1:
                module_num, pdf_path = successful_pdfs[0]
                return FileResponse(
                    open(pdf_path, 'rb'),
                    content_type='application/pdf',
                    as_attachment=True,
                    filename=f"Module_{module_num}_{subject.code or subject.name.replace(' ', '_')}.pdf"
                )
            
            # Create ZIP file with all reports
            zip_path = tempfile.mktemp(suffix='.zip')
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for module_num, pdf_path in successful_pdfs:
                    filename = f"Module_{module_num}_{subject.code or subject.name.replace(' ', '_')}.pdf"
                    zf.write(pdf_path, filename)
            
            return FileResponse(
                open(zip_path, 'rb'),
                content_type='application/zip',
                as_attachment=True,
                filename=f"{subject.code or subject.name.replace(' ', '_')}_All_Modules.zip"
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception(f"Report generation failed: {e}")
            raise Http404(f"Report generation error: {str(e)}")


class PublicGenerateAllModuleReportsView(PublicReportMixin, View):
    """Public version - Generate reports for all modules (no login required)."""
    
    def get(self, request, subject_pk):
        subject = self.get_subject(subject_pk)
        view = GenerateAllModuleReportsView()
        return view._generate_reports(subject)


class GenerateAnalyticsReportView(LoginRequiredMixin, View):
    """Generate and download analytics summary report."""
    
    def get(self, request, subject_pk):
        subject = get_object_or_404(
            Subject, pk=subject_pk, user=request.user
        )
        
        return self._generate_analytics(subject)
    
    def _generate_analytics(self, subject):
        """Shared analytics generation logic."""
        generator = ReportGenerator(subject)
        pdf_path = generator.generate_analytics_report()
        
        if pdf_path and Path(pdf_path).exists():
            return FileResponse(
                open(pdf_path, 'rb'),
                content_type='application/pdf',
                as_attachment=True,
                filename=f'{subject.code or subject.name}_analytics_report.pdf'
            )
        
        raise Http404("Analytics report generation failed")


class PublicGenerateAnalyticsReportView(PublicReportMixin, View):
    """Public version - Generate analytics report (no login required)."""
    
    def get(self, request, subject_pk):
        subject = self.get_subject(subject_pk)
        view = GenerateAnalyticsReportView()
        return view._generate_analytics(subject)
