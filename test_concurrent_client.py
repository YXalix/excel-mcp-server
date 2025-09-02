#!/usr/bin/env python3
"""
测试并发 Excel MCP 客户端的资源监控功能

这个脚本将演示如何使用增强的并发客户端来测试性能和资源使用情况。
"""

import asyncio
import sys
import os

# 添加当前目录到路径，以便导入我们的模块
sys.path.insert(0, os.path.dirname(__file__))

from concurrent_excel_mcp_client import ConcurrencyManager, ConcurrentExcelMCPClient


async def test_single_client():
    """测试单个客户端的资源监控"""
    print("🔬 测试单个客户端资源监控...")
    print("=" * 50)
    
    async with ConcurrentExcelMCPClient("http://localhost:8000", "test_client") as client:
        # 开始资源监控
        await client.resource_monitor.start_monitoring(interval=0.05)
        
        # 连接到服务器
        if not await client.connect():
            print("❌ 无法连接到服务器")
            return
        
        # 执行一些操作
        print("📊 执行测试操作...")
        
        # 测试工具列表
        tools = await client.list_tools()
        if tools:
            print(f"✅ 获取到 {len(tools.get('tools', []))} 个工具")
        
        # 测试读取数据
        data = await client.read_excel_data(
            "/Users/nashzhou/code/openhands/excel-mcp-server/large.xlsx",
            "Sheet",
            "A1"
        )
        if data:
            print("✅ 成功读取 Excel 数据")
        
        # 停止资源监控
        await client.resource_monitor.stop_monitoring()
        
        # 获取并打印指标
        summary = client.get_metrics_summary()
        print("\n📈 客户端性能摘要:")
        print(f"  总请求数: {summary.get('total_requests', 0)}")
        print(f"  成功率: {summary.get('success_rate', 0):.1f}%")
        print(f"  平均时延: {summary.get('avg_duration_ms', 0):.2f}ms")
        
        # 资源使用情况
        if "resource_usage" in summary:
            ru = summary["resource_usage"]
            print(f"\n💻 资源使用情况:")
            print(f"  峰值CPU: {ru.get('peak_cpu_percent', 0):.1f}%")
            print(f"  平均CPU: {ru.get('avg_cpu_percent', 0):.1f}%")
            print(f"  峰值内存: {ru.get('peak_memory_percent', 0):.1f}%")
            print(f"  平均内存: {ru.get('avg_memory_percent', 0):.1f}%")
            print(f"  内存变化: {ru.get('memory_delta_mb', 0):.1f} MB")
            print(f"  IO读取: {ru.get('total_io_read_bytes', 0):,} 字节")
            print(f"  IO写入: {ru.get('total_io_write_bytes', 0):,} 字节")


async def test_concurrent_clients():
    """测试并发客户端"""
    print("\n🚀 测试并发客户端...")
    print("=" * 50)
    
    manager = ConcurrencyManager()
    
    # 小规模测试
    summaries = await manager.run_concurrent_clients(3, 2)
    
    # 打印统计信息
    manager.print_overall_statistics(summaries)


async def main():
    """主测试函数"""
    print("🎯 Excel MCP 并发客户端资源监控测试")
    print("=" * 60)
    
    try:
        # 测试单个客户端
        await test_single_client()
        
        # 测试并发客户端
        await test_concurrent_clients()
        
    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
