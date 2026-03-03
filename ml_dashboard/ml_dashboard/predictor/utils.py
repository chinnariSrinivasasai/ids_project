import os
import pickle
import numpy as np
import shap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from django.conf import settings
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, LSTM
from lime.lime_tabular import LimeTabularExplainer

# =====================================
# GLOBALS (Safe for Gunicorn Workers)
# =====================================

model = None
graph = None
explainer = None
background_data = None


# =====================================
# Get Assets Directory Safely
# =====================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_ASSETS_DIR = os.path.join(BASE_DIR, 'ml_assets')


# =====================================
# Load LSTM Model (Matches Training)
# =====================================

def get_model():
    global model, graph

    if model is None:
        model_path = os.path.join(ML_ASSETS_DIR, 'lstm_weights.hdf5')

        model = Sequential()
        model.add(LSTM(32, input_shape=(41, 1)))
        model.add(Dropout(0.3))
        model.add(Dense(32, activation='relu'))
        model.add(Dense(2, activation='softmax'))

        model.load_weights(model_path)

        # Capture TF graph (important for Gunicorn)
        graph = tf.compat.v1.get_default_graph()

    return model


# =====================================
# Prediction
# =====================================

def make_prediction(input_string):
    try:
        input_list = [float(x.strip()) for x in input_string.split(',')]

        if len(input_list) != 41:
            return "Expected 41 features", 0.0, None, None

        input_array = np.array(input_list).reshape(1, 41, 1)

        model_instance = get_model()

        global graph
        if graph is not None:
            with graph.as_default():
                prediction_prob = model_instance.predict(input_array, verbose=0)
        else:
            prediction_prob = model_instance.predict(input_array, verbose=0)

        predicted_class = np.argmax(prediction_prob, axis=1)[0]
        confidence = float(np.max(prediction_prob))

        result = "Attack Detected" if predicted_class == 1 else "Normal Traffic"

        shap_plot = generate_shap_plot(model_instance, input_array)
        lime_html = generate_lime_explanation(model_instance, input_array)

        return result, confidence, shap_plot, lime_html

    except Exception as e:
        return f"Error: {str(e)}", 0.0, None, None


# =====================================
# SHAP Explanation
# =====================================

def generate_shap_plot(model_instance, input_array):
    global explainer, background_data

    input_2d = input_array.reshape(1, -1)

    if background_data is None:
        background_data = np.random.rand(10, input_2d.shape[1])

    def model_wrapper(data):
        data_3d = data.reshape(data.shape[0], 41, 1)

        global graph
        if graph is not None:
            with graph.as_default():
                return model_instance.predict(data_3d, verbose=0)
        return model_instance.predict(data_3d, verbose=0)

    if explainer is None:
        explainer = shap.KernelExplainer(model_wrapper, background_data)

    shap_values = explainer.shap_values(input_2d)

    # Save inside STATIC_ROOT (works in production)
    static_dir = settings.STATIC_ROOT
    os.makedirs(static_dir, exist_ok=True)

    plot_path = os.path.join(static_dir, 'shap_plot.png')

    shap.summary_plot(shap_values, input_2d, show=False)
    plt.savefig(plot_path, bbox_inches='tight')
    plt.close()

    return 'shap_plot.png'


# =====================================
# LIME Explanation
# =====================================

def generate_lime_explanation(model_instance, input_array):

    input_2d = input_array.reshape(1, -1)

    background = np.random.rand(100, input_2d.shape[1])

    def model_wrapper(data):
        data_3d = data.reshape(data.shape[0], 41, 1)

        global graph
        if graph is not None:
            with graph.as_default():
                return model_instance.predict(data_3d, verbose=0)
        return model_instance.predict(data_3d, verbose=0)

    explainer = LimeTabularExplainer(
        background,
        mode='classification'
    )

    exp = explainer.explain_instance(
        input_2d[0],
        model_wrapper,
        num_features=10
    )

    static_dir = settings.STATIC_ROOT
    os.makedirs(static_dir, exist_ok=True)

    lime_path = os.path.join(static_dir, 'lime_explanation.html')
    exp.save_to_file(lime_path)

    return 'lime_explanation.html'


# =====================================
# Load Training History
# =====================================

def load_training_history():
    path = os.path.join(ML_ASSETS_DIR, 'lstm_history.pckl')

    if os.path.exists(path):
        with open(path, 'rb') as f:
            return pickle.load(f)

    return {}