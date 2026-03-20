"""
Instagram Graph API integration for PhotoFlow.

Required credentials:
  access_token   — long-lived User Access Token (60-day, refreshable)
  ig_user_id     — Instagram Business/Creator account user ID

Scopes needed:
  instagram_basic, instagram_content_publish, pages_read_engagement
"""
import os
import time

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

from .base import SocialPlatform, PostResult

_GRAPH = 'https://graph.facebook.com/v19.0'


class InstagramAPI(SocialPlatform):
    platform_name = 'instagram'

    def is_connected(self) -> bool:
        return bool(
            self.credentials.get('access_token') and
            self.credentials.get('ig_user_id')
        )

    def verify_credentials(self) -> tuple[bool, str]:
        if not self.is_connected():
            return False, 'Missing access_token or ig_user_id'
        if not _HAS_REQUESTS:
            return False, 'requests library not installed'
        try:
            uid = self.credentials['ig_user_id']
            token = self.credentials['access_token']
            r = _requests.get(
                f'{_GRAPH}/{uid}',
                params={'fields': 'id,name', 'access_token': token},
                timeout=10
            )
            data = r.json()
            if 'error' in data:
                return False, data['error'].get('message', 'API error')
            return True, f"Connected as {data.get('name', uid)}"
        except Exception as e:
            return False, str(e)

    def post_photo(self, filepath: str, caption: str = '',
                   hashtags: list[str] | None = None) -> PostResult:
        """
        Post a photo to Instagram via the Graph API.
        NOTE: The image must be publicly accessible via URL.
        For local files, the caller must first upload to a CDN/temporary host.
        Pass the public URL as filepath when the file is already hosted.
        """
        if not _HAS_REQUESTS:
            return PostResult(False, self.platform_name, error='requests not installed')
        if not self.is_connected():
            return PostResult(False, self.platform_name, error='Not connected')

        token = self.credentials['access_token']
        uid = self.credentials['ig_user_id']
        full_caption = self._build_caption(caption, hashtags)

        # Determine if filepath is a URL or local path
        image_url = filepath if filepath.startswith('http') else None
        if not image_url:
            return PostResult(
                False, self.platform_name,
                error='Instagram requires a public image URL. Upload the image to a CDN first.'
            )

        try:
            # Step 1: Create media container
            r = _requests.post(
                f'{_GRAPH}/{uid}/media',
                data={
                    'image_url': image_url,
                    'caption': full_caption,
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
                return PostResult(False, self.platform_name, error='No container ID returned')

            # Step 2: Wait for container processing (up to 30s)
            for _ in range(6):
                time.sleep(5)
                status_r = _requests.get(
                    f'{_GRAPH}/{container_id}',
                    params={'fields': 'status_code', 'access_token': token},
                    timeout=10
                )
                status = status_r.json().get('status_code', '')
                if status == 'FINISHED':
                    break
                if status == 'ERROR':
                    return PostResult(False, self.platform_name, error='Media processing failed')

            # Step 3: Publish
            pub_r = _requests.post(
                f'{_GRAPH}/{uid}/media_publish',
                data={'creation_id': container_id, 'access_token': token},
                timeout=30
            )
            pub = pub_r.json()
            if 'error' in pub:
                return PostResult(False, self.platform_name,
                                  error=pub['error'].get('message', 'Publish error'))

            post_id = pub.get('id', '')
            url = f'https://www.instagram.com/p/{post_id}/' if post_id else ''
            return PostResult(True, self.platform_name, post_id=post_id, url=url)

        except Exception as e:
            return PostResult(False, self.platform_name, error=str(e))

    def get_auth_url(self, app_id: str, redirect_uri: str) -> str:
        """Generate OAuth2 authorization URL."""
        scopes = 'instagram_basic,instagram_content_publish,pages_read_engagement'
        return (
            f'https://www.facebook.com/v19.0/dialog/oauth'
            f'?client_id={app_id}'
            f'&redirect_uri={redirect_uri}'
            f'&scope={scopes}'
            f'&response_type=code'
        )
