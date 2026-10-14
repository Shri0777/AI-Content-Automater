from django import forms
from .models import Content, ContentVersion


class ContentForm(forms.ModelForm):
    """Form for creating and editing content metadata."""

    class Meta:
        model = Content
        fields = ['title', 'topic', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Content title',
                'autofocus': True
            }),
            'topic': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Topic or theme (optional)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Internal notes or instructions (optional)',
                'rows': 4
            }),
        }


class ContentVersionForm(forms.ModelForm):
    """Form for creating/editing content version text."""

    class Meta:
        model = ContentVersion
        fields = ['content_text', 'change_summary']
        widgets = {
            'content_text': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Content text',
                'rows': 10
            }),
            'change_summary': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe what changed in this version (optional)',
                'rows': 3
            }),
        }
