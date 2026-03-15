from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from sqlalchemy import text
from app.extensions import db

bp = Blueprint('main', __name__)


@bp.route('/')
@login_required
def index():
    """Dashboard home page."""
    return render_template('index.html', title='Dashboard')


@bp.route('/health')
def health():
    """Health check endpoint."""
    try:
        # Check database connection
        db.session.execute(text('SELECT 1'))
        db_status = 'connected'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'healthy' if db_status == 'connected' else 'unhealthy',
        'database': db_status,
        'version': '2.0.0'
    }), 200 if db_status == 'connected' else 503
