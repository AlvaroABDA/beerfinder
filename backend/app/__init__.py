import os
import secrets
from flask import Flask
from flask.json.provider import DefaultJSONProvider
from werkzeug.middleware.proxy_fix import ProxyFix

from .models import db
from . import data_access
from . import csrf
from . import security


class ModelAwareJSONProvider(DefaultJSONProvider):
    def default(self, o):
        if hasattr(o, 'to_dict'):
            return o.to_dict()
        return super().default(o)


def _load_or_create_secret_key():
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key

    key_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.secret_key')
    if os.path.exists(key_path):
        with open(key_path, 'r', encoding='utf-8') as f:
            key = f.read().strip()
            if key:
                return key

    key = secrets.token_hex(32)
    with open(key_path, 'w', encoding='utf-8') as f:
        f.write(key)
    return key


def create_app(test_config=None):
    app = Flask(__name__)
    app.json_provider_class = ModelAwareJSONProvider
    app.json = ModelAwareJSONProvider(app)

    is_prod = os.environ.get('APP_ENV') == 'production' or os.environ.get('FLASK_ENV') == 'production'

    app.config['SECRET_KEY'] = _load_or_create_secret_key()
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB máx por subida
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = is_prod

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'beerfinder.db')
        db_url = f"sqlite:///{db_path}"
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}

    if test_config:
        app.config.update(test_config)

    if is_prod or os.environ.get('TRUST_PROXY') == '1':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    if os.environ.get('SENTRY_DSN'):
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=os.environ['SENTRY_DSN'], traces_sample_rate=0.1)
        except ImportError:
            pass

    db.init_app(app)

    app.jinja_env.globals['is_active'] = data_access.is_active
    app.jinja_env.globals['csrf_token'] = csrf.get_csrf_token
    app.jinja_env.globals['resolve_media_url'] = data_access.resolve_media_url

    app.before_request(csrf.validate_csrf)
    app.after_request(security.apply_security_headers)

    from . import routes
    app.register_blueprint(routes.bp)
    from .beermatch import beermatch_bp
    app.register_blueprint(beermatch_bp)

    return app
