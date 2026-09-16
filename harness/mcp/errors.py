class MCPIntegrationError(Exception):
    """MCP Integration（MCP集成）基础异常。"""

class MCPConfigurationError(MCPIntegrationError):
    """配置不合法。"""

class MCPConnectionError(MCPIntegrationError):
    """Transport（传输层）或连接失败。"""

class MCPDiscoveryError(MCPIntegrationError):
    """能力发现失败。"""

class MCPToolCallError(MCPIntegrationError):
    """远程 Tool（工具）执行失败。"""













