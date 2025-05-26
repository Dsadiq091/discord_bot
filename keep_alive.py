# keep_alive.py
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "I'm alive"

def keep_alive():
    # Use port 8080 for Replit
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
