import os
from flask import Flask, render_template, request, session, jsonify
import requests
import json

app = Flask(__name__, template_folder="../templates")
app.secret_key = os.environ.get("SECRET_KEY", "default_secret_key_123!")
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Cấu hình API
API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY environment variable not set")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Danh sách model hỗ trợ
MODELS = {
    "qwen": {
        "name": "Qwen Turbo",
        "api_model": "qwen/qwen-turbo",
        "headers": {}
    },
    "deepseek_free": {
        "name": "DeepSeek R1 (Free)",
        "api_model": "deepseek/deepseek-r1:free",
        "headers": {}
    },
    "deepseek_hf": {
        "name": "DeepSeek R1 (HF)",
        "api_model": "deepseek-ai/DeepSeek-R1",
        "headers": {}
    },
    "gemini": {
        "name": "Gemini Pro",
        "api_model": "google/gemini-2.0-pro-exp-02-05:free",
        "headers": {
            "HTTP-Referer": os.environ.get("SITE_URL", "https://default-site.com"),
            "X-Title": os.environ.get("SITE_NAME", "My AI App")
        }
    },
    "nvidia_llama": {
        "name": "Nvidia Llama",
        "api_model": "nvidia/llama-3.1-nemotron-70b-instruct:free",
        "headers": {}
    }
}

@app.route('/')
def home():
    session.setdefault('model', 'qwen')
    session.setdefault('history', [])
    return render_template('index.html',
                         models=MODELS,
                         current_model=MODELS[session['model']]['name'])

@app.route('/set_model', methods=['POST'])
def set_model():
    model_key = request.form.get('model')
    if model_key in MODELS:
        session['model'] = model_key
        session['history'] = []
        return jsonify({
            'status': 'success',
            'model_name': MODELS[model_key]['name']
        })
    return jsonify({'status': 'error', 'message': 'Invalid model'}), 400

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({'error': 'Empty message'}), 400

        # Cập nhật lịch sử chat
        history = session.get('history', [])
        history.append({'role': 'user', 'content': user_message})
        
        # Lấy thông tin model
        model_info = MODELS.get(session.get('model', 'qwen'))
        if not model_info:
            return jsonify({'error': 'Model not found'}), 400

        # Chuẩn bị request
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            **model_info['headers']
        }
        payload = {
            'model': model_info['api_model'],
            'messages': history,
            'temperature': 0.7
        }

        # Gửi request đến OpenRouter
        response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        
        # Xử lý response
        response.raise_for_status()
        response_data = response.json()
        
        # Trích xuất reply
        reply = response_data['choices'][0]['message']['content']
        history.append({'role': 'assistant', 'content': reply})
        session['history'] = history

        # Xử lý định dạng DeepSeek
        result = {'final_answer': reply}
        if 'deepseek' in session['model']:
            if 'Final Answer:' in reply:
                parts = reply.split('Final Answer:', 1)
                result['reasoning'] = parts[0].strip()
                result['final_answer'] = parts[1].strip() if len(parts) > 1 else reply
            else:
                result['reasoning'] = ''
        
        return jsonify(result)

    except requests.exceptions.RequestException as e:
        error_msg = f"API Error: {str(e)}"
        if hasattr(e, 'response') and e.response:
            try:
                error_details = e.response.json().get('error', {}).get('message', e.response.text)
                error_msg += f" | Details: {error_details[:200]}"
            except json.JSONDecodeError:
                error_msg += f" | Response: {e.response.text[:200]}"
        return jsonify({'error': error_msg}), 500
    
    except Exception as e:
        return jsonify({'error': f"Internal error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
