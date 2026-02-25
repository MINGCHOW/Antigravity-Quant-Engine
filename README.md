# Antigravity Quant Engine

> **AI-Powered Stock Analysis & Position Management** — A-Share + HK Market

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-green)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)

---

## Overview

Quantitative analysis engine with multi-source data fetching, technical indicator computation, and automated n8n workflows for daily stock analysis, position monitoring, and signal settlement.

## Architecture

```
api/
├── main.py       # FastAPI — 5 endpoints (analyze, positions, signals, market, health)
├── fetcher.py    # 8-layer data fallback + realtime price + stock name resolver
└── quant.py      # Technicals (MA/RSI/ATR/MACD/BIAS) + signal generation + risk control
workflow/         # n8n workflows (gitignored — contains credentials)
tests/            # Unit tests
```

### Data Fetch Priority

`efinance → AkShare → Tencent → Qstock → Pytdx → Baostock → Sina → Yahoo Finance`

Each layer is tried in order with circuit breaker protection. If a source fails repeatedly, it is temporarily disabled.

## API

All non-public endpoints require `X-API-Key` header.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health + data source availability |
| `GET` | `/market` | CN + HK market regime (Bull / Neutral / Bear) |
| `POST` | `/analyze_full` | Full technical analysis + signal + risk control |
| `POST` | `/check_positions` | Position monitoring: trailing stop, take-profit, P&L |
| `POST` | `/settle_signals` | Signal settlement: success / fail / timeout + auto-writeback |

## Workflows (n8n)

| Workflow | Schedule | Function |
|----------|----------|----------|
| `stock_analysis` | Weekdays 16:10 | Analyze watchlist → AI summary (Gemini) → write to Feishu + notify |
| `monitor_position` | Weekdays 16:40 | Check positions → trailing stop → P&L writeback → sell/hold alerts |
| `monitor_position` (signal branch) | Weekdays 16:40 | Settle open signals → auto-writeback result/P&L/date to Feishu |
| `monitor_heartbeat` | Daily 10:00 | API health check → Feishu alert on failure |

## Deploy

```bash
# Docker
docker build -t ag-quant-engine .
docker run -p 8080:8080 -e API_KEY=your_key ag-quant-engine

# Local
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
```

## Security

- API key authentication on all sensitive endpoints
- Workflow files gitignored (contain Feishu credentials, API keys, user IDs)
- Docker build excludes debug scripts and workflow files

## Disclaimer

This project is for **research and educational purposes only**. Quantitative trading involves significant financial risk.
