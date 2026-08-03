# Render native Python deployment (alternative to Docker).
# Uses Daphne (ASGI) because the app uses Channels for live chat WebSockets.
# Daphne serves both HTTP and WebSocket traffic on the same port.
#
# If you use this, set the build command in Render to:
#   pip install -r requirements.txt && python manage.py collectstatic --noinput
# and the start command to:
#   daphne -b 0.0.0.0 -p $PORT config.asgi:application
#
# Note: The Docker deployment (Dockerfile) is recommended — it runs migrations,
# seeds plans, creates the admin, and starts Daphne automatically.

web: daphne -b 0.0.0.0 -p $PORT config.asgi:application