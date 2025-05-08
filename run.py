from flask import Flask
from flask_cors import CORS


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    CORS(app)

    from routes import main

    app.register_blueprint(main)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4200, debug=True)
