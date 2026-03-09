"""Forms for question editing and manual correction."""
from django import forms
from .models import Question
from apps.subjects.models import Module


class QuestionEditForm(forms.ModelForm):
    """Form for editing question classification."""
    class Meta:
        model = Question
        fields = ['module', 'difficulty', 'bloom_level', 'marks']
        widgets = {
            'module': forms.Select(attrs={'class': 'form-select form-control-dark'}),
            'difficulty': forms.Select(attrs={'class': 'form-select form-control-dark'}),
            'bloom_level': forms.Select(attrs={'class': 'form-select form-control-dark'}),
            'marks': forms.NumberInput(attrs={'class': 'form-control form-control-dark', 'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.paper:
            self.fields['module'].queryset = Module.objects.filter(
                subject=self.instance.paper.subject
            )


class QuestionTextEditForm(forms.ModelForm):
    """Form for manually correcting question text without reprocessing."""
    class Meta:
        model = Question
        fields = ['text', 'question_number', 'marks', 'part', 'sub_part']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control form-control-dark', 'rows': 5,
                'placeholder': 'Enter corrected question text'
            }),
            'question_number': forms.TextInput(attrs={'class': 'form-control'}),
            'marks': forms.NumberInput(attrs={'class': 'form-control form-control-dark', 'min': 0}),
            'part': forms.Select(
                choices=[('A', 'Part A'), ('B', 'Part B')],
                attrs={'class': 'form-select form-control-dark'}
            ),
            'sub_part': forms.TextInput(attrs={
                'class': 'form-control form-control-dark',
                'placeholder': 'Leave empty for Part A, or enter a/b for Part B'
            }),
        }
