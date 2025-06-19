from flask import Blueprint, jsonify, request, render_template, Response, Flask
import requests
import os
from lib_version import VersionUtil
import time
from collections import defaultdict

main = Blueprint("main", __name__)
app_version = VersionUtil.get_version()

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
duration_validation_req = 0.0
start_val_time = 0.0
# Histogram config
hist_buckets = [0.1, 1, 3, 5, 10]
hist_validation_pred_req = defaultdict(int)


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
        use_true_false_classes=use_true_false_classes,
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

        user_input = request.json.get("text")
        if not user_input:
            return jsonify({"error": "Missing 'text' in request body"}), 400

        model_service_url = f"http://{DNS}:{MODEL_PORT}/predict"
        model_response = requests.post(model_service_url, json={"text": user_input})
        model_response.raise_for_status()

        model_data = model_response.json()
        predicted_number = model_data.get("prediction")
        model_version = model_data.get("version")

        predicted_label = "Positive" if predicted_number == 1 else "Negative"

        duration_pred_req = time.time() - start_dur_time
        start_val_time = time.time()

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
    m += f'duration_validation_req{{version="{app_UI_version}"}} {duration_validation_req}\n\n'

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
