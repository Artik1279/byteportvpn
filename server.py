import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.getenv('PORT', 5000))  # Render выдаёт PORT автоматически
    app.run(host='0.0.0.0', port=port)
