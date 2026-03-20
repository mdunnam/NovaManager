"""
Pinterest API v5 integration for PhotoFlow.

Required credentials:
  access_token  — OAuth2 Bearer token
  board_id      — Target board ID

Scopes needed:
  boards:read, pins:write
"""
import os

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

from .base import SocialPlatform, PostResult

_API = 'https://api.pinterest.com/v5'


class PinterestAPI(SocialPlatform):
    platform_name = 'pinterest'

    def is_connected(self) -> bool:
        return bool(self.credentials.get('access_token'))

    def verify_credentials(self) -> tuple[bool, str]:
        if not self.is_connected():
            return False, 'Missing access_token'
        if not _HAS_REQUESTS:
            return False, 'requests not installed'
        try:
            r = _requests.get(
                f'{_API}/user_account',
                headers={'Authorization': f"Bearer {self.credentials['access_token']}"},
                timeout=10
            )
            data = r.json()
            if r.status_code == 200:
                return True, f"Connected as {data.get('username', '?')}"
            return False, data.get('message', f'HTTP {r.status_code}')
        except Exception as e:
            return False, str(e)

    def get_boards(self) -> list[dict]:
        """Fetch user's boards."""
        if not _HAS_REQUESTS or not self.is_connected():
            return []
        try:
            r = _requests.get(
                f'{_API}/boards',
                headers={'Authorization': f"Bearer {self.credentials['access_token']}"},
                timeout=10
            )
            return r.json().get('items', [])
        except Exception:
            return []

    def post_photo(self, filepath: str, caption: str = '',
                   hashtags: list[str] | None = None) -> PostResult:
        if not _HAS_REQUESTS:
            return PostResult(False, self.platform_name, error='requests not installed')
        if not self.is_connected():
            return PostResult(False, self.platform_name, error='Not connected')

        board_id = self.credentials.get('board_id')
        if not board_id:
            return PostResult(False, self.platform_name, error='No board_id configured')

        token = self.credentials['access_token']
        full_caption = self._build_caption(caption, hashtags)

        # Pinterest requires an image URL for standard pin creation
        if not filepath.startswith('http'):
            return PostResult(
                False, self.platform_name,
                error='Pinterest requires a public image URL. Upload the image to a CDN first.'
            )

        try:
            r = _requests.post(
                f'{_API}/pins',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                },
                json={
                    'board_id': board_id,
                    'title': caption[:100] if caption else '',
                    'description': full_caption[:500],
                    'media_source': {
                        'source_type': 'image_url',
                        'url': filepath,
                    },
                },
                timeout=30
            )
            data = r.json()
            if r.status_code in (200, 201):
                pin_id = data.get('id', '')
                url = f'https://pinterest.com/pin/{pin_id}/' if pin_id else ''
                return PostResult(True, self.platform_name, post_id=pin_id, url=url)
            return PostResult(False, self.platform_name,
                              error=data.get('message', f'HTTP {r.status_code}'))
        except Exception as e:
            return PostResult(False, self.platform_name, error=str(e))
