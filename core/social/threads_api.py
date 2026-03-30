"""
Threads API integration for PhotoFlow.

Required credentials:
  access_token  — OAuth2 User Access Token
  user_id       — Threads user ID

API is similar to Instagram Graph API (both Meta).
Scopes: threads_basic, threads_content_publish
"""
import time

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

from .base import SocialPlatform, PostResult

_GRAPH = 'https://graph.threads.net/v1.0'


class ThreadsAPI(SocialPlatform):
    platform_name = 'threads'

    def is_connected(self) -> bool:
        return bool(
            self.credentials.get('access_token') and
            self.credentials.get('user_id')
        )

    def verify_credentials(self) -> tuple[bool, str]:
        if not self.is_connected():
            return False, 'Missing access_token or user_id'
        if not _HAS_REQUESTS:
            return False, 'requests not installed'
        try:
            uid = self.credentials['user_id']
            token = self.credentials['access_token']
            r = _requests.get(
                f'{_GRAPH}/{uid}',
                params={'fields': 'id,username', 'access_token': token},
                timeout=10
            )
            data = r.json()
            if 'error' in data:
                return False, data['error'].get('message', 'API error')
            return True, f"Connected as @{data.get('username', uid)}"
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

        token = self.credentials['access_token']
        uid = self.credentials['user_id']
        full_caption = self._build_caption(caption, hashtags)

        image_url = filepath if filepath.startswith('http') else None
        if not image_url:
            return PostResult(False, self.platform_name,
                              error='Threads requires a public image URL.')

        try:
            # Step 1: Create media container
            r = _requests.post(
                f'{_GRAPH}/{uid}/threads',
                data={
                    'media_type': 'IMAGE',
                    'image_url': image_url,
                    'text': full_caption,
                    'access_token': token,
                },
                timeout=30
            )
            container = r.json()
            if 'error' in container:
                return PostResult(False, self.platform_name,
                                  error=container['error'].get('message', 'Container error'))
            container_id = container.get('id')
            if not container_id:
                return PostResult(False, self.platform_name, error='No container ID')

            # Step 2: Wait briefly
            time.sleep(3)

            # Step 3: Publish
            pub_r = _requests.post(
                f'{_GRAPH}/{uid}/threads_publish',
                data={'creation_id': container_id, 'access_token': token},
                timeout=30
            )
            pub = pub_r.json()
            if 'error' in pub:
                return PostResult(False, self.platform_name,
                                  error=pub['error'].get('message', 'Publish error'))
            post_id = pub.get('id', '')
            return PostResult(True, self.platform_name, post_id=post_id)
        except Exception as e:
            return PostResult(False, self.platform_name, error=str(e))
