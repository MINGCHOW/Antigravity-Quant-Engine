# -*- coding: utf-8 -*-
"""
V6.0 量化引擎 (Quant Engine)
集成 AkShare 数据源，负责宏观环境判断与个股风控计算。

Usage:
    python v6_quant_engine.py --mode market
    python v6_quant_engine.py --mode stock --code 600519 --price 1700 --atr 30 --balance 100000 --risk 0.01

Dependencies:
    pip install akshare pandas
"""

import argparse
import json
import sys
import datetime
import traceback
import time
import random

# 尝试导入 akshare，如果环境没安装，提供友好的错误提示
try:
    import akshare as ak
    import pandas as pd
except ImportError:
    print(json.dumps({
        "error": "Missing dependencies",
        "message": "请确保已安装 akshare 和 pandas: pip install akshare pandas"
    }, ensure_ascii=False))
    sys.exit(1)

def get_market_context():
    """
    获取大盘环境数据 (上证指数 + 北向资金)
    """
    try:
        # 1. 获取上证指数日线数据 (sh000001)
        # 注意：akshare 接口可能会更新，这里使用较稳定的接口
        index_df = ak.stock_zh_index_daily(symbol="sh000001")
        
        if index_df.empty:
            raise ValueError("无法获取上证指数数据")

        # 整理数据
        index_df['date'] = pd.to_datetime(index_df['date'])
        index_df = index_df.sort_values('date')
        
        # 计算 MA20
        index_df['MA20'] = index_df['close'].rolling(window=20).mean()
        
        last_row = index_df.iloc[-1]
        last_price = float(last_row['close'])
        last_ma20 = float(last_row['MA20'])
        
        # 2. 判断市场状态
        # 牛市: 价格在 MA20 之上 (简单的趋势定义)
        if last_price > last_ma20:
            status = "Bull"
            reason = "上证指数站上 20 日均线，趋势向好"
            sentiment = 80
        else:
            status = "Bear"
            reason = "上证指数跌破 20 日均线，趋势走弱，建议谨慎"
            sentiment = 40

        # 3. 获取北向资金 (Smart Money) - 可选，若接口超时则跳过
        north_inflow = 0
        try:
            # 北向资金实时数据
            # flow_df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上资金") 
            # 简化起见，这里先不强求实时接口，为了稳定性，我们在 V6.0 初期主要依赖指数趋势
            pass 
        except Exception:
            pass

        return {
            "market_status": status,
            "market_reason": reason,
            "index_price": last_price,
            "index_ma20": round(last_ma20, 2),
            "sentiment_score": sentiment,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    except Exception as e:
        return {
            "error": "Market Data Error",
            "message": str(e),
            "traceback": traceback.format_exc(),
            # 发生错误时的默认安全返回值
            "market_status": "Correction", 
            "market_reason": "无法获取大盘数据，默认按震荡市处理",
            "sentiment_score": 50
        }

def analyze_stock(code, current_price, atr_value, account_balance, risk_ratio):
    """
    个股深度分析 + 仓位计算
    """
    try:
        stock_code = str(code)
        
        # 港股处理 (AkShare 主要针对 A 股，港股数据较少，这里做个区分)
        is_hk = len(stock_code) == 5 # 简易判断，通常港股是5位
        
        fundamental_info = {
            "pe_ttm": None,
            "market_cap": None,
            "name": stock_code
        }

        # 1. 获取基本面数据 (A股 only)
        if not is_hk:
            try:
                # 获取个股实时行情/基本面 (东方财富接口)
                # 需注意 code 前缀，akshare 通常接受 600519 这种纯数字
                clean_code = stock_code.replace("sz", "").replace("sh", "")
                info_df = ak.stock_individual_info_em(symbol=clean_code)
                
                # akshare 返回的是 DataFrame [item, value]
                # item列包含: 总市值, 流通市值, 行业, 上市时间, 股票代码, 股票简称, 总股本, 流通股, 市盈率(动), 市盈率(TTM), 市盈率(静), 市净率 ...
                
                # 辅助函数提取值
                def get_val(item_name):
                    rows = info_df[info_df['item'] == item_name]
                    if not rows.empty:
                        return rows.iloc[0]['value']
                    return None

                fundamental_info['pe_ttm'] = get_val('市盈率(TTM)')
                fundamental_info['market_cap'] = get_val('总市值')
                fundamental_info['name'] = get_val('股票简称') or stock_code

            except Exception as e:
                print(f"Warning: Fetching fundamentals failed: {e}")

        # 2. 仓位管理计算 (核心风控)
        # 模型：固定风险百分比 (Fixed Fractional)
        # 允许亏损金额 = 总资金 * 单笔风险% (例如 10万 * 1% = 1000元)
        # 止损价差 (R) = 2.0 * ATR (这里我们用传入的 ATR 来计算 R)
        # 实际上，ATR 本身就是波动幅度。
        # 假设我们止损设在 2 * ATR 处。那么每股亏损就是 2 * ATR。
        # 买入股数 = 允许亏损金额 / (2 * ATR)
        
        # 安全检查
        if atr_value <= 0:
            atr_value = current_price * 0.03 # 如果 ATR 无效，默认 3% 波动

        risk_amount = account_balance * risk_ratio
        stop_loss_width = 2.0 * atr_value # A股默认 2倍 ATR
        if is_hk:
            stop_loss_width = 2.5 * atr_value # 港股 2.5倍

        shares_raw = risk_amount / stop_loss_width
        
        # 向下取整到手 (100股)
        lot_size = 100
        position_shares = int(shares_raw // lot_size) * lot_size
        
        # 资金利用率检查 (不能超过总资金)
        cost = position_shares * current_price
        if cost > account_balance:
            position_shares = int((account_balance // current_price) // lot_size) * lot_size
            cost = position_shares * current_price

        # 3. 估值检查警告
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
                "account_balance": account_balance,
                "risk_per_trade": f"{risk_ratio*100}%",
                "max_allowed_loss": risk_amount,
                "atr_used": atr_value,
                "suggested_position": position_shares,
                "estimated_cost": cost
            },
            "warnings": warnings
        }

    except Exception as e:
        return {
            "error": "Stock Analysis Error",
            "message": str(e),
            "traceback": traceback.format_exc(),
            "suggested_position": 0 # 出错则建议不买
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='V6 Quant Engine')
    parser.add_argument('--mode', type=str, required=True, choices=['market', 'stock'], help='Mode: market (macro) or stock (individual)')
    
    # Stock Mode Arguments
    parser.add_argument('--code', type=str, help='Stock Code (e.g., 600519)')
    parser.add_argument('--price', type=float, help='Current Price')
    parser.add_argument('--atr', type=float, help='ATR Value')
    parser.add_argument('--balance', type=float, default=100000, help='Account Balance (default: 100000)')
    parser.add_argument('--risk', type=float, default=0.01, help='Risk Ratio (default: 0.01)')

    args = parser.parse_args()

    # --- 稳定获取数据：拟人化延迟 (Jitter) ---
    # 随机等待 2.0 到 5.0 秒，防止因高频请求被数据源 (如东方财富/新浪) 拒绝
    if args.mode in ['market', 'stock']:
        time.sleep(random.uniform(2.0, 5.0))

    result = {}
    
    if args.mode == 'market':
        result = get_market_context()
    elif args.mode == 'stock':
        if not all([args.code, args.price, args.atr]):
            result = {"error": "Missing arguments for stock mode. Need --code, --price, --atr"}
        else:
            result = analyze_stock(args.code, args.price, args.atr, args.balance, args.risk)
            
    # 输出 JSON 到 stdout，供 n8n 捕获
    print(json.dumps(result, ensure_ascii=False, indent=2))
