"""Run one pipeline stage for a post, record it, and handle its failures.

What happens when a stage fails depends on the kind of error
(core/errors.py):
- ProviderBusy (rate limit, timeout): raise TryAgainLater, so the task
  retries later; on the last try the post fails instead.
- ProviderKeyRejected: the credential is marked invalid, the user is told,
  and the post fails. Retrying cannot help.
- Any other ProviderError, or a missing credential: the post fails with a
  plain reason.
Every run, good or bad, is saved as a GenerationStep: the audit trail.
"""

import time

from core.errors import ProviderBusy, ProviderError, ProviderKeyRejected
from credentials.services import CredentialMissing, reject_credential
from notifications.services import notify
from studio.models import GenerationStep, Post
from studio.pipeline import STAGES
from studio.statuses import change_status


class TryAgainLater(Exception):
    """Raised when a provider was busy and the stage should be retried."""


def record_step(post, stage_name, started, models, error=""):
    """Save a GenerationStep with what the stage used and how it went."""
    names = []
    prompt_versions = []
    input_tokens = 0
    output_tokens = 0
    for model in models:
        names.append(model.describe())
        prompt_versions = prompt_versions + model.prompt_versions
        input_tokens = input_tokens + model.input_tokens
        output_tokens = output_tokens + model.output_tokens
    GenerationStep.objects.create(
        post=post,
        stage=stage_name,
        succeeded=error == "",
        duration_ms=int((time.monotonic() - started) * 1000),
        error=error,
        providers=", ".join(names),
        prompt_versions=", ".join(prompt_versions),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def fail_post(post, reason):
    """Mark the post failed and tell the user why."""
    change_status(post, "failed", reason)
    notify(post.user, "post_failed", reason, related=post)


def handle_failure(post, error, can_retry):
    """Decide what a failed stage means for the post (see the list above)."""
    if isinstance(error, ProviderBusy) and can_retry:
        raise TryAgainLater(str(error)) from error
    if isinstance(error, ProviderKeyRejected) and error.credential is not None:
        reject_credential(error.credential, str(error))
    fail_post(post, str(error))


def run_stage(post_id, can_retry=False):
    """Run the stage for the post's current status and return its new status.

    A post that waits for the user, or is finished, is left alone. A post
    deleted (with its plan) while its job waited returns "deleted".
    """
    post = (
        Post.objects.select_related("plan", "topic", "article", "user")
        .filter(id=post_id)
        .first()
    )
    if post is None:
        return "deleted"
    stage_name = post.status
    stage = STAGES.get(stage_name)
    if stage is None:
        return post.status
    started = time.monotonic()
    try:
        models = stage(post)
    except (ProviderError, CredentialMissing) as error:
        record_step(post, stage_name, started, [], error=str(error))
        handle_failure(post, error, can_retry)
        return post.status
    record_step(post, stage_name, started, models)
    return post.status
