import os
import json
import uuid
import requests
import mimetypes
import base64
import logging
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)  # 解决跨域问题

# --- 配置 ---
class Config:
    GEMINI_PRO = 'sangfor-acip'
    # API 配置 - 使用提供的API信息
    API_URL = "http://14.116.240.82:30080/api/v1/conversation"
    API_KEY = "sk-e2706a82412705c0e90a26ba311da546"
    APP_ID = "2abd7b98-b122-4d8e-a8c8-21ccdac60783"

# --- 目录设置 ---
CONVERSATIONS_DIR = 'conversations'
TEMP_UPLOADS_DIR = 'temp_uploads'  # 用于临时存放上传的图片
if not os.path.exists(CONVERSATIONS_DIR):
    os.makedirs(CONVERSATIONS_DIR)
if not os.path.exists(TEMP_UPLOADS_DIR):
    os.makedirs(TEMP_UPLOADS_DIR)


# --- 辅助函数 ---
def get_conversation_title(history):
    """从第一条用户消息生成标题"""
    for message in history:
        if message['role'] == 'user' and message.get('content'):
            first_line = message['content'].split('\n')[0]
            return (first_line[:47] + '...') if len(first_line) > 50 else first_line
    return "New Chat"

def encode_image_to_base64(image_path):
    """将图片文件编码为 Base64 字符串"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error encoding image {image_path}: {e}")
        return None

def get_mime_type(image_path):
    """获取图片的 MIME 类型"""
    mime_type, _ = mimetypes.guess_type(image_path)
    return mime_type or 'application/octet-stream'


# --- 模型调用逻辑 ---
def call_api_stream(prompt):
    """调用指定的API，返回流式响应"""
    logging.info(f"Calling API with prompt: {prompt[:50]}...")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.API_KEY}"
    }
    
    data = {
        "app_id": Config.APP_ID,
        "stream": True,
        "query": prompt
    }
    
    try:
        with requests.post(Config.API_URL, headers=headers, json=data, stream=True) as response:
            if response.status_code != 200:
                yield f"data: {json.dumps({'error': f'API请求失败，状态码: {response.status_code}'})}\n\n"
                return

            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode("utf-8")
                        if line_str.startswith("data:"):
                            json_data = json.loads(line_str[6:])
                            answer_chunk = json_data.get("answer", "")
                            if answer_chunk:
                                yield f"data: {json.dumps({'answer': answer_chunk})}\n\n"
                    except json.JSONDecodeError:
                        yield f"data: {json.dumps({'error': f'无法解析的JSON数据: {line_str}'})}\n\n"
                    except Exception as e:
                        yield f"data: {json.dumps({'error': f'处理数据时出错: {str(e)}'})}\n\n"
        
        # 结束标记
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'error': f'请求处理失败: {str(e)}'})}\n\n"


# --- Flask 路由 ---
@app.route('/')
def index():
    """渲染主聊天界面"""
    return render_template('index.html')

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """列出所有保存的对话，按最后修改时间排序"""
    conversations = []
    if not os.path.exists(CONVERSATIONS_DIR):
        return jsonify([])

    try:
        file_paths = [
            os.path.join(CONVERSATIONS_DIR, f) 
            for f in os.listdir(CONVERSATIONS_DIR) 
            if f.endswith('.json')
        ]
        sorted_files = sorted(file_paths, key=os.path.getmtime, reverse=True)
        for filepath in sorted_files:
            try:
                filename = os.path.basename(filepath)
                conv_id = filename.split('.')[0]
                with open(filepath, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    title = get_conversation_title(history) 
                    conversations.append({'id': conv_id, 'title': title})
            except (json.JSONDecodeError, IOError, IndexError) as e:
                logging.warning(f"无法读取/解析 {filepath}: {e}")
    except Exception as e:
        logging.error(f"列出对话时出错: {e}")
        return jsonify({"error": "获取对话列表失败"}), 500
    return jsonify(conversations)

@app.route('/api/conversation/<conversation_id>', methods=['GET'])
def get_conversation_history(conversation_id):
    """获取单个对话的完整历史"""
    filepath = os.path.join(CONVERSATIONS_DIR, f"{conversation_id}.json")
    if not os.path.exists(filepath):
        return jsonify({'error': '未找到对话'}), 404
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            history = json.load(f)
            return jsonify(history)
    except Exception as e:
        return jsonify({'error': f"加载对话失败: {e}"}), 500

@app.route('/api/search/all', methods=['GET'])
def search_all_conversations():
    """在所有对话文件中搜索查询内容"""
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])
    all_results = []
    for filename in os.listdir(CONVERSATIONS_DIR):
        if not filename.endswith('.json'):
            continue
        filepath = os.path.join(CONVERSATIONS_DIR, filename)
        conv_id = filename.split('.')[0]
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                history = json.load(f)
            title = get_conversation_title(history)
            matches = []
            for message in history:
                content = message.get('content', '')
                if query in content.lower():
                    start_index = content.lower().find(query)
                    snippet_start = max(0, start_index - 30)
                    snippet_end = min(len(content), start_index + len(query) + 30)
                    snippet = "..." + content[snippet_start:snippet_end] + "..."
                    matches.append({'role': message['role'], 'snippet': snippet})
            if matches:
                all_results.append({
                    'id': conv_id,
                    'title': title,
                    'matches': matches
                })
        except Exception as e:
            logging.warning(f"搜索处理文件 {filename} 时出错: {e}")
    return jsonify(all_results)

@app.route('/api/chat', methods=['POST'])
def chat():
    """处理聊天请求，支持流式响应"""
    # 解析请求参数
    conversation_id = request.form.get('conversation_id')
    prompt = request.form.get('prompt', '')
    image_files = request.files.getlist('images')  # 获取所有上传的图片

    # 管理会话ID和历史记录
    is_new_conversation = False
    if not conversation_id or conversation_id == 'null':
        conversation_id = str(uuid.uuid4())
        is_new_conversation = True
        conversation_history = []
    else:
        filepath = os.path.join(CONVERSATIONS_DIR, f"{conversation_id}.json")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            conversation_history = []
            
    # 处理上传的图片
    saved_image_paths = []
    user_content_parts = [prompt]
    try:
        for image_file in image_files:
            if image_file and image_file.filename:
                filename = secure_filename(image_file.filename)
                filepath = os.path.join(TEMP_UPLOADS_DIR, f"{uuid.uuid4()}_{filename}")
                image_file.save(filepath)
                saved_image_paths.append(filepath)
                user_content_parts.append(f"[图片: {filename}]")

        # 构建用户消息并更新历史
        user_message_content = "\n".join(user_content_parts)
        user_message = {"role": "user", "content": user_message_content}
        conversation_history.append(user_message)
        
        # 保存用户消息
        conv_filepath = os.path.join(CONVERSATIONS_DIR, f"{conversation_id}.json")
        with open(conv_filepath, 'w', encoding='utf-8') as f:
            json.dump(conversation_history, f, indent=2, ensure_ascii=False)
        
        # 构建发送给API的提示
        # 由于API可能只需要最后一个问题，我们这里使用用户的最新输入
        # 如果需要上下文，可以改用完整历史
        formatted_prompt = prompt
            
        # 定义流式响应生成器
        def generate():
            full_response = ""
            # 从API获取流式响应
            for chunk in call_api_stream(formatted_prompt):
                yield chunk
                # 解析响应内容以累积完整回答
                if chunk.startswith("data:") and "[DONE]" not in chunk:
                    try:
                        data = json.loads(chunk[5:].strip())
                        if "answer" in data:
                            full_response += data["answer"]
                    except:
                        pass
            
            # 保存AI的完整响应到历史记录
            if full_response:
                ai_message = {"role": "assistant", "content": full_response}
                conversation_history.append(ai_message)
                with open(conv_filepath, 'w', encoding='utf-8') as f:
                    json.dump(conversation_history, f, indent=2, ensure_ascii=False)
        
        # 返回流式响应
        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        logging.error(f"聊天接口出错: {e}", exc_info=True)
        # 如果出错，从历史记录中移除最后添加的用户消息
        if conversation_history and conversation_history[-1]['role'] == 'user':
            conversation_history.pop()
        return jsonify({'error': f"发生意外错误: {str(e)}"}), 500

    finally:
        # 清理临时图片文件
        for path in saved_image_paths:
            try:
                os.remove(path)
                logging.info(f"已清理临时文件: {path}")
            except OSError as e:
                logging.error(f"清理文件 {path} 时出错: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8810, debug=False)
