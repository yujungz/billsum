# BillSum 使用说明书

## 1. 简介

BillSum 是一个多站点帐单统计应用，用于统计多个 AI 服务站点的消费记录。

核心功能：

- **数据传输**：从远程数据库导出消费日志，下载到本地并导入，自动生成统计表
- **日志查询**：浏览原始记录和统计表数据
- **数据统计**：按月/日/时段、用户、渠道、模型等维度统计消费，计算 token 费用
- **参数配置**：管理数据库连接和 SSH 配置
- **系统功能**：查看和清理 MySQL binlog

支持的站点：**ai、csp、pinova、wzg、qn、digitalcloud**

---

## 2. 环境要求

| 组件 | 要求 |
|------|------|
| Docker | 20.10+ |
| Docker Compose | v2+ |
| MySQL | 8.0+（已有容器 test-mysql8） |
| 浏览器 | Chrome / Edge / Firefox 最新版 |

---

## 3. 安装部署

### 3.1 创建 Docker 网络

```bash
docker network create billsum_net
```

### 3.2 将 MySQL 容器加入网络

```bash
docker network connect billsum_net test-mysql8
```

> 应用容器通过 Docker 内部网络直接连接 MySQL，使用容器名 `test-mysql8` 作为主机名。

### 3.3 构建并启动应用

```bash
docker-compose up -d --build
```

### 3.4 访问应用

浏览器打开 **http://localhost:8089**

### 3.5 常用运维命令

```bash
# 查看日志
docker logs -f billsum-app

# 停止
docker-compose down

# 重新构建（代码更新后）
docker-compose up -d --build
```

---

## 4. 功能说明

应用采用左右布局，左侧为导航菜单，右侧为功能界面。

---

### 4.1 参数配置

> 首次使用请先完成配置。

#### 本地数据库

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 容器名称 | test-mysql8 | MySQL Docker 容器名 |
| 主机 | test-mysql8 | Docker 网络内使用容器名 |
| 端口 | 3306 | MySQL 端口 |
| 用户名 | root | |
| 密码 | 123456 | |

配置完成后点击 **「测试连接」** 验证。

#### 站点 SSH 配置

切换到对应站点的 Tab 页，配置：

| 配置项 | 说明 |
|--------|------|
| 填充模式 | 见下方说明 |
| SSH 主机 | 远程服务器 IP 或域名 |
| SSH 端口 | 默认 22 |
| SSH 用户名 | 默认 root |
| 密钥路径 | SSH 私钥文件路径（容器内路径，需通过 volume 挂载） |
| 远程路径 | 远程数据存放路径，默认 ~/data/ |
| 远程容器名 | 远程 MySQL Docker 容器名 |
| 远程数据库名 | 默认 new-api |
| 远程数据库密码 | 远程 MySQL root 密码 |

**填充模式说明**：

| 模式 | 适用站点 | 说明 |
|------|----------|------|
| 完整 (full) | wzg、pinova、ai | 关联 ex_users + ex_tokens + ex_channels 三个表 |
| 简单 (simple) | csp | 关联 ex_users + ex_channels，不关联 ex_tokens |
| 最小 (minimal) | qn、digitalcloud | 仅登记表名，不做额外更新 |

点击 **「测试 SSH」** 验证连接。

配置完成后点击底部 **「保存配置」**。

---

### 4.2 数据传输

#### 输入参数

| 参数 | 说明 |
|------|------|
| 站点 | 选择要操作的站点 |
| 时间类型 | **月度** 或 **时段** |
| 月份 | 月度模式下选择，如 202604 表示 2026 年 4 月 |
| 开始/结束日期 | 时段模式下选择日期范围 |
| 基础表 | 是否同时传输 channels/users/tokens 三个基础表 |

#### 操作步骤

数据传输分 4 步，可单独执行或一键执行：

