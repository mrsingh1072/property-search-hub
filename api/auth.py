"""
Customer authentication for the web app.

Two login methods, both issuing a JWT session:
  1. Email OTP  — email → 6-digit code (Gmail SMTP) → verify → JWT
  2. Google     — Google Identity Services credential (ID token) → verify → JWT

Customers are stored in the `customers` table (Supabase). Favourites + booked
visits are tied to the customer so they can see everything they liked / scheduled.

Env:
  JWT_SECRET               signing secret for session tokens
  GOOGLE_OAUTH_CLIENT_ID   (optional) enables Google login
"""

import os
import time
import secrets
import logging
import re
import hmac
from threading import RLock
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET") or secrets.token_urlsafe(48)
if not os.environ.get("JWT_SECRET"):
    logger.warning("JWT_SECRET is unset: using a random process-local key. Run scripts/setup_local.py for persistent sessions.")
JWT_ALGO = "HS256"
JWT_TTL_DAYS = 30
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")

# In-memory OTP store (single uvicorn worker): email -> (code, expires_at)
_otp_store: dict[str, tuple[str, float]] = {}
_otp_attempts: dict[str, int] = {}   # email -> wrong-code attempts (brute-force guard)
_otp_last_sent: dict[str, float] = {}
_otp_lock = RLock()
_OTP_TTL = 600       # 10 minutes
_OTP_MAX_TRIES = 5   # lock the code after this many wrong guesses


# ── JWT sessions ──────────────────────────────────────────────────────────────

def issue_jwt(customer: dict) -> str:
    payload = {
        "sub": str(customer.get("id")),
        "email": customer.get("email"),
        "name": customer.get("name"),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_TTL_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def verify_jwt(token: str) -> dict | None:
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        return None


# ── Email OTP ─────────────────────────────────────────────────────────────────

def normalize_email(email: str) -> str:
    email = (email or '').strip().lower()
    if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        return ''
    return email


def otp_key(email, purpose):
    if purpose not in {'customer', 'broker'}:
        raise ValueError('Unknown login purpose')
    return email if purpose == 'customer' else 'broker:' + email


def request_otp(email: str, purpose: str = 'customer') -> bool:
    email = normalize_email(email)
    if not email:
        return False
    key, now = otp_key(email, purpose), time.time()
    with _otp_lock:
        # Keep the resend delay even after a code has been consumed.
        for old in list(_otp_last_sent):
            if now - _otp_last_sent[old] > _OTP_TTL:
                _otp_last_sent.pop(old, None)
                _otp_store.pop(old, None)
                _otp_attempts.pop(old, None)
        if now - _otp_last_sent.get(key, 0) < 60:
            return False
        _otp_last_sent[key] = now
        # A new request replaces the previous code; a failed send grants no code.
        _otp_store.pop(key, None)
        _otp_attempts.pop(key, None)
    code = f"{secrets.randbelow(1000000):06d}"
    sent = False
    try:
        from notifications.email_notifier import _send
        label = 'broker sign-in' if purpose == 'broker' else 'sign-in'
        html = (f"<div style='font-family:sans-serif'><p>Hi,</p>"
                f"<p>Your ApnaGhar {label} code is:</p>"
                f"<p style='font-size:28px;font-weight:700;letter-spacing:4px'>{code}</p>"
                f"<p>Valid for 10 minutes. Never share this code. "
                f"If you did not request it, ignore this email.</p></div>")
        sent = _send(email, f"Your ApnaGhar {label} code", html,
                     f"Your ApnaGhar {label} code is {code} (valid 10 minutes). Never share it.")
    except Exception:
        logger.error('OTP email delivery failed')
    with _otp_lock:
        if sent:
            _otp_store[key] = (code, time.time() + _OTP_TTL)
            _otp_attempts[key] = 0
        else:
            _otp_last_sent.pop(key, None)
    return bool(sent)


def verify_otp(email: str, code: str, purpose: str = 'customer') -> bool:
    email = normalize_email(email)
    if not email:
        return False
    key = otp_key(email, purpose)
    with _otp_lock:
        rec = _otp_store.get(key)
        if not rec:
            return False
        real, exp = rec
        if time.time() >= exp or _otp_attempts.get(key, 0) >= _OTP_MAX_TRIES:
            _otp_store.pop(key, None)
            _otp_attempts.pop(key, None)
            return False
        supplied = (code or '').strip()
        if not re.fullmatch(r'[0-9]{6}', supplied) or not hmac.compare_digest(supplied, real):
            attempts = _otp_attempts.get(key, 0) + 1
            _otp_attempts[key] = attempts
            if attempts >= _OTP_MAX_TRIES:
                _otp_store.pop(key, None)
                _otp_attempts.pop(key, None)
            return False
        _otp_store.pop(key, None)
        _otp_attempts.pop(key, None)
        return True


# ── Google Identity ───────────────────────────────────────────────────────────

def verify_google(credential: str) -> dict | None:
    """Verify a Google Identity Services credential (ID token). Returns profile dict."""
    if not GOOGLE_CLIENT_ID or not credential:
        return None
    try:
        from google.oauth2 import id_token as gid_token
        from google.auth.transport import requests as g_requests
        info = gid_token.verify_oauth2_token(credential, g_requests.Request(), GOOGLE_CLIENT_ID)
        if info.get("email_verified") is not True or not info.get("sub") or not normalize_email(info.get("email")):
            return None
        return {"email": normalize_email(info["email"]), "name": info.get("name"), "sub": info["sub"]}
    except Exception as e:
        logger.warning("Google token verification failed")
        return None


# ── Customer records ──────────────────────────────────────────────────────────

def get_or_create_customer(email: str, name: str | None = None, google_sub: str | None = None) -> dict:
    from database.supabase_client import get_client
    c = get_client()
    email = email.strip().lower()
    rows = c.table("customers").select("*").eq("email", email).limit(1).execute().data
    if rows:
        cust = rows[0]
        upd = {}
        if name and not cust.get("name"):
            upd["name"] = name
        if google_sub and not cust.get("google_sub"):
            upd["google_sub"] = google_sub
        if upd:
            c.table("customers").update(upd).eq("id", cust["id"]).execute()
            cust = {**cust, **upd}
        return cust
    saved = c.table("customers").insert(
        {"email": email, "name": name, "google_sub": google_sub, "favourites": []}
    ).execute().data
    return saved[0] if saved else {"email": email, "name": name, "favourites": []}


def get_customer(customer_id: str) -> dict | None:
    from database.supabase_client import get_client
    rows = get_client().table("customers").select("*").eq("id", customer_id).limit(1).execute().data
    return rows[0] if rows else None


def set_customer_favourites(customer_id: str, favourites: list[str]) -> None:
    from database.supabase_client import get_client
    get_client().table("customers").update({"favourites": favourites}).eq("id", customer_id).execute()


def set_customer_phone(customer_id: str, phone: str) -> None:
    from database.supabase_client import get_client
    get_client().table("customers").update({"phone": phone}).eq("id", customer_id).execute()
