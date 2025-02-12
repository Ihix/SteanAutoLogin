import os
import psutil
import winreg
import time
import subprocess
import vdf
from src.utils.logger import setup_logger
from src.utils.error_codes import ErrorCode
from src.utils.exceptions import SteamError
import win32api
import win32process
import win32security
import win32con
import ctypes
from ctypes import wintypes, create_string_buffer, c_void_p, c_size_t
import pymem
import configparser
from datetime import datetime

logger = setup_logger('steam_manager')

class SteamManager:
    """Steam 管理类,处理所有 Steam 相关操作"""
    
    def __init__(self):
        self.steam_reg_path = r"Software\Valve\Steam"
        self.default_steam_path = r"C:\Program Files (x86)\Steam"
        self._steam_path = None
        self._vdf_cache = {}
        self._last_vdf_check = 0
        self.memory_offset = self._get_memory_offset()
    
    @property
    def steam_path(self):
        """获取 Steam 路径(带缓存)"""
        if not self._steam_path:
            self._steam_path = self._get_steam_path()
        return self._steam_path
    
    def _get_steam_path(self):
        """从多个位置尝试获取 Steam 路径"""
        # 先检查进程
        for proc in psutil.process_iter(['name', 'exe']):
            if proc.info['name'].lower() == 'steam.exe':
                return proc.info['exe']
        # 再检查注册表
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.steam_reg_path, 0, 
                               winreg.KEY_READ)
            path = winreg.QueryValueEx(key, "SteamExe")[0]
            winreg.CloseKey(key)
            if os.path.exists(path):
                return path
        except WindowsError:
            pass
            
        # 使用默认路径
        default_path = os.path.join(self.default_steam_path, 'Steam.exe')
        if os.path.exists(default_path):
            return default_path
            
        raise SteamError(
            ErrorCode.STEAM_NOT_FOUND,
            "未找到Steam客户端,请检查安装"
        )
    
    def kill_steam_processes(self, retries=3, delay=1):
        """结束所有Steam相关进程"""
        steam_processes = ['steam.exe', 'steamwebhelper.exe', 'steamservice.exe', 'steamloginui.exe']
        killed = []
        
        for _ in range(retries):
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    if proc.info['name'].lower() in steam_processes:
                        proc.kill()
                        killed.append(proc.info['name'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                
            if killed:
                logger.info(f"已结束Steam进程: {', '.join(killed)}")
                time.sleep(delay)
    
    def read_loginusers_vdf(self, force_refresh=False):
        """读取Steam登录用户配置(带缓存)"""
        current_time = time.time()
        
        # 使用缓存
        if not force_refresh and current_time - self._last_vdf_check < 2:
            return self._vdf_cache
            
        try:
            vdf_path = os.path.join(os.path.dirname(self.steam_path), 'config', 'loginusers.vdf')
            if not os.path.exists(vdf_path):
                raise SteamError(
                    ErrorCode.STEAM_CONFIG_ERROR,
                    f"未找到登录配置文件: {vdf_path}"
                )
                
            with open(vdf_path, 'r', encoding='utf-8') as f:
                data = vdf.load(f)
                self._vdf_cache = data.get('users', {})
                self._last_vdf_check = current_time
                return self._vdf_cache
                
        except Exception as e:
            raise SteamError(
                ErrorCode.STEAM_CONFIG_ERROR,
                f"读取登录配置失败: {str(e)}"
            )
    
    def check_steam_config(self):
        """检查Steam配置文件状态"""
        config_path = os.path.join(os.path.dirname(self.steam_path), 'config')
        
        if not os.access(config_path, os.W_OK):
            raise SteamError(
                ErrorCode.STEAM_CONFIG_ERROR,
                "Steam配置目录没有写入权限"
            )
            
        files = ['loginusers.vdf', 'config.vdf']
        for file in files:
            file_path = os.path.join(config_path, file)
            if not os.path.exists(file_path):
                raise SteamError(
                    ErrorCode.STEAM_CONFIG_ERROR,
                    f"配置文件不存在: {file}"
                )
            if not os.access(file_path, os.W_OK):
                raise SteamError(
                    ErrorCode.STEAM_CONFIG_ERROR,
                    f"配置文件没有写入权限: {file}"
                )
        return True
    
    def set_auto_login_user(self, username):
        """设置Steam自动登录用户"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.steam_reg_path, 0, 
                               winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "AutoLoginUser", 0, winreg.REG_SZ, username)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            raise SteamError(
                ErrorCode.STEAM_CONFIG_ERROR,
                f"设置自动登录失败: {str(e)}"
            )
    
    def launch_steam(self, username=None, password=None, remember_password=True):
        """启动Steam客户端
        
        Args:
            username: 可选,指定登录用户名
            password: 可选,指定登录密码
            remember_password: 是否记住密码
        """
        cmd = [self.steam_path]
        if username and password:
            cmd.extend(['-login', username, password])
            if remember_password:
                cmd.append('-remember_password')
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            )
            
            time.sleep(0.5)
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise SteamError(
                    ErrorCode.STEAM_LAUNCH_FAILED,
                    f"Steam启动失败: {stderr.decode()}"
                )
            
            return process
            
        except Exception as e:
            raise SteamError(
                ErrorCode.STEAM_LAUNCH_FAILED,
                f"启动Steam失败: {str(e)}"
            )
    
    def _get_memory_offset(self):
        """从配置文件读取内存偏移量"""
        try:
            config = configparser.ConfigParser()
            config.read('config/config.ini', encoding='utf-8')
            memory_addr = config.get('Steam', 'memory_addr', fallback='steamui.dll+CC0E31')
            
            # 解析格式 "steamui.dll+CC0E31"
            if '+' in memory_addr:
                _, offset = memory_addr.split('+')
                # 移除可能存在的空格并转换为整数
                return int(offset.strip(), 16)
            else:
                logger.warning(f"内存地址格式不正确: {memory_addr}，使用默认值")
                return 0xCC0E31
            
        except Exception as e:
            logger.error(f"读取内存偏移量配置失败: {str(e)}")
            return 0xCC0E31  # 使用默认值

    def monitor_steam_memory(self):
        """监控 steamui.dll 特定地址的内存内容"""
        try:
            pm = pymem.Pymem("steam.exe")
            dll = pymem.process.module_from_name(pm.process_handle, "steamui.dll")
            if not dll:
                return None
                
            base_address = dll.lpBaseOfDll
            target_address = base_address + self.memory_offset
            memory_bytes = pm.read_bytes(target_address - 20, 61)
            string_value = memory_bytes.decode('ascii', errors='replace')
            
            return string_value
            
        except Exception as e:
            logger.debug(f"读取内存失败: {str(e)}")
            return None

    def check_login_success(self, username, max_wait=10):
        """通过监控内存来判断登录状态"""
        logger.info(f"开始检查登录状态: {username}")
        start_time = time.time()
        check_interval = 0.5
        last_content = None

        while time.time() - start_time < max_wait:
            try:
                content = self.monitor_steam_memory()
                
                # 如果内容发生变化，记录日志
                if content != last_content:
                    logger.debug(f"内存内容: {content}")
                    last_content = content

                if content and username.lower() in content.lower():
                    logger.info(f"检测到登录成功: {username}")
                    return True

                time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"检查登录状态失败: {str(e)}")
                time.sleep(check_interval)

        logger.warning(f"等待登录超时: {username}")
        return False 