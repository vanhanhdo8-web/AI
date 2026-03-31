import os
import random
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

AGENTS_DIR = 'agents'

def get_agent_content(agent_path):
    """Đọc nội dung file chuyên gia .md"""
    try:
        full_path = os.path.join(AGENTS_DIR, agent_path)
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        print(f"Lỗi đọc file: {e}")
    return "Bạn là một trợ lý AI hữu ích."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/agents', methods=['GET'])
def list_agents():
    agents_list = []
    if not os.path.exists(AGENTS_DIR):
        return jsonify({"success": False, "error": "Thư mục agents trống"}), 404
    for root, dirs, files in os.walk(AGENTS_DIR):
        for file in files:
            if file.endswith('.md'):
                rel_path = os.path.relpath(os.path.join(root, file), AGENTS_DIR)
                category = rel_path.split(os.sep)[0]
                agents_list.append({
                    "id": rel_path.replace(os.sep, '/'),
                    "name": file.replace('.md', '').replace('-', ' ').title(),
                    "path": rel_path,
                    "category": category
                })
    return jsonify({"success": True, "agents": agents_list})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    all_keys = data.get('api_keys', {}) # Lấy dictionary chứa tất cả keys từ Frontend
    agent_path = data.get('agent_path')
    user_prompt = data.get('user_prompt')
    
    system_instruction = get_agent_content(agent_path)

    # 1. Tách danh sách Gemini Keys (hỗ trợ nhập GEMINI_KEY_1, GEMINI_KEY_2...)
    gemini_keys = [v for k, v in all_keys.items() if "GEMINI" in k.upper()]
    
    # Xáo trộn danh sách key để dùng ngẫu nhiên, tránh tập trung vào 1 key duy nhất
    random.shuffle(gemini_keys)

    # 2. Vòng lặp thử từng Key Gemini cho đến khi thành công
    for current_key in gemini_keys:
        try:
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                system_instruction=system_instruction
            )
            response = model.generate_content(user_prompt)
            # Nếu thành công, trả về kết quả ngay
            return jsonify({
                "success": True, 
                "response": response.text, 
                "used_api": f"Gemini (Key: ...{current_key[-4:]})" 
            })
        except Exception as e:
            print(f"Key lỗi/Hết hạn: ...{current_key[-4:]} | Lỗi: {e}")
            continue # Thử sang Key tiếp theo trong danh sách

    # 3. Thử sang các API khác nếu có (Ví dụ Groq)
    groq_key = all_keys.get("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            completion = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return jsonify({"success": True, "response": completion.choices[0].message.content, "used_api": "Groq Failover"})
        except:
            pass

    # 4. Nếu tất cả đều "ngỏm"
    return jsonify({
        "success": False, 
        "error": "Tất cả các Key đều không hoạt động hoặc hết Token. Hãy thêm Key mới!"
    }), 400

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
