"""
Facebook Graph API integration for PhotoFlow (Page posting).

Required credentials:
  page_access_token  — Long-lived Page Access Token
  page_id            — Facebook Page ID

Scopes needed:
  pages_manage_posts, pages_read_engagement
"""
import os

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

from .base import SocialPlatform, PostResult

_GRAPH = 'https://graph.facebook.com/v19.0'


class FacebookAPI(SocialPlatform):
    platform_name = 'facebook'

    def is_connected(self) -> bool:
        return bool(
            self.credentials.get('page_access_token') and
            self.credentials.get('page_id')
        )

    def verify_credentials(self) -> tuple[bool, str]:
        if not self.is_connected():
            return False, 'Missing page_access_token or page_id'
        if not _HAS_REQUESTS:
            return False, 'requests not installed'
        try:
            pid = self.credentials['page_id']
            token = self.credentials['page_access_token']
            r = _requests.get(
                f'{_GRAPH}/{pid}',
                params={'fields': 'id,name', 'access_token': token},
                timeout=10
            )
            data = r.json()
            if 'error' in data:
                return False, data['error'].get('message', 'API error')
            return True, f"Connected as page: {data.get('name', pid)}"
        except Exception as e:
            return False, str(e)

    def post_photo(
        self,
        filepath: str,
        caption: str = '',
        hashtags: list[str] | None = None,
        alt_text: str = '',
    ) -> PostResult:
        if not _HAS_REQUESTS:
            return PostResult(False, self.platform_name, error='requests not installed')
        if not self.is_connected():
            return PostResult(False, self.platform_name, error='Not connected')

        pid = self.credentials['page_id']
        token = self.credentials['page_access_token']
        full_caption = self._build_caption(caption, hashtags)

        try:
            if filepath.startswith('http'):
                # Post via URL
                r = _requests.post(
                    f'{_GRAPH}/{pid}/photos',
                    data={'url': filepath, 'caption': full_caption, 'access_token': token},
                    timeout=30
                )
            elif os.path.exists(filepath):
                # Post via file upload
                with open(filepath, 'rb') as f:
                    r = _requests.post(
                        f'{_GRAPH}/{pid}/photos',
                        files={'source': f},
                        data={'caption': full_caption, 'access_token': token},
                        timeout=60
                    )
            else:
                return PostResult(False, self.platform_name, error='File not found')

            data = r.json()
            if 'error' in data:
                return PostResult(False, self.platform_name,
                                  error=data['error'].get('message', 'Post error'))
            post_id = data.get('id', '')
            url = f'https://www.facebook.com/{post_id}' if post_id else ''
            return PostResult(True, self.platform_name, post_id=post_id, url=url)
        except Exception as e:
            return PostResult(False, self.platform_name, error=str(e))
