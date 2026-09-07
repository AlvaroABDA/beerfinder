from flask import Flask
from . import routes

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'replace-with-secure-key'
    app.register_blueprint(routes.bp)
    return app
