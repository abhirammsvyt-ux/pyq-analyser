"""Forms for paper upload and management."""
from django import forms
from django.core.validators import FileExtensionValidator
from .models import Paper
import re


class PaperUploadForm(forms.ModelForm):
    """Form for uploading a single question paper."""
    
    class Meta:
        model = Paper
        fields = ['title', 'year', 'exam_type', 'file', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Data Structures Final Exam 2023',
            }),
            'year': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., 2023',
            }),
            'exam_type': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Final Exam, GATE, Mid-term',
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-file-input',
                'accept': '.pdf',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 2,
                'placeholder': 'Any additional notes about this paper',
            }),
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.name.lower().endswith('.pdf'):
                raise forms.ValidationError('Only PDF files are supported.')
            if file.size > 50 * 1024 * 1024:  # 50MB limit
                raise forms.ValidationError('File size must be under 50MB.')
        return file


class MultipleFileInput(forms.ClearableFileInput):
    """Custom widget for multiple file selection."""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Custom field for multiple file uploads."""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
            if result:
                result = [result]
            else:
                result = []
        return result


class BatchPaperUploadForm(forms.Form):
    """Form for uploading multiple question papers at once."""
    
    files = MultipleFileField(
        label="Question Papers (PDF)",
        help_text="Select multiple PDF files. Year and exam type will be auto-detected from filenames.",
        required=False,  # We'll validate manually
        widget=MultipleFileInput(attrs={
            'class': 'form-file-input',
            'accept': '.pdf',
            'multiple': True,
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        # Get files directly from request - Django doesn't handle multiple files well in forms
        return cleaned_data
    
    def clean_files(self):
        files = self.cleaned_data.get('files', [])
        
        # Handle empty/None case
        if not files or (isinstance(files, list) and len(files) == 0):
            raise forms.ValidationError('Please select at least one PDF file.')
        
        # Ensure it's a list
        if not isinstance(files, list):
            files = [files] if files else []
        
        cleaned_files = []
        for f in files:
            if f is None:
                continue
            if not f.name.lower().endswith('.pdf'):
                raise forms.ValidationError(f'"{f.name}" is not a PDF file. Only PDF files are supported.')
            if f.size > 50 * 1024 * 1024:  # 50MB limit per file
                raise forms.ValidationError(f'"{f.name}" exceeds 50MB limit.')
            cleaned_files.append(f)
        
        if not cleaned_files:
            raise forms.ValidationError('Please select at least one PDF file.')
        
        return cleaned_files
        
        return cleaned_files
    
    @staticmethod
    def parse_filename(filename):
        """Extract year, month, and exam type from filename."""
        # Remove extension
        name = filename.rsplit('.', 1)[0]
        
        # Common month patterns
        months = {
            'january': 'January', 'jan': 'January',
            'february': 'February', 'feb': 'February', 
            'march': 'March', 'mar': 'March',
            'april': 'April', 'apr': 'April',
            'may': 'May',
            'june': 'June', 'jun': 'June',
            'july': 'July', 'jul': 'July',
            'august': 'August', 'aug': 'August',
            'september': 'September', 'sep': 'September', 'sept': 'September',
            'october': 'October', 'oct': 'October',
            'november': 'November', 'nov': 'November',
            'december': 'December', 'dec': 'December',
        }
        
        # Extract year (4 digit number between 2000-2099)
        year_match = re.search(r'(20\d{2})', name)
        year = year_match.group(1) if year_match else None
        
        # Extract month
        month = None
        name_lower = name.lower()
        for key, value in months.items():
            if key in name_lower:
                month = value
                break
        
        # Build exam type
        exam_type = None
        if month and year:
            exam_type = f"{month} {year}"
        elif month:
            exam_type = month
        elif year:
            exam_type = year
        
        # Clean up title - remove date parts for cleaner title
        title = name
        if year:
            title = title.replace(year, '').strip()
        for key in months.keys():
            title = re.sub(rf'\b{key}\b', '', title, flags=re.IGNORECASE)
        # Clean up extra separators
        title = re.sub(r'[,_\-]+\s*$', '', title).strip()
        title = re.sub(r'\s+', ' ', title).strip()
        
        return {
            'title': title or filename,
            'year': year,
            'exam_type': exam_type,
        }

