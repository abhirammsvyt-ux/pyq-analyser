"""Views for paper upload and management."""
from django.views.generic import ListView, DetailView, CreateView, DeleteView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
import hashlib

from apps.subjects.models import Subject, Module
from .models import Paper
from .forms import PaperUploadForm, BatchPaperUploadForm


class GenericPaperUploadView(FormView):
    """Upload papers without requiring authentication - PUBLIC ACCESS."""
    
    form_class = BatchPaperUploadForm
    template_name = 'papers/paper_upload_new.html'  # New enhanced template
    
    def get_or_create_subject(self, name, code, university, university_type, syllabus_file=None):
        """Get or create a subject with modules for public or authenticated user."""
        from apps.subjects.models import Module
        
        # Use provided name/code or defaults
        subject_name = name or 'My Question Papers'
        subject_code = code or 'DEFAULT'
        
        # For authenticated users, associate with user
        user = self.request.user if self.request.user.is_authenticated else None
        
        # Create new subject for each upload session (public mode)
        subject = Subject.objects.create(
            user=user,  # Can be None for public access
            name=subject_name,
            code=subject_code,
            description=f'Question papers for {subject_name}',
            university=university or 'Unknown',
            university_type=university_type or 'OTHER'
        )
        
        # Handle syllabus upload
        if syllabus_file:
            subject.syllabus_file = syllabus_file
            # Extract syllabus text (basic extraction)
            try:
                import pdfplumber
                with pdfplumber.open(syllabus_file) as pdf:
                    syllabus_text = '\n'.join([page.extract_text() or '' for page in pdf.pages])
                subject.syllabus_text = syllabus_text
            except:
                pass
            subject.save()
        
        # Create 5 modules by default
        module_names = [
            'Module 1',
            'Module 2', 
            'Module 3',
            'Module 4',
            'Module 5'
        ]
        for i, mod_name in enumerate(module_names, 1):
            Module.objects.create(
                subject=subject,
                name=mod_name,
                number=i,
                description=f'Module {i} of {subject_name}',
                weightage=20  # Equal weightage
            )
        
        self._subject = subject
        return subject
    
    def get_success_url(self):
        # Redirect to public processing page (no login required)
        if hasattr(self, '_subject') and self._subject:
            # For guest users, redirect to a public processing view
            return reverse_lazy('papers:processing_status', kwargs={'subject_pk': self._subject.pk})
        return reverse_lazy('papers:upload_generic')
    
    def post(self, request, *args, **kwargs):
        """Handle file upload with university type and syllabus."""
        files = request.FILES.getlist('files')
        university_type = request.POST.get('university_type', 'KTU')  # KTU or OTHER
        university_name = request.POST.get('university_name', '').strip()
        subject_name = request.POST.get('subject_name', '').strip()
        subject_code = request.POST.get('subject_code', '').strip()
        syllabus_file = request.FILES.get('syllabus_file')
        
        if not files:
            messages.error(request, 'Please select at least one PDF file.')
            return self.get(request, *args, **kwargs)
        
        # Validate files
        for f in files:
            if not f.name.lower().endswith('.pdf'):
                messages.error(request, f'"{f.name}" is not a PDF file. Only PDF files are supported.')
                return self.get(request, *args, **kwargs)
            if f.size > 50 * 1024 * 1024:
                messages.error(request, f'"{f.name}" exceeds 50MB limit.')
                return self.get(request, *args, **kwargs)
        
        # Set default university name if not provided
        if not university_name:
            university_name = 'KTU' if university_type == 'KTU' else 'Other University'
        
        # Get or create subject with modules
        subject = self.get_or_create_subject(
            subject_name, 
            subject_code, 
            university_name,
            university_type,
            syllabus_file
        )
        
        # Process files
        uploaded_count = 0
        for uploaded_file in files:
            # Parse filename for metadata
            parsed = BatchPaperUploadForm.parse_filename(uploaded_file.name)
            
            # Calculate file hash for deduplication
            file_hash = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                file_hash.update(chunk)
            file_hash_hex = file_hash.hexdigest()
            uploaded_file.seek(0)  # Reset file pointer
            
            # Check if file already exists (by hash)
            if Paper.objects.filter(subject=subject, file_hash=file_hash_hex).exists():
                messages.warning(
                    request,
                    f'"{uploaded_file.name}" already uploaded (skipped)'
                )
                continue
            
            # Create paper (NO AUTO-PROCESSING)
            paper = Paper.objects.create(
                subject=subject,
                title=parsed['title'],
                year=parsed['year'],
                exam_type=parsed['exam_type'],
                file=uploaded_file,
                file_hash=file_hash_hex,
                status=Paper.ProcessingStatus.PENDING,
                status_detail='Uploaded - Ready for processing'
            )
            uploaded_count += 1
            
            # DO NOT auto-process - user will trigger manually
        
        if uploaded_count > 0:
            messages.success(
                request,
                f'{uploaded_count} paper(s) uploaded successfully! Click "Start Processing" to begin analysis.'
            )
        
        return redirect(self.get_success_url())


