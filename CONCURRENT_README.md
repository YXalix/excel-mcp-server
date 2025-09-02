# 并发 Excel MCP 客户端 - 资源监控版本

这是一个增强版的 Excel MCP 客户端，支持并发请求和系统资源监控。

## 功能特性

### 🚀 并发能力

- 支持多个客户端同时连接和操作
- 异步处理多个请求
- 自动管理连接池和会话

### 📊 性能监控

- 请求时延统计（平均、最小、最大、中位数、标准差）
- 95th 和 99th 分位数时延
- 成功率统计
- 请求计数和错误跟踪

### 💻 资源监控

- **CPU 使用率监控**
  - 实时 CPU 使用率
  - 峰值 CPU 使用率
  - 平均 CPU 使用率
  
- **内存使用监控**
  - 实时内存使用量（MB）
  - 内存使用率百分比
  - 峰值内存使用
  - 内存使用变化量
  
- **I/O 使用监控**
  - 读取字节数
  - 写入字节数
  - I/O 操作计数

## 安装依赖

```bash
pip install aiohttp psutil
```

## 使用方法

### 1. 启动 Excel MCP 服务器

```bash
uvx excel-mcp-server streamable-http
```

### 2. 运行并发测试

#### 基本并发测试

```python
from concurrent_excel_mcp_client import ConcurrencyManager

async def run_test():
    manager = ConcurrencyManager()
    
    # 运行 5 个并发客户端，每个执行 3 个操作
    summaries = await manager.run_concurrent_clients(5, 3)
    
    # 打印详细统计
    manager.print_overall_statistics(summaries)

# 运行测试
asyncio.run(run_test())
```

#### 单客户端资源监控

```python
from concurrent_excel_mcp_client import ConcurrentExcelMCPClient

async def single_client_test():
    async with ConcurrentExcelMCPClient() as client:
        # 开始资源监控
        await client.resource_monitor.start_monitoring()
        
        # 连接并执行操作
        await client.connect()
        data = await client.read_excel_data("file.xlsx", "Sheet1")
        
        # 停止监控并获取统计
        await client.resource_monitor.stop_monitoring()
        summary = client.get_metrics_summary()
        
        print(f"资源使用: {summary['resource_usage']}")
```

### 3. 运行示例测试

```bash
# 运行完整的并发演示
python concurrent_excel_mcp_client.py

# 运行资源监控测试
python test_concurrent_client.py
```

## 输出示例

### 性能统计示例

```markdown
📊 并发性能统计
================================================================================
总客户端数量: 5
成功客户端数量: 5
失败客户端数量: 0

请求统计:
  总请求数: 15
  成功请求数: 15
  失败请求数: 0
  总体成功率: 100.0%

时延统计 (毫秒):
  平均时延: 125.43
  最小时延: 89.21
  最大时延: 203.87
  中位数时延: 118.95
  标准差: 28.76
  95th 分位数: 186.54
  99th 分位数: 198.32

资源使用统计:
  CPU使用率 - 最大峰值: 15.2%, 平均峰值: 12.8%
  CPU使用率 - 平均使用: 8.5%
  内存使用率 - 最大峰值: 1.8%, 平均峰值: 1.6%
  内存使用率 - 平均使用: 1.4%
  内存变化 - 总计: 2.3 MB, 平均每客户端: 0.5 MB
  IO使用 - 总读取: 15,234 字节, 总写入: 8,956 字节

全局资源使用:
  峰值CPU使用率: 18.5%
  峰值内存使用率: 2.1%
  内存使用变化: 3.1 MB
  总IO读取: 18,456 字节
  总IO写入: 12,345 字节
```

## 类和方法说明

### `SystemMetrics`

记录单次系统资源快照的数据类。

### `RequestMetrics`

记录单次请求性能指标的数据类。

### `ResourceStats`

聚合的资源使用统计数据类。

### `SystemResourceMonitor`

系统资源监控器，负责：

- 定时收集系统指标
- 计算峰值和平均值
- 提供资源使用统计

### `ConcurrentExcelMCPClient`

增强的异步 MCP 客户端，支持：

- 异步连接和请求处理
- 集成的资源监控
- 详细的性能指标收集

### `ConcurrencyManager`

并发管理器，提供：

- 多客户端并发执行
- 全局资源监控
- 聚合统计和报告

## 配置选项

### 资源监控间隔

```python
# 设置监控间隔为 50ms（默认 100ms）
await client.resource_monitor.start_monitoring(interval=0.05)
```

### 并发级别

```python
# 10 个并发客户端，每个执行 5 个操作
summaries = await manager.run_concurrent_clients(10, 5)
```

## 注意事项

1. **平台兼容性**: I/O 监控在某些平台上可能不可用，代码会自动回退到安全模式
2. **资源开销**: 资源监控本身会消耗少量 CPU 和内存
3. **权限要求**: 某些系统指标可能需要特定权限
4. **服务器负载**: 高并发测试可能对 MCP 服务器造成负载

## 故障排除

### 常见问题

1. **连接失败**
   - 确保 MCP 服务器正在运行
   - 检查端口号是否正确

2. **I/O 统计为 0**
   - 某些平台不支持进程 I/O 统计
   - 这是正常现象，不影响其他功能

3. **高 CPU 使用率**
   - 降低监控频率 (`interval` 参数)
   - 减少并发客户端数量

## 扩展功能

这个客户端可以轻松扩展以支持：

- 自定义性能指标
- 网络延迟监控
- 数据库连接池监控
- 自定义报告格式
- 实时性能仪表板
