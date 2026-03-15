from flask import Blueprint
from app.routes import main, auth

def register_blueprints(app):
    """Register all blueprints with the app."""
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp, url_prefix='/auth')
