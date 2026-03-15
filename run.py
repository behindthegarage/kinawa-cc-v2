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

# Add the project directory to the path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

from app import create_app

def main():
    """Run the Flask application."""
    # Get config from command line or environment
    config_map = {
        'dev': 'development',
        'development': 'development',
        'test': 'testing',
        'testing': 'testing',
        'prod': 'production',
        'production': 'production'
    }
    
    config_name = 'default'
    
    # Check command line args
    for arg in sys.argv[1:]:
        if arg.startswith('--config='):
            config_name = config_map.get(arg.split('=')[1], 'default')
    
    # Check environment variable
    if 'FLASK_ENV' in os.environ:
        config_name = config_map.get(os.environ['FLASK_ENV'], config_name)
    
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

if __name__ == '__main__':
    main()
