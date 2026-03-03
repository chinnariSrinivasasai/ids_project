import os
import json
import numpy as np
from django.shortcuts import render
from django.conf import settings

from .utils import (
    load_training_history,
    make_prediction,
    get_model
)


# ===============================
# Fix numpy JSON serialization
# ===============================
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


# ===============================
# Dashboard View
# ===============================
def dashboard(request):

    prediction_result = None
    prediction_confidence = None
    shap_image = None
    lime_html = None
    input_values = ""
    error_message = None

    # ===============================
    # Handle POST (Prediction)
    # ===============================
    if request.method == 'POST':
        input_values = request.POST.get('features', '').strip()

        if input_values:
            try:
                prediction_result, prediction_confidence, shap_image, lime_html = make_prediction(input_values)
            except Exception as e:
                error_message = f"Prediction Error: {str(e)}"
        else:
            error_message = "Please enter feature values."

    # ===============================
    # Load Training History
    # ===============================
    history = load_training_history()
    history_json = json.dumps(history, cls=NumpyEncoder) if history else "{}"

    # ===============================
    # Model Status
    # ===============================
    model_loaded = False
    try:
        model = get_model()
        model_loaded = True if model else False
    except Exception:
        model_loaded = False

    models_status = {
        "LSTM Model": "Loaded" if model_loaded else "Not Loaded"
    }

    # ===============================
    # Context Data
    # ===============================
    context = {
        "history_json": history_json,
        "prediction_result": prediction_result,
        "prediction_confidence": prediction_confidence,
        "shap_image": shap_image,
        "lime_html": lime_html,
        "last_input": input_values,
        "error_message": error_message,
        "models_status": models_status
    }

    return render(request, "dashboard.html", context)