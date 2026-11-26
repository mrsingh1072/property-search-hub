"""Per-request staff identity and mandatory broker data ownership filters."""
from contextvars import ContextVar
from dataclasses import dataclass
from fastapi import HTTPException


@dataclass(frozen=True)
class StaffPrincipal:
    role: str
    broker_id: str | None = None
    user_id: str | None = None
    name: str = ''
    email: str = ''
    phone: str = ''


current_staff = ContextVar('apnaghar_staff', default=None)


class ScopedQuery:
    def __init__(self, query, table, principal, operation, client):
        self.query, self.table, self.principal = query, table, principal
        self.operation, self.client = operation, client

    def __getattr__(self, name):
        method = getattr(self.query, name)
        if not callable(method):
            raise HTTPException(403, 'Unsupported broker query')
        def chained(*args, **kwargs):
            return ScopedQuery(method(*args, **kwargs), self.table, self.principal, self.operation, self.client)
        return chained

    def execute(self):
        query = self.query
        if self.table in {'properties', 'leads', 'meetings'}:
            query = query.eq('broker_id', self.principal.broker_id)
        elif self.table == 'brokers':
            query = query.eq('id', self.principal.broker_id)
        elif self.table == 'broker_confirmations':
            phone = self.principal.phone[-10:]
            query = query.in_('broker_phone', [phone, '91' + phone, '+91' + phone])
        elif self.table == 'sessions':
            rows = self.client.table('leads').select('session_id').eq('broker_id', self.principal.broker_id).execute().data or []
            ids = [row['session_id'] for row in rows if row.get('session_id')]
            query = query.in_('session_id', ids or ['__no_assigned_session__'])
        else:
            raise HTTPException(403, 'This resource requires admin access')
        return query.execute()


class ScopedTable:
    def __init__(self, table, principal, client):
        self.table, self.principal, self.client = table, principal, client

    def _operation(self, operation, *args, **kwargs):
        if operation != 'select' and self.table not in {'properties', 'leads', 'meetings', 'sessions', 'broker_confirmations'}:
            raise HTTPException(403, 'Broker accounts cannot change approval or account records')
        if operation in {'insert', 'upsert', 'update'} and args:
            original = args[0]
            payloads = original if isinstance(original, list) else [original]
            for payload in payloads:
                if self.table in {'properties', 'leads', 'meetings'}:
                    if 'broker_id' in payload and payload['broker_id'] != self.principal.broker_id:
                        raise HTTPException(403, 'Cannot change listing or lead ownership')
                    if operation in {'insert', 'upsert'}:
                        payload['broker_id'] = self.principal.broker_id
                    if operation == 'upsert' and payload.get('id'):
                        existing = self.client.table(self.table).select('broker_id').eq('id', payload['id']).limit(1).execute().data or []
                        if existing and existing[0].get('broker_id') != self.principal.broker_id:
                            raise HTTPException(403, 'Cannot replace another broker listing')
                if self.table == 'properties' and isinstance(payload.get('data'), dict):
                    source = payload['data'].get('source_ids') or {}
                    if source.get('broker_id') not in {None, self.principal.broker_id}:
                        raise HTTPException(403, 'Cannot change listing contact ownership')
                if self.table == 'broker_confirmations' and operation in {'insert', 'upsert', 'update'}:
                    phone = str(payload.get('broker_phone', self.principal.phone))
                    if phone[-10:] != self.principal.phone[-10:]:
                        raise HTTPException(403, 'Cannot change confirmation ownership')
                if self.table == 'sessions' and operation in {'insert', 'upsert'}:
                    sid = payload.get('session_id')
                    rows = self.client.table('leads').select('id').eq('broker_id', self.principal.broker_id).eq('session_id', sid).limit(1).execute().data
                    if not rows:
                        raise HTTPException(403, 'Conversation is not assigned to this broker')
        query = getattr(self.client.table(self.table), operation)(*args, **kwargs)
        # Inserts are checked before execution; ownership filters apply to reads/updates/deletes.
        if operation in {'insert', 'upsert'}:
            return query
        return ScopedQuery(query, self.table, self.principal, operation, self.client)

    def select(self, *a, **k): return self._operation('select', *a, **k)
    def insert(self, *a, **k): return self._operation('insert', *a, **k)
    def upsert(self, *a, **k): return self._operation('upsert', *a, **k)
    def update(self, *a, **k): return self._operation('update', *a, **k)
    def delete(self, *a, **k): return self._operation('delete', *a, **k)


class ScopedClient:
    def __init__(self, client, principal):
        self.client, self.principal = client, principal

    def table(self, name):
        return ScopedTable(name, self.principal, self.client)

    @property
    def storage(self):
        return self.client.storage

    def rpc(self, name, params=None):
        if name == 'match_properties':
            return self.client.rpc(name, params or {})
        if name == 'mark_property_booked':
            rows = self.client.table('properties').select('id').eq('id', (params or {}).get('prop_id')).eq('broker_id', self.principal.broker_id).limit(1).execute().data
            if rows:
                return self.client.rpc(name, params)
        raise HTTPException(403, 'This operation requires admin access')


def approved_broker_channel(failure=False):
    """Apply the same ownership rules to verified broker messaging commands."""
    from functools import wraps
    def decorate(function):
        @wraps(function)
        def wrapped(phone, *args, **kwargs):
            from database.supabase_client import get_broker_by_phone
            broker = get_broker_by_phone(phone)
            if not broker or broker.get('approval_status') != 'approved' or not broker.get('is_active'):
                return failure
            principal = StaffPrincipal(role='broker', broker_id=broker['id'], name=broker['name'],
                                       email=broker.get('email') or '', phone=broker.get('phone') or '')
            handle = current_staff.set(principal)
            try:
                return function(phone, *args, **kwargs)
            finally:
                current_staff.reset(handle)
        return wrapped
    return decorate
