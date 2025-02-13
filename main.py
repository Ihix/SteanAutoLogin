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
import configparser

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

class FlaskApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.setup_app()
        
    def setup_app(self):
        """配置 Flask 应用"""
        # 禁用默认日志
        logging.getLogger('werkzeug').disabled = True
        self.app.logger.disabled = True
        self.app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        self.app.logger.setLevel(logging.ERROR)
        
        # 注册蓝图
        self.app.register_blueprint(api, url_prefix='/api')
        
        # 注册路由
        self.register_routes()
        
        # 注册错误处理
        self.register_error_handlers()
    
    def register_routes(self):
        """注册所有路由"""
        @self.app.route('/')
        def index():
            return send_from_directory(os.path.join(BASE_DIR, 'assets'), 'index.html')
            
        @self.app.route('/assets/static/<path:path>')
        def serve_static(path):
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
            
        @self.app.route('/test')
        def test():
            logger.info("测试路由被访问")
            return "测试成功"
    
    def register_error_handlers(self):
        """注册错误处理器"""
        @self.app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Flask错误: {str(e)}", exc_info=True)
            return str(e), 500
            
    def run(self, host='127.0.0.1', port=5000):
        """运行 Flask 应用"""
        try:
            logger.info("Flask服务器正在启动...")
            self.app.run(host=host, port=port, debug=False, use_reloader=False)
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
    
    retry_interval = 0.5  # 初始重试间隔
    max_interval = 2.0    # 最大重试间隔
    
    while time.time() - start_time < timeout:
        try:
            import requests
            response = requests.get('http://127.0.0.1:5000/test')
            if response.status_code == 200:
                logger.info("Flask服务器已就绪")
                return True
        except requests.exceptions.RequestException as e:
            logger.debug(f"等待中... ({str(e)}) 下次重试间隔: {retry_interval}秒")
            time.sleep(retry_interval)
            # 指数增加重试间隔,但不超过最大值
            retry_interval = min(retry_interval * 2, max_interval)
            
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

class WebViewManager:
    def __init__(self):
        self.window = None
        
    def create_window(self, title, url, width=800, height=600):
        """创建 WebView 窗口"""
        try:
            logger.info("正在创建主窗口...")
            self.window = webview.create_window(
                title,
                url,
                width=width,
                height=height
            )
            logger.info("窗口创建成功")
            return self.window
        except Exception as e:
            logger.error(f"创建窗口失败: {str(e)}", exc_info=True)
            raise
            
    def start(self, debug=True):
        """启动 WebView"""
        try:
            logger.info("准备启动WebView...")
            # 从配置文件读取debug选项
            config = configparser.ConfigParser()
            config.read('config/config.ini', encoding='utf-8')
            enable_debug = config.getboolean('General', 'enable_webview_debug', fallback=False)
            
            logger.info(f"WebView debug模式: {'启用' if enable_debug else '禁用'}")
            webview.start(debug=enable_debug)
            logger.info("WebView已退出")
        except Exception as e:
            logger.error(f"启动WebView失败: {str(e)}", exc_info=True)
            raise
            
    def cleanup(self):
        """清理资源"""
        if self.window:
            try:
                self.window.destroy()
            except Exception as e:
                logger.error(f"关闭窗口失败: {str(e)}", exc_info=True)

def main():
    """主程序入口"""
    webview_manager = None
    try:
        # 设置日志
        setup_logging()
        logger.info("=== Steam Account Switcher 启动 ===")
        logger.info("正在初始化系统...")
        
        # 确保静态文件
        logger.info("检查静态文件...")
        if not ensure_static_files():
            logger.error("静态文件检查失败,程序无法继续运行")
            raise RuntimeError("静态文件检查失败")
        logger.info("静态文件检查完成")
        
        # 创建并启动 Flask 应用
        logger.info("正在启动Flask服务...")
        flask_app = FlaskApp()
        server_thread = threading.Thread(
            target=flask_app.run,
            kwargs={'host': '127.0.0.1', 'port': 5000}
        )
        server_thread.daemon = True
        server_thread.start()
        
        # 等待服务器就绪
        logger.info("等待Flask服务就绪...")
        if not wait_for_server(timeout=10):
            logger.error("Flask服务启动失败,程序无法继续运行")
            raise RuntimeError("Flask服务器启动失败")
        logger.info("Flask服务已就绪")
        
        # 创建并启动 WebView
        logger.info("正在创建主窗口...")
        webview_manager = WebViewManager()
        webview_manager.create_window(
            'Steam Account Switcher',
            'http://127.0.0.1:5000'
        )
        logger.info("正在启动WebView...")
        webview_manager.start()
        
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}", exc_info=True)
        logger.error(f"错误详情: {traceback.format_exc()}")
        if webview_manager:
            webview_manager.cleanup()
        sys.exit(1)

if __name__ == '__main__':
    main() 