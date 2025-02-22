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
        
        # Xử lý response không phải JSON
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            return jsonify({
                "error": f"API returned invalid JSON: {response.text[:200]}"
            }), 500

        if response.status_code != 200:
            error_msg = response_data.get("error", {}).get("message", response.text)
            return jsonify({"error": error_msg}), response.status_code

        reply = response_data["choices"][0]["message"]["content"]
        history.append({"role": "assistant", "content": reply})
        session["history"] = history

        # Xử lý định dạng DeepSeek đặc biệt
        reply_data = {"final_answer": reply}
        if model_key in ["deepseek_free", "deepseek_hf"]:
            if "Final Answer:" in reply:
                parts = reply.split("Final Answer:", 1)
                reply_data["reasoning"] = parts[0].strip()
                reply_data["final_answer"] = parts[1].strip() if len(parts) > 1 else reply
            else:
                reply_data["reasoning"] = ""
        
        return jsonify(reply_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
