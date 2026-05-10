import os
import sys
import logging

# Add the token_server directory to the python path so its local imports work
token_server_path = os.path.join(os.path.dirname(__file__), 'token_server')
sys.path.append(token_server_path)

# Now we can import the app from server.py
from server import app

if __name__ == "__main__":
    # Get port from environment variable (Railway sets this automatically)
    port = int(os.environ.get("PORT", 8080))
    logging.info(f"Starting server on port {port}...")
    app.run(host="0.0.0.0", port=port)
