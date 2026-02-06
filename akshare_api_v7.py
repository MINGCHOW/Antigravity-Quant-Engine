# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import akshare as ak
import pandas as pd
import requests
import datetime
import traceback
import random
import time
import json

# Try importing yfinance for fallback
try:
    import yfinance as yf
except ImportError:
    yf = None

app = FastAPI(title="AkShare Quant API V7.1 (Hybrid)", version="7.1")

# --- Models ---
class AnalyzeRequest(BaseModel):
    code: str
    balance: float = 100000.0
    risk: float = 0.01

# --- Data Fetcher with Fallback ---
class DataFetcher:
    @staticmethod
    def get_a_share_history(code: str):
        """A股 K线获取 (Priority: AkShare -> Tencent)"""
        symbol = code.replace("sh", "").replace("sz", "")
        # 1. Try AkShare (EastMoney source usually)
        try:
            # qfq: 前复权
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
            if not df.empty:
                # Standardize columns: date, open, close, high, low, volume
                df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close', 
                                   '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
                df['date'] = pd.to_datetime(df['date'])
                return df
        except Exception as e:
            print(f"[Fallback] AkShare A-Share failed for {code}: {e}")

        # 2. Fallback: Tencent Interface
        try:
            # Tencent's legacy interface for day k-line
            # This is a bit complex to parse, usually returns "date open close high low volume..."
            market_prefix = "sh" if code.startswith("6") else "sz"
            full_code = f"{market_prefix}{symbol}"
            url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={full_code},day,,,320,qfq" 
            r = requests.get(url, timeout=5)
            data = r.json()
            k_data = data['data'][full_code]['day'] # List of lists
            # ["2023-01-01", "open", "close", "high", "low", "vol"]
            df = pd.DataFrame(k_data, columns=['date', 'open', 'close', 'high', 'low', 'volume', 'unknown'])
            df = df[['date', 'open', 'close', 'high', 'low', 'volume']]
            df['date'] = pd.to_datetime(df['date'])
            for col in ['open', 'close', 'high', 'low', 'volume']:
                df[col] = pd.to_numeric(df[col])
            print(f"[Fallback] Recovered {code} using Tencent.")
            return df
        except Exception as e:
            print(f"[Error] All A-Share sources failed for {code}: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_hk_share_history(code: str):
        """港股 K线获取 (Priority: AkShare -> Yahoo)"""
        # AkShare HK symbol usually 5 digits like "00700"
        symbol = code if len(str(code)) == 5 else f"{int(code):05d}"
        
        # 1. Try AkShare
        try:
            df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                return df
        except Exception as e:
             print(f"[Fallback] AkShare HK failed for {code}: {e}")

        # 2. Fallback: Yahoo Finance
        try:
            if yf:
                # Yahoo symbol: 0700.HK
                y_symbol = f"{int(symbol):04d}.HK" 
                ticker = yf.Ticker(y_symbol)
                df = ticker.history(period="1y")
                df.reset_index(inplace=True)
                df.rename(columns={'Date': 'date', 'Open': 'open', 'Close': 'close', 
                                   'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)
                # Convert timezone aware to naive
                df['date'] = df['date'].dt.tz_localize(None)
                print(f"[Fallback] Recovered {code} using Yahoo.")
                return df
        except Exception as e:
            print(f"[Error] All HK sources failed for {code}: {e}")
            return pd.DataFrame()

# --- Quant Logic ---
def calculate_technicals(df: pd.DataFrame):
    if df.empty: 
        return {}
    
    # Sort
    df = df.sort_values('date')
    closes = df['close']
    highs = df['high']
    lows = df['low']
    
    # MAs
    ma5 = closes.rolling(5).mean().iloc[-1]
    ma10 = closes.rolling(10).mean().iloc[-1]
    ma20 = closes.rolling(20).mean().iloc[-1]
    ma60 = closes.rolling(60).mean().iloc[-1]
    
    # EMAs
    ema13 = closes.ewm(span=13, adjust=False).mean().iloc[-1]
    ema26 = closes.ewm(span=26, adjust=False).mean().iloc[-1]
    
    # RSI
    delta = closes.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi14 = 100 - (100 / (1 + rs)).iloc[-1]
    
    # ATR
    # TR = Max(H-L, Abs(H-Cp), Abs(L-Cp))
    prev_close = closes.shift(1)
    tr1 = highs - lows
    tr2 = (highs - prev_close).abs()
    tr3 = (lows - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean().iloc[-1]

    # Bias
    current_price = closes.iloc[-1]
    bias_ma5 = ((current_price - ma5) / ma5) * 100 if ma5 else 0

    # Volume Ratio
    if 'volume' in df.columns and len(df) > 5:
        vol = df['volume']
        avg_vol5 = vol.iloc[-6:-1].mean() # Previous 5 days
        curr_vol = vol.iloc[-1]
        volume_ratio = round(curr_vol / avg_vol5, 2) if avg_vol5 > 0 else 1.0
    else:
        volume_ratio = 1.0

    # MA Alignment
    ma_alignment = "多头排列 📈" if (ma5 > ma10 and ma10 > ma20) else "趋势不明 ⚖️"
    if ema13 < ema26: ma_alignment = "趋势向下 📉"

    return {
        "current_price": round(current_price, 2),
        "ma5": round(ma5, 2), "ma10": round(ma10, 2), "ma20": round(ma20, 2), "ma60": round(ma60, 2),
        "ema13": round(ema13, 2), "ema26": round(ema26, 2),
        "rsi14": round(rsi14, 2),
        "atr14": round(atr14, 3),
        "bias_ma5": round(bias_ma5, 2),
        "volume_ratio": volume_ratio,
        "ma_alignment": ma_alignment,
        "trend_score": 0 # Placeholder
    }

def generate_signal(tech_data, is_hk=False):
    # Unpack
    price = tech_data.get('current_price', 0)
    ma5 = tech_data.get('ma5', 0)
    ma10 = tech_data.get('ma10', 0)
    ma20 = tech_data.get('ma20', 0)
    ema13 = tech_data.get('ema13', 0)
    ema26 = tech_data.get('ema26', 0)
    atr = tech_data.get('atr14', 0)
    
    signal = "观望 ⚪"
    reasons = []
    
    # Trend Score
    score = 50
    if price > ma20: score += 10
    if ma5 > ma10 and ma10 > ma20: score += 20
    if ema13 > ema26: score += 20
    
    # VCP / Consolidation Breakout
    # Logic: Price > MAs, MAs aligned, recent volatility contraction (mock check)
    if price > ma20 and ma5 > ma20:
        if abs(ma5 - ma20)/ma20 < 0.05: # Squeeze
            signal = "强烈买入 🚀"
            reasons.append("均线粘合突破 (VCP特征)")
        else:
            signal = "买入 🟢"
            reasons.append("多头趋势")
            
    # Stop Loss Calculation
    multiplier = 2.5 if is_hk else 2.0
    stop_loss = price - (multiplier * atr)
    risk_per_share = price - stop_loss
    take_profit = price + (1.5 * risk_per_share)

    # Support / Resistance (Simple Logic)
    support_level = ma20
    resistance_level = price * 1.05 # Simple placeholder if no recent high logic
    
    return {
        "signal": signal,
        "signal_reasons": reasons,
        "trend_score": score,
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "support_level": round(support_level, 2),
        "resistance_level": round(resistance_level, 2)
    }

# --- Endpoints ---

@app.get("/market")
def get_market_context():
    """V6 Logic for Market Context"""
    try:
        # Fallback Logic for Index could go here, but index is usually stable
        index_df = ak.stock_zh_index_daily(symbol="sh000001")
        if index_df.empty: raise ValueError("Index Data Empty")
        
        index_df['close'] = pd.to_numeric(index_df['close'])
        ma20 = index_df['close'].rolling(20).mean().iloc[-1]
        price = index_df['close'].iloc[-1]
        
        status = "Bull" if price > ma20 else "Bear"
        
        return {
            "market_status": status, 
            "index_price": price,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(e)
        return {"market_status": "Correction", "error": str(e)}

@app.post("/analyze_full")
def analyze_full(req: AnalyzeRequest):
    """V7 Full Stack Analysis"""
    try:
        code = req.code
        # Identify Market
        is_hk = len(str(code)) == 5
        
        # 1. Fetch History (Hybrid)
        if is_hk:
            df = DataFetcher.get_hk_share_history(code)
            market = "HK"
        else:
            df = DataFetcher.get_a_share_history(code)
            market = "CN"
            
        if df.empty:
            return {"error": "No Data found", "code": code}
            
        # 2. Tech Calc
        tech = calculate_technicals(df)
        
        # 3. Signal & Risk
        sig = generate_signal(tech, is_hk)
        
        # 4. Position Sizing
        risk_per_share = tech['current_price'] - sig['stop_loss']
        if risk_per_share <= 0: risk_per_share = tech['atr14'] # Safety
        
        account_risk_money = req.balance * req.risk
        suggested_shares = int(account_risk_money / risk_per_share / 100) * 100
        if suggested_shares < 100: suggested_shares = 0
        
        # 5. Base Info (Optional AkShare call for Name/PE)
        name = code
        pe = 0
        try:
             # Fast fundamental check (skip if too slow)
             pass 
        except: pass

        # Compile Result for n8n/AI
        return {
            "code": code,
            "name": name,
            "market": market,
            "technical": tech,
            "signal": sig,
            "risk_ctrl": {
                "suggested_position": suggested_shares,
                "risk_money": account_risk_money
            },
            "prompt_data": { # Pre-formatted strings for AI Prompt
                "price_info": f"现价: {tech['current_price']}, MA20: {tech['ma20']}",
                "risk_info": f"止损: {sig['stop_loss']}, ATR: {tech['atr14']}"
            }
        }

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
