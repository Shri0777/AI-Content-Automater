"""Settings for linking social media accounts (imported by base.py)."""

from config.env import read_text

# Social platforms (Phase 4). Users link their own accounts, but direct
# links (X, LinkedIn, Facebook) need an app that the operator registers with
# each platform. A platform whose client id is empty cannot be linked.
SOCIAL_APPS = {
    "x": {
        "client_id": read_text("X_CLIENT_ID", ""),
        "client_secret": read_text("X_CLIENT_SECRET", ""),
    },
    "linkedin": {
        "client_id": read_text("LINKEDIN_CLIENT_ID", ""),
        "client_secret": read_text("LINKEDIN_CLIENT_SECRET", ""),
    },
    "facebook": {
        "client_id": read_text("FACEBOOK_APP_ID", ""),
        "client_secret": read_text("FACEBOOK_APP_SECRET", ""),
    },
}
# Where each platform's API lives. Tests point these at a stub server.
SOCIAL_API_URLS = {
    "buffer": "https://api.buffer.com",
    "x": "https://api.x.com",
    "linkedin": "https://api.linkedin.com",
    "linkedin_oauth": "https://www.linkedin.com/oauth/v2",
    "facebook": "https://graph.facebook.com/v27.0",
}
# LinkedIn's API wants the version (year and month) in every request.
LINKEDIN_API_VERSION = read_text("LINKEDIN_API_VERSION", "202610")
# The address the outside world uses to reach this API. Platforms send users
# back here after they approve a link, and Buffer downloads posters from here,
# so for Buffer it must be reachable from the internet.
PUBLIC_API_URL = read_text("PUBLIC_API_URL", "http://localhost:8000")
# The frontend page users return to after linking an account.
FRONTEND_URL = read_text("FRONTEND_URL", "http://localhost:5173")
