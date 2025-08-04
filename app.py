import os
from flask import Flask, send_from_directory, request, jsonify, Response
import requests
import json

app = Flask(__name__, static_folder='static')

# 配置信息
config = {
    "API_URL": "http://14.116.240.82:30080/api/v1/conversation",
    "API_KEY": "sk-e2706a82412705c0e90a26ba311da546",
    "APP_ID": "2abd7b98-b122-4d8e-a8c8-21ccdac60783"
}

@app.route('/')
def index():
    """提供根目录下的index.html文件"""
    return send_from_directory('.', 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """提供静态文件"""
    return send_from_directory('static', path)

@app.route('/chat', methods=['POST'])
def chat():
    """处理聊天请求，支持流式响应"""
    # 获取用户输入
    user_message = request.json.get('message')
    
    # 构建API请求
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['API_KEY']}"
    }
    
    data = {
        "app_id": config['APP_ID'],
        "stream": True,
        "query": user_message
    }
    
    # 使用流式处理
    def generate():
        try:
            # 发送请求并获取流式响应
            response = requests.post(
                config['API_URL'], 
                headers=headers, 
                json=data, 
                stream=True
            )
            
            # 检查响应状态
            if response.status_code != 200:
                yield f"data: {json.dumps({'error': f'API请求失败，状态码: {response.status_code}'})}\n\n"
                return
            
            # 处理SSE流
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8')
                        # 解析SSE格式
                        if line_str.startswith("data:"):
                            json_data = json.loads(line_str[6:])
                            message = json_data.get("answer", "")
                            # 发送到前端
                            yield f"data: {json.dumps({'message': message})}\n\n"
                    except json.JSONDecodeError:
                        # 跳过无法解析的行
                        continue
                    except Exception as e:
                        yield f"data: {json.dumps({'error': f'处理响应时出错: {str(e)}'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': f'请求API时出错: {str(e)}'})}\n\n"
        finally:
            # 发送结束信号
            yield 'data: {"end": true}\n\n'
    
    # 返回事件流响应
    return Response(generate(), mimetype='text/event-stream')

@app.route('/health')
def health_check():
    """健康检查端点"""
    return jsonify(status="OK", message="信息科AI助手服务正常运行")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)