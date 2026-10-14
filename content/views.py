from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction

from .models import Content, ContentVersion
from .forms import ContentForm, ContentVersionForm
from .authorization import user_owns_content


@login_required
def content_list(request):
    """
    List all content owned by the current user.
    """
    contents = Content.objects.filter(owner=request.user)
    return render(request, 'content/list.html', {
        'contents': contents
    })


@login_required
@require_http_methods(["GET", "POST"])
def content_create(request):
    """
    Create new content with initial version.
    """
    if request.method == 'POST':
        content_form = ContentForm(request.POST)
        version_form = ContentVersionForm(request.POST)

        if content_form.is_valid() and version_form.is_valid():
            with transaction.atomic():
                # Create content
                content = content_form.save(commit=False)
                content.owner = request.user
                content.save()

                # Create initial version
                version = version_form.save(commit=False)
                version.content = content
                version.version_number = 1
                version.created_by = request.user
                version.save()

                # Set current version
                content.current_version = version
                content.save(update_fields=['current_version'])

                messages.success(request, f'Content "{content.title}" created successfully.')
                return redirect('content:detail', pk=content.pk)
    else:
        content_form = ContentForm()
        version_form = ContentVersionForm()

    return render(request, 'content/create.html', {
        'content_form': content_form,
        'version_form': version_form
    })


@login_required
@user_owns_content
def content_detail(request, pk):
    """
    Display content details and current version.
    """
    content = get_object_or_404(Content, pk=pk)
    current_version = content.current_version

    return render(request, 'content/detail.html', {
        'content': content,
        'current_version': current_version
    })


@login_required
@user_owns_content
@require_http_methods(["GET", "POST"])
def content_edit(request, pk):
    """
    Edit content metadata and optionally create new version.
    """
    content = get_object_or_404(Content, pk=pk)

    if request.method == 'POST':
        content_form = ContentForm(request.POST, instance=content)
        version_form = ContentVersionForm(request.POST)

        create_version = request.POST.get('create_version') == 'true'

        if content_form.is_valid():
            with transaction.atomic():
                # Update content metadata
                content = content_form.save()

                # Create new version if requested and form is valid
                if create_version and version_form.is_valid():
                    new_version = ContentVersion.create_next_version(
                        content=content,
                        created_by=request.user,
                        content_text=version_form.cleaned_data['content_text'],
                        change_summary=version_form.cleaned_data.get('change_summary', '')
                    )

                    # Update current version
                    content.current_version = new_version
                    content.save(update_fields=['current_version'])

                    messages.success(request, 'Content updated with new version.')
                else:
                    messages.success(request, 'Content metadata updated.')

                return redirect('content:detail', pk=content.pk)
    else:
        content_form = ContentForm(instance=content)
        version_form = ContentVersionForm(
            initial={
                'content_text': content.current_version.content_text if content.current_version else ''
            }
        )

    return render(request, 'content/edit.html', {
        'content': content,
        'content_form': content_form,
        'version_form': version_form
    })


@login_required
@user_owns_content
@require_http_methods(["POST"])
def content_delete(request, pk):
    """
    Delete content (soft delete or hard delete).
    """
    content = get_object_or_404(Content, pk=pk)
    title = content.title

    content.delete()

    messages.success(request, f'Content "{title}" deleted successfully.')
    return redirect('content:list')


@login_required
@user_owns_content
def content_versions(request, pk):
    """
    List all versions of a content item.
    """
    content = get_object_or_404(Content, pk=pk)
    versions = content.versions.all()

    return render(request, 'content/versions.html', {
        'content': content,
        'versions': versions
    })


@login_required
@user_owns_content
def content_transition(request, pk):
    """
    Transition content to a new lifecycle state.
    """
    if request.method == 'POST':
        content = get_object_or_404(Content, pk=pk)
        new_state = request.POST.get('new_state')

        try:
            content.transition_to(new_state)
            messages.success(request, f'Content transitioned to {content.get_lifecycle_state_display()}.')
        except Exception as e:
            messages.error(request, f'Transition failed: {str(e)}')

        return redirect('content:detail', pk=content.pk)

    return redirect('content:detail', pk=pk)
