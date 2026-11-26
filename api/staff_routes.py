"""Broker applications, approved sign-in and local-admin account review."""
import asyncio
import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from api import staff_auth
from city_config import AREAS
from database.staff_scope import current_staff

router = APIRouter()
TEMPLATES = Path(__file__).parent / 'templates'


class BrokerApplication(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(min_length=10, max_length=20)
    password: str = Field(min_length=12, max_length=128)
    agency: str = Field(default='', max_length=160)
    verification_reference: str = Field(default='', max_length=200)
    areas: list[str] = Field(default_factory=list, max_length=30)


class Credentials(BaseModel):
    username: str = Field(default='', max_length=254)
    email: str = Field(default='', max_length=254)
    password: str = Field(min_length=1, max_length=128)


class BrokerReview(BaseModel):
    action: str
    note: str = Field(default='', max_length=1000)


def public_profile(broker):
    return {key: broker.get(key) for key in ('id', 'name', 'email', 'phone', 'agency', 'areas', 'approval_status', 'is_active', 'created_at', 'reviewed_at')}


def set_session(response, token):
    response.set_cookie(staff_auth.COOKIE_NAME, token, httponly=True, samesite='strict', max_age=3600,
                        secure=os.environ.get('PUBLIC_BASE_URL', '').startswith('https://'))
    response.headers['Cache-Control'] = 'no-store'


@router.get('/broker/apply', response_class=HTMLResponse)
async def apply_page():
    return HTMLResponse((TEMPLATES / 'broker_apply.html').read_text(encoding='utf-8'))


@router.post('/broker/apply', status_code=201)
def apply_broker(payload: BrokerApplication, request: Request):
    staff_auth.rate_limit(request, 'broker-application', maximum=5)
    email = payload.email.strip().lower()
    phone = re.sub(r'\D', '', payload.phone)
    if phone.startswith('91') and len(phone) == 12:
        phone = phone[2:]
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or not re.fullmatch(r'[6-9]\d{9}', phone):
        raise HTTPException(400, 'Enter a valid email and Indian mobile number')
    if not payload.name.strip() or any(not area.strip() or len(area) > 100 for area in payload.areas):
        raise HTTPException(400, 'Enter valid profile and locality details')
    client = staff_auth.service_client()
    try:
        if client.table('brokers').select('id').eq('email', email).limit(1).execute().data:
            raise HTTPException(409, 'An application or account already exists. Contact ApnaGhar admin.')
        if client.table('brokers').select('id').eq('phone', phone).limit(1).execute().data:
            raise HTTPException(409, 'An application or account already exists. Contact ApnaGhar admin.')
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Broker applications are unavailable. Ask admin to apply migration 007.')
    user_id = None
    try:
        # No email is sent here. Admin verifies the applicant before confirming access.
        user = client.auth.admin.create_user({'email': email, 'password': payload.password,
                                              'email_confirm': False}).user
        if not user:
            raise ValueError('Account was not created')
        user_id = str(user.id)
        row = {'id': 'broker_' + uuid.uuid4().hex, 'auth_user_id': user_id,
               'name': payload.name.strip(), 'email': email, 'phone': phone,
               'agency': payload.agency.strip(), 'verification_reference': payload.verification_reference.strip(),
               'areas': list(dict.fromkeys(area.strip() for area in payload.areas)) or list(AREAS),
               'approval_status': 'pending', 'is_active': False}
        client.table('brokers').insert(row).execute()
    except Exception:
        if user_id:
            try:
                client.auth.admin.delete_user(user_id)
            except Exception:
                pass
        raise HTTPException(400, 'Could not submit application. Check your details or contact ApnaGhar admin.')
    return {'ok': True, 'status': 'pending', 'message': 'Application submitted. ApnaGhar admin must verify and approve your account before you can sign in.'}


@router.post('/broker/auth')
def broker_sign_in(payload: Credentials, request: Request, response: Response):
    staff_auth.rate_limit(request, 'broker-login')
    email = (payload.email or payload.username).strip().lower()
    try:
        rows = staff_auth.service_client().table('brokers').select('*').eq('email', email).limit(1).execute().data or []
    except Exception:
        raise HTTPException(503, 'Broker login is unavailable. Check migration 007.')
    if not rows or not rows[0].get('auth_user_id'):
        raise HTTPException(401, 'Invalid email or password')
    broker = rows[0]
    if broker.get('approval_status') != 'approved' or not broker.get('is_active'):
        raise HTTPException(403, 'Your broker account is not currently approved. Contact ApnaGhar admin.')
    try:
        result = staff_auth.auth_client().auth.sign_in_with_password({'email': email, 'password': payload.password})
        if not result.session or not result.user or str(result.user.id) != broker['auth_user_id']:
            raise ValueError('Account mismatch')
    except Exception:
        raise HTTPException(401, 'Invalid email or password')
    token = result.session.access_token
    set_session(response, token)
    return {'token': token, 'role': 'broker', 'broker': public_profile(broker)}


@router.get('/broker/me')
def broker_me():
    principal = current_staff.get()
    return {'role': principal.role, 'broker_id': principal.broker_id, 'name': principal.name,
            'email': principal.email, 'phone': principal.phone}


@router.post('/broker/logout')
@router.post('/admin/logout')
def logout(response: Response):
    response.delete_cookie(staff_auth.COOKIE_NAME)
    response.headers['Cache-Control'] = 'no-store'
    return {'ok': True}


@router.get('/admin/login', response_class=HTMLResponse)
async def admin_login_page():
    return HTMLResponse((TEMPLATES / 'admin_login.html').read_text(encoding='utf-8'))


@router.post('/admin/auth')
def admin_sign_in(payload: Credentials, request: Request, response: Response):
    staff_auth.rate_limit(request, 'admin-login')
    token = staff_auth.admin_sign_in(payload.username.strip(), payload.password)
    set_session(response, token)
    return {'token': token, 'role': 'admin'}


@router.get('/admin', response_class=HTMLResponse)
async def admin_page():
    staff_auth.require_admin()
    return HTMLResponse((TEMPLATES / 'admin_brokers.html').read_text(encoding='utf-8'))


@router.get('/admin/brokers')
def list_applications(status: str = ''):
    staff_auth.require_admin()
    if status and status not in {'pending', 'approved', 'rejected', 'suspended'}:
        raise HTTPException(400, 'Invalid account status')
    try:
        query = staff_auth.service_client().table('brokers').select('*').order('created_at', desc=True)
        if status:
            query = query.eq('approval_status', status)
        rows = query.limit(500).execute().data or []
        profiles = [{**public_profile(row), 'verification_reference': row.get('verification_reference'),
                     'has_account': bool(row.get('auth_user_id')), 'reviewed_by': row.get('reviewed_by')}
                    for row in rows]
    except Exception:
        raise HTTPException(503, 'Broker review is unavailable. Apply migration 007 in Supabase.')
    return {'brokers': profiles}


@router.post('/admin/brokers/{broker_id}/review')
def review_broker(broker_id: str, payload: BrokerReview):
    principal = staff_auth.require_admin()
    if payload.action not in {'approved', 'rejected', 'suspended'}:
        raise HTTPException(400, 'Invalid review action')
    client = staff_auth.service_client()
    rows = client.table('brokers').select('*').eq('id', broker_id).limit(1).execute().data or []
    if not rows or not rows[0].get('auth_user_id'):
        raise HTTPException(404, 'Broker account not found')
    try:
        if payload.action == 'approved':
            # Approval means the admin has checked identity/contact information.
            client.auth.admin.update_user_by_id(rows[0]['auth_user_id'], {'email_confirm': True})
        client.rpc('review_broker_application', {'target_broker_id': broker_id, 'next_status': payload.action,
            'reviewer_name': principal.name, 'review_note': payload.note.strip()}).execute()
    except Exception:
        raise HTTPException(503, 'Could not save broker review. Check Supabase setup and try again.')
    return {'ok': True, 'status': payload.action}
