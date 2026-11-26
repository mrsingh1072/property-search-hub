"""Enforce staff identity and ownership before private routes run."""
import asyncio
import re
from urllib.parse import urlparse

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from api import staff_auth
from database.staff_scope import current_staff

PUBLIC = {'/broker/login', '/broker/apply', '/broker/auth', '/broker/logout',
          '/admin/login', '/admin/auth', '/admin/logout'}


def protected_path(path, method):
    if path in PUBLIC:
        return False
    return (path == '/broker' or path.startswith('/broker/') or path == '/admin' or path.startswith('/admin/')
            or path == '/upload' or path.startswith('/upload/') or path.startswith('/api/broker/')
            or path == '/meetings/upcoming' or path == '/cron/send-reminders'
            or (method not in {'GET', 'HEAD', 'OPTIONS'} and re.match(r'^/properties/[^/]+/images', path)))


def check_ownership(path, principal):
    if principal.role == 'admin':
        return
    match = re.match(r'^/(?:broker/)?properties/([^/]+)(?:/|$)', path)
    if not match:
        match = re.match(r'^/broker/(?:edit|images)/([^/]+)(?:/|$)', path)
    table = 'properties' if match else None
    if not match:
        match = re.match(r'^/broker/leads/([^/]+)(?:/|$)', path)
        table = 'leads' if match else None
    if not match:
        match = re.match(r'^/broker/meetings/([^/]+)/(?:confirm|decline|reschedule)$', path)
        table = 'meetings' if match else None
    if match:
        rows = (staff_auth.service_client().table(table).select('id')
                .eq('id', match.group(1)).eq('broker_id', principal.broker_id).limit(1).execute().data)
        if not rows:
            raise HTTPException(404, 'Resource not found')


class StaffAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path.rstrip('/') or '/'
        if not protected_path(path, request.method):
            return await call_next(request)
        try:
            header = request.headers.get('authorization', '')
            token = header[7:].strip() if header.lower().startswith('bearer ') else ''
            token = token or request.cookies.get(staff_auth.COOKIE_NAME) or request.query_params.get('token')
            if not token and request.method not in {'GET', 'HEAD', 'OPTIONS'}:
                # Cache before parsing so FastAPI can still read JSON and uploaded files.
                await request.body()
                if 'application/json' in request.headers.get('content-type', ''):
                    try:
                        body = await request.json()
                        token = body.get('token') if isinstance(body, dict) else None
                    except ValueError:
                        pass
                elif 'form' in request.headers.get('content-type', ''):
                    form = await request.form()
                    token = form.get('token')
                    await form.close()
            principal = await asyncio.to_thread(staff_auth.authenticate_token, token if isinstance(token, str) else None)
            if (path == '/admin' or path.startswith('/admin/') or path == '/cron/send-reminders') and principal.role != 'admin':
                raise HTTPException(403, 'ApnaGhar admin access required')
            if request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.cookies.get(staff_auth.COOKIE_NAME):
                origin = request.headers.get('origin')
                if origin and urlparse(origin).netloc != request.url.netloc:
                    raise HTTPException(403, 'Cross-origin staff request denied')
            await asyncio.to_thread(check_ownership, path, principal)
            handle = current_staff.set(principal)
            try:
                response = await call_next(request)
                response.headers["Cache-Control"] = "no-store"
                return response
            finally:
                current_staff.reset(handle)
        except HTTPException as exc:
            if exc.status_code == 401 and request.method == 'GET' and 'text/html' in request.headers.get('accept', ''):
                return RedirectResponse('/admin/login' if path.startswith('/admin') else '/broker/login', status_code=303)
            return JSONResponse({'detail': exc.detail}, status_code=exc.status_code)
        except Exception:
            return JSONResponse({'detail': 'Broker account services are unavailable. Check migration 007 and server logs.'}, status_code=503)
