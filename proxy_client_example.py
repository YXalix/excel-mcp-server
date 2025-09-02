import asyncio
import json
import uuid
import aiohttp
import sys
import argparse
from typing import Dict, Any, List, Optional

class ProxyExcelMCPClient:
    """用于连接Excel MCP代理服务器的客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8017/mcp", session_id: Optional[str] = None):
        """
        初始化客户端
        
        Args:
            base_url: 代理服务器的基础URL
            session_id: 会话ID，如果不提供则自动生成
        """
        self.base_url = base_url
        self.session_id = session_id or str(uuid.uuid4())
        self.request_id = 0
    
    async def call(self, method: str, **params) -> Dict[str, Any]:
        """
        调用MCP方法
        
        Args:
            method: MCP方法名
            **params: 方法参数
            
        Returns:
            MCP响应结果
        """
        self.request_id += 1
        
        # 构建请求
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params
        }
        
        # 准备请求头
        headers = {
            "Content-Type": "application/json",
            "X-Session-ID": self.session_id
        }
        
        # 发送请求
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, 
                                   json=request, 
                                   headers=headers) as response:
                
                # 检查响应状态
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Error {response.status}: {text}")
                
                # 解析响应
                result = await response.json()
                
                # 检查错误
                if "error" in result:
                    raise Exception(f"RPC Error: {result['error']}")
                
                return result["result"]
    
    async def create_workbook(self, filepath: str) -> str:
        """创建新的Excel工作簿"""
        return await self.call("create_workbook", filepath=filepath)
    
    async def create_worksheet(self, filepath: str, sheet_name: str) -> str:
        """在工作簿中创建新的工作表"""
        return await self.call("create_worksheet", filepath=filepath, sheet_name=sheet_name)
    
    async def write_data_to_excel(
        self, 
        filepath: str, 
        sheet_name: str, 
        data: List[List], 
        start_cell: str = "A1"
    ) -> str:
        """向Excel写入数据"""
        return await self.call(
            "write_data_to_excel",
            filepath=filepath,
            sheet_name=sheet_name,
            data=data,
            start_cell=start_cell
        )
    
    async def read_data_from_excel(
        self,
        filepath: str,
        sheet_name: str,
        start_cell: str = "A1",
        end_cell: Optional[str] = None,
        preview_only: bool = False
    ) -> str:
        """从Excel读取数据"""
        params = {
            "filepath": filepath,
            "sheet_name": sheet_name,
            "start_cell": start_cell,
            "preview_only": preview_only
        }
        
        if end_cell:
            params["end_cell"] = end_cell
            
        return await self.call("read_data_from_excel", **params)
    
    async def get_workbook_metadata(self, filepath: str, include_ranges: bool = False) -> str:
        """获取工作簿元数据"""
        return await self.call(
            "get_workbook_metadata",
            filepath=filepath,
            include_ranges=include_ranges
        )
    
    async def apply_formula(
        self,
        filepath: str,
        sheet_name: str,
        cell: str,
        formula: str
    ) -> str:
        """在单元格中应用公式"""
        return await self.call(
            "apply_formula",
            filepath=filepath,
            sheet_name=sheet_name,
            cell=cell,
            formula=formula
        )
    
    async def format_range(
        self,
        filepath: str,
        sheet_name: str,
        start_cell: str,
        end_cell: Optional[str] = None,
        **format_params
    ) -> str:
        """设置单元格区域的格式"""
        params = {
            "filepath": filepath,
            "sheet_name": sheet_name,
            "start_cell": start_cell,
            **format_params
        }
        
        if end_cell:
            params["end_cell"] = end_cell
            
        return await self.call("format_range", **params)
    
    async def create_chart(
        self,
        filepath: str,
        sheet_name: str,
        data_range: str,
        chart_type: str,
        target_cell: str,
        title: str = "",
        x_axis: str = "",
        y_axis: str = ""
    ) -> str:
        """创建图表"""
        return await self.call(
            "create_chart",
            filepath=filepath,
            sheet_name=sheet_name,
            data_range=data_range,
            chart_type=chart_type,
            target_cell=target_cell,
            title=title,
            x_axis=x_axis,
            y_axis=y_axis
        )
    
    # 可以根据需要添加更多的方法...

async def main():
    """主函数示例"""
    parser = argparse.ArgumentParser(description="Excel MCP代理客户端示例")
    parser.add_argument("--url", default="http://localhost:8017/mcp", help="代理服务器URL")
    parser.add_argument("--session", default=None, help="会话ID (可选)")
    parser.add_argument("--file", default="./example.xlsx", help="Excel文件路径")
    args = parser.parse_args()
    
    client = ProxyExcelMCPClient(base_url=args.url, session_id=args.session)
    
    print(f"使用会话ID: {client.session_id}")
    
    # 创建工作簿
    print("创建工作簿...")
    result = await client.create_workbook(args.file)
    print(f"结果: {result}")
    
    # 创建工作表
    print("\n创建工作表...")
    result = await client.create_worksheet(args.file, "数据")
    print(f"结果: {result}")
    
    # 写入数据
    print("\n写入数据...")
    data = [
        ["姓名", "年龄", "城市"],
        ["张三", 25, "北京"],
        ["李四", 30, "上海"],
        ["王五", 35, "广州"]
    ]
    result = await client.write_data_to_excel(args.file, "数据", data)
    print(f"结果: {result}")
    
    # 应用公式
    print("\n应用公式...")
    result = await client.apply_formula(args.file, "数据", "D2", "=B2*2")
    print(f"结果: {result}")
    
    result = await client.apply_formula(args.file, "数据", "D3", "=B3*2")
    print(f"结果: {result}")
    
    result = await client.apply_formula(args.file, "数据", "D4", "=B4*2")
    print(f"结果: {result}")
    
    # 设置格式
    print("\n设置格式...")
    result = await client.format_range(
        args.file, "数据", "A1", "D1",
        bold=True,
        bg_color="#CCCCCC"
    )
    print(f"结果: {result}")
    
    # 读取数据
    print("\n读取数据...")
    result = await client.read_data_from_excel(args.file, "数据")
    print(f"结果: {result}")
    
    # 获取工作簿元数据
    print("\n获取工作簿元数据...")
    result = await client.get_workbook_metadata(args.file, include_ranges=True)
    print(f"结果: {result}")
    
    print("\n完成演示!")

if __name__ == "__main__":
    asyncio.run(main())
