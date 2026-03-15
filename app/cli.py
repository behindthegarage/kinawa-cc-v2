"""CLI commands for Kinawa CC v2."""
import click
from flask.cli import with_appcontext
from app.extensions import db
from app.models import User


def init_app_cli(app):
    """Register CLI commands with the app."""
    
    @app.cli.command('init-app')
    @with_appcontext
    def init_app():
        """Initialize the application - create tables and admin user."""
        # Create all tables
        db.create_all()
        click.echo('Database tables created.')
        
        # Create admin user if it doesn't exist
        admin_username = app.config.get('ADMIN_USERNAME', 'admin')
        admin_password = app.config.get('ADMIN_PASSWORD', 'kinawa2026')
        
        admin = User.query.filter_by(username=admin_username).first()
        if not admin:
            admin = User(
                username=admin_username,
                email='admin@clubkinawa.net'
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            click.echo(f'Created admin user: {admin_username}')
        else:
            click.echo(f'Admin user already exists: {admin_username}')
        
        click.echo('Application initialization complete.')
