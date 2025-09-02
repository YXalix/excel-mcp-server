import subprocess
import time
import unittest
import requests
import json
import os
import uuid
import signal
import sys
import tempfile
import shutil

class TestProxyServer(unittest.TestCase):
    """测试Excel MCP代理服务器功能"""
    
    @classmethod
    def setUpClass(cls):
        """启动代理服务器"""
        # 创建临时目录用于存储Excel文件
        cls.temp_dir = tempfile.mkdtemp(prefix="excel_mcp_test_")
        
        # 设置环境变量
        env = os.environ.copy()
        env["EXCEL_FILES_PATH"] = cls.temp_dir
        env["FASTMCP_PORT"] = "8099"  # 使用不同的端口避免冲突
        
        # 启动代理服务器
        cls.server_process = subprocess.Popen(
            [sys.executable, "-m", "excel_mcp", "proxy"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待服务器启动
        time.sleep(5)
        
        # 服务器基础URL
        cls.base_url = "http://localhost:8099/mcp"
    
    @classmethod
    def tearDownClass(cls):
        """关闭代理服务器并清理临时文件"""
        # 终止服务器进程
        cls.server_process.terminate()
        try:
            cls.server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.server_process.kill()
        
        # 清理临时目录
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    def make_request(self, method, params, session_id=None):
        """发送请求到代理服务器"""
        # 构建请求
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        # 准备请求头
        headers = {"Content-Type": "application/json"}
        if session_id:
            headers["X-Session-ID"] = session_id
        
        # 发送请求
        response = requests.post(self.base_url, json=request, headers=headers)
        
        # 检查响应状态
        self.assertEqual(response.status_code, 200)
        
        # 解析响应
        result = response.json()
        
        # 返回会话ID和结果
        return response.headers.get("X-Session-ID"), result
    
    def test_01_create_workbook(self):
        """测试创建工作簿功能"""
        # 生成唯一的文件名
        filename = f"test_{uuid.uuid4().hex}.xlsx"
        filepath = os.path.join(self.temp_dir, filename)
        
        # 发送请求
        session_id, result = self.make_request(
            "create_workbook",
            {"filepath": filepath}
        )
        
        # 验证结果
        self.assertIsNotNone(session_id)
        self.assertIn("result", result)
        self.assertNotIn("error", result)
    
    def test_02_session_persistence(self):
        """测试会话持久性"""
        # 生成唯一的文件名和会话ID
        filename = f"test_{uuid.uuid4().hex}.xlsx"
        filepath = os.path.join(self.temp_dir, filename)
        session_id = str(uuid.uuid4())
        
        # 创建工作簿
        _, result1 = self.make_request(
            "create_workbook",
            {"filepath": filepath},
            session_id
        )
        
        # 创建工作表
        _, result2 = self.make_request(
            "create_worksheet",
            {"filepath": filepath, "sheet_name": "Data"},
            session_id
        )
        
        # 写入数据
        _, result3 = self.make_request(
            "write_data_to_excel",
            {
                "filepath": filepath,
                "sheet_name": "Data",
                "data": [["Test"]]
            },
            session_id
        )
        
        # 验证结果
        self.assertNotIn("error", result1)
        self.assertNotIn("error", result2)
        self.assertNotIn("error", result3)
    
    def test_03_multiple_sessions(self):
        """测试多个会话"""
        # 生成唯一的文件名
        filename = f"test_{uuid.uuid4().hex}.xlsx"
        filepath = os.path.join(self.temp_dir, filename)
        
        # 创建两个会话
        session_id1 = str(uuid.uuid4())
        session_id2 = str(uuid.uuid4())
        
        # 在第一个会话中创建工作簿和工作表
        _, result1 = self.make_request(
            "create_workbook",
            {"filepath": filepath},
            session_id1
        )
        
        _, result2 = self.make_request(
            "create_worksheet",
            {"filepath": filepath, "sheet_name": "Session1"},
            session_id1
        )
        
        # 在第二个会话中添加另一个工作表
        _, result3 = self.make_request(
            "create_worksheet",
            {"filepath": filepath, "sheet_name": "Session2"},
            session_id2
        )
        
        # 获取工作簿元数据
        _, result4 = self.make_request(
            "get_workbook_metadata",
            {"filepath": filepath},
            session_id1
        )
        
        # 验证结果
        self.assertNotIn("error", result1)
        self.assertNotIn("error", result2)
        self.assertNotIn("error", result3)
        self.assertNotIn("error", result4)
        
        # 验证两个工作表都存在
        metadata = result4["result"]
        self.assertIn("Session1", metadata)
        self.assertIn("Session2", metadata)
    
    def test_04_error_handling(self):
        """测试错误处理"""
        # 尝试读取不存在的文件
        _, result = self.make_request(
            "read_data_from_excel",
            {
                "filepath": "non_existent.xlsx",
                "sheet_name": "Sheet1"
            }
        )
        
        # 验证错误响应
        self.assertIn("error", result)

if __name__ == "__main__":
    unittest.main()
