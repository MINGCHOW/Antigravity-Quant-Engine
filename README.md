# Antigravity Quant Engine

> **AI-Powered Quantitative Trading Engine** — A-Share + HK Stock Multi-Source Analysis

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🚀 Core Features

- **8-Layer Data Shield** — efinance → AkShare → Tencent → Qstock → Pytdx → Baostock → Sina → Yahoo Finance
- **Cross-Market** — Full A-Share + HK Stock support with anti-scraping (dynamic UA, circuit breaker)
- **Quant Engine** — MA/EMA/RSI/ATR/MACD/BIAS + symmetric 5-level signals + ATR-driven dynamic stop-loss/take-profit
- **Market Radar** — Bull/Neutral/Bear detection with buffer zones (CN ±2%, HK ±3%)
- **n8n Workflows** — Daily AI analysis (Gemini) → Feishu alerts, position monitoring, heartbeat

## 📂 Structure

```
api/
├── main.py          # FastAPI (5 endpoints)
├── fetcher.py       # 8-Layer data + spot cache + name resolver
├── quant.py         # Technicals, signals, ETF detection
└── __init__.py
workflow/            # n8n workflows (gitignored, contains credentials)
tests/test_quant.py  # Unit tests (9 tests)
Dockerfile           # Cloud deployment
```

## 🛠️ Deploy

```bash
# Docker
docker build -t ag-quant-engine .
docker run -p 8080:8080 -e API_KEY=your_key ag-quant-engine

# Local
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
```

## 📡 API Endpoints

All non-public endpoints require `X-API-Key` header.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | Public | System health + circuit breaker status |
| GET | `/market` | 🔐 | CN + HK market status (Bull/Neutral/Bear) |
| POST | `/analyze_full` | 🔐 | Full analysis: technicals + signal + risk control |
| POST | `/check_positions` | 🔐 | Position check: stop-loss / take-profit / trailing stop |
| POST | `/settle_signals` | 🔐 | Signal settlement: success / fail / timeout |

## 🔄 Version History

| Version | Date | Key Changes |
|---------|------|-------------|
| V14 | 2026-02-24 | P0: settle_signals fix, HK buffer, _last_source, HTTPS, API_KEY security |
| V13 | 2026-02-24 | Audit: support/resistance fix, bull/bear buffer, ERROR branch |
| V12 | 2026-02-24 | Critical: check_positions NameError, lightweight health check |
| V10 | 2026-02-10 | Modular rewrite, MACD, symmetric scoring, ATR risk control |

## 🛡️ Security

- API key authentication on all sensitive endpoints
- Workflow credentials isolated via `.gitignore` (never committed)
- Docker build excludes debug scripts and templates

## ⚖️ Disclaimer

This project is for **research and educational purposes only**. Quantitative trading involves significant financial risk.
