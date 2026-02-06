# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import akshare as ak
import pandas as pd
import datetime
import traceback
import random
import time

app = FastAPI(title="AkShare Quant API", version="6.0")

# --- Models ---

class StockRequest(BaseModel):
    code: str
    price: float
    atr: float
    balance: float = 100000.0
    risk: float = 0.01

# --- Logic (Ported from v6_quant_engine.py) ---

@app.get("/market")
def get_market_context():
    """获取大盘环境数据 (上证指数 + 北向资金)"""
    try:
        # 随机延迟，防止上游风控
        time.sleep(random.uniform(1.0, 3.0))

        # 1. 获取上证指数日线数据 (sh000001)
        index_df = ak.stock_zh_index_daily(symbol="sh000001")
        
        if index_df.empty:
            raise ValueError("无法获取上证指数数据")

        index_df['date'] = pd.to_datetime(index_df['date'])
        index_df = index_df.sort_values('date')
        
        # 计算 MA20
        index_df['MA20'] = index_df['close'].rolling(window=20).mean()
        
        last_row = index_df.iloc[-1]
        last_price = float(last_row['close'])
        last_ma20 = float(last_row['MA20'])
        
        if last_price > last_ma20:
            status = "Bull"
            reason = "上证指数站上 20 日均线，趋势向好"
            sentiment = 80
        else:
            status = "Bear"
            reason = "上证指数跌破 20 日均线，趋势走弱"
            sentiment = 40

        return {
            "market_status": status,
            "market_reason": reason,
            "index_price": last_price,
            "index_ma20": round(last_ma20, 2),
            "sentiment_score": sentiment,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    except Exception as e:
        print(traceback.format_exc())
        return {
            "market_status": "Correction",
            "market_reason": f"System Error: {str(e)}",
            "sentiment_score": 50
        }

@app.post("/stock")
def analyze_stock(req: StockRequest):
    """个股深度分析 + 仓位计算"""
    try:
        # 随机延迟
        time.sleep(random.uniform(1.0, 3.0))

        stock_code = req.code
        is_hk = len(str(stock_code)) == 5
        
        fundamental_info = {
            "pe_ttm": None,
            "market_cap": None,
            "name": stock_code
        }

        # 1. 获取基本面 (A股 Only)
        if not is_hk:
            try:
                clean_code = str(stock_code).replace("sz", "").replace("sh", "")
                info_df = ak.stock_individual_info_em(symbol=clean_code)
                
                def get_val(item_name):
                    rows = info_df[info_df['item'] == item_name]
                    if not rows.empty:
                        return rows.iloc[0]['value']
                    return None

                fundamental_info['pe_ttm'] = get_val('市盈率(TTM)')
                fundamental_info['market_cap'] = get_val('总市值')
                fundamental_info['name'] = get_val('股票简称') or stock_code

            except Exception as e:
                print(f"Warning: Fundamental fetch failed for {stock_code}: {e}")

        # 2. 仓位计算
        atr_value = req.atr if req.atr > 0 else req.price * 0.03
        
        stop_loss_width = 2.0 * atr_value
        if is_hk:
            stop_loss_width = 2.5 * atr_value

        risk_amount = req.balance * req.risk
        shares_raw = risk_amount / stop_loss_width
        
        lot_size = 100
        position_shares = int(shares_raw // lot_size) * lot_size
        
        cost = position_shares * req.price
        if cost > req.balance:
            position_shares = int((req.balance // req.price) // lot_size) * lot_size
            cost = position_shares * req.price

        # 3. 预警
        warnings = []
        pe = fundamental_info.get('pe_ttm')
        if pe and isinstance(pe, (int, float)):
            if pe > 80:
                warnings.append("⚠️ 高估值预警: PE(TTM) > 80")
            elif pe < 0:
                warnings.append("⚠️ 业绩亏损预警: PE为负")

        return {
            "stock_name": fundamental_info['name'],
            "pe_ttm": pe,
            "market_cap": fundamental_info['market_cap'],
            "risk_analysis": {
                "account_balance": req.balance,
                "risk_per_trade": req.risk,
                "suggested_position": position_shares,
                "estimated_cost": cost
            },
            "warnings": warnings
        }

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "ok", "service": "AkShare API V6.0"}
