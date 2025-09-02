#!/usr/bin/env python3
"""
Excel MCP 服务器的完整 Python 客户端实现

使用方法:
1. 确保 Excel MCP 服务器正在运行: uvx excel-mcp-server streamable-http
2. 运行此脚本: python excel_mcp_client.py

作者根据 MCP 协议要求实现了正确的调用流程:
1. 发送 initialize 请求获取 session ID
2. 发送 notifications/initialized 通知
3. 调用具体的工具方法
"""

import requests
import json
from typing import Optional, Dict, Any, List


class ExcelMCPClient:
    """Excel MCP 服务器客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8017"):
        """
        初始化客户端
        
        Args:
            base_url: MCP 服务器基础 URL
        """
        self.base_url = base_url
        self.mcp_url = f"{base_url}/mcp"
        self.session_id: Optional[str] = None
        self.session = requests.Session()
        self._id_counter = 1

    def _get_next_id(self) -> int:
        """获取下一个请求 ID"""
        self._id_counter += 1
        return self._id_counter

    def connect(self) -> bool:
        """
        连接到 MCP 服务器并完成初始化流程
        
        Returns:
            bool: 是否成功连接
        """
        print("🔄 正在连接到 Excel MCP 服务器...")
        
        # 第一步：初始化会话
        if not self._initialize():
            return False
        
        # 第二步：发送 initialized 通知
        if not self._send_initialized():
            return False
        
        print("✅ 成功连接到 Excel MCP 服务器")
        return True

    def _initialize(self) -> bool:
        """发送初始化请求"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "python-excel-mcp-client",
                    "version": "1.0.0"
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json,text/event-stream"
        }

        try:
            response = self.session.post(self.mcp_url, json=payload, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ 初始化失败，状态码: {response.status_code}")
                return False
            
            # 获取 session ID
            session_id = response.headers.get('mcp-session-id')
            if not session_id:
                print("❌ 未获取到 session ID")
                return False
            
            self.session_id = session_id
            print(f"✅ 获取到 session ID: {session_id}")
            return True

        except Exception as e:
            print(f"❌ 初始化请求失败: {e}")
            return False

    def _send_initialized(self) -> bool:
        """发送 initialized 通知"""
        if not self.session_id:
            print("❌ 没有有效的 session ID")
            return False
        
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json,text/event-stream",
            "mcp-session-id": self.session_id
        }
        
        try:
            response = self.session.post(self.mcp_url, json=payload, headers=headers)
            # initialized 通知通常没有响应内容
            return True
            
        except Exception as e:
            print(f"❌ 发送 initialized 通知失败: {e}")
            return False

    def list_tools(self) -> Optional[Dict]:
        """
        列出所有可用的工具
        
        Returns:
            Dict: 包含工具列表的字典，如果失败返回 None
        """
        return self._call_method("tools/list", {})

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Any]:
        """
        调用指定的工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            Any: 工具返回结果，如果失败返回 None
        """
        params = {
            "name": tool_name,
            "arguments": arguments
        }

        result = self._call_method("tools/call", params)
        
        if result and "structuredContent" in result:
            return result["structuredContent"]["result"]
        elif result and "content" in result:
            # 处理返回内容
            content = result["content"]
            if isinstance(content, list) and len(content) > 0:
                return content[0].get("text", "")
            return content
        
        return result

    def _call_method(self, method: str, params: Dict[str, Any]) -> Optional[Dict]:
        """
        调用 MCP 方法
        
        Args:
            method: 方法名
            params: 参数
            
        Returns:
            Dict: 响应结果
        """
        if not self.session_id:
            print("❌ 没有有效的 session ID，请先调用 connect()")
            return None
        
        payload = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": method,
            "params": params
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json,text/event-stream",
            "mcp-session-id": self.session_id
        }
        
        try:
            response = self.session.post(self.mcp_url, json=payload, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ 方法调用失败，状态码: {response.status_code}")
                return None
            
            # 解析 SSE 响应
            response_text = response.text
            if response_text.startswith('event:'):
                lines = response_text.strip().split('\n')
                for line in lines:
                    if line.startswith('data:'):
                        try:
                            data = json.loads(line[5:].strip())
                            if 'result' in data:
                                return data['result']
                            elif 'error' in data:
                                print(f"❌ 服务器错误: {data['error']}")
                                return None
                        except json.JSONDecodeError:
                            pass
            
            return None
            
        except Exception as e:
            print(f"❌ 方法调用异常: {e}")
            return None

    # 便捷方法
    def read_excel_data(self, filepath: str, sheet_name: str, start_cell: str = "A1", 
                       end_cell: Optional[str] = None) -> Optional[str]:
        """
        读取 Excel 数据
        
        Args:
            filepath: Excel 文件路径
            sheet_name: 工作表名称
            start_cell: 起始单元格
            end_cell: 结束单元格（可选）
            
        Returns:
            str: JSON 格式的 Excel 数据
        """
        arguments = {
            "filepath": filepath,
            "sheet_name": sheet_name,
            "start_cell": start_cell
        }
        
        if end_cell:
            arguments["end_cell"] = end_cell
        
        return self.call_tool("read_data_from_excel", arguments)

    def write_excel_data(self, filepath: str, sheet_name: str, data: List[List], 
                        start_cell: str = "A1") -> Optional[str]:
        """
        写入 Excel 数据
        
        Args:
            filepath: Excel 文件路径
            sheet_name: 工作表名称
            data: 要写入的数据（二维列表）
            start_cell: 起始单元格
            
        Returns:
            str: 操作结果消息
        """
        arguments = {
            "filepath": filepath,
            "sheet_name": sheet_name,
            "data": data,
            "start_cell": start_cell
        }
        
        return self.call_tool("write_data_to_excel", arguments)

    def create_workbook(self, filepath: str) -> Optional[str]:
        """
        创建新的 Excel 工作簿
        
        Args:
            filepath: 文件路径
            
        Returns:
            str: 操作结果消息
        """
        return self.call_tool("create_workbook", {"filepath": filepath})

    def get_workbook_metadata(self, filepath: str, include_ranges: bool = False) -> Optional[str]:
        """
        获取工作簿元数据
        
        Args:
            filepath: Excel 文件路径
            include_ranges: 是否包含范围信息
            
        Returns:
            str: 工作簿元数据
        """
        arguments = {
            "filepath": filepath,
            "include_ranges": include_ranges
        }

        return self.call_tool("get_workbook_metadata", arguments)


def demo():
    """演示客户端使用"""
    # 创建客户端实例
    client = ExcelMCPClient()

    # 连接到服务器
    if not client.connect():
        print("❌ 无法连接到服务器")
        return
    
    print("\n" + "="*60)

    # 演示 1: 列出所有工具
    print("📋 获取可用工具列表...")
    tools = client.list_tools()
    if tools and isinstance(tools, dict) and "tools" in tools:
        print(f"✅ 找到 {len(tools['tools'])} 个工具:")
        for tool in tools["tools"][:3]:  # 只显示前3个
            print(f"   • {tool['name']}: {tool['description'][:60]}...")
    
    print("\n" + "="*60)

    # 演示 2: 读取 Excel 数据
    print("📊 读取 Excel 数据...")
    excel_data = client.read_excel_data(
        filepath="/Users/nashzhou/code/openhands/excel-mcp-server/small.xlsx",
        sheet_name="Sheet",
        start_cell="A1"
    )

    if excel_data:
        print("✅ 成功读取 Excel 数据:")
        try:
            # 尝试格式化 JSON 输出
            data = json.loads(excel_data)
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(excel_data)
    else:
        print("❌ 读取 Excel 数据失败")

    print("\n" + "="*60)

    # 演示 3: 获取工作簿元数据
    print("📈 获取工作簿元数据...")
    metadata = client.get_workbook_metadata(
        filepath="/Users/nashzhou/code/openhands/excel-mcp-server/small.xlsx"
    )

    if metadata:
        print("✅ 工作簿元数据:")
        print(metadata)
    else:
        print("❌ 获取工作簿元数据失败")


if __name__ == "__main__":
    demo()
