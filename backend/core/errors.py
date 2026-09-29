"""Sanitized error handling — never leak raw portal HTML/status text to the user."""


class PortalError(Exception):
    """Raised by a scraper client when the government portal can't fulfil the
    request. `user_message` is always safe to show as-is; `detail` is for logs."""

    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(detail or user_message)
        self.user_message = user_message
        self.detail = detail


NOT_FOUND = "No record found for the details you entered. Please double-check and try again."
PORTAL_DOWN = "The government portal isn't responding right now. Please try again in a few minutes."
PORTAL_TIMEOUT = "The government portal is taking too long to respond. Please try again shortly."
CAPTCHA_FAILED = "Couldn't verify the security check. Please try again."
BAD_INPUT = "Please check the details you entered and try again."
