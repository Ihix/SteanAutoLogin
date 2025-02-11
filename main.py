import webview
from flask import Flask, send_from_directory
from src.account_manager import AccountManager
from src.api import api
import os
import sys
import socket
import logging
import threading
import time
from src.utils.logger import setup_logger
import traceback

# 禁用 Flask 默认的日志输出
logging.getLogger('werkzeug').disabled = True

app = Flask(__name__)
# 关闭 Flask 的开发模式日志
app.logger.disabled = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # 禁用静态文件缓存

# 设置 Flask 的日志级别
app.logger.setLevel(logging.ERROR)  # 只显示错误级别的日志

app.register_blueprint(api, url_prefix='/api')

# 添加全局变量存储服务器线程
server_thread = None
window = None
flask_started = threading.Event()  # 添加事件标志

logger = setup_logger('main')

def setup_logging():
    """设置全局日志配置"""
    # 确保之前的处理器被移除
    logger.handlers.clear()
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)  # 明确指定输出到 stdout
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 验证日志级别
    logger.debug("日志级别测试: DEBUG")
    logger.info("日志级别测试: INFO")
    logger.warning("日志级别测试: WARNING")
    
    # 设置 webview 日志
    webview_logger = logging.getLogger('webview')
    webview_logger.handlers.clear()
    webview_logger.setLevel(logging.DEBUG)
    webview_logger.addHandler(console_handler)
    
    # 设置 Flask 日志
    flask_logger = logging.getLogger('flask')
    flask_logger.handlers.clear()
    flask_logger.setLevel(logging.DEBUG)
    flask_logger.addHandler(console_handler)
    
    # 设置 werkzeug 日志
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.handlers.clear()
    werkzeug_logger.setLevel(logging.DEBUG)
    werkzeug_logger.addHandler(console_handler)

def check_single_instance():
    """确保只运行一个实例"""
    try:
        # 创建 socket 并尝试绑定到特定端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 12345))  # 使用一个不常用的端口
        # 保持 socket 打开
        return sock
    except socket.error:
        return None

def get_base_path():
    """获取基础路径，兼容打包后的路径"""
    if getattr(sys, 'frozen', False):
        # 打包后的路径
        return sys._MEIPASS
    # 开发环境路径
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()

@app.route('/')
def index():
    file_path = os.path.join(BASE_DIR, 'assets', 'index.html')
    logger.info(f"请求首页, 文件路径: {file_path}")
    if not os.path.exists(file_path):
        logger.error(f"首页文件不存在: {file_path}")
        return "首页文件不存在", 404
    return send_from_directory(os.path.join(BASE_DIR, 'assets'), 'index.html')

@app.route('/assets/static/<path:path>')
def serve_static(path):
    file_path = os.path.join(BASE_DIR, 'assets', 'static', path)
    logger.info(f"请求静态文件: {file_path}")
    if not os.path.exists(file_path):
        logger.error(f"静态文件不存在: {file_path}")
        return f"文件不存在: {path}", 404
    
    # 添加正确的 MIME 类型
    mime_types = {
        '.js': 'application/javascript',
        '.css': 'text/css',
        '.ico': 'image/x-icon',
    }
    ext = os.path.splitext(path)[1]
    mimetype = mime_types.get(ext)
    
    return send_from_directory(
        os.path.join(BASE_DIR, 'assets', 'static'),
        path,
        mimetype=mimetype
    )

def start_server():
    """启动Flask服务器"""
    try:
        logger.info("Flask服务器正在启动...")
        # 添加异常处理中间件
        @app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Flask错误: {str(e)}", exc_info=True)
            return str(e), 500
        
        # 添加测试路由
        @app.route('/test')
        def test():
            logger.info("测试路由被访问")
            return "测试成功"
            
        app.run(port=5000, host='127.0.0.1', debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask服务器启动失败: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Flask服务器线程结束")
        flask_started.set()

def wait_for_server(timeout=10):
    """等待服务器启动"""
    start_time = time.time()
    logger.info("等待Flask服务器启动...")
    
    while time.time() - start_time < timeout:
        try:
            import requests
            response = requests.get('http://127.0.0.1:5000/test')
            if response.status_code == 200:
                logger.info("Flask服务器已就绪")
                return True
        except requests.exceptions.RequestException as e:
            logger.debug(f"等待中... ({str(e)})")
            time.sleep(0.5)
            
    logger.error(f"等待Flask服务器超时 ({timeout}秒)")
    return False

def ensure_static_files():
    """确保所有必需的静态文件存在"""
    files = {
        'libs/naive-ui.js': 'https://unpkg.com/naive-ui@2.34.4/dist/index.prod.js',
        'libs/vue.global.prod.js': 'https://unpkg.com/vue@3.2.47/dist/vue.global.prod.js'
    }
    
    try:
        # 确保目录存在
        static_dirs = ['libs', 'js', 'css']
        for dir_name in static_dirs:
            dir_path = os.path.join(BASE_DIR, 'assets', 'static', dir_name)
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"检查目录: {dir_path}")
        
        # 下载第三方库文件
        for local_path, url in files.items():
            full_path = os.path.join(BASE_DIR, 'assets', 'static', local_path)
            if not os.path.exists(full_path):
                logger.info(f"下载文件: {local_path} 从 {url}")
                import requests
                response = requests.get(url)
                response.raise_for_status()  # 检查下载是否成功
                with open(full_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"文件已保存: {full_path}")
            else:
                logger.info(f"文件已存在: {full_path}")
        
        # 验证所有必需文件
        all_required_files = [
            'libs/naive-ui.js',
            'libs/vue.global.prod.js',
            'js/app.js',
            'css/style.css'
        ]
        
        for file_path in all_required_files:
            full_path = os.path.join(BASE_DIR, 'assets', 'static', file_path)
            if not os.path.exists(full_path):
                logger.error(f"缺少必需文件: {full_path}")
                return False
            logger.info(f"验证文件存在: {full_path}")
            
        return True
        
    except Exception as e:
        logger.error(f"确保静态文件时出错: {str(e)}", exc_info=True)
        return False

if __name__ == '__main__':
    window = None
    try:
        # 设置日志
        setup_logging()
        logger.info("=== Steam Account Switcher 启动 ===")
        
        # ... 其他初始化代码 ...
        
        # 启动 Flask 服务器
        logger.info("正在启动Flask服务器...")
        server_thread = threading.Thread(target=start_server)
        server_thread.daemon = True
        server_thread.start()
        logger.info("Flask服务器线程已启动")
        
        # 等待服务器就绪
        if not wait_for_server(timeout=10):
            raise RuntimeError("Flask服务器启动失败")
        
        # 创建窗口
        logger.info("正在创建主窗口...")
        window = webview.create_window(
            'Steam Account Switcher',
            'http://127.0.0.1:5000',
            width=800,
            height=600
        )
        logger.info("窗口创建成功，准备启动WebView...")
        
        # 启动WebView
        webview.start(debug=False)
        logger.info("WebView已退出")
        
    except Exception as e:
        logger.error("程序出错", exc_info=True)
        if window:
            try:
                window.destroy()
            except:
                pass
        sys.exit(1) 