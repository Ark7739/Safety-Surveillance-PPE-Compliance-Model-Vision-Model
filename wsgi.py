"""
WSGI entry point for production deployment.
Used by Gunicorn / uWSGI / any WSGI server.
"""
from app import app, socketio, init_detector

# Initialize the detector at import time
init_detector()

# This is what Gunicorn will use
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
