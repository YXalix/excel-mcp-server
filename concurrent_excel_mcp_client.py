#!/usr/bin/env python3
"""
并发 Excel MCP 服务器客户端实现

支持以下功能:
1. 并发连接多个客户端
2. 并发执行多个请求
3. 记录每个请求的时延
4. 统计分析并发性能

使用方法:
1. 确保 Excel MCP 服务器正在运行: uvx excel-mcp-server streamable-http
2. 运行此脚本: python concurrent_excel_mcp_client.py

作者: 基于原 excel_mcp_client.py 扩展
"""

import asyncio
import aiohttp
import json
import time
import statistics
import psutil
import os
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import concurrent.futures
import threading


@dataclass
class RequestMetrics:
    """请求指标数据"""
    request_id: str
    method: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error: Optional[str] = None


@dataclass
class SystemMetrics:
    """系统资源使用指标"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    io_read_bytes: int
    io_write_bytes: int
    io_read_count: int
    io_write_count: int


@dataclass 
class ResourceStats:
    """资源统计数据"""
    start_metrics: SystemMetrics
    end_metrics: SystemMetrics
    peak_cpu: float
    peak_memory: float
    total_io_read: int
    total_io_write: int


class SystemResourceMonitor:
    """系统资源监控器"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.monitoring = False
        self.metrics_history: List[SystemMetrics] = []
        self._monitor_task = None
        
    def get_current_metrics(self) -> SystemMetrics:
        """获取当前系统指标"""
        # CPU使用率
        cpu_percent = self.process.cpu_percent()
        
        # 内存使用情况
        memory_info = self.process.memory_info()
        memory_percent = self.process.memory_percent()
        memory_used_mb = memory_info.rss / 1024 / 1024
        
        # IO使用情况 (可能不在所有平台上可用)
        io_read_bytes = 0
        io_write_bytes = 0
        io_read_count = 0
        io_write_count = 0
        
        try:
            if hasattr(self.process, 'io_counters'):
                io_counters = getattr(self.process, 'io_counters')()
                io_read_bytes = io_counters.read_bytes
                io_write_bytes = io_counters.write_bytes
                io_read_count = io_counters.read_count
                io_write_count = io_counters.write_count
        except (AttributeError, OSError, PermissionError):
            # 如果IO计数器不可用，使用0
            pass
        
        return SystemMetrics(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_used_mb,
            io_read_bytes=io_read_bytes,
            io_write_bytes=io_write_bytes,
            io_read_count=io_read_count,
            io_write_count=io_write_count
        )
    
    async def start_monitoring(self, interval: float = 0.1):
        """开始监控系统资源"""
        self.monitoring = True
        self.metrics_history = []
        
        async def monitor_loop():
            while self.monitoring:
                try:
                    metrics = self.get_current_metrics()
                    self.metrics_history.append(metrics)
                    await asyncio.sleep(interval)
                except Exception as e:
                    print(f"监控过程中出错: {e}")
                    break
        
        self._monitor_task = asyncio.create_task(monitor_loop())
    
    async def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self._monitor_task:
            await self._monitor_task
    
    def get_resource_stats(self) -> Optional[ResourceStats]:
        """获取资源统计信息"""
        if len(self.metrics_history) < 2:
            return None
        
        start_metrics = self.metrics_history[0]
        end_metrics = self.metrics_history[-1]
        
        # 计算峰值
        peak_cpu = max(m.cpu_percent for m in self.metrics_history)
        peak_memory = max(m.memory_percent for m in self.metrics_history)
        
        # 计算总IO
        total_io_read = end_metrics.io_read_bytes - start_metrics.io_read_bytes
        total_io_write = end_metrics.io_write_bytes - start_metrics.io_write_bytes
        
        return ResourceStats(
            start_metrics=start_metrics,
            end_metrics=end_metrics,
            peak_cpu=peak_cpu,
            peak_memory=peak_memory,
            total_io_read=total_io_read,
            total_io_write=total_io_write
        )


