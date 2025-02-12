from datetime import datetime
from typing import Optional, Any, Dict
from .error_codes import ErrorCode
import traceback

class SteamError(Exception):
    """Steam 相关异常基类"""
    
    def __init__(
        self,
        code: ErrorCode,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.code = code
        self.message = message or code.message
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.now()
        self.traceback = traceback.format_exc() if cause else None
        
        # 调用父类构造函数
        super().__init__(self.message)
    
    @property
    def error_dict(self) -> Dict[str, Any]:
        """将异常信息转换为字典格式"""
        return {
            'code': self.code.value,
            'category': self.code.category,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'cause': str(self.cause) if self.cause else None,
            'traceback': self.traceback
        }
    
    def add_detail(self, key: str, value: Any) -> 'SteamError':
        """添加详细信息"""
        self.details[key] = value
        return self
    
    def with_cause(self, cause: Exception) -> 'SteamError':
        """设置导致异常的原因"""
        self.cause = cause
        self.traceback = traceback.format_exc()
        return self
    
    def __str__(self) -> str:
        """格式化异常信息"""
        parts = [f"[{self.code.category}] {self.message} (代码: {self.code.value})"]
        if self.details:
            parts.append(f"详细信息: {self.details}")
        if self.cause:
            parts.append(f"原因: {str(self.cause)}")
        return " | ".join(parts)

class ConfigError(SteamError):
    """配置相关异常"""
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            ErrorCode.CONFIG_PARSE_ERROR,
            message,
            details,
            cause
        )

class AccountError(SteamError):
    """账户相关异常"""
    def __init__(
        self,
        code: ErrorCode,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        if not 1200 <= code.value < 1300:
            code = ErrorCode.ACCOUNT_DATA_ERROR
        super().__init__(code, message, details, cause)

class FileError(SteamError):
    """文件操作相关异常"""
    def __init__(
        self,
        message: str,
        path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        details = details or {}
        if path:
            details['path'] = path
            
        super().__init__(
            ErrorCode.FILE_NOT_FOUND,
            message,
            details,
            cause
        ) 