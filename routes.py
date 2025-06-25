from flask import Blueprint, jsonify, request, render_template, Response
import requests
import os
import time
from collections import defaultdict

main = Blueprint("main", __name__)
version_file = open("VERSION", "r")
app_version = version_file.read().strip()
version_file.close()

# Environment configuration
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "4200")
MODEL_PORT = os.getenv("MODEL_PORT", "5050")
DNS = os.getenv("DNS", "localhost")
enable_colorful_feedback_btns = os.getenv("COLORFUL_BUTTONS", "true") == "true"
app_UI_version = "v1.0" if enable_colorful_feedback_btns else "v2.0"

# Metrics counters
count_reqs = 0
count_preds = 0
count_correct_preds = 0
count_incorrect_preds = 0
latest_pred_duration = 0.0
latest_validation_duration = 0.0
latest_prediction_time = 0.0

# Histogram configuration
hist_buckets = [0.1, 1, 3, 5, 10]
hist_validation_pred_req = defaultdict(int)


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


@main.route("/userInput", methods=["POST"])
def user_input():
    try:
        global count_reqs, latest_pred_duration, latest_prediction_time
        count_reqs += 1

        start_time = time.time()
        user_input = request.json.get("text")
        if not user_input:
            return jsonify({"error": "Missing 'text' in request body"}), 400

        model_service_url = f"http://{DNS}:{MODEL_PORT}/predict"
        model_response = requests.post(model_service_url, json={"text": user_input})
        model_response.raise_for_status()

        model_data = model_response.json()
        predicted_number = model_data.get("prediction")
        predicted_label = "Positive" if predicted_number == 1 else "Negative"

        latest_pred_duration = time.time() - start_time
        latest_prediction_time = time.time()

        return jsonify({"label": predicted_label})

    except requests.exceptions.RequestException as e:
        print(f"Error communicating with model-service: {e}")
        return jsonify({"error": "Model service failed"}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@main.route("/judgment", methods=["POST"])
def judgment():
    try:
        global count_preds, count_correct_preds, count_incorrect_preds
        global latest_validation_duration, hist_validation_pred_req, latest_prediction_time

        is_correct = request.json.get("isCorrect")
        if not isinstance(is_correct, bool):
            return (
                jsonify(
                    {"status": "error", "message": "Expected a boolean 'isCorrect'"}
                ),
                400,
            )

        duration = time.time() - latest_prediction_time
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


@main.route("/metrics", methods=["GET"])
def metrics():
    m = ""
    m += "# HELP count_reqs The number of user prediction requests.\n"
    m += "# TYPE count_reqs counter\n"
    m += f'count_reqs{{version="{app_UI_version}"}} {count_reqs}\n\n'

    m += "# HELP count_preds Number of user judgments received.\n"
    m += "# TYPE count_preds counter\n"
    m += f'count_preds{{version="{app_UI_version}"}} {count_preds}\n\n'

    m += "# HELP count_correct_preds Judgments marked correct by the user.\n"
    m += "# TYPE count_correct_preds counter\n"
    m += f'count_correct_preds{{version="{app_UI_version}"}} {count_correct_preds}\n\n'

    m += "# HELP count_incorrect_preds Judgments marked incorrect by the user.\n"
    m += "# TYPE count_incorrect_preds counter\n"
    m += f'count_incorrect_preds{{version="{app_UI_version}"}} {count_incorrect_preds}\n\n'

    m += "# HELP duration_pred_req Latest prediction duration in seconds.\n"
    m += "# TYPE duration_pred_req gauge\n"
    m += f'duration_pred_req{{version="{app_UI_version}"}} {latest_pred_duration}\n\n'

    m += "# HELP duration_validation_req Latest user judgment duration in seconds.\n"
    m += "# TYPE duration_validation_req gauge\n"
    m += f'duration_validation_req{{version="{app_UI_version}"}} {latest_validation_duration}\n\n'

    m += "# HELP hist_duration_pred_req Histogram of user judgment delay.\n"
    m += "# TYPE hist_duration_pred_req histogram\n"
    cumulative = 0
    for bucket in hist_buckets:
        cumulative += hist_validation_pred_req[bucket]
        m += f'hist_duration_pred_req{{le="{bucket}", version="{app_UI_version}"}} {cumulative}\n'
    cumulative += hist_validation_pred_req["+Inf"]
    m += f'hist_duration_pred_req{{le="+Inf", version="{app_UI_version}"}} {cumulative}\n'

    return Response(m, mimetype="text/plain")
