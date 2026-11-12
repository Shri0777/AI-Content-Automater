"""The base class for sending a finished post to a social media platform.

This is the adapter pattern: Publisher is the base class, and every platform
has one subclass that knows how to talk to it (the demo network's is in
demo/publisher.py). The rest of the code calls
social.services.get_publisher(platform).publish(...), so it never needs to
know which platform it is posting to.
"""


class Publisher:
    """The base class every platform's publisher follows."""

    def publish(self, account, caption, image_bytes):
        """Post caption and image to account; return the platform's post id.

        Raise core.errors.ProviderError if the platform refuses or fails.
        """
        raise NotImplementedError("Each publisher must define publish().")
