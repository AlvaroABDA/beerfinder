from functools import wraps
from flask import session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from . import data_access

_HASH_PREFIXES = ('pbkdf2:', 'scrypt:')


def hash_password(plain_password):
    return generate_password_hash(plain_password)


def verify_password(user, plain_password):
    stored = user.get('password', '')
    if stored.startswith(_HASH_PREFIXES):
        return check_password_hash(stored, plain_password)
    return stored == plain_password


def needs_rehash(user):
    return not user.get('password', '').startswith(_HASH_PREFIXES)


def login_user(user):
    session['user_id'] = user['id']
    session['role'] = 'ADMIN' if user.get('role') == 'ADMIN' else 'USER'
    session['username'] = user['username']
    session['email_verified'] = bool(user.get('email_verified'))


def logout_user():
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('username', None)
    session.pop('email_verified', None)


def current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return data_access.get_user_by_id(user_id)


def is_authenticated():
    return 'user_id' in session


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('routes.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated() or session.get('role') != 'ADMIN':
            return redirect(url_for('routes.login'))
        return f(*args, **kwargs)
    return decorated_function
