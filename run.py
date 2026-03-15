#!/usr/bin/env python3
"""
Kinawa Command Center v2 - Flask Application Runner

Usage:
    python run.py                    # Run with default config
    python run.py --config=dev       # Run with development config
    python run.py --config=prod      # Run with production config
    FLASK_ENV=development flask run  # Using Flask CLI
"""

import os
import sys

# Load environment variables from .env file early
from dotenv import load_dotenv
project_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_dir, '.env'))

# Add the project directory to the path
sys.path.insert(0, project_dir)

from app import create_app

def get_config_name():
    """Get config name from environment or use default."""
    config_map = {
        'dev': 'development',
        'development': 'development',
        'test': 'testing',
        'testing': 'testing',
        'prod': 'production',
        'production': 'production'
    }
    
    config_name = 'default'
    
    # Check command line args (only when running directly)
    if __name__ == '__main__':
        for arg in sys.argv[1:]:
            if arg.startswith('--config='):
                config_name = config_map.get(arg.split('=')[1], 'default')
    
    # Check environment variable (FLASK_ENV takes precedence)
    flask_env = os.environ.get('FLASK_ENV')
    if flask_env:
        config_name = config_map.get(flask_env, config_name)
    
    return config_name

def main():
    """Run the Flask application."""
    config_name = get_config_name()
    
    # Create and run the app
    app = create_app(config_name)
    
    # Get host and port from environment or use defaults
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = app.config.get('DEBUG', False)
    
    print(f"Starting Kinawa CC v2 on http://{host}:{port}")
    print(f"Config: {config_name}")
    print(f"Debug: {debug}")
    print(f"Press Ctrl+C to stop")
    
    app.run(host=host, port=port, debug=debug)

# Create app instance for Flask CLI (uses FLASK_ENV from .env)
config_name = get_config_name()
app = create_app(config_name)

if __name__ == '__main__':
    main()
