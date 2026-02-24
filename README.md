# Antigravity Quant Engine (V13)

> **AI-Powered Quantitative Trading Engine**
> *A-Share + HK Stock Multi-Source Analysis System*

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

模块化、多数据源的量化交易引擎，集成 **AkShare**、**腾讯**、**Yahoo Finance** 等 8 层数据源，结合 **AI Agent** 提供实时行情分析、信号生成和自动化风控。

---

## 🚀 核心特性

### 📊 多源数据获取 (8-Layer Shield)
| 层级 | 数据源 | 协议 | 特点 |
|------|--------|------|------|
| 0 | efinance | API | 最快 (东方财富) |
| 1 | AkShare | HTTP | 主力 (东方财富爬虫) |
| 2 | 腾讯财经 | HTTPS | 高可用 |
| 3 | Qstock | HTTP | 同花顺独立源 |
| 4 | Pytdx | TCP | 抗封锁 (多服务器) |
| 5 | Baostock | API | 官方备用 |
| 6 | 新浪财经 | HTTP | 传统源 |
| 7 | Yahoo Finance | HTTPS | 国际兜底 (HK+CN) |

- **跨市场**: 完整支持 **A 股** 和 **港股**
- **反爬虫**: 智能重试、动态 UA、熔断器
- **实时缓存**: Spot 数据 30 秒 TTL 缓存，O(1) 查找

### 📈 量化分析核心 (Titan V13)
- **对称评分体系**: 买卖平衡的 5 级信号 (强烈买入/买入/观望/减仓/卖出)
- **技术指标**: MA(5/10/20/60)、EMA(13/26)、RSI(14)、ATR(14)、MACD、BIAS、量比
- **动态风控**: ATR 驱动止损/止盈 (2:1 盈亏比)，最大止损 10-15%
- **市场判断**: 沪指 + 恒指双市场状态 (Bull/Neutral/Bear/Crash)，±2% 缓冲区防抽搐
- **支撑/阻力**: 取最近支撑位 (保护资金) + 最近阻力位 (务实目标)
- **ETF 精确检测**: 港股代码区间 + A 股前缀匹配

### 🤖 工作流自动化 (n8n)
- **每日分析**: 每只股票经 API → AI (Gemini) → 飞书多维表格 → 飞书卡片通知
- **持仓监控**: 自动检查止损/止盈/移动止损，ERROR 时发红色告警
- **系统心跳**: 轻量级 Spot API 探针，异常时告警

---

## 📂 项目结构

```text
├─ api/
│  ├─ main.py       # FastAPI 入口 (5 个端点)
│  ├─ fetcher.py    # 数据层 (8-Layer + Spot Cache + Name Resolver)
│  ├─ quant.py      # 量化核心 (指标/信号/ETF)
│  └─ __init__.py
├─ workflow/
│  ├─ stock_analysis.json      # 每日 AI 分析工作流
│  ├─ monitor_heartbeat.json   # 系统心跳监控
│  └─ monitor_position.json    # 持仓风控监控
├─ tests/
│  └─ test_quant.py # 单元测试
├─ Dockerfile       # Cloud Run / Docker 部署
├─ .dockerignore    # 排除调试/模板文件
└─ requirements.txt # 依赖锁定 (12 packages)
```

---

## 🛠️ 部署

### Docker (推荐)

```bash
# 构建
docker build -t ag-quant-engine .

# 运行
docker run -p 8080:8080 -e API_KEY=your_secure_key ag-quant-engine
```

### 本地开发

```bash
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## 📡 API 文档

所有非公开端点需要 `X-API-Key` Header 认证。

### `GET /health` (公开)
系统健康检查 (V12 轻量级 Spot API 探针)

```json
{
  "status": "healthy",
  "latency_ms": 1200,
  "checks": {
    "data_source": {"status": "ok", "rows": 5200},
    "circuit_breaker": {"error_count": 0, "is_open": false}
  }
}
```

### `GET /market` 🔐
大盘状态 (A股 + 港股 + 涨跌家数)

```json
{
  "market_status": "Bull",
  "cn_status": "Bull",
  "hk_status": "Neutral",
  "up_count": 3200,
  "down_count": 1500,
  "is_frozen": false
}
```

### `POST /analyze_full` 🔐
全栈分析 (技术指标 + 信号 + 风控)

```json
// Request
{
  "code": "00700",
  "market": "HK",      // V13: 可选，显式指定市场
  "balance": 100000,
  "risk": 0.01
}

// Response
{
  "code": "00700",
  "market": "HK",
  "name": "腾讯控股",
  "signal_type": "买入 🟢",
  "trend_score": 72,
  "current_price": 385.20,
  "stop_loss": 365.00,
  "take_profit": 425.00,
  "technical": { "rsi14": 55.3, "macd_cross": "golden", ... },
  "risk_ctrl": { "suggested_position": 200 }
}
```

### `POST /check_positions` 🔐
持仓检查 (止损/止盈/移动止损)

```json
// Request
{
  "positions": [
    {
      "code": "00700",
      "market": "HK",
      "buy_price": 370.0,
      "current_stop": 355.0,
      "target_price": 420.0,
      "shares": 200,
      "record_id": "rec_xxx"
    }
  ]
}

// Response
{
  "positions": [
    {
      "code": "00700",
      "action": "HOLD",
      "current_price": 385.20,
      "new_stop": 362.50,
      "pnl_percent": 4.11,
      "reason": "📈 上调止损 (355.00 → 362.50)"
    }
  ]
}
```

### `POST /settle_signals` 🔐
信号结算 (V13: 使用实时价格)

---

## 🔄 版本历史

| 版本  | 日期 | 主要变更 |
|-------|------|----------|
| V13   | 2026-02-24 | 专业审查: 支撑/阻力修正, 牛熊缓冲区, ERROR分支, 市场参数 |
| V12   | 2026-02-24 | 致命修复: `check_positions` NameError, 轻量心跳, CN名称 |
| V11.1 | 2026-02-12 | 子目录隔离 |
| V11.0 | 2026-02-12 | GitHub 结构标准化 |
| V10.4 | 2026-02-12 | Docker Hub 兼容 |
| V10.3 | 2026-02-11 | Spot-Only 降级, HK Ticker 格式修复 |
| V10.2 | 2026-02-11 | 多源 HK 价格, Yahoo 备用, 名称增强 |
| V10.1 | 2026-02-11 | HK 指数超时修复, Spot 实时价格 |
| V10.0 | 2026-02-10 | 模块化重构, MACD, 对称评分, ATR 风控 |

---

## 🛡️ 安全

- **API 认证**: 所有关键端点通过 `X-API-Key` 保护
- **隐私隔离**: 工作流敏感凭证通过 Template 文件隔离
- **Docker 安全**: `.dockerignore` 排除调试脚本和模板文件

---

## ⚖️ 免责声明

本项目仅用于**研究和学习目的**。量化交易涉及重大金融风险，使用者需自行承担风险。
