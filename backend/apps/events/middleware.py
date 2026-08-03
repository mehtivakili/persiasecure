"""
JWT auth for Channels: reads ?token=<access> from the WS query string and
resolves it to a User in scope. Falls back to session auth otherwise.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _get_user(token):
    from rest_framework_simplejwt.tokens import AccessToken
    from apps.accounts.models import User

    try:
        access = AccessToken(token)
        return User.objects.get(id=access["user_id"])
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = (query.get("token") or [None])[0]
        if token:
            scope["user"] = await _get_user(token)
        return await super().__call__(scope, receive, send)