class ConcurrentExcelMCPClient:
    """支持并发的 Excel MCP 服务器客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8000", client_id: Optional[str] = None):
        """
        初始化客户端
        
        Args:
            base_url: MCP 服务器基础 URL
            client_id: 客户端ID，用于区分不同的并发客户端
        """
        self.base_url = base_url
        self.mcp_url = f"{base_url}/mcp"
        self.client_id = client_id or f"client_{threading.current_thread().ident}"
        self.session_id: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self._id_counter = 1
        self.metrics: List[RequestMetrics] = []
        self.resource_monitor = SystemResourceMonitor()
        self._lock = threading.Lock()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()

    def _get_next_id(self) -> int:
        """获取下一个请求 ID"""
        with self._lock:
            self._id_counter += 1
            return self._id_counter

    def _record_metric(self, request_id: str, method: str, start_time: float, 
                      end_time: float, success: bool, error: Optional[str] = None):
        """记录请求指标"""
        duration = end_time - start_time
        metric = RequestMetrics(
            request_id=request_id,
            method=method,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=success,
            error=error
        )
        with self._lock:
            self.metrics.append(metric)

    async def connect(self) -> bool:
        """
        连接到 MCP 服务器并完成初始化流程
        
        Returns:
            bool: 是否成功连接
        """
        print(f"🔄 客户端 {self.client_id} 正在连接到 Excel MCP 服务器...")
        
        # 第一步：初始化会话
        if not await self._initialize():
            return False
        
        # 第二步：发送 initialized 通知
        if not await self._send_initialized():
            return False
        
        print(f"✅ 客户端 {self.client_id} 成功连接到 Excel MCP 服务器")
        return True

    async def _initialize(self) -> bool:
        """发送初始化请求"""
        start_time = time.time()
        request_id = f"{self.client_id}_init_{self._get_next_id()}"
        
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
                    "name": f"concurrent-python-excel-mcp-client-{self.client_id}",
                    "version": "1.0.0"
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json,text/event-stream"
        }

        try:
            if not self.session:
                raise RuntimeError("Session not initialized")
                
            async with self.session.post(self.mcp_url, json=payload, headers=headers) as response:
                end_time = time.time()
                
                if response.status != 200:
                    error_msg = f"初始化失败，状态码: {response.status}"
                    print(f"❌ 客户端 {self.client_id}: {error_msg}")
                    self._record_metric(request_id, "initialize", start_time, end_time, False, error_msg)
                    return False
                
                # 获取 session ID
                session_id = response.headers.get('mcp-session-id')
                if not session_id:
                    error_msg = "未获取到 session ID"
                    print(f"❌ 客户端 {self.client_id}: {error_msg}")
                    self._record_metric(request_id, "initialize", start_time, end_time, False, error_msg)
                    return False
                
                self.session_id = session_id
                self._record_metric(request_id, "initialize", start_time, end_time, True)
                print(f"✅ 客户端 {self.client_id} 获取到 session ID: {session_id}")
                return True

        except Exception as e:
            end_time = time.time()
            error_msg = f"初始化请求失败: {e}"
            print(f"❌ 客户端 {self.client_id}: {error_msg}")
            self._record_metric(request_id, "initialize", start_time, end_time, False, error_msg)
            return False

    async def _send_initialized(self) -> bool:
        """发送 initialized 通知"""
        if not self.session_id:
            print(f"❌ 客户端 {self.client_id}: 没有有效的 session ID")
            return False
        
        start_time = time.time()
        request_id = f"{self.client_id}_initialized_{self._get_next_id()}"
        
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
            if not self.session:
                raise RuntimeError("Session not initialized")
                
            async with self.session.post(self.mcp_url, json=payload, headers=headers) as response:
                end_time = time.time()
                self._record_metric(request_id, "notifications/initialized", start_time, end_time, True)
                return True
                
        except Exception as e:
            end_time = time.time()
            error_msg = f"发送 initialized 通知失败: {e}"
            print(f"❌ 客户端 {self.client_id}: {error_msg}")
            self._record_metric(request_id, "notifications/initialized", start_time, end_time, False, error_msg)
            return False

    async def list_tools(self) -> Optional[Dict]:
        """
        列出所有可用的工具
        
        Returns:
            Dict: 包含工具列表的字典，如果失败返回 None
        """
        return await self._call_method("tools/list", {})

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Any]:
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

        result = await self._call_method("tools/call", params)
        
        if result and "structuredContent" in result:
            return result["structuredContent"]["result"]
        elif result and "content" in result:
            # 处理返回内容
            content = result["content"]
            if isinstance(content, list) and len(content) > 0:
                return content[0].get("text", "")
            return content
        
        return result

    async def _call_method(self, method: str, params: Dict[str, Any]) -> Optional[Dict]:
        """
        调用 MCP 方法
        
        Args:
            method: 方法名
            params: 参数
            
        Returns:
            Dict: 响应结果
        """
        if not self.session_id:
            print(f"❌ 客户端 {self.client_id}: 没有有效的 session ID，请先调用 connect()")
            return None
        
        start_time = time.time()
        request_id = f"{self.client_id}_{method}_{self._get_next_id()}"
        
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
            if not self.session:
                raise RuntimeError("Session not initialized")
                
            async with self.session.post(self.mcp_url, json=payload, headers=headers) as response:
                end_time = time.time()
                
                if response.status != 200:
                    error_msg = f"方法调用失败，状态码: {response.status}"
                    print(f"❌ 客户端 {self.client_id}: {error_msg}")
                    self._record_metric(request_id, method, start_time, end_time, False, error_msg)
                    return None
                
                # 解析 SSE 响应
                response_text = await response.text()
                if response_text.startswith('event:'):
                    lines = response_text.strip().split('\n')
                    for line in lines:
                        if line.startswith('data:'):
                            try:
                                data = json.loads(line[5:].strip())
                                if 'result' in data:
                                    self._record_metric(request_id, method, start_time, end_time, True)
                                    return data['result']
                                elif 'error' in data:
                                    error_msg = f"服务器错误: {data['error']}"
                                    print(f"❌ 客户端 {self.client_id}: {error_msg}")
                                    self._record_metric(request_id, method, start_time, end_time, False, error_msg)
                                    return None
                            except json.JSONDecodeError:
                                pass
                
                error_msg = "无法解析响应"
                self._record_metric(request_id, method, start_time, end_time, False, error_msg)
                return None
                
        except Exception as e:
            end_time = time.time()
            error_msg = f"方法调用异常: {e}"
            print(f"❌ 客户端 {self.client_id}: {error_msg}")
            self._record_metric(request_id, method, start_time, end_time, False, error_msg)
            return None

    # 便捷方法
    async def read_excel_data(self, filepath: str, sheet_name: str, start_cell: str = "A1", 
                             end_cell: Optional[str] = None) -> Optional[str]:
        """读取 Excel 数据"""
        arguments = {
            "filepath": filepath,
            "sheet_name": sheet_name,
            "start_cell": start_cell
        }
        
        if end_cell:
            arguments["end_cell"] = end_cell
        
        return await self.call_tool("read_data_from_excel", arguments)

    async def get_workbook_metadata(self, filepath: str, include_ranges: bool = False) -> Optional[str]:
        """获取工作簿元数据"""
        arguments = {
            "filepath": filepath,
            "include_ranges": include_ranges
        }
        return await self.call_tool("get_workbook_metadata", arguments)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取性能指标摘要"""
        if not self.metrics:
            return {"message": "没有指标数据"}
        
        successful_metrics = [m for m in self.metrics if m.success]
        failed_metrics = [m for m in self.metrics if not m.success]
        
        durations = [m.duration for m in successful_metrics]
        
        summary = {
            "client_id": self.client_id,
            "total_requests": len(self.metrics),
            "successful_requests": len(successful_metrics),
            "failed_requests": len(failed_metrics),
            "success_rate": len(successful_metrics) / len(self.metrics) * 100 if self.metrics else 0,
        }
        
        if durations:
            summary.update({
                "avg_duration_ms": statistics.mean(durations) * 1000,
                "min_duration_ms": min(durations) * 1000,
                "max_duration_ms": max(durations) * 1000,
                "median_duration_ms": statistics.median(durations) * 1000,
            })
            
            if len(durations) > 1:
                summary["std_duration_ms"] = statistics.stdev(durations) * 1000
        
        # 添加资源使用统计
        resource_stats = self.resource_monitor.get_resource_stats()
        if resource_stats:
            summary.update({
                "resource_usage": {
                    "peak_cpu_percent": resource_stats.peak_cpu,
                    "peak_memory_percent": resource_stats.peak_memory,
                    "start_memory_mb": resource_stats.start_metrics.memory_used_mb,
                    "end_memory_mb": resource_stats.end_metrics.memory_used_mb,
                    "memory_delta_mb": resource_stats.end_metrics.memory_used_mb - resource_stats.start_metrics.memory_used_mb,
                    "total_io_read_bytes": resource_stats.total_io_read,
                    "total_io_write_bytes": resource_stats.total_io_write,
                    "avg_cpu_percent": statistics.mean([m.cpu_percent for m in self.resource_monitor.metrics_history]) if self.resource_monitor.metrics_history else 0,
                    "avg_memory_percent": statistics.mean([m.memory_percent for m in self.resource_monitor.metrics_history]) if self.resource_monitor.metrics_history else 0,
                }
            })
        
        return summary


