from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import subprocess
import os
from .account_manager import AccountManager
import winreg
import psutil
import json
import time
import vdf  # 需要先 pip install vdf
import configparser
from src.utils.logger import setup_logger
from src.utils.error_codes import ErrorCode
from src.utils.exceptions import SteamSwitcherException, SteamError, AccountError, FileError
from functools import wraps
from src.steam_manager import SteamManager

api = Blueprint('api', __name__)
account_manager = AccountManager()
logger = setup_logger('api')
steam_manager = SteamManager()

# 添加装饰器定义
def handle_errors(f):
    """API错误处理装饰器"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except SteamSwitcherException as e:
            logger.error(f"业务错误: {str(e)}", exc_info=True)
            return jsonify({
                "status": "error",
                "code": e.error_code.code,
                "message": e.error_code.message,
                "detail": e.detail
            }), 400
        except Exception as e:
            logger.error(f"系统错误: {str(e)}", exc_info=True)
            return jsonify({
                "status": "error",
                "code": ErrorCode.UNKNOWN_ERROR.code,
                "message": ErrorCode.UNKNOWN_ERROR.message,
                "detail": str(e)
            }), 500
    return wrapper

@api.route('/accounts', methods=['GET'])
def get_accounts():
    """获取所有账户信息"""
    try:
        # 先加载账号
        account_manager.load_accounts()
        
        # 检查封禁状态并获取解封账号列表
        unbanned_accounts = account_manager.check_ban_status()
        
        # 检查VDF状态
        account_manager.check_vdf_accounts()
        
        response_data = {
            "accounts": account_manager.accounts,
            "unbanned": unbanned_accounts
        }
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"获取账号信息失败: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "获取账号信息失败"
        }), 500

@api.route('/accounts', methods=['POST'])
def add_account():
    """添加新账户"""
    data = request.json
    account = {
        'username': data['username'],
        'password': data['password'],
        'game_id': '',
        'status': '正常',
        'steam_id': '',
        'persona_name': '',
        'last_login': '',
        'can_quick_switch': False
    }
    account_manager.accounts.append(account)
    account_manager.save_accounts()
    return jsonify({"status": "success"})

@api.route('/accounts/<username>', methods=['DELETE'])
def delete_account(username):
    """删除账户"""
    account_manager.accounts = [a for a in account_manager.accounts if a['username'] != username]
    account_manager.save_accounts()
    return jsonify({"status": "success"})

@api.route('/accounts/<username>/ban', methods=['POST'])
def set_ban_time(username):
    """设置账户封禁时间"""
    try:
        data = request.json
        days = int(data['days'])
        
        # 计算封禁结束时间
        ban_end = datetime.now() + timedelta(days=days)
        ban_time = ban_end.strftime("%m-%d %H:%M")
        
        for account in account_manager.accounts:
            if account['username'] == username:
                account['ban_time'] = ban_time  # 存储封禁时间
                account['status'] = ban_time    # 显示封禁时间
                print(f"设置账号 {username} 的封禁时间为: {ban_time}")
                break
                
        account_manager.save_accounts()
        return jsonify({"status": "success"})
        
    except Exception as e:
        print(f"设置封禁时间失败: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "设置封禁时间失败"
        }), 500

@api.route('/accounts/<username>/game_id', methods=['PUT'])
def update_game_id(username):
    """更新账户的游戏ID"""
    data = request.json
    game_id = data.get('game_id', '')
    
    for account in account_manager.accounts:
        if account['username'] == username:
            account['game_id'] = game_id
            break
            
    account_manager.save_accounts()
    return jsonify({"status": "success"})

@api.route('/accounts/<username>', methods=['PUT'])
def update_account(username):
    """更新账户信息"""
    data = request.json
    
    for account in account_manager.accounts:
        if account['username'] == username:
            account['password'] = data['password']
            break
            
    account_manager.save_accounts()
    return jsonify({"status": "success"})

def get_steam_path():
    """获取Steam路径"""
    # 1. 从配置文件获取
    config = configparser.ConfigParser()
    config.read('config/config.ini', encoding='utf-8')
    steam_path = config.get('Steam', 'path', fallback='')
    if steam_path and os.path.exists(steam_path):
        return steam_path

    # 2. 从进程获取
    for proc in psutil.process_iter(['name', 'exe']):
        try:
            if proc.info['name'].lower() == 'steam.exe':
                return proc.info['exe']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 3. 从注册表获取
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")
        steam_path = os.path.join(winreg.QueryValueEx(key, "InstallPath")[0], "Steam.exe")
        if os.path.exists(steam_path):
            return steam_path
    except WindowsError:
        pass

    return None

def save_steam_path(path):
    """保存Steam路径到配置文件"""
    try:
        config = configparser.ConfigParser()
        config.read('config/config.ini', encoding='utf-8')
        if not config.has_section('Steam'):
            config.add_section('Steam')
        config.set('Steam', 'path', path)
        with open('config/config.ini', 'w', encoding='utf-8') as f:
            config.write(f)
        return True
    except Exception as e:
        print(f"保存Steam路径失败: {str(e)}")
        return False

@api.route('/steam/path', methods=['POST'])
def set_steam_path():
    """设置Steam路径"""
    data = request.json
    path = data.get('path')
    
    if not path or not os.path.exists(path):
        return jsonify({
            "status": "error",
            "message": "无效的Steam路径"
        }), 400
        
    if save_steam_path(path):
        return jsonify({"status": "success"})
    else:
        return jsonify({
            "status": "error",
            "message": "保存Steam路径失败"
        }), 500

def read_loginusers_vdf():
    """读取 Steam 登录用户信息"""
    try:
        steam_path = get_steam_path()
        if not steam_path:
            logger.error("未找到Steam路径")
            return None
            
        vdf_path = os.path.join(os.path.dirname(steam_path), 'config', 'loginusers.vdf')
        if not os.path.exists(vdf_path):
            logger.error(f"未找到登录用户配置文件: {vdf_path}")
            return None
            
        with open(vdf_path, 'r', encoding='utf-8') as f:
            data = vdf.load(f)
            users = data.get('users', {})
            # 打印VDF内容用于调试
            logger.debug(f"VDF文件内容: {json.dumps(users, indent=2)}")
            return users
    except Exception as e:
        logger.error(f"读取登录用户配置失败: {str(e)}")
        return None

def kill_steam():
    """结束Steam相关进程"""
    steam_processes = ['steam.exe', 'steamwebhelper.exe', 'steamservice.exe']
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() in steam_processes:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    # 等待所有Steam进程完全结束
    time.sleep(1)

def set_registry_value(key_path, name, value):
    """设置Steam注册表值"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"设置注册表失败: {str(e)}")
        return False

