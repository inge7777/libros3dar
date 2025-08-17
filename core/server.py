from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from .env import get_paths

def create_app():
    p = get_paths()
    app = Flask(__name__, static_folder=str(p["PROJECT"]/"www"))
    CORS(app)

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.route("/", defaults={"path": "index.html"})
    @app.route("/<path:path>")
    def static_serve(path):
        root = p["PROJECT"]/ "www"
        return send_from_directory(root, path)

    return app