class ConcurrencyManager:
    """并发管理器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.all_metrics: List[RequestMetrics] = []
        self.global_resource_monitor = SystemResourceMonitor()

    async def run_concurrent_clients(self, num_clients: int, operations_per_client: int) -> List[Dict[str, Any]]:
        """
        运行并发客户端
        
        Args:
            num_clients: 并发客户端数量
            operations_per_client: 每个客户端执行的操作数量
            
        Returns:
            List[Dict]: 每个客户端的性能指标摘要
        """
        print(f"🚀 启动 {num_clients} 个并发客户端，每个客户端执行 {operations_per_client} 个操作...")
        
        # 开始全局资源监控
        await self.global_resource_monitor.start_monitoring(interval=0.1)
        
        # 创建并发任务
        tasks = []
        for i in range(num_clients):
            client_id = f"client_{i+1}"
            task = self._run_single_client(client_id, operations_per_client)
            tasks.append(task)
        
        # 等待所有任务完成
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # 停止全局资源监控
        await self.global_resource_monitor.stop_monitoring()
        
        # 处理结果
        summaries = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ 客户端 {i+1} 执行失败: {result}")
                summaries.append({"client_id": f"client_{i+1}", "error": str(result)})
            else:
                summaries.append(result)
                # 收集所有指标
                if isinstance(result, dict) and "metrics" in result:
                    self.all_metrics.extend(result["metrics"])
        
        print(f"✅ 所有并发客户端执行完毕，总用时: {end_time - start_time:.2f} 秒")
        return summaries

    async def _run_single_client(self, client_id: str, num_operations: int) -> Dict[str, Any]:
        """运行单个客户端"""
        async with ConcurrentExcelMCPClient(self.base_url, client_id) as client:
            # 开始资源监控
            await client.resource_monitor.start_monitoring(interval=0.1)
            
            # 连接到服务器
            if not await client.connect():
                await client.resource_monitor.stop_monitoring()
                return {"client_id": client_id, "error": "连接失败"}
            
            # 执行多个操作
            tasks = []
            for i in range(num_operations):
                if i % 3 == 0:
                    # 读取 Excel 数据
                    task = client.read_excel_data(
                        "/Users/nashzhou/code/openhands/excel-mcp-server/small.xlsx",
                        "Sheet",
                        "A1"
                    )
                elif i % 3 == 1:
                    # 获取工作簿元数据
                    task = client.get_workbook_metadata(
                        "/Users/nashzhou/code/openhands/excel-mcp-server/large.xlsx"
                    )
                else:
                    # 列出工具
                    task = client.list_tools()
                
                tasks.append(task)
            
            # 并发执行所有操作
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # 停止资源监控
            await client.resource_monitor.stop_monitoring()
            
            # 获取性能指标
            summary = client.get_metrics_summary()
            summary["metrics"] = client.metrics
            return summary

    def print_overall_statistics(self, summaries: List[Dict[str, Any]]):
        """打印总体统计信息"""
        print("\n" + "="*80)
        print("📊 并发性能统计")
        print("="*80)
        
        # 基本统计
        total_clients = len([s for s in summaries if "error" not in s])
        failed_clients = len([s for s in summaries if "error" in s])
        
        print(f"总客户端数量: {len(summaries)}")
        print(f"成功客户端数量: {total_clients}")
        print(f"失败客户端数量: {failed_clients}")
        
        if total_clients == 0:
            print("❌ 没有成功的客户端")
            return
        
        # 聚合指标
        total_requests = sum(s.get("total_requests", 0) for s in summaries if "error" not in s)
        successful_requests = sum(s.get("successful_requests", 0) for s in summaries if "error" not in s)
        failed_requests = sum(s.get("failed_requests", 0) for s in summaries if "error" not in s)
        
        print(f"\n请求统计:")
        print(f"  总请求数: {total_requests}")
        print(f"  成功请求数: {successful_requests}")
        print(f"  失败请求数: {failed_requests}")
        print(f"  总体成功率: {successful_requests/total_requests*100:.1f}%" if total_requests > 0 else "  总体成功率: 0%")
        
        # 时延统计
        if self.all_metrics:
            successful_durations = [m.duration * 1000 for m in self.all_metrics if m.success]
            
            if successful_durations:
                print(f"\n时延统计 (毫秒):")
                print(f"  平均时延: {statistics.mean(successful_durations):.2f}")
                print(f"  最小时延: {min(successful_durations):.2f}")
                print(f"  最大时延: {max(successful_durations):.2f}")
                print(f"  中位数时延: {statistics.median(successful_durations):.2f}")
                if len(successful_durations) > 1:
                    print(f"  标准差: {statistics.stdev(successful_durations):.2f}")
                
                # 分位数
                sorted_durations = sorted(successful_durations)
                p95_index = int(len(sorted_durations) * 0.95)
                p99_index = int(len(sorted_durations) * 0.99)
                print(f"  95th 分位数: {sorted_durations[p95_index]:.2f}")
                print(f"  99th 分位数: {sorted_durations[p99_index]:.2f}")
        
        # 资源使用统计
        self._print_resource_statistics(summaries)
        
        # 全局资源统计
        global_resource_stats = self.global_resource_monitor.get_resource_stats()
        if global_resource_stats:
            print(f"\n全局资源使用:")
            print(f"  峰值CPU使用率: {global_resource_stats.peak_cpu:.1f}%")
            print(f"  峰值内存使用率: {global_resource_stats.peak_memory:.1f}%")
            print(f"  内存使用变化: {global_resource_stats.end_metrics.memory_used_mb - global_resource_stats.start_metrics.memory_used_mb:.1f} MB")
            print(f"  总IO读取: {global_resource_stats.total_io_read:,} 字节")
            print(f"  总IO写入: {global_resource_stats.total_io_write:,} 字节")
        
        # 每个客户端的详细信息
        print(f"\n客户端详细信息:")
        for summary in summaries:
            if "error" in summary:
                print(f"  {summary['client_id']}: ❌ {summary['error']}")
            else:
                avg_duration = summary.get("avg_duration_ms", 0)
                success_rate = summary.get("success_rate", 0)
                total = summary.get("total_requests", 0)
                resource_info = ""
                if "resource_usage" in summary:
                    ru = summary["resource_usage"]
                    resource_info = f", 峰值CPU: {ru.get('peak_cpu_percent', 0):.1f}%, 峰值内存: {ru.get('peak_memory_percent', 0):.1f}%"
                print(f"  {summary['client_id']}: {total} 请求, {success_rate:.1f}% 成功率, {avg_duration:.2f}ms 平均时延{resource_info}")
    
    def _print_resource_statistics(self, summaries: List[Dict[str, Any]]):
        """打印资源使用统计"""
        resource_summaries = [s for s in summaries if "error" not in s and "resource_usage" in s]
        
        if not resource_summaries:
            return
        
        print(f"\n资源使用统计:")
        
        # 聚合资源数据
        peak_cpus = [s["resource_usage"]["peak_cpu_percent"] for s in resource_summaries]
        peak_memories = [s["resource_usage"]["peak_memory_percent"] for s in resource_summaries]
        avg_cpus = [s["resource_usage"]["avg_cpu_percent"] for s in resource_summaries]
        avg_memories = [s["resource_usage"]["avg_memory_percent"] for s in resource_summaries]
        memory_deltas = [s["resource_usage"]["memory_delta_mb"] for s in resource_summaries]
        total_io_reads = [s["resource_usage"]["total_io_read_bytes"] for s in resource_summaries]
        total_io_writes = [s["resource_usage"]["total_io_write_bytes"] for s in resource_summaries]
        
        if peak_cpus:
            print(f"  CPU使用率 - 最大峰值: {max(peak_cpus):.1f}%, 平均峰值: {statistics.mean(peak_cpus):.1f}%")
            print(f"  CPU使用率 - 平均使用: {statistics.mean(avg_cpus):.1f}%")
        
        if peak_memories:
            print(f"  内存使用率 - 最大峰值: {max(peak_memories):.1f}%, 平均峰值: {statistics.mean(peak_memories):.1f}%")
            print(f"  内存使用率 - 平均使用: {statistics.mean(avg_memories):.1f}%")
        
        if memory_deltas:
            total_memory_change = sum(memory_deltas)
            print(f"  内存变化 - 总计: {total_memory_change:.1f} MB, 平均每客户端: {statistics.mean(memory_deltas):.1f} MB")
        
        if total_io_reads:
            total_read = sum(total_io_reads)
            total_write = sum(total_io_writes)
            print(f"  IO使用 - 总读取: {total_read:,} 字节, 总写入: {total_write:,} 字节")


async def demo_concurrent():
    """并发演示"""
    print("🎯 Excel MCP 服务器并发性能测试")
    print("="*60)
    
    # 创建并发管理器
    manager = ConcurrencyManager()
    
    # 测试不同的并发级别
    test_configs = [
        (2, 1),   # 2个客户端，每个5个操作
        # (5, 3),   # 5个客户端，每个3个操作
        # (10, 100),  # 10个客户端，每个100个操作
    ]
    
    for num_clients, operations_per_client in test_configs:
        print(f"\n🔬 测试配置: {num_clients} 客户端 × {operations_per_client} 操作")
        print("-" * 60)
        
        # 重置指标
        manager.all_metrics = []
        
        # 运行测试
        summaries = await manager.run_concurrent_clients(num_clients, operations_per_client)
        
        # 打印统计信息
        manager.print_overall_statistics(summaries)
        
        # 等待一段时间再进行下一个测试
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(demo_concurrent())
