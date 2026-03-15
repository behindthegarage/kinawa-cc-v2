from flask import Flask
from flask_migrate import Migrate
from config import config_by_name
from app.extensions import db, login_manager
from app.models import User, Staff, ScheduleAssignment, ChecklistItem, ChecklistCompletion, GFSReconciliation

def create_app(config_name='default'):
    """Application factory pattern."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config_by_name[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    Migrate(app, db)
    
    # Register blueprints
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.routes.schedule import bp as schedule_bp
    app.register_blueprint(schedule_bp)
    
    from app.routes.staff import bp as staff_bp
    app.register_blueprint(staff_bp)
    
    from app.routes.licensing import bp as licensing_bp
    app.register_blueprint(licensing_bp)
    
    from app.routes.gfs import bp as gfs_bp
    app.register_blueprint(gfs_bp)
    
    # Register context processors
    from datetime import datetime
    @app.context_processor
    def inject_now():
        return {'now': datetime.now}
    
    # Register CLI commands
    from app.cli import init_app_cli
    init_app_cli(app)
    
    return app
