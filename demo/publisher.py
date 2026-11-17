"""A fake social network for demo mode and tests.

It never contacts the internet. "Publishing" just invents a post id; the
Publication row saved by publishing/services.py is the record of the post.
"""

import uuid

from social.publishers import Publisher


class DemoPublisher(Publisher):
    """Pretends to publish a post and returns a made-up post id."""

    def publish(self, account, content):
        """Return a new fake post id, as a real platform would."""
        return f"demo-post-{uuid.uuid4().hex[:12]}"
