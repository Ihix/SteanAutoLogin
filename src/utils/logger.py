import os
import logging
import configparser
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
import colorlog

class ColoredFormatter(colorlog.ColoredFormatter):
    """自定义的彩色日志格式化器"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s %(log_color)s[%(levelname)8s]%(reset)s %(blue)s[%(name)s]%(reset)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            reset=True,
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING': 'yellow',
                'ERROR':   'red',
                'CRITICAL': 'red,bg_white',
            },
            secondary_log_colors={},
            style='%'
        )

def get_log_level(config_path='config/config.ini'):
    """从配置文件获取日志级别"""
    try:
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
        level = config.get('General', 'log_level', fallback='INFO').upper()
        return getattr(logging, level, logging.INFO)
    except Exception as e:
        print(f"读取日志级别配置失败: {str(e)}, 使用默认级别 INFO")
        return logging.INFO

def setup_logger(name, log_dir='logs'):
    """设置日志记录器
    
    Args:
        name: 日志记录器名称
        log_dir: 日志存储目录
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    # 获取配置的日志级别
    log_level = get_log_level()
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    
    # 清理现有的处理器，避免重复
    if logger.hasHandlers():
        logger.handlers.clear()
    
    logger.setLevel(log_level)
    logger.propagate = False  # 避免日志重复
    
    # 文件处理器 - 按日期命名
    log_file = os.path.join(log_dir, f'steam_switcher_{datetime.now().strftime("%Y%m%d")}.log')
    file_formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)8s] [%(name)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=30,  # 保留30天的日志
        encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(log_level)
    logger.addHandler(file_handler)
    
    # 控制台处理器（带颜色）
    console_handler = colorlog.StreamHandler()
    console_handler.setFormatter(ColoredFormatter())
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)
    
    return logger

# 创建一个用于测试的函数
def test_logger(name='test'):
    """测试日志记录器的各个级别"""
    logger = setup_logger(name)
    logger.debug('这是一条调试日志')
    logger.info('这是一条信息日志')
    logger.warning('这是一条警告日志')
    logger.error('这是一条错误日志')
    logger.critical('这是一条严重错误日志') 