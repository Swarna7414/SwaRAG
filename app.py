"""
SwaRAG - Hugging Face Spaces Entry Point
"""
import os
from api.api import app

# Hugging Face Spaces uses port 7860 by default
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(debug=False, host="0.0.0.0", port=port)
