#!/bin/bash

# Excel MCP Server curl 调用示例
# 展示如何正确调用 Excel MCP 工具的完整流程

BASE_URL="http://localhost:8017"
MCP_URL="${BASE_URL}/stream/mcp"

echo "🔄 第一步：初始化 MCP 会话并获取 session ID"

# 发送初始化请求
INIT_RESPONSE=$(curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json,text/event-stream" \
  -D /tmp/headers.txt \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {
        "roots": {"listChanged": true},
        "sampling": {}
      },
      "clientInfo": {
        "name": "curl-client",
        "version": "1.0.0"
      }
    }
  }')

echo "📋 初始化响应:"
echo "$INIT_RESPONSE"

# 提取 session ID
SESSION_ID=$(grep -i "mcp-session-id:" /tmp/headers.txt | cut -d' ' -f2 | tr -d '\r\n')

if [ -z "$SESSION_ID" ]; then
    echo "❌ 无法获取 session ID"
    exit 1
fi

echo "✅ 获取到 session ID: $SESSION_ID"

echo ""
echo "🔄 第二步：发送 initialized 通知"

# 发送 initialized 通知
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json,text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "notifications/initialized"
  }' > /dev/null

echo "✅ 已发送 initialized 通知"

echo ""
echo "🔄 第三步：调用 read_data_from_excel 工具"

# 调用工具
TOOL_RESPONSE=$(curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json,text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "read_data_from_excel",
      "arguments": {
        "filepath": "/Users/nashzhou/code/openhands/excel-mcp-server/small.xlsx",
        "sheet_name": "Sheet",
        "start_cell": "A1"
      }
    }
  }')

echo "📊 工具调用响应:"
echo "$TOOL_RESPONSE"

# 提取并格式化 JSON 数据
if echo "$TOOL_RESPONSE" | grep -q "data:"; then
    JSON_DATA=$(echo "$TOOL_RESPONSE" | grep "data:" | sed 's/data: //' | jq -r '.result.structuredContent.result')
    
    if [ "$JSON_DATA" != "null" ] && [ -n "$JSON_DATA" ]; then
        echo ""
        echo "🎉 格式化的 Excel 数据:"
        echo "$JSON_DATA" | jq .
    fi
fi

# 清理临时文件
rm -f /tmp/headers.txt

echo ""
echo "✅ curl 调用示例完成！"
