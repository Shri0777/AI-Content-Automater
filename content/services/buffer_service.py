"""
Buffer Publishing Service (Phase 6 - Official GraphQL API).

Implements the official Buffer GraphQL API (https://api.buffer.com):
- Token validation and safe masking (never logs/exposes raw tokens)
- Account and organization discovery (query GetAccountAndOrgs)
- Channel/profile discovery (query GetChannels)
- Immediate publishing (mutation CreatePost with mode: shareNow)
- Scheduled publishing (mutation CreatePost with mode: customScheduled and dueAt ISO-8601 UTC)
- Union response handling (PostActionSuccess vs MutationError)
- Bounded transient retries for idempotent safe operations
- Ambiguous outcome handling on network timeouts (BR-018: no blind retries)
"""
import logging
from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10  # seconds
MAX_TRANSIENT_RETRIES = 1
DEFAULT_GRAPHQL_ENDPOINT = "https://api.buffer.com"


class BufferPublishingService:
    """
    Client for interacting with the official Buffer GraphQL API.
    All operations are sent via POST to https://api.buffer.com with Bearer auth.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT
    ):
        self.access_token = access_token or getattr(settings, 'BUFFER_ACCESS_TOKEN', '')
        # Support both BUFFER_API_URL and legacy BUFFER_API_BASE_URL setting names
        configured_url = api_url or getattr(settings, 'BUFFER_API_URL', None) or getattr(settings, 'BUFFER_API_BASE_URL', None)
        self.api_url = (configured_url or DEFAULT_GRAPHQL_ENDPOINT).rstrip('/')
        self.timeout = timeout

    @staticmethod
    def mask_token(token: Optional[str]) -> str:
        """Safely mask access token for display in UI/logs without secret disclosure."""
        if not token:
            return "Not configured"
        clean = token.strip()
        if len(clean) <= 8:
            return "Configured"
        return f"{clean[:4]}...{clean[-4:]}"

    def is_configured(self) -> bool:
        """Return True if a non-empty Buffer access token is configured."""
        return bool(self.access_token and self.access_token.strip())

    def get_masked_token(self) -> Optional[str]:
        """Return masked token string or None if unconfigured."""
        if not self.is_configured():
            return None
        return self.mask_token(self.access_token)

    def _get_headers(self) -> Dict[str, str]:
        """Construct secure authorization and content-type headers."""
        return {
            'Authorization': f"Bearer {self.access_token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def get_connection_status(self) -> Dict[str, Any]:
        """
        Validate token and check connection to Buffer via GraphQL account query.
        
        Returns:
            Dict containing configured status, connected flag, account info, and masked token.
        """
        if not self.is_configured():
            return {
                'configured': False,
                'connected': False,
                'status': 'unconfigured',
                'masked_token': 'Not configured',
                'error': 'BUFFER_ACCESS_TOKEN is not configured.'
            }

        query = """
        query GetAccountAndOrgs {
          account {
            id
            email
            organizations {
              id
              name
              ownerEmail
            }
          }
        }
        """

        try:
            res = requests.post(
                self.api_url,
                headers=self._get_headers(),
                json={'query': query},
                timeout=self.timeout
            )

            if res.status_code == 200:
                body = res.json()
                if 'errors' in body and body['errors']:
                    first_err = body['errors'][0]
                    err_msg = first_err.get('message', 'GraphQL error')
                    extensions = first_err.get('extensions', {})
                    code = extensions.get('code')
                    if code == 'UNAUTHENTICATED' or 'unauthenticated' in err_msg.lower():
                        return {
                            'configured': True,
                            'connected': False,
                            'status': 'unauthorized',
                            'masked_token': self.mask_token(self.access_token),
                            'error': 'Invalid Buffer credentials (UNAUTHENTICATED).'
                        }
                    return {
                        'configured': True,
                        'connected': False,
                        'status': 'error',
                        'masked_token': self.mask_token(self.access_token),
                        'error': f"Buffer GraphQL error: {err_msg}"
                    }

                account = body.get('data', {}).get('account')
                if not account:
                    return {
                        'configured': True,
                        'connected': False,
                        'status': 'error',
                        'masked_token': self.mask_token(self.access_token),
                        'error': 'Account data missing in Buffer response.'
                    }

                orgs = account.get('organizations', [])
                first_org = orgs[0] if orgs else {}

                return {
                    'configured': True,
                    'connected': True,
                    'status': 'connected',
                    'masked_token': self.mask_token(self.access_token),
                    'user_id': account.get('id'),
                    'user_name': first_org.get('name') or account.get('email'),
                    'email': account.get('email'),
                    'organization_id': first_org.get('id'),
                    'organizations': orgs
                }

            elif res.status_code == 401:
                return {
                    'configured': True,
                    'connected': False,
                    'status': 'unauthorized',
                    'masked_token': self.mask_token(self.access_token),
                    'error': 'Invalid Buffer credentials (HTTP 401).'
                }
            elif res.status_code == 429:
                return {
                    'configured': True,
                    'connected': False,
                    'status': 'rate_limited',
                    'masked_token': self.mask_token(self.access_token),
                    'error': 'Buffer API rate limit reached (HTTP 429).'
                }
            else:
                return {
                    'configured': True,
                    'connected': False,
                    'status': 'error',
                    'masked_token': self.mask_token(self.access_token),
                    'error': f"Buffer returned HTTP {res.status_code}"
                }

        except requests.exceptions.Timeout:
            return {
                'configured': True,
                'connected': False,
                'status': 'error',
                'masked_token': self.mask_token(self.access_token),
                'error': 'Buffer API connection timed out.'
            }
        except Exception as e:
            return {
                'configured': True,
                'connected': False,
                'status': 'error',
                'masked_token': self.mask_token(self.access_token),
                'error': f"Connection failure: {str(e)}"
            }

    def get_profiles(self) -> List[Dict[str, Any]]:
        """
        Fetch authorized social channels connected to this Buffer account.
        
        Returns:
            List of profile dicts (id, service, formatted_username, etc.) or empty list.
        """
        if not self.is_configured():
            raise RuntimeError('Buffer is not configured; channel authorization cannot be verified.')

        # Step 1: Query account and organization IDs
        org_query = """
        query GetOrganizations {
          account {
            organizations {
              id
            }
          }
        }
        """

        try:
            res = requests.post(
                self.api_url,
                headers=self._get_headers(),
                json={'query': org_query},
                timeout=self.timeout
            )
            if res.status_code != 200:
                logger.warning('Buffer organization discovery failed with HTTP %s', res.status_code)
                raise RuntimeError('Buffer channel discovery failed; destination authorization cannot be verified.')

            body = res.json()
            if body.get('errors') or not isinstance(body.get('data', {}).get('account'), dict):
                raise RuntimeError('Buffer channel discovery returned an invalid response; destination authorization cannot be verified.')
            account = body['data']['account']
            orgs = account.get('organizations', [])
            if not orgs:
                return []

            # Step 2: Query channels for each organization
            channels_query = """
            query GetChannels($input: ChannelsInput!) {
              channels(input: $input) {
                id
                name
                displayName
                service
                avatar
                isQueuePaused
              }
            }
            """

            profiles: List[Dict[str, Any]] = []
            for org in orgs:
                org_id = org.get('id')
                if not org_id:
                    continue

                chan_res = requests.post(
                    self.api_url,
                    headers=self._get_headers(),
                    json={
                        'query': channels_query,
                        'variables': {'input': {'organizationId': org_id}}
                    },
                    timeout=self.timeout
                )

                if chan_res.status_code != 200:
                    raise RuntimeError('Buffer channel discovery failed; destination authorization cannot be verified.')
                chan_body = chan_res.json()
                channels = chan_body.get('data', {}).get('channels')
                if chan_body.get('errors') or not isinstance(channels, list):
                    raise RuntimeError('Buffer channel discovery returned an invalid response; destination authorization cannot be verified.')
                for ch in channels:
                    if ch.get('id'):
                        profiles.append({
                            'id': ch.get('id'),
                            'service': ch.get('service', 'unknown'),
                            'formatted_username': ch.get('displayName') or ch.get('name') or ch.get('id'),
                            'service_username': ch.get('name'),
                            'avatar': ch.get('avatar'),
                            'disabled': ch.get('isQueuePaused', False)
                        })

            return profiles

        except Exception as e:
            logger.warning('Buffer channel discovery failed; refusing to authorize destinations (%s).', type(e).__name__)
            raise RuntimeError('Buffer channel discovery failed; destination authorization cannot be verified.') from None

    def create_update(
        self,
        profile_ids: List[str],
        text: str,
        now: bool = True,
        due_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a social update in Buffer via the GraphQL createPost mutation.
        
        Args:
            profile_ids: List of Buffer channel IDs
            text: Post text content
            now: True to publish immediately (mode: shareNow), False for scheduled (mode: customScheduled)
            due_at: Optional future timestamp for scheduled publication
            
        Returns:
            Dict containing success flag, updates list, sanitized response data, or error details.
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'Buffer access token is not configured.',
                'error_type': 'unconfigured'
            }

        if not profile_ids:
            return {
                'success': False,
                'error': 'At least one target Buffer channel must be selected.',
                'error_type': 'missing_destination'
            }

        clean_text = (text or '').strip()
        if not clean_text:
            return {
                'success': False,
                'error': 'Content text cannot be empty.',
                'error_type': 'empty_text'
            }

        # Format ISO 8601 UTC timestamp string for GraphQL customScheduled dueAt
        due_at_iso = None
        if not now and due_at:
            if timezone.is_naive(due_at):
                due_at = timezone.make_aware(due_at, timezone.get_current_timezone())
            utc_dt = due_at.astimezone(dt_timezone.utc)
            due_at_iso = utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        mutation = """
        mutation CreatePost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess {
              post {
                id
                text
                status
                dueAt
              }
            }
            ... on MutationError {
              message
            }
          }
        }
        """

        updates: List[Dict[str, Any]] = []

        for channel_id in profile_ids:
            input_vars = {
                'input': {
                    'channelId': str(channel_id),
                    'text': clean_text,
                    'schedulingType': 'automatic',
                    'mode': 'shareNow' if now else 'customScheduled'
                }
            }
            if not now and due_at_iso:
                input_vars['input']['dueAt'] = due_at_iso

            attempt = 0
            channel_success = False

            while attempt <= MAX_TRANSIENT_RETRIES:
                attempt += 1
                try:
                    res = requests.post(
                        self.api_url,
                        headers=self._get_headers(),
                        json={'query': mutation, 'variables': input_vars},
                        timeout=self.timeout
                    )

                    if res.status_code == 200:
                        body = res.json()

                        # Check top-level GraphQL errors
                        if 'errors' in body and body['errors']:
                            first_err = body['errors'][0]
                            err_msg = first_err.get('message', 'GraphQL error')
                            code = first_err.get('extensions', {}).get('code')
                            err_type = 'unauthorized' if code == 'UNAUTHENTICATED' else 'graphql_error'
                            return {
                                'success': False,
                                'error': f"Buffer error: {err_msg}",
                                'error_type': err_type,
                                'response_data': {'channel_id': channel_id}
                            }

                        result_data = body.get('data', {}).get('createPost', {})

                        # Union type 1: PostActionSuccess
                        if 'post' in result_data and result_data['post']:
                            post = result_data['post']
                            post_id = post.get('id')
                            if not post_id:
                                return {
                                    'success': False,
                                    'error': 'Buffer accepted mutation but did not return post ID.',
                                    'error_type': 'malformed_response'
                                }

                            updates.append({
                                'id': post_id,
                                'profile_id': channel_id,
                                'status': post.get('status') or ('scheduled' if not now else 'pending'),
                                'due_at': post.get('dueAt')
                            })
                            channel_success = True
                            break

                        # Union type 2: MutationError
                        if 'message' in result_data:
                            err_msg = result_data['message']
                            return {
                                'success': False,
                                'error': f"Buffer error: {err_msg}",
                                'error_type': 'mutation_error',
                                'response_data': {'channel_id': channel_id}
                            }

                        return {
                            'success': False,
                            'error': 'Unexpected Buffer response format.',
                            'error_type': 'malformed_response'
                        }

                    elif res.status_code == 401:
                        return {
                            'success': False,
                            'error': 'Buffer credentials invalid or expired (HTTP 401).',
                            'error_type': 'unauthorized',
                            'response_data': {'channel_id': channel_id}
                        }
                    elif res.status_code == 429:
                        return {
                            'success': False,
                            'error': 'Buffer rate limit exceeded (HTTP 429).',
                            'error_type': 'rate_limited',
                            'response_data': {'channel_id': channel_id}
                        }
                    elif res.status_code >= 500:
                        # A server error can happen after the mutation was applied. Never
                        # blindly retry createPost: Buffer may already have accepted it.
                        return {
                            'success': False,
                            'is_ambiguous': True,
                            'error': f"Buffer server returned HTTP {res.status_code}; outcome cannot be confirmed safely.",
                            'error_type': 'ambiguous_server_error',
                            'response_data': {'channel_id': channel_id}
                        }
                    else:
                        return {
                            'success': False,
                            'error': f"Buffer returned HTTP {res.status_code}",
                            'error_type': 'provider_error',
                            'response_data': {'channel_id': channel_id}
                        }

                except requests.exceptions.Timeout:
                    # CRITICAL (BR-018): Network timeout after dispatch is ambiguous.
                    # Do NOT retry automatically, as Buffer may have received and posted the update!
                    logger.warning("Buffer update submission timed out. Marking outcome as ambiguous to avoid duplication.")
                    return {
                        'success': False,
                        'is_ambiguous': True,
                        'error': 'Buffer post submission timed out in ambiguous state.',
                        'error_type': 'ambiguous_timeout',
                        'response_data': {'channel_id': channel_id}
                    }
                except requests.exceptions.ConnectionError:
                    # Connection failures can occur after request bytes were sent.
                    # Do not retry a non-idempotent createPost mutation.
                    return {
                        'success': False,
                        'is_ambiguous': True,
                        'error': 'Buffer connection failed during submission; check Buffer before retrying.',
                        'error_type': 'ambiguous_connection_error',
                        'response_data': {'channel_id': channel_id}
                    }
                except Exception:
                    # Do not expose exception text: it may contain request URLs or secrets.
                    return {
                        'success': False,
                        'is_ambiguous': True,
                        'error': 'Unexpected failure during Buffer submission; check Buffer before retrying.',
                        'error_type': 'ambiguous_unexpected_error',
                        'response_data': {'channel_id': channel_id}
                    }

            if not channel_success:
                return {
                    'success': False,
                    'error': f"Dispatch failed for channel {channel_id} after retries.",
                    'error_type': 'transient_failure'
                }

        # Sanitize response data: only store necessary audit identifiers
        sanitized_response = {
            'channels': [u['profile_id'] for u in updates],
            'post_ids': [u['id'] for u in updates],
            'mode': 'shareNow' if now else 'customScheduled'
        }

        return {
            'success': True,
            'updates': updates,
            'response_data': sanitized_response
        }
