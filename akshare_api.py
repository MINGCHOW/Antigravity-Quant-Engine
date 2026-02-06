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
import logging
import math # Added for NaN checks

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try importing optional libraries
try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from pytdx.hq import TdxHq_API
    tdx_api = TdxHq_API()
except ImportError:
    tdx_api = None

try:
    import baostock as bs
    # Init Baostock on startup
    bs.login()
except ImportError:
    bs = None

try:
    import qstock as qs
except ImportError:
    qs = None

try:
    import efinance as ef
except ImportError:
    ef = None

from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

app = FastAPI(title="AkShare Quant API V9.0 (Titan Edition)", version="9.0")

# --- Constants ---
# Dynamic User-Agent Generator
ua = UserAgent()

def get_headers():
    return {
        "User-Agent": ua.random,
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

# --- Models ---
class AnalyzeRequest(BaseModel):
    code: str
    balance: float = 100000.0
    risk: float = 0.01

# --- Data Fetcher with 8-Layer Fallback (V9.0 Titan) ---
class DataFetcher:
    """
    V9.0 Titan Hierarchy:
    0. efinance (EastMoney API) - Priority 0 (Fastest/Stable)
    1. AkShare (EastMoney Scraper) - Priority 1
    2. Tencent (HTTP) - High Availability
    3. Qstock (Tonghuashun) - Independent Source
    4. Pytdx (TCP) - Anti-Blocking
    5. Baostock (Official) - Backup
    6. Sina (Legacy) - Backup
    7. Yahoo (International) - Last Resort
    """
    @staticmethod
    def _clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names and types (V8.6 Logic)"""
        try:
            # Normalize efinance/qstock columns if needed
            if '日期' in df.columns: df.rename(columns={'日期': 'date'}, inplace=True)
            if '开盘' in df.columns: df.rename(columns={'开盘': 'open'}, inplace=True)
            if '收盘' in df.columns: df.rename(columns={'收盘': 'close'}, inplace=True)
            if '最高' in df.columns: df.rename(columns={'最高': 'high'}, inplace=True)
            if '最低' in df.columns: df.rename(columns={'最低': 'low'}, inplace=True)
            if '成交量' in df.columns: df.rename(columns={'成交量': 'volume'}, inplace=True)
            if '成交' in df.columns: df.rename(columns={'成交': 'volume'}, inplace=True)

            # Ensure proper columns exist
            required_cols = {'date', 'open', 'close', 'high', 'low', 'volume'}
            if not required_cols.issubset(df.columns):
                return pd.DataFrame() 

            # Standardize date
            df['date'] = pd.to_datetime(df['date'])
            
            # Enforce numeric types (Critical for calculation safety)
            for col in ['open', 'close', 'high', 'low', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Drop NaNs created by coercion
            df.dropna(subset=['open', 'close'], inplace=True)
            return df
        except:
            return pd.DataFrame()

    @staticmethod
    def get_a_share_history(code: str, retries=2):
        time.sleep(random.uniform(0.5, 1.5)) 
        
        symbol = code.replace("sh", "").replace("sz", "")
        market_prefix = "sh" if code.startswith("6") else "sz"
        
        # 0. efinance (Priority 0)
        if ef:
            try:
                logger.info(f"Attempting efinance (#0) for {code}...")
                # efinance uses 6-digit code
                df = ef.stock.get_quote_history(symbol)
                if not df.empty and len(df) > 30:
                    return DataFetcher._clean_data(df)
            except Exception as e:
                logger.warning(f"efinance failed: {e}")

        # 1. AkShare (EastMoney)
        for attempt in range(retries):
            try:
                logger.info(f"Attempting AkShare (#1) for {code}...")
                df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
                if not df.empty and len(df) > 30:
                    df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close', 
                                       '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
                    return DataFetcher._clean_data(df)
            except Exception as e:
                logger.warning(f"AkShare failed: {e}")
                time.sleep(1.0) 

        # 2. Tencent (HTTP)
        try:
            logger.info(f"Attempting Tencent (#2) Fallback...")
            full_code = f"{market_prefix}{symbol}"
            url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={full_code},day,,,320,qfq" 
            r = requests.get(url, headers=get_headers(), timeout=8)
            data = r.json()
            k_data = data['data'][full_code]['day']
            df = pd.DataFrame(k_data, columns=['date', 'open', 'close', 'high', 'low', 'volume', 'unknown'])
            df = df[['date', 'open', 'close', 'high', 'low', 'volume']]
            return DataFetcher._clean_data(df)
        except Exception as e:
            logger.warning(f"Tencent failed: {e}")

        # 3. Qstock (Tonghuashun)
        if qs:
            try:
                logger.info(f"Attempting Qstock-THS (#3) Fallback...")
                df = qs.get_data(code_list=[code], start='20240101', end=datetime.date.today().strftime('%Y%m%d'), freq='d')
                if not df.empty:
                    if 'date' not in df.columns and isinstance(df.index, pd.DatetimeIndex):
                        df.reset_index(inplace=True)
                        df.rename(columns={'index': 'date'}, inplace=True)
                    
                    # Try renaming standard Chinese columns
                    df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close', 
                                       '最高': 'high', '最低': 'low', '成交量': 'volume', '成交': 'volume'}, inplace=True)
                    
                    return DataFetcher._clean_data(df[['date', 'open', 'close', 'high', 'low', 'volume']])
            except Exception as e:
                logger.warning(f"Qstock failed: {e}")

        # 4. Pytdx (TCP) - Thread Safe Version
        # Note: Do not use global tdx_api instance for concurrency safety
        try:
            from pytdx.hq import TdxHq_API
            local_tdx = TdxHq_API()
            logger.info(f"Attempting Pytdx (#4 TCP) Fallback...")
            with local_tdx.connect('119.147.212.81', 7709): 
                market_code = 1 if code.startswith("6") else 0
                data = local_tdx.get_security_bars(9, market_code, symbol, 0, 100)
                if data:
                    df = local_tdx.to_df(data)
                    df.rename(columns={'datetime': 'date', 'vol': 'volume'}, inplace=True)
                    return DataFetcher._clean_data(df[['date', 'open', 'close', 'high', 'low', 'volume']])
        except Exception as e:
             logger.warning(f"Pytdx failed: {e}")

        # 5. Baostock (Official)
        if bs:
            try:
                logger.info(f"Attempting Baostock (#5) Fallback...")
                rs = bs.query_history_k_data_plus(f"{market_prefix}.{symbol}",
                    "date,open,high,low,close,volume",
                    start_date=(datetime.date.today() - datetime.timedelta(days=365)).strftime('%Y-%m-%d'), 
                    end_date=datetime.date.today().strftime('%Y-%m-%d'),
                    frequency="d", adjustflag="1")
                
                data_list = []
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())
                
                if data_list:
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    return DataFetcher._clean_data(df)
            except Exception as e:
                logger.error(f"Baostock failed: {e}")

        # 6. Sina (Legacy)
        try:
            logger.info(f"Attempting Sina (#6) Fallback...")
            sina_symbol = f"{market_prefix}{symbol}"
            df = ak.stock_zh_a_daily(symbol=sina_symbol, adjust="qfq")
            if not df.empty:
                return DataFetcher._clean_data(df)
        except Exception as e:
            logger.error(f"Sina failed: {e}")

        # 7. Yahoo Finance
        if yf:
            try:
                logger.info(f"Attempting Yahoo (#7) Fallback...")
                suffix = ".SS" if code.startswith("6") else ".SZ"
                y_symbol = f"{symbol}{suffix}"
                ticker = yf.Ticker(y_symbol)
                df = ticker.history(period="1y")
                
                if not df.empty:
                    df.reset_index(inplace=True)
                    df.rename(columns={'Date': 'date', 'Open': 'open', 'Close': 'close', 
                                       'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)
                    df['date'] = df['date'].dt.tz_localize(None)
                    return DataFetcher._clean_data(df)
            except Exception as e:
                logger.warning(f"Yahoo failed: {e}")

        return pd.DataFrame()


    @staticmethod
    def get_hk_share_history(code: str):
        try:
            time.sleep(random.uniform(0.5, 1.5)) 
            clean_code = str(code).strip().upper().replace("HK", "")
            if not clean_code.isdigit():
                 # Handle cases like "00700" -> "00700" (fine)
                 # Handle cases like "HK00700" -> "00700" (fine)
                 # Handle garbage -> return empty
                 logger.warning(f"Invalid HK code format: {code}")
                 return pd.DataFrame()

            symbol = f"{int(clean_code):05d}" # Standardize to 5 chars (e.g. 00700)
            
            # 1. Try AkShare
            try:
                df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
                if not df.empty:
                    df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close', 
                                       '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
                    return DataFetcher._clean_data(df)
            except Exception as e:
                logger.warning(f"AkShare HK failed for {code}: {e}")

            # 2. Try Yahoo
            if yf:
                try:
                    # Yahoo needs 4 digits + .HK usually, or 5 if it's 5 digits. 
                    # Most HK stocks on Yahoo are 4 digits .HK (e.g. 0700.HK)
                    # Use safe int conversion
                    y_symbol = f"{int(clean_code):04d}.HK" 
                    ticker = yf.Ticker(y_symbol)
                    df = ticker.history(period="1y")
                    
                    if not df.empty:
                        df.reset_index(inplace=True)
                        df.rename(columns={'Date': 'date', 'Open': 'open', 'Close': 'close', 
                                           'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)
                        df['date'] = df['date'].dt.tz_localize(None)
                        return DataFetcher._clean_data(df)
                except Exception as e:
                    logger.warning(f"Yahoo HK failed for {code}: {e}")
        except:
             pass
            
        return pd.DataFrame()

# --- Quant Logic (V8.6 Global NaN Protection) ---
def safe_round(val, decimals=2):
    try:
        if pd.isna(val) or val == float('inf') or val == float('-inf'):
            return 0.0
        return round(float(val), decimals)
    except:
        return 0.0

def calculate_technicals(df: pd.DataFrame):
    if df.empty: return {}
    df = df.sort_values('date')
    closes = df['close']
    highs = df['high']
    lows = df['low']
    volumes = df['volume']
    
    # Ensure sufficient data
    if len(df) < 5: return {}

    ma5 = closes.rolling(5).mean().iloc[-1]
    ma10 = closes.rolling(10).mean().iloc[-1]
    ma20 = closes.rolling(20).mean().iloc[-1]
    ma60 = closes.rolling(60).mean().iloc[-1]
    ema13 = closes.ewm(span=13, adjust=False).mean().iloc[-1]
    ema26 = closes.ewm(span=26, adjust=False).mean().iloc[-1]
    
    delta = closes.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    
    # Safe RSI calc
    loss_val = loss.iloc[-1]
    if loss_val == 0:
        rsi14 = 100.0 if gain.iloc[-1] > 0 else 50.0 
    else:
        rs = gain.iloc[-1] / loss_val
        rsi14 = 100 - (100 / (1 + rs))
    
    tr1 = highs - lows
    tr2 = (highs - closes.shift(1)).abs()
    tr3 = (lows - closes.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean().iloc[-1]

    current_price = closes.iloc[-1]
    # Safe Bias calc
    bias_ma5 = ((current_price - ma5) / ma5) * 100 if (ma5 and ma5 != 0) else 0.0
    
    current_volume = volumes.iloc[-1]
    volume_ma5 = volumes.rolling(5).mean().iloc[-1]
    # Safe Volume Ratio
    volume_ratio = current_volume / volume_ma5 if (volume_ma5 and volume_ma5 > 0) else 1.0
    
    ma_alignment = "趋势不明 ⚖️"
    # Safe MA alignment check (handle NaNs)
    if all(not pd.isna(x) for x in [ma5, ma10, ma20, ma60]):
        if ma5 > ma10 > ma20 > ma60:
            ma_alignment = "多头排列 📈"
        elif ma5 < ma10 < ma20 < ma60:
            ma_alignment = "趋势向下 📉"
            
    recent_lows = lows.tail(20).min()
    # Safe Support/Resistance
    support_level = min(recent_lows, ma20) if not pd.isna(ma20) else recent_lows
    
    recent_highs = highs.tail(20).max()
    res_list = [x for x in [recent_highs, ma5, ma10] if not pd.isna(x)]
    resistance_level = max(res_list) if res_list else current_price * 1.1
    
    return {
        "current_price": safe_round(current_price),
        "ma5": safe_round(ma5), "ma10": safe_round(ma10), 
        "ma20": safe_round(ma20), "ma60": safe_round(ma60),
        "ema13": safe_round(ema13), "ema26": safe_round(ema26),
        "rsi14": safe_round(rsi14),
        "atr14": safe_round(atr14),
        "bias_ma5": safe_round(bias_ma5),
        "volume_ratio": safe_round(volume_ratio),
        "ma_alignment": ma_alignment,
        "support_level": safe_round(support_level),
        "resistance_level": safe_round(resistance_level)
    }

def generate_signal(tech, is_hk=False):
    score = 50
    reasons = []
    signal = "观望 😶"
    
    p = tech.get('current_price', 0)
    ma5 = tech.get('ma5', 0)
    ma20 = tech.get('ma20', 0)
    rsi = tech.get('rsi14', 50)
    vol_ratio = tech.get('volume_ratio', 1)
    
    if p > ma5: score += 10
    if p > ma20: score += 20; reasons.append("站上月线")
    else: score -= 20; reasons.append("跌破月线")
    
    if rsi > 70: score -= 10; reasons.append("RSI超买")
    elif rsi < 30: score += 10; reasons.append("RSI超卖")
    
    if vol_ratio > 1.5:
        reasons.append("放量上涨")
        score += 10
    elif vol_ratio < 0.8:
        reasons.append("缩量整理")
    
    if p > ma20 and ma5 > ma20:
        if ma20 > 0 and abs(ma5 - ma20)/ma20 < 0.05:
            signal = "强烈买入 🚀"
            reasons.append("均线粘合突破 (VCP特征)")
        else:
            signal = "买入 🟢"
            reasons.append("多头趋势")
            
    multiplier = 2.5 if is_hk else 2.0
    atr = tech.get('atr14', 0) if tech.get('atr14') else p * 0.03 # Fallback ATR
    
    atr_stop = p - (multiplier * atr)
    supp = tech.get('support_level', 0)
    stop_loss = min(atr_stop, supp * 0.98) if supp > 0 else atr_stop
    
    risk_per_share = p - stop_loss
    take_profit = p + (1.5 * risk_per_share) if risk_per_share > 0 else p * 1.1
    
    suggested_buy = max(supp, p * 0.98)
    
    return {
        "signal": signal,
        "signal_reasons": reasons,
        "trend_score": int(score), # int is safe
        "stop_loss": safe_round(stop_loss),
        "take_profit": safe_round(take_profit),
        "suggested_buy": safe_round(suggested_buy),
        "support_level": safe_round(supp),
        "resistance_level": safe_round(tech.get('resistance_level', 0))
    }

# --- Endpoints ---
@app.get("/market")
def get_market_context():
    try:
        time.sleep(random.uniform(0.5, 1.0)) # Anti-bot
        index_df = ak.stock_zh_index_daily(symbol="sh000001")
        if index_df.empty: raise ValueError("Index Data Empty")
        price = float(index_df['close'].iloc[-1])
        ma20 = float(index_df['close'].rolling(20).mean().iloc[-1])
        status = "Bull" if price > ma20 else "Bear"
        return {"market_status": status, "index_price": safe_round(price), "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    except Exception as e:
        return {"market_status": "Correction", "error": str(e)}

@app.post("/analyze_full")
def analyze_full(req: AnalyzeRequest):
    try:
        code = req.code
        is_hk = len(str(code)) == 5
        if is_hk:
            df = DataFetcher.get_hk_share_history(code)
            market = "HK"
        else:
            df = DataFetcher.get_a_share_history(code)
            market = "CN"
            
        if df.empty:
            return {"error": "No Data found", "code": code}
            
        tech = calculate_technicals(df)
        sig = generate_signal(tech, is_hk)
        tech['trend_score'] = sig['trend_score']
        
        # Risk Logic
        risk_per_share = tech['current_price'] - sig['stop_loss']
        if risk_per_share <= 0: risk_per_share = tech['atr14']
        
        account_risk_money = req.balance * req.risk
        
        if risk_per_share <= 0.0001:
            suggested_shares = 0
        else:
            raw_shares = account_risk_money / risk_per_share / 100
            suggested_shares = int(raw_shares) * 100
            
        if suggested_shares < 100: suggested_shares = 0
        
        return {
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "market": market,
            "code": code,
            "name": code, 
            "signal_type": sig['signal'],
            "trend_score": sig['trend_score'],
            "current_price": tech['current_price'],
            "atr14": tech['atr14'],
            "bias_ma5": tech['bias_ma5'],
            "rsi14": tech['rsi14'],
            "volume_ratio": tech['volume_ratio'],
            "ma_alignment": tech['ma_alignment'],
            "suggested_buy": sig['suggested_buy'],
            "stop_loss": sig['stop_loss'],
            "take_profit": sig['take_profit'],
            "support_level": sig['support_level'],
            "resistance_level": sig['resistance_level'],
            "technical": tech,
            "signal": sig,
            "risk_ctrl": {
                "risk_per_share": safe_round(risk_per_share),
                "suggested_position": suggested_shares
            },
            "prompt_data": {
                "price_info": f"现价: {tech['current_price']}, MA20: {tech['ma20']}",
                "market_stat": market,
                "volume_info": f"量比: {tech['volume_ratio']}, 均线: {tech['ma_alignment']}",
                "levels_info": f"支撑: {sig['support_level']}, 压力: {sig['resistance_level']}"
            }
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
