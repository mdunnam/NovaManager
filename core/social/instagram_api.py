"""Instagram Graph API integration for PhotoFlow.

Credentials used by this client:
    access_token            Long-lived user token.
    ig_user_id              Instagram Business/Creator account id.
    page_id                 Linked Facebook Page id.
    app_id                  Meta app id.
    app_secret              Meta app secret.
    redirect_uri            OAuth redirect URI (typically localhost).
    local_media_root        Optional local folder mapped to a public base URL.
    public_image_base_url   Optional public CDN/site URL used for local files.
"""
from pathlib import Path
from urllib.parse import quote, urlencode
import time

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

from .base import SocialPlatform, PostResult

_GRAPH = 'https://graph.facebook.com/v19.0'
_SCOPES = [
    'instagram_basic',
    'instagram_content_publish',
    'pages_read_engagement',
    'pages_show_list',
]


class InstagramAPI(SocialPlatform):
    """Instagram Graph API helper with OAuth and account discovery support."""

    platform_name = 'instagram'

    def is_connected(self) -> bool:
        """Return True when the minimum credentials required for posting exist."""
        return bool(
            self.credentials.get('access_token') and
            self.credentials.get('ig_user_id')
        )

    @staticmethod
    def build_auth_url(app_id: str, redirect_uri: str, state: str = '') -> str:
        """Build the Meta OAuth URL for Instagram Graph API access."""
        params = {
            'client_id': app_id,
            'redirect_uri': redirect_uri,
            'scope': ','.join(_SCOPES),
            'response_type': 'code',
        }
        if state:
            params['state'] = state
        return f'https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}'

    @staticmethod
    def exchange_code_for_short_lived_token(
        app_id: str,
        app_secret: str,
        redirect_uri: str,
        code: str,
    ) -> tuple[bool, dict]:
        """Exchange an OAuth authorization code for a short-lived user token."""
        if not _HAS_REQUESTS:
            return False, {'error': 'requests library not installed'}
        try:
            resp = _requests.get(
                f'{_GRAPH}/oauth/access_token',
                params={
                    'client_id': app_id,
                    'client_secret': app_secret,
                    'redirect_uri': redirect_uri,
                    'code': code,
                },
                timeout=20,
            )
            data = resp.json()
            if 'error' in data:
                return False, data
            return True, data
        except Exception as exc:
            return False, {'error': {'message': str(exc)}}

    @staticmethod
    def exchange_for_long_lived_token(
        app_id: str,
        app_secret: str,
        short_lived_token: str,
    ) -> tuple[bool, dict]:
        """Exchange a short-lived user token for a long-lived user token."""
        if not _HAS_REQUESTS:
            return False, {'error': 'requests library not installed'}
        try:
            resp = _requests.get(
                f'{_GRAPH}/oauth/access_token',
                params={
                    'grant_type': 'fb_exchange_token',
                    'client_id': app_id,
                    'client_secret': app_secret,
                    'fb_exchange_token': short_lived_token,
                },
                timeout=20,
            )
            data = resp.json()
            if 'error' in data:
                return False, data
            return True, data
        except Exception as exc:
            return False, {'error': {'message': str(exc)}}

    @staticmethod
    def discover_connected_instagram_account(access_token: str) -> tuple[bool, dict]:
        """Resolve the first Facebook Page linked to an Instagram business account."""
        if not _HAS_REQUESTS:
            return False, {'error': 'requests library not installed'}
        try:
            resp = _requests.get(
                f'{_GRAPH}/me/accounts',
                params={
                    'fields': 'id,name,instagram_business_account{id,username}',
                    'access_token': access_token,
                },
                timeout=20,
            )
            data = resp.json()
            if 'error' in data:
                return False, data
            for page in data.get('data', []):
                ig = page.get('instagram_business_account') or {}
                ig_user_id = ig.get('id')
                if ig_user_id:
                    return True, {
                        'page_id': page.get('id', ''),
                        'page_name': page.get('name', ''),
                        'ig_user_id': ig_user_id,
                        'ig_username': ig.get('username', ''),
                    }
            return False, {
                'error': {
                    'message': (
                        'No Facebook Page linked to an Instagram Business/Creator account '
                        'was found for this login.'
                    )
                }
            }
        except Exception as exc:
            return False, {'error': {'message': str(exc)}}

    def verify_credentials(self) -> tuple[bool, str]:
        """Validate the token by querying the linked Instagram account."""
        if not self.is_connected():
            return False, 'Missing access_token or ig_user_id'
        if not _HAS_REQUESTS:
            return False, 'requests library not installed'
        try:
            uid = self.credentials['ig_user_id']
            token = self.credentials['access_token']
            resp = _requests.get(
                f'{_GRAPH}/{uid}',
                params={
                    'fields': 'id,username,account_type',
                    'access_token': token,
                },
                timeout=10,
            )
            data = resp.json()
            if 'error' in data:
                return False, data['error'].get('message', 'API error')
            account_name = data.get('username') or uid
            account_type = data.get('account_type') or 'unknown'
            return True, f'Connected as @{account_name} ({account_type})'
        except Exception as exc:
            return False, str(exc)

    def _resolve_public_image_url(self, filepath: str) -> str:
        """Return a public image URL for Graph API publishing.

        Instagram requires a publicly reachable image URL. This helper maps a
        local file path to a public URL when ``public_image_base_url`` is set.
        """
        if filepath.startswith('http://') or filepath.startswith('https://'):
            return filepath

        base_url = (self.credentials.get('public_image_base_url') or '').strip().rstrip('/')
        if not base_url:
            return ''

        local_media_root = (self.credentials.get('local_media_root') or '').strip()
        path = Path(filepath)
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path

        if local_media_root:
            try:
                rel = resolved.relative_to(Path(local_media_root).resolve())
                rel_parts = [quote(part) for part in rel.parts]
                return base_url + '/' + '/'.join(rel_parts)
            except Exception:
                pass

        return base_url + '/' + quote(resolved.name)

    def post_photo(self, filepath: str, caption: str = '', hashtags: list[str] | None = None) -> PostResult:
        """Publish an Instagram image post through the Graph API."""
        if not _HAS_REQUESTS:
            return PostResult(False, self.platform_name, error='requests library not installed')
        if not self.is_connected():
            return PostResult(False, self.platform_name, error='Not connected')

        token = self.credentials['access_token']
        uid = self.credentials['ig_user_id']
        full_caption = self._build_caption(caption, hashtags)
        image_url = self._resolve_public_image_url(filepath)

        if not image_url:
            return PostResult(
                False,
                self.platform_name,
                error=(
                    'Instagram requires a public image URL. Configure '
                    'local_media_root + public_image_base_url in Settings, or use a file '
                    'path that is already publicly hosted.'
                ),
            )

        try:
            resp = _requests.post(
                f'{_GRAPH}/{uid}/media',
                data={
                    'image_url': image_url,
                    'caption': full_caption,
                    'access_token': token,
                },
                timeout=30,
            )
            container = resp.json()
            if 'error' in container:
                return PostResult(
                    False,
                    self.platform_name,
                    error=container['error'].get('message', 'Container error'),
                )

            container_id = container.get('id')
            if not container_id:
                return PostResult(False, self.platform_name, error='No container ID returned')

            for _ in range(12):
                time.sleep(2)
                status_resp = _requests.get(
                    f'{_GRAPH}/{container_id}',
                    params={'fields': 'status_code', 'access_token': token},
                    timeout=10,
                )
                status_code = (status_resp.json() or {}).get('status_code', '')
                if status_code == 'FINISHED':
                    break
                if status_code == 'ERROR':
                    return PostResult(False, self.platform_name, error='Media processing failed')

            publish_resp = _requests.post(
                f'{_GRAPH}/{uid}/media_publish',
                data={'creation_id': container_id, 'access_token': token},
                timeout=30,
            )
            publish_data = publish_resp.json()
            if 'error' in publish_data:
                return PostResult(
                    False,
                    self.platform_name,
                    error=publish_data['error'].get('message', 'Publish error'),
                )

            post_id = publish_data.get('id', '')
            url = f'https://www.instagram.com/p/{post_id}/' if post_id else ''
            return PostResult(True, self.platform_name, post_id=post_id, url=url)
        except Exception as exc:
            return PostResult(False, self.platform_name, error=str(exc))
