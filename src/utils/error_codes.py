from enum import Enum, auto

class ErrorCode(Enum):
    """Steam 相关错误码枚举"""
    
    # 通用错误 (1000-1099)
    UNKNOWN_ERROR = 1000
    INVALID_PARAMETER = 1001
    PERMISSION_DENIED = 1002
    FILE_NOT_FOUND = 1003
    
    # Steam 客户端错误 (1100-1199)
    STEAM_NOT_FOUND = 1100
    STEAM_LAUNCH_FAILED = 1101
    STEAM_ALREADY_RUNNING = 1102
    STEAM_LOGIN_FAILED = 1103
    STEAM_CONFIG_ERROR = 1104
    STEAM_MEMORY_ERROR = 1105
    
    # 账户相关错误 (1200-1299)
    ACCOUNT_NOT_FOUND = 1200
    ACCOUNT_ALREADY_EXISTS = 1201
    ACCOUNT_DATA_ERROR = 1202
    INVALID_CREDENTIALS = 1203
    
    # 配置相关错误 (1300-1399)
    CONFIG_NOT_FOUND = 1300
    CONFIG_PARSE_ERROR = 1301
    CONFIG_WRITE_ERROR = 1302
    
    @property
    def message(self) -> str:
        """获取错误码对应的默认错误消息"""
        return ERROR_MESSAGES.get(self, "未知错误")
    
    @property
    def category(self) -> str:
        """获取错误类别"""
        code = self.value
        if 1000 <= code < 1100:
            return "通用错误"
        elif 1100 <= code < 1200:
            return "Steam客户端错误"
        elif 1200 <= code < 1300:
            return "账户错误"
        elif 1300 <= code < 1400:
            return "配置错误"
        return "未知类别"

# 错误码对应的默认错误消息
ERROR_MESSAGES = {
    ErrorCode.UNKNOWN_ERROR: "未知错误",
    ErrorCode.INVALID_PARAMETER: "无效的参数",
    ErrorCode.PERMISSION_DENIED: "权限不足",
    ErrorCode.FILE_NOT_FOUND: "文件未找到",
    
    ErrorCode.STEAM_NOT_FOUND: "未找到Steam客户端",
    ErrorCode.STEAM_LAUNCH_FAILED: "Steam启动失败",
    ErrorCode.STEAM_ALREADY_RUNNING: "Steam已在运行",
    ErrorCode.STEAM_LOGIN_FAILED: "Steam登录失败",
    ErrorCode.STEAM_CONFIG_ERROR: "Steam配置错误",
    ErrorCode.STEAM_MEMORY_ERROR: "Steam内存读取错误",
    
    ErrorCode.ACCOUNT_NOT_FOUND: "账户不存在",
    ErrorCode.ACCOUNT_ALREADY_EXISTS: "账户已存在",
    ErrorCode.ACCOUNT_DATA_ERROR: "账户数据错误",
    ErrorCode.INVALID_CREDENTIALS: "无效的登录凭证",
    
    ErrorCode.CONFIG_NOT_FOUND: "配置文件不存在",
    ErrorCode.CONFIG_PARSE_ERROR: "配置文件解析错误",
    ErrorCode.CONFIG_WRITE_ERROR: "配置文件写入错误",
} 