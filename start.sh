#!/bin/bash
# Start the Django ASGI server with Daphne.
# Uses the PORT env var provided by Render (defaults to 8000 locally).
exec daphne -b 0.0.0.0 -p ${PORT:-8000} config.asgi:application