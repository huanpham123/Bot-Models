import os
from flask import Flask, render_template, request, session, jsonify
import requests
import json

app = Flask(__name__, template_folder="../templates")
app.secret_key = os.environ.get("SECRET_KEY", "default_secret_key")
app.config['SESSION_COOKIE_SAMESITE'] = "Lax"

API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise Exception("API_KEY is not set in environment variables")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

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
    session.setdefault("model", "qwen")
    session.setdefault("history", [])
    return render_template("index.html", 
                         models=MODELS,
                         current_model=MODELS[session["model"]]["name"])

@app.route('/set_model', methods=['POST'])
def set_model():
    model = request.form.get("model")
    if model in MODELS:
        session["model"] = model
        session["history"] = []
        return jsonify({
            "status": "success", 
            "model": model, 
            "model_name": MODELS[model]["name"]
        })
    return jsonify({"status": "error", "message": "Model not found"}), 400

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message")
        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        history = session.get("history", [])
        history.append({"role": "user", "content": user_message})

        model_key = session.get("model", "qwen")
        model_info = MODELS.get(model_key)
        if not model_info:
            return jsonify({"error": "Invalid model selected"}), 400

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            **model_info["extra_headers"]
        }
        payload = {
            "model": model_info["api_model"],
            "messages": history
        }

        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()

        result = response.json()
        reply = result["choices"][0]["message"]["content"]
        history.append({"role": "assistant", "content": reply})
        session["history"] = history

        # Xử lý định dạng đặc biệt cho DeepSeek
        if model_key in ["deepseek_free", "deepseek_hf"]:
            if "Final Answer:" in reply:
                reasoning, final = reply.split("Final Answer:", 1)
                reply_data = {
                    "reasoning": reasoning.strip(),
                    "final_answer": final.strip()
                }
            else:
                reply_data = {
                    "reasoning": "",
                    "final_answer": reply.strip()
                }
        else:
            reply_data = {
                "reasoning": "",
                "final_answer": reply
            }

        return jsonify(reply_data)

    except requests.exceptions.HTTPError as err:
        try:
            error_msg = response.json().get("error", {}).get("message", response.text)
        except:
            error_msg = f"{err}: {response.text[:200]}" if response else str(err)
        return jsonify({"error": error_msg}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
