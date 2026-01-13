# Weibo Search Crawler (DrissionPage Hybrid Mode + RQ)

基于 DrissionPage 混合模式和 Python-RQ 解耦架构的微博搜索爬虫系统。

## 特性

- **DrissionPage 混合模式**:
  - **浏览器模式**: 使用真实的 Chromium 实现生成有效的访客 Cookie (SUB/SUBP)。
- **curl_cffi 模式**: 共享浏览器的 Cookie 和 UA，进行高并发数据抓取。
- **RQ 解耦架构**: 分离 `Cookie` 和 `Search` Worker，提升稳定性和扩展性。
- **智能代理**: 集成 IP 代理，支持自动切换与持久化。
- **数据持久化**: Redis (用于去重/缓存) 和 JSONL 日志 (用于持久化) 双重存储。

## 前置要求

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (或者使用 poetry/pip)
- Redis 5.0+
- Google Chrome / Chromium

## 快速开始

### 1. 安装与配置

```bash
# 安装依赖
make install

# 配置环境
cp .env.example .env
# 编辑 .env 填入你的 Redis 和 代理配置
```

### 2. 启动基础设施 (可选)

如果你使用 Docker 运行 Redis:
```bash
make redis-start
```

### 3. 初始化 Cookie 池

在搜索之前，确保 Cookie 池中有有效的 Cookie：
```bash
make fill-pool
```

### 4. 运行搜索

```bash
# 简单搜索
make search KEYWORD="人工智能"
```

### 5. 启动后台 Workers

生产环境建议分开运行 Workers:

```bash
# 启动所有 Worker
make worker-all

# 或分别启动
make worker-cookie
make worker-search
```

## 监控

- **Logs**: 查看 `logs/` 目录下的日志文件。
- **Dashboard**: `make dashboard` 启动 RQ 仪表盘 (http://localhost:9181)。

## License

MIT
