"""
Base classes for social media platform integrations.
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class PostResult:
    """Result from a social media post attempt."""
    success: bool
    platform: str
    post_id: str = ''
    url: str = ''
    error: str = ''
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SocialPlatform:
    """Base class for social media platform integrations."""

    platform_name = 'unknown'

    def __init__(self, credentials: dict):
        """
        credentials: dict with keys like access_token, client_id, etc.
        Specific keys depend on the platform subclass.
        """
        self.credentials = credentials or {}

    def is_connected(self) -> bool:
        """Return True if credentials look valid (not a live check)."""
        raise NotImplementedError

    def post_photo(
        self,
        filepath: str,
        caption: str = '',
        hashtags: list[str] | None = None,
        alt_text: str = '',
    ) -> PostResult:
        """Post a single photo. Subclasses must implement."""
        raise NotImplementedError

    def _build_caption(self, caption: str, hashtags: list[str] | None) -> str:
        """Combine caption text with hashtags."""
        parts = [caption.strip()] if caption.strip() else []
        if hashtags:
            tag_str = ' '.join(
                f'#{t.lstrip("#")}' for t in hashtags if t.strip()
            )
            parts.append(tag_str)
        return '\n\n'.join(parts)

    def verify_credentials(self) -> tuple[bool, str]:
        """
        Make a lightweight API call to verify credentials.
        Returns (success, message).
        Default implementation just checks is_connected().
        """
        if self.is_connected():
            return True, 'Credentials present'
        return False, 'No credentials configured'
