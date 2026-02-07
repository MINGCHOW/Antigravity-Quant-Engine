# 🚀 AKShare 量化分析引擎 (AH Stock Titan V9.3)

<div align="center">

**A股港股智能分析系统 | N8N + FastAPI + Gemini AI**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![n8n](https://img.shields.io/badge/n8n-Workflow-orange.svg)](https://n8n.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 📋 项目简介

本项目是一套完整的**A股/港股量化分析系统**，集成了：

- 🔥 **8层数据源容错系统** - 自动切换 6 个数据源，确保数据获取稳定
- 🤖 **AI 智能分析** - Google Gemini 生成专业交易建议
- 📊 **N8N 工作流自动化** - 定时执行、飞书推送、数据存储
- 📈 **全栈技术指标** - MA/EMA/RSI/ATR/MACD 等 20+ 指标

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        N8N 工作流                                │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
│  │ 定时触发  │ → │ 读取股票  │ → │ API分析   │ → │ Gemini AI    │ │
│  │ 17:30    │   │ 列表      │   │ 请求      │   │ 智能建议     │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────┘ │
│                                      ↓                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
│  │ 循环控制  │ ← │ Wait 35s │ ← │ 飞书推送  │ ← │ 飞书写入     │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                               ↓ HTTP
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI 分析引擎                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              8-Layer Data Source Shield                   │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │  │
│  │  │efinance │ │ akshare │ │ tencent │ │ qstock  │        │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │  │
│  │  │  pytdx  │ │baostock │ │  sina   │ │  yahoo  │        │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                               ↓                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 技术指标计算 | 信号生成 | 风控参数 | 止损止盈 | 仓位建议    ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 项目结构

```
akshare-quant-engine/
├── api/
│   └── akshare_api.py      # FastAPI 分析引擎（核心）
├── workflow/
│   └── AH Stock V9.1 Titan.json  # N8N 工作流（本地保存）
├── Dockerfile               # Docker 部署配置
├── requirements.txt         # Python 依赖
├── .gitignore              # Git 忽略规则
└── README.md               # 项目文档
```

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/MINGCHOW/akshare-quant-engine.git
cd akshare-quant-engine
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动 API 服务

```bash
# 本地运行
uvicorn api.akshare_api:app --host 0.0.0.0 --port 8000 --reload

# 或 Docker 运行
docker build -t akshare-api .
docker run -p 8000:8000 akshare-api
```

### 4. 导入 N8N 工作流

1. 打开 N8N 控制台
2. 导入 `workflow/AH Stock V9.1 Titan.json`
3. 配置以下凭证：
   - Google Sheets OAuth2
   - Feishu API
   - Google Gemini API

---

## 🔌 API 接口

### 获取大盘状态

```bash
GET /market
```

**响应示例**：
```json
{
  "market_status": "Bull",
  "sh_index": 3250.12,
  "sz_index": 10821.45,
  "hs_index": 20156.78
}
```

### 全栈分析

```bash
POST /analyze_full
Content-Type: application/json

{
  "code": "601958",
  "balance": 100000,
  "risk": 0.01
}
```

**响应示例**：
```json
{
  "date": "2026-02-07",
  "market": "CN",
  "code": "601958",
  "name": "金钼股份",
  "technical": {
    "current_price": 19.56,
    "ma5": 19.31,
    "ma20": 19.82,
    "rsi14": 50.44,
    "atr14": 1.45,
    "volume_ratio": 0.67,
    "ma_alignment": "趋势不明 ⚖️"
  },
  "signal": {
    "signal": "观望 😶",
    "trend_score": 40,
    "stop_loss": 16.66,
    "take_profit": 23.91,
    "signal_reasons": ["跌破月线", "缩量整理"]
  },
  "risk_ctrl": {
    "suggested_position": 300
  }
}
```

---

## 📊 技术指标说明

| 指标 | 计算方法 | 用途 |
|------|----------|------|
| MA5/10/20/60 | 简单移动平均 | 趋势判断 |
| EMA13/26 | 指数移动平均 | MACD 基础 |
| RSI(14) | 相对强弱指数 | 超买超卖 |
| ATR(14) | 平均真实波幅 | 止损设置 |
| BIAS | 乖离率 | 回归判断 |
| 量比 | 当日量/5日均量 | 量能分析 |

---

## 🛡️ 8层数据源容错

系统按以下优先级自动切换数据源：

| 优先级 | 数据源 | 支持市场 | 特点 |
|--------|--------|----------|------|
| 1 | efinance | A股/港股 | 速度快，稳定 |
| 2 | akshare | A股/港股 | 数据全，官方维护 |
| 3 | tencent | A股/港股 | 实时性好 |
| 4 | qstock | A股 | 同花顺数据源 |
| 5 | pytdx | A股 | 通达信协议 |
| 6 | baostock | A股 | 历史数据优 |
| 7 | sina | A股/港股 | 老牌数据源 |
| 8 | yahoo | 港股 | 国际数据 |

---

## 🤖 AI 分析说明

工作流使用 **Google Gemini** 进行智能分析：

- **模型**: `gemini-3-pro-image-preview`
- **温度**: 0.3（稳定输出）
- **输出格式**: 结构化 JSON

### 输出示例

```json
{
  "stock_name": "金钼股份",
  "analysis_summary": "技术面偏多但受大盘拖累，建议轻仓观望",
  "trend_prediction": "中性偏多",
  "sentiment_score": 62,
  "decision_type": "hold",
  "operation_advice": "可小仓位试探性布局，严格止损"
}
```

---

## 📱 飞书推送

分析结果自动推送至飞书：

- **卡片消息** - 彩色卡片展示核心信息
- **多维表格** - 完整数据存储，支持筛选分析
- **颜色编码**：
  - 🟦 青色: 强烈买入
  - 🟩 绿色: 买入
  - 🟦 蓝色: 观望
  - 🟧 橙色: 减仓
  - 🟥 红色: 卖出

---

## ⚙️ 环境变量

| 变量名 | 说明 | 必需 |
|--------|------|------|
| `TAVILY_API_KEY` | Tavily 新闻搜索 API Key | 否 |

---

## 🐳 Docker 部署

```bash
# 构建镜像
docker build -t akshare-api .

# 运行容器
docker run -d \
  --name akshare-api \
  -p 8000:8000 \
  -e TAVILY_API_KEY=your_key \
  akshare-api
```

---

## 📝 更新日志

### V9.3 Titan (2026-02-07)
- ✅ 修复数据流问题：提示词构建正确读取 API 数据
- ✅ 修复飞书字段类型：数值转字符串
- ✅ 新增 ETF 识别：自动检测港股/A股 ETF
- ✅ 新增 JSON 自动修复：三层解析策略
- ✅ 增强卡片颜色：8种颜色 + 动态 Emoji
- ✅ API Key 安全：使用环境变量
- ✅ Wait 优化：35秒避免 API 限流

### V9.0 (2026-02-06)
- 8层数据源容错系统
- 全栈技术指标计算
- N8N 手动循环控制器
- Gemini AI 集成

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

<div align="center">

**Made with ❤️ by MINGCHOW**

</div>
