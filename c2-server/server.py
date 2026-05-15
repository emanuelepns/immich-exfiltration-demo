from flask import Flask, send_from_directory
import os

app = Flask(__name__)

@app.route("/tomas.js")
def serve_script():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'tomas.js')

