from flask import Blueprint, jsonify, request, render_template, Response, Flask
import requests
import os
from lib_version import VersionUtil
import time
from collections import defaultdict
from cachetools import TTLCache
import logging

main = Blueprint("main", __name__)
version_file = open("VERSION", "r")
app_version = version_file.read().strip()  # v1.0.17
version_file.close()

# Environment variables
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "4200")
MODEL_PORT = os.getenv("MODEL_PORT", "5050")
DNS = os.getenv("DNS", "localhost")
enable_colorful_feedback_btns = os.getenv("COLORFUL_BUTTONS", "true") == "true"
app_UI_version = "v1.0" if enable_colorful_feedback_btns else "v2.0"

count_reqs = 0
count_preds = 0
count_correct_preds = 0
count_incorrect_preds = 0
duration_pred_req = 0.0
latest_pred_duration = 0.0
latest_validation_duration = 0.0

# Histogram config
hist_buckets = [0.1, 1, 3, 5, 10]
hist_validation_pred_req = defaultdict(int)

# Cache to track start times and prediction validation duration
# by session_id (auto-expire after 30 min, can hold up to 20 sessions)
session_start_times = TTLCache(maxsize=20, ttl=1800)
validation_durations = TTLCache(maxsize=20, ttl=1800)


# ---
# summary: Render the frontend HTML page
# description: Fetches model version and renders the main HTML template.
# operationId: renderFrontend
# responses:
#   200:
#     description: Successfully rendered page
@main.route("/", methods=["GET"])
def index():
    try:
        model_service_url = f"http://{DNS}:{MODEL_PORT}/version"
        response = requests.get(model_service_url)
        response.raise_for_status()
        model_version = response.json().get("version", "Unknown")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching model version: {e}")
        model_version = "Unavailable"

    return render_template(
        "main.html",
        title="Team18 Frontend",
        enable_colorful_feedback_btns=enable_colorful_feedback_btns,
        app_version=app_version,
        model_service_version=model_version,
    )


# ---
# summary: Submit text input for sentiment prediction
# description: Forwards user input to the model-service and returns the predicted sentiment label.
# operationId: postUserInput
# parameters:
#   - name: text
#     in: body
#     description: Text input from the user
#     required: true
#     schema:
#       type: object
#       required:
#         - text
#       properties:
#         text:
#           type: string
# responses:
#   200:
#     description: Successfully received prediction
#     schema:
#       type: object
#       properties:
#         label:
#           type: string
#   400:
#     description: Missing text in request body
#   500:
#     description: Internal or model service error
@main.route("/userInput", methods=["POST"])
def user_input():
    try:
        global count_reqs, latest_pred_duration
        count_reqs += 1

        start_time = time.time()
        user_input = request.json.get("text")
        if not user_input:
            return jsonify({"error": "Missing 'text' in request body"}), 400

        session_id = request.cookies.get("sessionId")

        model_service_url = f"http://{DNS}:{MODEL_PORT}/predict"
        model_response = requests.post(model_service_url, json={"text": user_input})
        model_response.raise_for_status()

        model_data = model_response.json()
        predicted_number = model_data.get("prediction")
        predicted_label = "Positive" if predicted_number == 1 else "Negative"

        latest_pred_duration = time.time() - start_time
        if session_id:
            session_start_times[session_id] = time.time()

        return jsonify({"label": predicted_label})

    except requests.exceptions.RequestException as e:
        print(f"Error communicating with model-service: {e}")
        return jsonify({"error": "Model service failed"}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ---
# summary: Submit judgment for model prediction
# description: Accepts boolean user feedback indicating whether the prediction was correct.
# operationId: postJudgment
# parameters:
#   - name: isCorrect
#     in: body
#     description: Boolean indicating correctness of prediction
#     required: true
#     schema:
#       type: object
#       required:
#         - isCorrect
#       properties:
#         isCorrect:
#           type: boolean
# responses:
#   200:
#     description: Judgment recorded successfully
#   400:
#     description: Invalid judgment format
#   500:
#     description: Internal server error
@main.route("/judgment", methods=["POST"])
def judgment():
    try:
        global count_preds, count_correct_preds, count_incorrect_preds, latest_validation_duration

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
        start_time = session_start_times.get(session_id)
        if start_time is None:
            return (
                jsonify({"status": "error", "message": "Session expired or invalid."}),
                400,
            )

        now = time.time()
        duration = now - start_time
        validation_durations[session_id] = duration
        latest_validation_duration = duration

        for bucket in hist_buckets:
            if duration <= bucket:
                hist_validation_pred_req[bucket] += 1
                break
        hist_validation_pred_req["+Inf"] += 1

        if is_correct:
            count_correct_preds += 1
        else:
            count_incorrect_preds += 1
        count_preds += 1

        return jsonify(
            {
                "status": "success",
                "message": "Judgment received",
                "receivedJudgment": is_correct,
            }
        )

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ---
# summary: Expose application metrics
# description: Returns Prometheus-compatible metrics for prediction statistics and timing.
# operationId: getMetrics
# produces:
#   - text/plain
# responses:
#   200:
#     description: Plain-text Prometheus metrics
@main.route("/metrics", methods=["GET"])
def metrics():
    m = ""
    m += "# HELP count_reqs The number of requests that have been created for sentiment prediction of a review.\n"
    m += "# TYPE count_reqs counter\n"
    m += f'count_reqs{{version="{app_UI_version}"}} {count_reqs}\n\n'

    m += "# HELP count_preds The number of sentiment analysis predictions that have been created.\n"
    m += "# TYPE count_preds counter\n"
    m += f'count_preds{{version="{app_UI_version}"}} {count_preds}\n\n'

    m += "# HELP count_correct_preds The number of correct sentiment analysis predictions according to the user.\n"
    m += "# TYPE count_correct_preds counter\n"
    m += f'count_correct_preds{{version="{app_UI_version}"}} {count_correct_preds}\n\n'

    m += "# HELP count_incorrect_preds The number of incorrect sentiment analysis predictions according to the user.\n"
    m += "# TYPE count_incorrect_preds counter\n"
    m += f'count_incorrect_preds{{version="{app_UI_version}"}} {count_incorrect_preds}\n\n'

    m += "# HELP duration_pred_req How long in seconds it takes predict the sentiment of a review.\n"
    m += "# TYPE duration_pred_req gauge\n"
    m += f'duration_pred_req{{version="{app_UI_version}"}} {latest_pred_duration}\n\n'

    m += "# HELP duration_validation_req How long in seconds it takes the person to validate the sentiment of a review.\n"
    m += "# TYPE duration_validation_req gauge\n"
    m += f'duration_validation_req{{version="{app_UI_version}"}} {latest_validation_duration}\n\n'

    m += "# HELP hist_duration_pred_req Histogram of the duration of the prediction request.\n"
    m += "# TYPE hist_duration_pred_req histogram\n"
    cumulative = 0
    for bucket in hist_buckets:
        cumulative += hist_validation_pred_req[bucket]
        m += f'hist_duration_pred_req{{le="{bucket}", version="{app_UI_version}"}} {cumulative}\n'
    cumulative += hist_validation_pred_req["+Inf"]
    m += f'hist_duration_pred_req{{le="+Inf", version="{app_UI_version}"}} {cumulative}\n'

    print(m)
    return Response(m, mimetype="text/plain")
