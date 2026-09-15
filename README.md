# 采购领域专家智能助手

基于 **Harness 工程架构** 的采购领域智能助手：用户用自然语言下达指令，主 Agent 理解意图后把任务派给两个专职子 Agent，完成市场调研、采购比价、订单生成与 ERP 库存对接，并在关键写操作处引入人工审批。

核心理念：**Agent = Model + Harness**。模型只负责「思考」，Harness 负责工具、规划、记忆、沙箱、中间件、子 Agent 编排与安全护栏。

## 系统架构

```
┌───────────┐   SSE    ┌──────────────┐      ┌──────────────────────────────┐
│  React     │ ───────▶ │  FastAPI     │ ───▶ │  DeepAgent（主 Agent）         │
│  前端      │          │  Web (8000)  │      │   ├─ procurement-researcher   │
│  (5173)    │ ◀─────── │  会话 / 流式  │      │   └─ procurement-executor     │
└───────────┘          └──────────────┘      └───────┬──────────────┬────────┘
                                                      │              │
                                        ┌─────────────▼─────┐  ┌─────▼──────────────┐
                                        │  MCP Server       │  │  Docker 沙箱        │
                                        │  (8001)           │  │  （代码执行/文件系统） │
                                        └─────────┬─────────┘  └────────────────────┘
                                                  │
                                        ┌─────────▼─────────┐
                                        │  ERP 后端 (8080)   │
                                        └───────────────────┘

外部依赖：阿里云百炼 qwen（LLM）· Tavily（联网搜索）· MongoDB (27017)
```

## 核心能力（Harness 能力落地）

| Harness 能力 | 本项目实现 |
| ------------ | ---------- |
| 规划 | `TodoListMiddleware`，多步任务先列计划再执行 |
| 子 Agent 编排 | 1 主 + 2 专职子 Agent（研究员 / 执行员） |
| 工具调用 | MCP 网关对接 ERP + 联网搜索 + 技能安装 |
| 记忆 | MongoDB 持久化用户偏好（`/memories/`） |
| 沙箱 | Docker 沙箱（代码执行 + 文件系统） |
| 中间件栈 | 健康检查、熔断、技能同步、记忆更新、摘要压缩、调用限制 |
| 安全护栏 | 双重人工介入（缺字段追问 + 写操作审批） |

## 两个子 Agent

- **procurement-researcher（采购研究员）**：查询现有物料/供应商报价，联网搜索候选商品与行情，做「买哪个好」的对比分析，产出调研报告。
- **procurement-executor（采购执行员）**：查询/生成/修改采购订单、直接下单（入库/出库），对接 ERP 库存、物料与供应商。

主 Agent 通过 `task` 工具派活，只接收子 Agent 返回的精简结论。子 Agent 之间对话隔离，各自只拿到派活时传递的上下文。

## 双重人工介入（HITL）

1. **缺字段追问**：下单缺少物料编号 / 数量时，`request_order_info` 中断向用户补齐。
2. **写操作审批**：`order_create` / `order_update` / `order_place` 执行前需人工 approve / reject。

## 技术栈

- **前端**：React 18 + Vite 5
- **Web 层**：FastAPI + SSE 流式输出
- **Agent 核心**：deepagents（LangGraph / LangChain）
- **MCP**：FastMCP 网关
- **数据**：MongoDB（Motor 异步驱动）
- **沙箱**：Docker（`python:3.11-slim`）
- **LLM**：阿里云百炼 DashScope（qwen，OpenAI 兼容接口）
- **联网搜索**：Tavily

## 目录结构

```
.
├── frontend/              # React + Vite 前端
├── src/
│   ├── api_view/          # FastAPI Web 层（会话、SSE 流式）
│   └── agent/             # Agent 核心
│       ├── main_agent.py  # 主 Agent 组装（工具 / 中间件 / 子 Agent）
│       ├── subagents.py   # 两个子 Agent 定义
│       ├── middlewares/   # 中间件栈
│       ├── backends/      # 沙箱 + 三层路由文件系统
│       └── tools/         # MCP 客户端 / HITL / 联网搜索 / 技能安装
├── mcp_server/            # MCP 网关（ERP 接口 → MCP 工具）
├── mock_erp/              # 模拟 ERP 后端（测试替身）
├── skills/                # 子 Agent 技能手册
├── test/                  # 测试
├── docker-compose.yml     # MongoDB
└── .env.example           # 环境变量模板
```

## 快速开始

### 前置条件

- Python 3.11+
- Node.js 18+
- Docker + Docker Compose
- 阿里云百炼 API Key（LLM）
- Tavily API Key（联网搜索，可选）

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env：填入 LLM_API_KEY（或设置系统环境变量 DASHSCOPE_API_KEY）和 TAVILY_API_KEY
```

### 2. 启动 MongoDB

```bash
docker compose up -d
```

### 3. 启动 Mock ERP（测试替身）

```bash
python -m mock_erp.main
```

### 4. 启动 MCP Server

```bash
python -m mcp_server.server_main
```

### 5. 启动 Web 层

```bash
uvicorn src.api_view.web_main:app --reload --port 8000
```

### 6. 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 <http://localhost:5173>。

> 接入真实 ERP 时，只需把 `.env` 里的 `ERP_BASE_URL` 指向真实服务地址即可，无需改动调用方。

## 一个典型流程

> 用户：「查一下哪些物料库存预警，然后调研高性价比的补货方案」

1. 主 Agent 判断意图，派给采购执行员查询库存预警清单；
2. 拿到预警物料后，派给采购研究员联网调研、对比报价；
3. 研究员产出调研报告，用户确认后，派给执行员生成采购订单；
4. `order_create` 触发人工审批，用户 approve 后下单入库（库存增加）。
