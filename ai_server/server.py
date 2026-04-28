from flask import Flask, request, jsonify
from sign_detector import detect_sign
import cv2
import numpy as np

app = Flask(__name__)

@app.route("/detect_sign", methods=["POST"])
def detect():
    file = request.files["image"]

    npimg = np.frombuffer(file.read(), np.uint8)
    frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    text = detect_sign(frame)
    return jsonify({
    "text": text
    })