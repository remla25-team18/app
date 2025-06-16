from flask import Blueprint, jsonify, request, render_template, Response, Flask
import requests
import os
from lib_version import VersionUtil
import time
from collections import defaultdict
from cachetools import TTLCache
import logging

main = Blueprint("main", __name__)
app_version = VersionUtil.get_version()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "4200")
MODEL_PORT = os.getenv("MODEL_PORT", "5050")
DNS = os.getenv("DNS", "localhost")
use_true_false_classes = os.getenv("USE_TRUE_FALSE_CLASSES", "true") == "true"
app_UI_version = "v2.0" if use_true_false_classes else "v1.0"

count_reqs = 0
count_preds = 0
count_correct_preds = 0
count_incorrect_preds = 0
duration_pred_req = 0.0
# Histogram config
hist_buckets = [0.1, 1, 3, 5, 10]
hist_validation_pred_req = defaultdict(int)

# Cache to track start times and prediction validation duration 
# by session_id (auto-expire after 30 min, can hold up to 20 sessions)
session_start_times = TTLCache(maxsize=20, ttl=1800)
validation_durations = TTLCache(maxsize=20, ttl=1800)


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
        use_true_false_classes=use_true_false_classes,
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

        count_reqs += 1
        duration_pred_req = 1

        start_dur_time = time.time()

        # Step 1: Extract user input from the request
        user_input = request.json.get("text")
        if not user_input:
            return jsonify({"error": "Missing 'text' in request body"}), 400
        
        session_id = request.cookies.get("sessionId")

        # logger.info(f"Got session_id from cookie: {session_id}")
        # logger.info(f"All session_start_times keys: {list(session_start_times.keys())}")

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
        session_start_times[session_id] = time.time()

        # logger.info(f"Add entry: {list(session_start_times.keys())}")
        # logger.info(f"Start time: {session_start_times[session_id]}")
        
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
        global count_preds
        global count_correct_preds
        global count_incorrect_preds
        global hist_validation_pred_req

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
     
        session_id = request.cookies.get("sessionId")

        # logger.info(f"Confirm session_id from cookie: {session_id}")

        # Check if session start time exists
        start_time = session_start_times.get(session_id)
        if start_time is None:
            return jsonify({
                "status": "error",
                "message": "Session expired or invalid."
            }), 400
        
        now = time.time()
        validation_durations[session_id] = now - start_time
        # logger.info(f"now: {now}")
        # logger.info(f"start time: {start_time}")
        # logger.info(f"duration: {validation_durations[session_id]}")

        for bucket in hist_buckets:
            if validation_durations[session_id] <= bucket:
                hist_validation_pred_req[bucket] += 1
                break
        hist_validation_pred_req["+Inf"] += 1

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


@main.route("/metrics", methods=["GET"])
def metrics():
    global count_reqs
    global count_preds
    global count_correct_preds
    global count_incorrect_preds
    global duration_pred_req
    global hist_validation_pred_req

    session_id = request.cookies.get("sessionId")

    m = "# HELP count_reqs The number of requests that have been created for sentiment prediction of a review.\n"
    m += "# TYPE count_reqs counter\n"
    m += f'count_reqs{{version="{app_UI_version}"}} {count_reqs}\n\n'

    m += "# HELP count_preds The number of sentiment analysis predictions that have been created.\n"
    m += "# TYPE count_preds counter\n"
    m += f'count_preds{{version="{app_UI_version}"}} {count_preds}\n\n'

    m += "# HELP count_correct_preds The number of correct sentiment analysis predictions according to the user.\n"
    m += "# TYPE count_correct_preds counter\n"
    m += f'count_correct_preds{{version="{app_UI_version}"}} {count_correct_preds}\n\n'

    m += "# HELP count_incorrect_preds The number of incorrect sentiment analysis predictions  according to the user.\n"
    m += "# TYPE count_incorrect_preds counter\n"
    m += f'count_incorrect_preds{{version="{app_UI_version}"}} {count_incorrect_preds}\n\n'

    m += "# HELP duration_pred_req How long in seconds it takes predict the sentiment of a review.\n"
    m += "# TYPE duration_pred_req gauge\n"
    m += f'duration_pred_req{{version="{app_UI_version}"}} {duration_pred_req}\n\n'

    m += "# HELP duration_validation_req How long in seconds it take the person to validate the sentiment of a review.\n"
    m += "# TYPE duration_validation_req gauge\n"

    duration_val = validation_durations.get(session_id)
    if duration_val is not None:
        m += f'duration_validation_req{{version="{app_UI_version}"}} {duration_val}\n\n'
    else:
        m += f'duration_validation_req{{version="{app_UI_version}"}} 0.0\n\n'

    m += "# HELP hist_duration_pred_req Histogram of the duration of the prediction request.\n"
    m += "# TYPE hist_duration_pred_req histogram\n"
    cumulative = 0

    cumulative = 0
    for bucket in hist_buckets:
        cumulative += hist_validation_pred_req[bucket]
        m += f'hist_duration_pred_req{{le="{bucket}", version="{app_UI_version}"}} {cumulative}\n'
        prev_bucket = bucket

    # Add +Inf bucket
    cumulative += hist_validation_pred_req["+Inf"]
    m += f'hist_duration_pred_req{{le="+Inf", version="{app_UI_version}"}} {cumulative}\n'

    print(m)

    return Response(m, mimetype="text/plain")
