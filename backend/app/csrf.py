import secrets
from flask import session, request, abort

def get_csrf_token():
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_hex(32)
        session['csrf_token'] = token
    return token

def validate_csrf():
    if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return
    submitted = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
    expected = session.get('csrf_token')
    if not expected or not submitted or not secrets.compare_digest(submitted, expected):
        abort(403)
