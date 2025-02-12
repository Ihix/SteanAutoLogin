import os
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

# 建议：使用单例模式配置
_log_initialized = False

def setup_logger(name, log_dir='logs'):
    """设置日志记录器
    
    Args:
        name: 日志记录器名称
        log_dir: 日志存储目录
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    global _log_initialized
    if not _log_initialized:
        # 全局配置一次
        _log_initialized = True
        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)
        
        # 创建日志记录器
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)  # 改为 DEBUG 级别以获取更多信息
        
        # 日志格式
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 文件处理器 - 按日期命名
        log_file = os.path.join(log_dir, f'steam_switcher_{datetime.now().strftime("%Y%m%d")}.log')
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=30,  # 保留30天的日志
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
    
    return logging.getLogger(name) 