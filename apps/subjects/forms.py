"""
Forms for subject and module management.
"""
from django import forms
from .models import Subject, Module


class SubjectForm(forms.ModelForm):
    """Form for creating/editing subjects."""
    
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description', 'university', 'exam_board', 'year', 'syllabus_file']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Data Structures and Algorithms',
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., CS201',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Brief description of the subject',
            }),
            'university': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., VTU, Anna University',
            }),
            'exam_board': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Semester Exam, GATE',
            }),
            'year': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., 2024, 3rd Year',
            }),
        }


class ModuleForm(forms.ModelForm):
    """Form for creating/editing modules."""
    
    topics_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 3,
            'placeholder': 'Enter topics, one per line',
        }),
        help_text='Enter each topic on a new line'
    )
    
    keywords_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 2,
            'placeholder': 'Enter keywords, comma-separated',
        }),
        help_text='Enter keywords separated by commas'
    )
    
    class Meta:
        model = Module
        fields = ['name', 'number', 'description', 'weightage']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Arrays and Linked Lists',
            }),
            'number': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 1,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 2,
                'placeholder': 'Module description',
            }),
            'weightage': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 0,
                'max': 100,
                'step': 0.01,
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Pre-populate topics and keywords
            self.fields['topics_text'].initial = '\n'.join(self.instance.topics or [])
            self.fields['keywords_text'].initial = ', '.join(self.instance.keywords or [])
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Parse topics
        topics_text = self.cleaned_data.get('topics_text', '')
        instance.topics = [t.strip() for t in topics_text.split('\n') if t.strip()]
        
        # Parse keywords
        keywords_text = self.cleaned_data.get('keywords_text', '')
        instance.keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]
        
        if commit:
            instance.save()
        return instance
