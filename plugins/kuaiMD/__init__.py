from flask import Blueprint, Response, request  # 使用Flask的request对象
import requests
import threading
import time

from plugins.kuaiMD.kuaiMD import start_server

kuaiMD_bp = Blueprint('kuaiMD', __name__)

kuaiMD_port = 12001
server_started = False  # 添加服务器状态标志


def register_plugin(app):
    # 创建蓝图
    bp = Blueprint('kuaiMD_plugin', __name__)

    # 注册路由
    bp.register_blueprint(kuaiMD_bp)

    # 创建插件对象（包含元数据）
    plugin = type('Plugin', (), {
        'name': 'KuaiMD Plugin',
        'version': '0.0.1',
        'description': 'A plugin demonstrating plugin system capabilities',
        'author': '--kuaibote.com--',
        'blueprint': bp,
        'enabled': True,
        'config': app.config.get('HELLO_PLUGIN_CONFIG', {})
    })()

    # 添加自定义方法
    plugin.greet = lambda: f"Hello from {plugin.name}!"

    # 使用线程启动服务器
    global server_started
    if not server_started:
        server_thread = threading.Thread(target=start_server, kwargs={'port': kuaiMD_port})
        server_thread.daemon = True  # 设置为守护线程
        server_thread.start()

        # 等待服务器启动
        time.sleep(1)  # 给服务器一点启动时间
        server_started = True

    return plugin


@kuaiMD_bp.route('/kuaiMD', methods=['GET', 'POST', 'PUT', 'DELETE'])
@kuaiMD_bp.route('/kuaiMD/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def index(path=''):
    target_url = f'http://localhost:{kuaiMD_port}/{path}'

    try:
        # 根据请求方法转发请求
        if request.method == 'GET':
            response = requests.get(
                target_url,
                params=request.args,
                headers=dict(request.headers)
            )
        elif request.method == 'POST':
            response = requests.post(
                target_url,
                data=request.get_data(),
                headers=dict(request.headers),
                params=request.args
            )
        elif request.method == 'PUT':
            response = requests.put(
                target_url,
                data=request.get_data(),
                headers=dict(request.headers),
                params=request.args
            )
        elif request.method == 'DELETE':
            response = requests.delete(
                target_url,
                headers=dict(request.headers),
                params=request.args
            )
        else:
            return Response("Method not allowed", status=405)

        # 返回代理响应
        return Response(
            response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )

    except requests.exceptions.ConnectionError:
        return Response("Backend server is not responding", status=502)
    except Exception as e:
        return Response(f"Proxy error: {str(e)}", status=500)
