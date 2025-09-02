import os
import logging
import subprocess
import json
import uuid
import time
from typing import Dict, Optional, List, Any
from threading import Lock
import asyncio
import signal
from fastapi import FastAPI, Request, Response, WebSocket, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
import tempfile

# 配置日志
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(ROOT_DIR, "excel-mcp-proxy.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger("excel-mcp-proxy")

# 子进程管理
class StdioSubprocessManager:
    def __init__(self, excel_files_path: str):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.process_locks: Dict[str, Lock] = {}
        self.last_activity: Dict[str, float] = {}
        self.excel_files_path = excel_files_path
        self.idle_timeout = 300  # 5分钟无活动后关闭子进程
        self._cleanup_task = None
    
    def start_cleanup_task(self):
        """启动定期清理任务"""
        async def cleanup_loop():
            while True:
                await asyncio.sleep(60)  # 每分钟检查一次
                self.cleanup_idle_processes()
        
        loop = asyncio.get_event_loop()
        self._cleanup_task = loop.create_task(cleanup_loop())
    
    def cleanup_idle_processes(self):
        """清理闲置的子进程"""
        current_time = time.time()
        for session_id, last_time in list(self.last_activity.items()):
            if current_time - last_time > self.idle_timeout:
                logger.info(f"Cleaning up idle process for session {session_id}")
                self.terminate_process(session_id)
    
    def get_or_create_process(self, session_id: str) -> subprocess.Popen:
        """获取现有进程或创建新进程"""
        if session_id in self.processes:
            # 更新最后活动时间
            self.last_activity[session_id] = time.time()
            return self.processes[session_id]
        
        # 创建新进程
        logger.info(f"Creating new stdio process for session {session_id}")
        
        # 确保环境变量中有Excel文件路径
        env = os.environ.copy()
        env["EXCEL_FILES_PATH"] = self.excel_files_path
        
        # 启动子进程
        process = subprocess.Popen(
            ["python", "-m", "excel_mcp", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            bufsize=0,  # 无缓冲
            universal_newlines=False  # 使用二进制模式
        )
        
        self.processes[session_id] = process
        self.process_locks[session_id] = Lock()
        self.last_activity[session_id] = time.time()
        
        return process
    
    def get_process_lock(self, session_id: str) -> Lock:
        """获取进程的锁"""
        if session_id not in self.process_locks:
            self.process_locks[session_id] = Lock()
        return self.process_locks[session_id]
    
    def terminate_process(self, session_id: str):
        """终止指定的子进程"""
        if session_id in self.processes:
            try:
                process = self.processes[session_id]
                # 尝试优雅关闭
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 如果超时，强制关闭
                    process.kill()
                
                logger.info(f"Terminated process for session {session_id}")
            except Exception as e:
                logger.error(f"Error terminating process for session {session_id}: {e}")
            
            # 清理资源
            self.processes.pop(session_id, None)
            self.process_locks.pop(session_id, None)
            self.last_activity.pop(session_id, None)
    
    def terminate_all(self):
        """终止所有子进程"""
        for session_id in list(self.processes.keys()):
            self.terminate_process(session_id)
        
        if self._cleanup_task:
            self._cleanup_task.cancel()

# FastAPI应用
app = FastAPI(title="Excel MCP Proxy Server")

# 创建临时目录用于存储Excel文件
def get_excel_files_path():
    """获取Excel文件存储路径"""
    excel_files_path = os.environ.get("EXCEL_FILES_PATH")
    if not excel_files_path:
        excel_files_path = os.path.join(tempfile.gettempdir(), "excel_mcp_files")
    
    os.makedirs(excel_files_path, exist_ok=True)
    return excel_files_path

# 创建子进程管理器
process_manager = StdioSubprocessManager(get_excel_files_path())

@app.on_event("startup")
async def startup_event():
    """启动时执行的事件"""
    process_manager.start_cleanup_task()
    logger.info(f"Excel MCP Proxy Server started. Excel files path: {process_manager.excel_files_path}")

@app.on_event("shutdown")
async def shutdown_event():
    """关闭时执行的事件"""
    process_manager.terminate_all()
    logger.info("Excel MCP Proxy Server shut down")

# 处理HTTP POST请求
@app.post("/{path:path}")
async def handle_request(request: Request, path: str):
    """处理HTTP POST请求并转发到stdio子进程"""
    # 从请求中获取会话ID或创建新的会话ID
    session_id = request.headers.get("X-Session-ID", str(uuid.uuid4()))
    
    # 读取请求体
    body = await request.body()
    
    # 获取或创建子进程
    process = process_manager.get_or_create_process(session_id)
    process_lock = process_manager.get_process_lock(session_id)
    
    try:
        # 获取锁以确保对同一进程的操作是线程安全的
        with process_lock:
            # 将请求发送到子进程
            process.stdin.write(body + b"\n")
            process.stdin.flush()
            
            # 从子进程读取响应
            response_line = process.stdout.readline()
            
            if not response_line:
                # 如果没有响应，可能子进程已终止
                process_manager.terminate_process(session_id)
                raise HTTPException(status_code=500, detail="Subprocess terminated unexpectedly")
            
            # 解析响应
            try:
                # 尝试解析JSON响应
                parsed_response = json.loads(response_line.decode("utf-8"))
                
                # 设置响应头，包括会话ID
                headers = {"X-Session-ID": session_id}
                
                # 返回响应
                return Response(
                    content=json.dumps(parsed_response).encode("utf-8"),
                    media_type="application/json",
                    headers=headers
                )
            except json.JSONDecodeError:
                # 如果不是有效的JSON，返回原始响应
                return Response(
                    content=response_line,
                    headers={"X-Session-ID": session_id}
                )
    except Exception as e:
        logger.error(f"Error processing request for session {session_id}: {e}")
        # 出现异常时终止进程
        process_manager.terminate_process(session_id)
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

# 处理WebSocket连接
@app.websocket("/ws/{path:path}")
async def websocket_endpoint(websocket: WebSocket, path: str):
    """处理WebSocket连接并转发到stdio子进程"""
    await websocket.accept()
    
    # 创建唯一的会话ID
    session_id = str(uuid.uuid4())
    
    # 获取或创建子进程
    process = process_manager.get_or_create_process(session_id)
    process_lock = process_manager.get_process_lock(session_id)
    
    try:
        # 创建异步任务来读取子进程输出
        async def read_subprocess_output():
            while True:
                # 注意：这里使用了阻塞读取，可能需要在实际部署时优化
                response_line = process.stdout.readline()
                if not response_line:
                    break
                
                # 更新最后活动时间
                process_manager.last_activity[session_id] = time.time()
                
                # 发送响应到WebSocket
                await websocket.send_bytes(response_line)
        
        # 创建任务
        read_task = asyncio.create_task(read_subprocess_output())
        
        # 处理从WebSocket接收的消息
        try:
            while True:
                # 接收WebSocket消息
                data = await websocket.receive_bytes()
                
                # 更新最后活动时间
                process_manager.last_activity[session_id] = time.time()
                
                # 获取锁以确保对同一进程的操作是线程安全的
                with process_lock:
                    # 将消息发送到子进程
                    process.stdin.write(data + b"\n")
                    process.stdin.flush()
        except Exception as e:
            logger.error(f"WebSocket error for session {session_id}: {e}")
        finally:
            # 取消读取任务
            read_task.cancel()
            try:
                await read_task
            except asyncio.CancelledError:
                pass
    finally:
        # 清理资源
        process_manager.terminate_process(session_id)

# 处理流式HTTP请求
@app.post("/stream/{path:path}")
async def handle_stream_request(request: Request, path: str):
    """处理流式HTTP请求并转发到stdio子进程"""
    # 从请求中获取会话ID或创建新的会话ID
    session_id = request.headers.get("X-Session-ID", str(uuid.uuid4()))
    
    # 读取请求体
    body = await request.body()
    
    # 获取或创建子进程
    process = process_manager.get_or_create_process(session_id)
    process_lock = process_manager.get_process_lock(session_id)
    
    # 定义生成器函数，用于流式返回响应
    async def response_generator():
        try:
            # 获取锁以确保对同一进程的操作是线程安全的
            with process_lock:
                # 将请求发送到子进程
                process.stdin.write(body + b"\n")
                process.stdin.flush()
                
                # 从子进程读取响应
                while True:
                    response_line = process.stdout.readline()
                    
                    if not response_line:
                        break
                    
                    # 更新最后活动时间
                    process_manager.last_activity[session_id] = time.time()
                    
                    # 返回响应行
                    yield response_line
        except Exception as e:
            logger.error(f"Error in stream request for session {session_id}: {e}")
            # 出现异常时终止进程
            process_manager.terminate_process(session_id)
            yield f"Error: {str(e)}".encode("utf-8")
    
    # 返回流式响应
    return StreamingResponse(
        response_generator(),
        media_type="application/jsonl",
        headers={"X-Session-ID": session_id}
    )

def run_proxy_server(host: str = "0.0.0.0", port: int = 8017):
    """运行Excel MCP代理服务器"""
    logger.info(f"Starting Excel MCP Proxy Server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