def get_registry_value(key_path, name):
    """获取Steam注册表值"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return value
    except WindowsError:
        return None

def check_login_status(username, max_wait=30):
    """检查登录状态"""
    try:
        # 使用VDF检查方式
        return steam_manager.check_login_success(username, max_wait)
    except Exception as e:
        logger.error(f"检查登录状态失败: {str(e)}")
        return False

@api.route('/login', methods=['POST'])
@handle_errors
def login_account():
    """处理账号登录请求"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    remember_password = data.get('remember_password', True)
    
    # 参数验证
    if not username or not password:
        raise SteamSwitcherException(
            ErrorCode.INVALID_PARAMS,
            "账号和密码不能为空"
        )
    
    # 账号验证
    account = next(
        (acc for acc in account_manager.accounts 
         if acc['username'] == username),
        None
    )
    if not account:
        raise AccountError(
            ErrorCode.ACCOUNT_NOT_FOUND,
            f"账号 {username} 不存在"
        )
    
    try:
        # 尝试快速切换
        if account.get('can_quick_switch'):
            if quick_switch_login(username):
                update_login_time(account)
                return jsonify({"status": "success", "refresh": True})
        
        # 使用密码登录
        if password_login(username, password, remember_password):
            update_login_time(account)
            return jsonify({"status": "success", "refresh": True})
            
        raise AccountError(
            ErrorCode.INVALID_PASSWORD,
            "登录失败,请检查密码"
        )
        
    except Exception as e:
        raise SteamError(
            ErrorCode.STEAM_LOGIN_FAILED,
            str(e)
        )

def quick_switch_login(username):
    """快速切换登录
    
    Args:
        username: 要登录的用户名
    
    Returns:
        bool: 是否登录成功
    """
    logger.info(f"尝试快速切换: {username}")
    
    # 检查配置
    steam_manager.check_steam_config()
    
    # 设置自动登录用户
    steam_manager.set_auto_login_user(username)
    
    # 结束Steam进程
    steam_manager.kill_steam_processes()
    
    # 启动Steam
    steam_manager.launch_steam()
    
    # 检查登录状态
    return check_login_status(username)

def password_login(username, password, remember_password=True):
    """使用密码登录
    
    Args:
        username: 用户名
        password: 密码
        remember_password: 是否记住密码
    
    Returns:
        bool: 是否登录成功
    """
    logger.info(f"尝试密码登录: {username}")
    
    # 结束现有Steam进程
    steam_manager.kill_steam_processes()
    
    # 启动Steam并登录
    steam_manager.launch_steam(
        username=username,
        password=password,
        remember_password=remember_password
    )
    
    # 检查登录状态
    return check_login_status(username)

def update_login_time(account):
    """更新账号登录时间"""
    account['last_login'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    account_manager.save_accounts()

@api.route('/api/save_accounts', methods=['POST'])
def save_accounts():
    """保存账号列表"""
    try:
        accounts = request.json
        account_manager.accounts = accounts
        account_manager.save_accounts()
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"保存账号列表失败: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "保存失败"
        }), 500 