from flask import session
from functools import wraps
from flask import redirect, url_for
from .data_access import load_users

def login_user(user):
    session['user_id'] = user['id']
    session['role'] = user['role']
    session['username'] = user['username']

def logout_user():
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('username', None)

def current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    users = load_users()
    for user in users:
        if user['id'] == user_id:
            return user
    return None

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
