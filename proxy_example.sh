#!/bin/bash

# 示例：如何使用Excel MCP代理服务器

# 启动代理服务器（在后台运行）
echo "启动Excel MCP代理服务器..."
uvx excel-mcp-server proxy &
PROXY_PID=$!

# 等待服务器启动
sleep 2

# 创建一个会话ID
SESSION_ID=$(uuidgen)
echo "使用会话ID: $SESSION_ID"

# 发送创建工作簿的请求
echo "创建工作簿..."
curl -X POST http://localhost:8017/mcp \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "create_workbook",
    "params": {
      "filepath": "./example.xlsx"
    }
  }'

echo -e "\n"

# 发送创建工作表的请求
echo "创建工作表..."
curl -X POST http://localhost:8017/mcp \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "create_worksheet",
    "params": {
      "filepath": "./example.xlsx",
      "sheet_name": "Data"
    }
  }'

echo -e "\n"

# 写入数据
echo "写入数据..."
curl -X POST http://localhost:8017/mcp \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "write_data_to_excel",
    "params": {
      "filepath": "./example.xlsx",
      "sheet_name": "Data",
      "start_cell": "A1",
      "data": [
        ["Name", "Age", "City"],
        ["Alice", 25, "New York"],
        ["Bob", 30, "Boston"],
        ["Charlie", 35, "Chicago"]
      ]
    }
  }'

echo -e "\n"

# 获取工作簿元数据
echo "获取工作簿元数据..."
curl -X POST http://localhost:8017/mcp \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "get_workbook_metadata",
    "params": {
      "filepath": "./example.xlsx",
      "include_ranges": true
    }
  }'

echo -e "\n"

# 结束会话（向代理服务器发送终止特定会话的信号，实际上并不需要，因为服务器会自动清理闲置会话）
# 但我们可以模拟新的会话启动

echo "启动新会话..."
NEW_SESSION_ID=$(uuidgen)
echo "使用新会话ID: $NEW_SESSION_ID"

# 读取前面创建的工作簿中的数据（使用新会话）
echo "读取数据（使用新会话）..."
curl -X POST http://localhost:8017/mcp \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: $NEW_SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "read_data_from_excel",
    "params": {
      "filepath": "./example.xlsx",
      "sheet_name": "Data"
    }
  }'

echo -e "\n"

# 清理工作
echo "清理..."
# 终止代理服务器
kill $PROXY_PID

echo "演示完成！"
