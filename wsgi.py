from app import app, socketio

# This is for Gunicorn to use as an entry point
# For Flask-SocketIO with eventlet worker, we need to export the socketio app
# When using Gunicorn, we must use: "gunicorn --worker-class eventlet -w 1 wsgi:application"

# Handle different versions of Flask-SocketIO
try:
    application = socketio.wsgi_app
except AttributeError:
    # For older versions of Flask-SocketIO
    application = app