class PaperListView(LoginRequiredMixin, ListView):
    """List papers for a subject."""
    
    model = Paper
    template_name = 'papers/paper_list.html'
    context_object_name = 'papers'
    
    def get_queryset(self):
        self.subject = get_object_or_404(
            Subject, pk=self.kwargs['subject_pk'], user=self.request.user
        )
        return Paper.objects.filter(subject=self.subject).order_by('-year', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subject'] = self.subject
        return context


class PaperDetailView(LoginRequiredMixin, DetailView):
    """View paper details and extracted questions."""
    
    model = Paper
    template_name = 'papers/paper_detail.html'
    context_object_name = 'paper'
    
    def get_queryset(self):
        return Paper.objects.filter(subject__user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['questions'] = self.object.questions.all().select_related('module')
        return context


class PaperUploadView(LoginRequiredMixin, FormView):
    """Upload multiple question papers at once."""
    
    form_class = BatchPaperUploadForm
    template_name = 'papers/paper_upload.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.subject = get_object_or_404(
            Subject, pk=kwargs['subject_pk'], user=request.user
        )
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subject'] = self.subject
        return context
    
    def get_success_url(self):
        return reverse_lazy('papers:list', kwargs={'subject_pk': self.subject.pk})
    
    def post(self, request, *args, **kwargs):
        """Handle file upload - bypass form validation and handle files directly."""
        files = request.FILES.getlist('files')
        
        if not files:
            messages.error(request, 'Please select at least one PDF file.')
            return self.get(request, *args, **kwargs)
        
        # Validate files
        for f in files:
            if not f.name.lower().endswith('.pdf'):
                messages.error(request, f'"{f.name}" is not a PDF file. Only PDF files are supported.')
                return self.get(request, *args, **kwargs)
            if f.size > 50 * 1024 * 1024:
                messages.error(request, f'"{f.name}" exceeds 50MB limit.')
                return self.get(request, *args, **kwargs)
        
        # Process files
        uploaded_count = 0
        for uploaded_file in files:
            # Parse filename for metadata
            parsed = BatchPaperUploadForm.parse_filename(uploaded_file.name)
            
            # Calculate file hash for deduplication
            file_hash = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                file_hash.update(chunk)
            file_hash_hex = file_hash.hexdigest()
            uploaded_file.seek(0)  # Reset file pointer
            
            # Check if file already exists (by hash)
            if Paper.objects.filter(subject=self.subject, file_hash=file_hash_hex).exists():
                messages.warning(
                    request,
                    f'"{uploaded_file.name}" already uploaded (skipped)'
                )
                continue
            
            # Create paper
            paper = Paper.objects.create(
                subject=self.subject,
                title=parsed['title'],
                year=parsed['year'],
                exam_type=parsed['exam_type'],
                file=uploaded_file,
                file_hash=file_hash_hex,
            )
            uploaded_count += 1
            
            # Queue background analysis task
            try:
                from apps.analysis.tasks import queue_paper_analysis
                queue_paper_analysis(paper)
            except Exception as e:
                messages.warning(
                    request,
                    f'"{uploaded_file.name}" uploaded but analysis could not be queued: {str(e)}'
                )
        
        if uploaded_count > 0:
            messages.success(
                request,
                f'{uploaded_count} paper(s) uploaded successfully! Analysis has been queued.'
            )
        
        return redirect(self.get_success_url())


class PaperDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a paper."""
    
    model = Paper
    template_name = 'papers/paper_confirm_delete.html'
    
    def get_queryset(self):
        return Paper.objects.filter(subject__user=self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('papers:list', kwargs={'subject_pk': self.object.subject.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f'Paper "{self.object.title}" deleted.')
        return super().form_valid(form)


class PublicProcessingStatusView(DetailView):
    """
    Public view for guest users to track paper processing.
    No login required - accessible via subject ID only.
    """
    
    model = Subject
    template_name = 'papers/processing_status.html'
    context_object_name = 'subject'
    pk_url_kwarg = 'subject_pk'
    
    def get_queryset(self):
        # Allow any subject to be viewed (public access)
        return Subject.objects.prefetch_related('modules', 'papers')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get paper processing status counts
        papers = self.object.papers.all()
        context['papers_pending'] = papers.filter(status='pending').count()
        context['papers_processing'] = papers.filter(status='processing').count()
        context['papers_completed'] = papers.filter(status='completed').count()
        context['papers_failed'] = papers.filter(status='failed').count()
        context['papers_total'] = papers.count()
        context['questions_count'] = sum(p.get_question_count() for p in papers)
        
        # Check if any papers are being processed
        context['has_processing'] = context['papers_processing'] > 0
        context['has_pending'] = context['papers_pending'] > 0
        
        # Pass user authentication status
        context['is_guest'] = not self.request.user.is_authenticated
        
        return context