| 步骤 | 说明 |
|------|------|
| 1. 远程导出 | SSH 连接远程服务器，执行 mysqldump 导出日志数据 |
| 2. 远程下载 | 通过 SFTP 将导出的压缩文件下载到本地 |
| 3. 本地导入 | 解压并导入 SQL 文件到本地 MySQL |
| 4. 本地填充 | 从原始表生成统计表，填充销售/采购信息 |

- 点击 **「一键执行」** 自动按顺序执行全部步骤
- 页面会显示步骤进度条和执行日志

#### 表命名规则

| 类型 | 原始表名 | 统计表名 |
|------|----------|----------|
| 月度 | logs202604orig | logs202604 |
| 时段 | logs20260427_20260515orig | logs20260427_20260515 |

#### 测试用例

站点：wzg，月度，202604

---

### 4.3 日志查询

#### 切换查询类型

- **原始记录**：从远程导入的数据，包括 channels、users、tokens 和 logs*orig 表
- **统计表**：本地生成的数据，包括 ex_channels、ex_users、ex_tokens 和 logs* 表

#### 操作方式

1. 选择站点
2. 选择查询类型（原始记录 / 统计表）
3. 从下拉框选择要查看的表
4. 表格自动加载数据，支持分页浏览

---

### 4.4 数据统计

#### 统计条件

| 条件 | 必填 | 说明 |
|------|------|------|
| 站点 | 是 | 选择统计的站点 |
| 日志表 | 是 | 选择已导入的统计日志表（如 logs202604） |
| 统计粒度 | 否 | 可多选：按月、按日、用户、渠道、模型 |
| 用户名 | 否 | 模糊筛选 |
| 渠道 | 否 | 模糊筛选 |
| 模型 | 否 | 模糊筛选 |

> 统计粒度可以自由组合，例如同时勾选「按日」+「用户」+「模型」。

#### 统计内容说明

| 统计项 | 计算方式 |
|--------|----------|
| 调用记录数 | 时间段内的记录数 |
| 输入Token(M) | prompt_tokens / 1,000,000 |
| 输入费用 | prompt_tokens × model_ratio × 2 / 1,000,000 |
| 输出Token(M) | completion_tokens / 1,000,000 |
| 输出费用 | completion_tokens × model_ratio × 2 × completion_ratio / 1,000,000 |
| 读缓存Token(M) | cache_tokens / 1,000,000 |
| 读缓存费用 | cache_tokens × model_ratio × 2 × cache_ratio / 1,000,000 |
| 创缓存Token(M) | cache_creation_tokens / 1,000,000 |
| 创缓存费用 | cache_creation_tokens × model_ratio × 2 × cache_creation_ratio / 1,000,000 |
| 创缓存5M(M) | cache_creation_tokens_5m / 1,000,000 |
| 创缓存5M费 | cache_creation_tokens_5m × model_ratio × 2 × cache_creation_ratio_5m / 1,000,000 |
| 缓存总费用 | 读缓存费用 + max(创缓存费用, 创缓存5M费) |
| 消费额度 | 输入费用 + 输出费用 + 缓存总费用 |

#### 导出

点击 **「导出 CSV」** 按钮将当前查询结果导出为 CSV 文件。

---

### 4.5 系统功能

#### Binlog 管理

- 点击 **「刷新」** 查看 MySQL binlog 文件列表和大小
- 点击 **「清除 Binlog」** 清理所有 binlog 文件（操作需确认）

---

## 5. 数据库结构

### 数据库命名

每个站点对应一个本地数据库，命名规则为 `sum_{站点名}`。

| 站点 | 数据库名 |
|------|----------|
| ai | sum_ai |
| csp | sum_csp |
| pinova | sum_pinova |
| wzg | sum_wzg |
| qn | sum_qn |
| digitalcloud | sum_digitalcloud |

另有一个公共数据库 **sum_all**，存储日志表名登记信息。

### 表结构

