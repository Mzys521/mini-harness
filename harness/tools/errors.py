class ToolRuntimeError(Exception):
    """ Tool 运行时异常(所有工具异常的基类) """

class ToolNotFoundError(ToolRuntimeError):
    """ Tool 不存在异常(注册表按名查找失败时抛出) """

class ToolPermissionError(ToolRuntimeError):
    """ Tool 权限异常(注意: 执行器目前直接返回 PERMISSION_DENIED 结果，未抛出本异常) """

class RetryableToolError(ToolRuntimeError):
    """ 明确允许重试的 Tool 错误(由执行器按 max_retries 重试) """
