"""Local admin authentication and Supabase-backed, admin-approved broker accounts."""
import hashlib
import hmac
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock

import jwt
from fastapi import HTTPException
from supabase import create_client
from database.staff_scope import StaffPrincipal, current_staff

COOKIE_NAME = 'apnaghar_staff'
_ATTEMPTS = defaultdict(deque)
_ATTEMPT_LOCK = Lock()


def service_client():
    from database.supabase_client import get_service_client
    return get_service_client()


def auth_client():
    # A separate client prevents sign-in from changing the shared service-role session.
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        raise HTTPException(503, 'Account services are not configured')
    return create_client(url, key)


def rate_limit(request, action, maximum=10):
    host = request.client.host if request.client else 'unknown'
    key, now = (action, host), time.monotonic()
    with _ATTEMPT_LOCK:
        if len(_ATTEMPTS) > 10000:
            for item in list(_ATTEMPTS):
                if not _ATTEMPTS[item] or now - _ATTEMPTS[item][-1] > 900:
                    del _ATTEMPTS[item]
        queue = _ATTEMPTS[key]
        while queue and now - queue[0] > 900:
            queue.popleft()
        if len(queue) >= maximum:
            raise HTTPException(429, 'Too many attempts. Please try again in 15 minutes.')
        queue.append(now)


def admin_settings():
    username = os.environ.get('ADMIN_USERNAME', '').strip()
    password = os.environ.get('ADMIN_PASSWORD', '')
    secret = os.environ.get('ADMIN_SESSION_SECRET', '')
    if not username or len(password) < 12 or len(secret) < 32:
        raise HTTPException(503, 'Admin login is not configured. Run scripts/setup_local.py.')
    return username, password, secret


def admin_sign_in(username, password):
    expected_user, expected_password, secret = admin_settings()
    if not (hmac.compare_digest(username, expected_user) & hmac.compare_digest(password, expected_password)):
        raise HTTPException(401, 'Invalid admin credentials')
    return jwt.encode({'sub': expected_user, 'role': 'admin', 'aud': 'apnaghar-admin',
        'credential_version': hashlib.sha256(expected_password.encode()).hexdigest(),
        'iat': datetime.now(timezone.utc), 'exp': datetime.now(timezone.utc) + timedelta(hours=1)}, secret, algorithm='HS256')


def authenticate_token(token):
    if not token or len(token) > 16000:
        raise HTTPException(401, 'Please sign in')
    # Unverified metadata is used only to choose a verifier, never to grant access.
    try:
        audience = jwt.decode(token, options={'verify_signature': False}).get('aud')
    except Exception:
        raise HTTPException(401, 'Invalid session')
    if audience == 'apnaghar-admin':
        username, password, secret = admin_settings()
        try:
            claims = jwt.decode(token, secret, algorithms=['HS256'], audience='apnaghar-admin',
                                options={'require': ['sub', 'exp', 'role', 'credential_version']})
            if claims['role'] != 'admin' or claims['sub'] != username or not hmac.compare_digest(
                claims['credential_version'], hashlib.sha256(password.encode()).hexdigest()):
                raise ValueError('Admin credentials changed')
            return StaffPrincipal(role='admin', name=username)
        except Exception:
            raise HTTPException(401, 'Admin session expired. Please sign in again.')
    try:
        user = auth_client().auth.get_user(token).user
        if not user:
            raise ValueError('Missing user')
    except Exception:
        raise HTTPException(401, 'Broker session expired. Please sign in again.')
    try:
        rows = service_client().table('brokers').select('*').eq('auth_user_id', str(user.id)).limit(1).execute().data or []
    except Exception:
        raise HTTPException(503, 'Broker account setup is unavailable. Apply migration 007.')
    if not rows or rows[0].get('approval_status') != 'approved' or not rows[0].get('is_active'):
        raise HTTPException(403, 'Broker access requires current ApnaGhar admin approval')
    broker = rows[0]
    return StaffPrincipal(role='broker', broker_id=broker['id'], user_id=str(user.id),
                          name=broker['name'], email=broker.get('email') or '', phone=broker.get('phone') or '')


def require_staff_token(token=None):
    principal = current_staff.get()
    return principal or authenticate_token(token)


def require_admin():
    principal = current_staff.get()
    if not principal or principal.role != 'admin':
        raise HTTPException(403, 'ApnaGhar admin access required')
    return principal


def actor_broker_id(supplied=None):
    principal = current_staff.get()
    if not principal:
        raise HTTPException(401, 'Please sign in')
    if principal.role == 'broker':
        return principal.broker_id
    if not supplied:
        raise HTTPException(400, 'Choose an approved broker for this listing or import')
    rows = service_client().table('brokers').select('id').eq('id', supplied).eq('approval_status', 'approved').eq('is_active', True).limit(1).execute().data
    if not rows:
        raise HTTPException(400, 'An approved broker account is required')
    return supplied