| 表名 | 类型 | 说明 |
|------|------|------|
| channels | 原始 | 渠道信息 |
| users | 原始 | 用户信息 |
| tokens | 原始 | 令牌信息 |
| logs{period}orig | 原始 | 原始日志（从远程导入） |
| ex_channels | 统计 | 扩展渠道表（含供应商、折扣） |
| ex_users | 统计 | 扩展用户表（含销售员、折扣） |
| ex_tokens | 统计 | 扩展令牌表（含折扣） |
| logs{period} | 统计 | 统计日志表（含费用计算字段） |

### 日志统计表关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| prompt_tokens | bigint | 输入 token 数 |
| completion_tokens | bigint | 输出 token 数 |
| cache_tokens | decimal | 读取缓存 token 数 |
| cache_creation_tokens | decimal | 创建缓存 token 数 |
| cache_creation_tokens_5m | decimal | 创建缓存 5M token 数 |
| model_ratio | decimal | 模型倍率 |
| completion_ratio | decimal | 输出倍率 |
| cache_ratio | decimal | 缓存读取倍率 |
| cache_creation_ratio | decimal | 缓存创建倍率 |
| cache_creation_ratio_5m | decimal | 缓存创建 5M 倍率 |
| us_salesperson | varchar | 上游销售员 |
| us_discount | decimal | 上游折扣 |
| cn_buyer | varchar | 下游采购员 |
| cn_supplier | varchar | 下游供应商 |
| cn_discount | decimal | 下游折扣 |

---

## 6. 数据流程图

```
远程服务器                              本地
┌──────────┐                       ┌──────────┐
│ MySQL    │  1. mysqldump         │          │
│ (new-api)│ ──────────────────►   │  SSH     │
│          │     logs → .tgz       │  连接    │
└──────────┘                       │          │
                                   └────┬─────┘
                                        │ 2. SFTP 下载
                                        ▼
                                   ┌──────────┐
                                   │ 本地文件  │
                                   │ (.tgz)   │
                                   └────┬─────┘
                                        │ 3. 解压 + 导入
                                        ▼
                                   ┌──────────┐
                                   │ MySQL    │
                                   │ sum_wzg  │
                                   │          │
                                   │ logs202604orig  (原始表)
                                   │      │
                                   │      │ 4. old2new 生成
                                   │      ▼
                                   │ logs202604      (统计表)
                                   │      │
                                   │      │ 5. uptnew 填充
                                   │      ▼
                                   │ logs202604      (含费用字段)
                                   └──────────┘
```

---

## 7. 开发模式

如需本地开发调试（不使用 Docker）：

### 后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认在 http://localhost:5173，自动代理 `/api` 请求到后端 8000 端口。

---

## 8. 常见问题

**Q: 点击「测试连接」提示连接失败？**

检查 MySQL 容器是否在运行：`docker ps | grep test-mysql8`。确认应用容器和 MySQL 容器在同一 Docker 网络中：`docker network inspect billsum_net`。

**Q: 远程导出失败？**

1. 确认 SSH 密钥文件路径正确，且已挂载到应用容器内
2. 确认远程服务器上的 Docker 容器名称和密码正确
3. 查看日志：`docker logs billsum-app`

**Q: 统计表没有数据？**

1. 确认已完成数据传输全部 4 个步骤
2. 确认 ex_users、ex_channels、ex_tokens 表中有关联数据
3. 在日志查询页面检查原始表和统计表是否存在

**Q: 如何挂载 SSH 密钥？**

在 docker-compose.yml 中添加 volume 映射：

```yaml
volumes:
  - /path/to/ssh/keys:/root/.ssh:ro
```

然后在参数配置中设置密钥路径为 `/root/.ssh/your_key_file`。

---

## 9. 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Element Plus + Vite |
| 后端 | Python 3.11 + FastAPI + Uvicorn |
| 数据库 | MySQL 9.6 |
| SSH | Paramiko |
| Web 服务器 | Nginx（反向代理） |
| 容器 | Docker + docker-compose |
