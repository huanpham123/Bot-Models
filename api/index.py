import os
from flask import Flask, render_template, request, session, jsonify
import requests
import json

# Tạo Flask app và chỉ định thư mục templates
app = Flask(__name__, template_folder="../templates")
app.secret_key = os.environ.get("SECRET_KEY", "default_secret_key")

# Lấy API key từ biến môi trường (không nên hard-code)
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise Exception("API_KEY is not set in environment variables")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Cấu hình các mô hình chatbot
MODELS = {
    "qwen": {
         "name": "Qwen Turbo",
         "api_model": "qwen/qwen-turbo",
         "extra_headers": {}
    },
    "deepseek_free": {
         "name": "DeepSeek R1",
         "api_model": "deepseek/deepseek-r1:free",
         "extra_headers": {}
    },
    "deepseek_hf": {
         "name": "DeepSeek R1 (HF)",
         "api_model": "deepseek-ai/DeepSeek-R1",
         "extra_headers": {}
    },
    "gemini": {
         "name": "Gemini Pro",
         "api_model": "google/gemini-2.0-pro-exp-02-05:free",
         "extra_headers": {
              "HTTP-Referer": os.environ.get("REFERER", "https://your-site.com"),
              "X-Title": os.environ.get("SITE_NAME", "YourSiteName")
         }
    },
    "nvidia_llama": {
         "name": "Nvidia Llama",
         "api_model": "nvidia/llama-3.1-nemotron-70b-instruct:free",
         "extra_headers": {}
    }
}

@app.route('/')
def index():
    # Nếu chưa chọn mô hình, đặt mặc định là Qwen Turbo
    if "model" not in session:
        session["model"] = "qwen"
    # Khởi tạo lịch sử hội thoại nếu chưa có
    if "history" not in session:
        session["history"] = []
    return render_template("index.html", models=MODELS, current_model=MODELS[session["model"]]["name"])

@app.route('/set_model', methods=['POST'])
def set_model():
    model = request.form.get("model")
    if model in MODELS:
        session["model"] = model
        session["history"] = []  # Xoá lịch sử khi chuyển mô hình
        return jsonify({"status": "success", "model": model, "model_name": MODELS[model]["name"]})
    return jsonify({"status": "error", "message": "Model not found"}), 400

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    history = session.get("history", [])
    history.append({"role": "user", "content": user_message})

    selected_model_key = session.get("model", "qwen")
    model_info = MODELS.get(selected_model_key)
    if not model_info:
        return jsonify({"error": "Invalid model selected"}), 400

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    headers.update(model_info.get("extra_headers", {}))
    
    payload = {
        "model": model_info["api_model"],
        "messages": history
    }
    
    response = requests.post(API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        # Nếu header không chứa 'application/json', trả về lỗi JSON
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            print("Response not JSON. Body:", response.text)
            return jsonify({
                "error": "Server did not return JSON",
                "details": response.text
            }), 500

        try:
            result = response.json()
        except json.JSONDecodeError:
            print("JSONDecodeError. Body:", response.text)
            return jsonify({
                "error": "Invalid JSON returned by API",
                "details": response.text
            }), 500

        reply = result.get("choices", [{}])[0].get("message", {}).get("content", "No reply.")
        history.append({"role": "assistant", "content": reply})
        session["history"] = history

        if selected_model_key in ["deepseek_free", "deepseek_hf"]:
            if "Final Answer:" in reply:
                reasoning, final_answer = reply.split("Final Answer:", 1)
                reply_data = {"reasoning": reasoning.strip(), "final_answer": final_answer.strip()}
            else:
                reply_data = {"final_answer": reply}
        else:
            reply_data = {"final_answer": reply}
            
        return jsonify(reply_data)
    else:
        print("API Error:", response.status_code, response.text)
        return jsonify({
            "error": "API error", 
            "status_code": response.status_code, 
            "details": response.text
        }), 500

if __name__ == '__main__':
    app.run()
