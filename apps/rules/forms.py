"""Forms for rule management."""
from django import forms
from .models import ClassificationRule


class RuleForm(forms.ModelForm):
    """Form for creating/editing classification rules."""
    
    class Meta:
        model = ClassificationRule
        fields = ['name', 'description', 'rule_type', 'natural_language', 'priority', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Array-related questions',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 2,
                'placeholder': 'What does this rule do?',
            }),
            'rule_type': forms.Select(attrs={'class': 'form-select'}),
            'natural_language': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'e.g., "If the question mentions array, linked list, or stack, classify it as Module 1"',
            }),
            'priority': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 0,
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
