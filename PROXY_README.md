# Excel MCP 代理服务器使用指南

本文档提供了如何使用 Excel MCP 代理服务器的详细说明。代理服务器模式可以为每个客户端请求动态创建独立的 stdio MCP 子进程，提供更好的隔离性和可扩展性。

## 基本概念

Excel MCP 代理服务器实现了以下功能：

1. **HTTP 和 WebSocket 接口**：支持标准的 MCP 请求响应模式
2. **会话管理**：为每个客户端维护独立的 stdio 子进程
3. **自动资源清理**：闲置会话会自动清理，释放系统资源
4. **状态隔离**：不同客户端的状态完全独立，互不影响

## 启动代理服务器

可以通过以下命令启动代理服务器：

```bash
# 直接启动
uvx excel-mcp-server proxy

# 或者指定端口和主机
FASTMCP_PORT=9000 FASTMCP_HOST=127.0.0.1 uvx excel-mcp-server proxy

# 或者指定 Excel 文件路径
EXCEL_FILES_PATH=/path/to/excel/files uvx excel-mcp-server proxy
```

## 客户端连接

客户端可以使用标准的 MCP 客户端连接到代理服务器：

```json
{
   "mcpServers": {
      "excel": {
         "url": "http://localhost:8017/mcp"
      }
   }
}
```

## 会话管理

### 会话 ID

代理服务器使用会话 ID 来标识不同的客户端连接。会话 ID 通过 HTTP 头 `X-Session-ID` 传递：

- 如果客户端未提供会话 ID，服务器会自动生成一个新的会话 ID
- 如果客户端提供了会话 ID，服务器会尝试复用现有的会话
- 会话 ID 会在响应头中返回，客户端应保存并在后续请求中使用

### 示例：使用 cURL 发送带会话 ID 的请求

```bash
# 使用固定的会话 ID
curl -X POST http://localhost:8017/mcp \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: your-session-id" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "create_workbook",
    "params": {
      "filepath": "./example.xlsx"
    }
  }'
```

## 会话生命周期

1. **创建**：首次收到某个会话 ID 的请求时，创建新的子进程
2. **活动**：每次请求都会更新会话的活动时间戳
3. **清理**：超过 5 分钟没有活动的会话会被自动清理

## 支持的请求类型

代理服务器支持以下几种请求方式：

1. **普通 HTTP POST**：标准的 JSON-RPC 请求/响应
2. **WebSocket**：用于持续连接的场景
3. **流式 HTTP**：用于流式返回结果的场景

### 示例：WebSocket 连接

```javascript
const ws = new WebSocket('ws://localhost:8017/ws/mcp');
ws.onopen = () => {
  ws.send(JSON.stringify({
    jsonrpc: "2.0",
    id: 1,
    method: "create_workbook",
    params: {
      filepath: "./example.xlsx"
    }
  }));
};
ws.onmessage = (event) => {
  console.log(JSON.parse(event.data));
};
```

## 高级用例

### 并发请求处理

代理服务器能够处理来自不同客户端的并发请求，每个客户端会话都有自己独立的子进程。

### 负载均衡

如果需要处理大量并发请求，可以设置多个代理服务器实例，并使用负载均衡器在它们之间分配请求。

### 容器化部署

代理服务器适合在容器环境中部署：

```Dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装依赖
RUN pip install uv
RUN uv install excel-mcp-server

# 设置文件目录
ENV EXCEL_FILES_PATH=/app/excel_files
RUN mkdir -p ${EXCEL_FILES_PATH}

# 暴露端口
EXPOSE 8017

# 启动代理服务器
CMD ["uvx", "excel-mcp-server", "proxy"]
```

## 故障排除

### 常见问题

1. **子进程无响应**：如果子进程无响应，代理服务器会自动终止并重新创建新的子进程
2. **内存占用高**：如果有大量闲置会话，可以调整 `idle_timeout` 参数减少闲置时间
3. **Excel 文件权限问题**：确保 EXCEL_FILES_PATH 目录有正确的读写权限

### 日志

代理服务器的日志位于 `excel-mcp-proxy.log` 文件中。如果需要调试，可以查看此日志文件了解详细信息。

## 性能优化

1. 对于高负载场景，建议增加系统的文件描述符限制
2. 可以根据系统资源调整闲置会话超时时间
3. 对于频繁访问的 Excel 文件，可以考虑使用内存文件系统提高性能
