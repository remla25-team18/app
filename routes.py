from flask import Blueprint, jsonify, request, render_template, Response, Flask
import requests
import os
from lib_version import VersionUtil
import time
from collections import defaultdict
# import prometheus_client import Counter, Histogram

main = Blueprint("main", __name__)
app_version = VersionUtil.get_version()

# Environment variables
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "4200")
MODEL_PORT = os.getenv("MODEL_PORT", "5050")
DNS = os.getenv("MODEL_SERVICE_URL", "localhost")

count_reqs = 0
count_preds = 0
count_correct_preds = 0
count_incorrect_preds = 0
duration_pred_req = 0.0
duration_validation_req = 0.0
start_val_time = 0.0
# Histogram config
hist_buckets = [0.1, 1, 3, 5, 10]
hist_validation_pred_req = defaultdict(int)


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
        model_service_version=model_version,
    )


@main.route("/userInput", methods=["POST"])
def user_input():
    """
    Endpoint to receive user input and forward it to the model-service.
    """
    try:
        global count_reqs
        global duration_pred_req
        global start_val_time

        count_reqs += 1
        duration_pred_req = 1

        start_dur_time = time.time()

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
        model_version = model_data.get("version")

        # Map the prediction number to a label
        predicted_label = "Positive" if predicted_number == 1 else "Negative"
        
        duration_pred_req = time.time() - start_dur_time
        start_val_time = time.time()
        
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
        global duration_validation_req
        global start_val_time
        global count_preds
        global count_correct_preds
        global count_incorrect_preds
        global hist_validation_pred_req

        if start_val_time != 0:
            duration_validation_req = time.time() - start_val_time
            for bucket in hist_buckets:
                if duration_validation_req <= bucket:
                    hist_validation_pred_req[bucket] += 1
                    break
            hist_validation_pred_req["+Inf"] += 1
            start_val_time = 0

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
        
        if is_correct:
            count_correct_preds += 1
        else:

         count_incorrect_preds += 1
        count_preds += 1

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


@main.route('/metrics', methods=['GET'])
def metrics():
    global count_reqs
    global count_preds
    global count_correct_preds
    global count_incorrect_preds
    global duration_pred_req
    global duration_validation_req
    global hist_validation_pred_req
    
    m = "# HELP count_reqs The number of requests that have been created for sentiment prediction of a review.\n"
    m += "# TYPE count_reqs counter\n"
    m += "count_reqs {}\n\n".format(count_reqs)

    m += "# HELP count_preds The number of sentiment analysis predictions that have been created.\n"
    m += "# TYPE count_preds counter\n"
    m += "count_preds {}\n\n".format(count_preds)

    m += "# HELP count_correct_preds The number of correct sentiment analysis predictions according to the user.\n"
    m += "# TYPE count_correct_preds counter\n"
    m += "count_correct_preds {}\n\n".format(count_correct_preds)

    m += "# HELP count_incorrect_preds The number of incorrect sentiment analysis predictions  according to the user.\n"
    m += "# TYPE count_incorrect_preds counter\n"
    m += "count_incorrect_preds {}\n\n".format(count_incorrect_preds)

    m += "# HELP duration_pred_req How long in seconds it takes predict the sentiment of a review.\n"
    m += "# TYPE duration_pred_req gauge\n"
    m += "duration_pred_req {}\n\n".format(duration_pred_req)

    m += "# HELP duration_validation_req How long in seconds it take the person to validate the sentiment of a review.\n"
    m += "# TYPE duration_validation_req gauge\n"
    m += "duration_validation_req {}\n\n".format(duration_validation_req)

    m += "# HELP hist_duration_pred_req Histogram of the duration of the prediction request.\n"
    m += "# TYPE hist_duration_pred_req histogram\n"
    cumulative = 0
    
    cumulative = 0
    for bucket in hist_buckets:
        cumulative += hist_validation_pred_req[bucket]
        m += f'hist_duration_pred_req{{le="{bucket}"}} {cumulative}\n'
        prev_bucket = bucket

    # Add +Inf bucket
    cumulative += hist_validation_pred_req["+Inf"]
    m += f'hist_duration_pred_req{{le="+Inf"}} {cumulative}\n'

    print(m)
  
    return Response(m, mimetype="text/plain")