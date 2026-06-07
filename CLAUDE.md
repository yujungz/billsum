# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

BillSum - 多站点帐单统计应用。从远程 MySQL 数据库导出消费日志，导入本地库后进行数据填充和统计分析。支持按月/按时段统计，计算 token 费用（含缓存费用）。

## Tech Stack

- Backend: Python 3.11 + FastAPI + aiomysql + paramiko
- Frontend: Vue 3 + Element Plus + Vite
- Database: MySQL (容器 test-mysql8)
- Deploy: Docker + nginx

## Development

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # dev server at localhost:5173, proxies /api to :8000
npm run build        # production build to dist/
```

### Docker

```bash
# 先创建 Docker 网络
docker network create billsum_net
# 将已有 MySQL 容器加入网络
docker network connect billsum_net test-mysql8
# 构建并启动
docker-compose up --build
```

## Architecture

```
backend/app/
  main.py           - FastAPI entry, mounts all routers
  config.py         - Pydantic config models, JSON file persistence
  database.py       - aiomysql connection pool, query helpers
  api/              - Route handlers (transfer, query, statistics, settings, system)
  services/
    ssh_service.py  - SSH/SFTP via paramiko
    transfer_service.py - Data pipeline: export→download→import→fill
    sql_templates.py    - Parameterized SQL (old2new, uptnew per site mode)
    query_service.py    - Table listing and paginated queries
    stats_service.py    - Statistics with cost calculations

frontend/src/
  App.vue           - Left-right layout (el-aside sidebar + el-main router-view)
  views/            - TransferView, QueryView, StatsView, ConfigView, SystemView
  api/index.js      - Axios API client
```

### Data Flow

1. SSH to remote → mysqldump logs table (renamed to logs{period}orig) → compress .tgz
2. SFTP download → decompress locally
3. Import SQL into local MySQL `sum_{site}` database
4. old2new: copy orig table to processed table, extract JSON fields (cache tokens, ratios)
5. uptnew: JOIN ex_users/ex_tokens/ex_channels to fill sales/buyer/discount info

### Site Uptnew Modes

- `full`: JOIN ex_users + ex_tokens + ex_channels (wzg/pinova/ai) — discount uses CASE WHEN tokens vs users
- `simple`: JOIN ex_users + ex_channels only (csp) — discount from ex_users
- `minimal`: No update, just register table name (qn/digitalcloud)

### Cost Calculation

- Input cost = prompt_tokens × model_ratio × 2 / 1,000,000
- Output cost = completion_tokens × model_ratio × 2 × completion_ratio / 1,000,000
- Cache read cost = cache_tokens × model_ratio × 2 × cache_ratio / 1,000,000
- Cache create cost = cache_creation_tokens × model_ratio × 2 × cache_creation_ratio / 1,000,000
- Cache 5M cost = cache_creation_tokens_5m × model_ratio × 2 × cache_creation_ratio_5m / 1,000,000
- Cache total = cache read cost + GREATEST(cache create cost, cache 5M cost)
- Total cost = input + output + cache total
