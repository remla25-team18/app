from flask import Blueprint, jsonify, request, render_template
import requests
import os
from lib_version import VersionUtil

main = Blueprint("main", __name__)
app_version = VersionUtil.get_version()

# Environment variables
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "4200")
MODEL_PORT = os.getenv("MODEL_PORT", "5050")
DNS = os.getenv("DNS", "localhost")


@main.route("/", methods=["GET"])
def index():
    try:
        # Fetch the model version from the /version endpoint of the model-service
        model_service_url = f"http://{DNS}:{MODEL_PORT}/version"
        response = requests.get(model_service_url)
        response.raise_for_status()  # Raise an error for non-2xx responses

        # Extract the model version from the response
        model_version = response.json().get("version", "Unknown")
    except requests.exceptions.RequestException as e:
        # Handle errors from the model-service
        print(f"Error fetching model version: {e}")
        model_version = "Unavailable"

    return render_template(
        "main.html",
        title="Team18 Frontend",
        app_version=app_version,
        model_version=model_version,
    )


@main.route("/userInput", methods=["POST"])
def user_input():
    """
    Endpoint to receive user input and forward it to the model-service.
    """
    try:
        # Step 1: Extract user input from the request
        user_input = request.json.get("text")
        if not user_input:
            return jsonify({"error": "Missing 'text' in request body"}), 400

        # Step 2: Send request to model-service
        model_service_url = f"http://{DNS}:{MODEL_PORT}/predict"
        model_response = requests.post(model_service_url, json={"text": user_input})
        model_response.raise_for_status()  # Raise an error for non-2xx responses

        # Step 3: Extract the prediction and model version
        model_data = model_response.json()
        predicted_number = model_data.get("prediction")
        # model_version = model_data.get("version")

        # Map the prediction number to a label
        predicted_label = "Positive" if predicted_number == 1 else "Negative"

        # # For frontend test
        # predicted_label = "Positive"  # Placeholder for actual prediction
        # model_version = "v1.0"  # Placeholder for actual model version

        # Step 4: Send the label and model version back to the frontend
        return jsonify({"label": predicted_label})

    except requests.exceptions.RequestException as e:
        # Handle errors from the model-service
        print(f"Error communicating with model-service: {e}")
        return jsonify({"error": "Model service failed"}), 500
    except Exception as e:
        # Handle other errors
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@main.route("/judgment", methods=["POST"])
def judgment():
    """
    Endpoint to receive user feedback on the model's prediction.
    """
    try:
        # Step 1: Extract the 'isCorrect' field from the request
        is_correct = request.json.get("isCorrect")
        if not isinstance(is_correct, bool):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Invalid judgment format. Expected a boolean value in the 'isCorrect' property.",
                    }
                ),
                400,
            )

        # Step 2: Return a success response
        return jsonify(
            {
                "status": "success",
                "message": "Judgment received",
                "receivedJudgment": is_correct,
            }
        )

    except Exception as e:
        # Handle unexpected errors
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error"}), 500
