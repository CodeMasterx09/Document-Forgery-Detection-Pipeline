# api_server.py
# Flask API Server - connects your Document Forgery Detection to n8n
# Run with: python api_server.py

from flask import Flask, request, jsonify
import tempfile
import os
import base64

# Import your existing pipeline from run_all.py
from run_all import analyze_document

app = Flask(__name__)


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Main endpoint - receives a document image and returns forgery analysis.

    Accepts two formats:
      1. Multipart form: send the image as a file field named 'file'
      2. JSON body:      send { "image_base64": "<base64 string>" }

    Returns the full JSON report from your pipeline.
    """

    tmp_path = None

    try:
        # --- Option 1: File upload (multipart form) ---
        if 'file' in request.files:
            file = request.files['file']
            ext = os.path.splitext(file.filename)[1] or '.jpg'
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name

        # --- Option 2: Base64 JSON body ---
        elif request.json and 'image_base64' in request.json:
            image_data = base64.b64decode(request.json['image_base64'])
            ext = request.json.get('file_extension', '.jpg')
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(image_data)
                tmp_path = tmp.name

        else:
            return jsonify({
                "error": "No image provided. Send a 'file' field (multipart) or 'image_base64' (JSON)."
            }), 400

        # Run your existing full pipeline
        report = analyze_document(tmp_path)
        return jsonify(report), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        # Always clean up the temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint - n8n can use this to verify the server is up."""
    return jsonify({"status": "running", "service": "Document Forgery Detection API"}), 200


if __name__ == '__main__':
    print("=" * 55)
    print("  Document Forgery Detection - Flask API Server")
    print("=" * 55)
    print("\n  Endpoints:")
    print("    POST http://localhost:5000/analyze   <- n8n calls this")
    print("    GET  http://localhost:5000/health    <- health check")
    print("\n  Make sure Flowise is also running on localhost:3000")
    print("=" * 55)
    app.run(host='0.0.0.0', port=5000, debug=True)
