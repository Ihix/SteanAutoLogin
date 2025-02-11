from enum import Enum

class ErrorCode(Enum):
    # 通用错误 1000-1999
    UNKNOWN_ERROR = (1000, "未知错误")
    INVALID_PARAMS = (1001, "无效的参数")
    
    # Steam相关错误 2000-2999 
    STEAM_NOT_FOUND = (2000, "未找到Steam客户端")
    STEAM_LAUNCH_FAILED = (2001, "Steam启动失败")
    STEAM_LOGIN_FAILED = (2002, "Steam登录失败")
    STEAM_CONFIG_ERROR = (2003, "Steam配置错误")
    STEAM_PROCESS_ERROR = (2004, "Steam进程操作失败")
    
    # 账号相关错误 3000-3999
    ACCOUNT_NOT_FOUND = (3000, "账号不存在")
    ACCOUNT_EXISTS = (3001, "账号已存在")
    INVALID_PASSWORD = (3002, "密码错误")
    ACCOUNT_BANNED = (3003, "账号已被封禁")
    
    # 文件操作错误 4000-4999
    FILE_NOT_FOUND = (4000, "文件不存在")
    FILE_ACCESS_DENIED = (4001, "文件访问被拒绝")
    FILE_SAVE_FAILED = (4002, "文件保存失败")
    
    def __init__(self, code, message):
        self.code = code
        self.message = message 