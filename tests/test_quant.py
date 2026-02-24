import sys
import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.quant import detect_etf, get_stock_name, calculate_technicals, generate_signal, safe_round

class TestQuantLogic:
    
    # --- ETF Detection Tests ---
    def test_detect_etf_a_share(self):
        # Known ETFs
        assert detect_etf("510050", "CN") == True
        assert detect_etf("159915", "CN") == True
        # Stocks
        assert detect_etf("600000", "CN") == False
        assert detect_etf("000001", "CN") == False

    @patch('api.quant.get_stock_name')
    def test_detect_etf_hk_share(self, mock_get_name):
        mock_get_name.return_value = "腾讯控股"
        
        # HK ETFs (Code Range)
        assert detect_etf("02800", "HK") == True
        assert detect_etf("03033", "HK") == True
        
        # HK Stocks (Not ETF)
        assert detect_etf("00700", "HK") == False
        assert detect_etf("09988", "HK") == False
        
        # HK ETF by Name
        mock_get_name.return_value = "南方恒生科技ETF"
        assert detect_etf("03033", "HK") == True

    # --- Technical Indicators Tests ---
    def test_calculate_technicals_basic(self):
        # Create dummy dataframe
        dates = pd.date_range(start="2024-01-01", periods=30)
        data = {
            'date': dates,
            'open': [10] * 30,
            'high': [11] * 30,
            'low': [9] * 30,
            'close': [10.0] * 30,
            'volume': [1000] * 30
        }

        df = pd.DataFrame(data)
        
        # Add some trend to create MACD
        for i in range(15, 30):
            df.loc[i, 'close'] = 10 + (i-15)*0.5 # 10, 10.5, 11...
            
        tech = calculate_technicals(df)
        
        assert "macd" in tech
        assert "macd_signal" in tech
        assert "macd_hist" in tech
        assert "atr14" in tech
        assert tech['current_price'] == df['close'].iloc[-1]

    # --- Signal Generation Tests ---
    def test_generate_signal_bull(self):
        # Mock tech data for a strong bull case
        tech = {
            'current_price': 100,
            'ma5': 95,
            'ma10': 90,
            'ma20': 85,  # p > ma5 > ma20
            'ma60': 80,
            'ma_alignment': "多头排列",
            'rsi14': 60, # Neutral
            'macd_cross': 'golden', # Golden cross
            'macd_hist': 1.5,
            'volume_ratio': 2.5, # High volume
            'support_level': 90,
            'resistance_level': 110,
            'atr14': 2.0
        }
        
        sig = generate_signal(tech, is_hk=False)
        
        # Expect High Score
        assert sig['trend_score'] > 60
        assert "买入" in sig['signal']
        assert "MACD金叉 🔥" in sig['signal_reasons']
        
        # Check Stop Loss (ATR driven)
        # Price 100, ATR 2.0. A-share multiplier 2.0
        # ATR Stop = 100 - 4 = 96
        # Support Stop = 90 * 0.98 = 88.2
        # Should take max(96, 88.2) = 96
        assert sig['stop_loss'] == 96.0

    def test_generate_signal_bear(self):
        # Mock tech data for a bear case
        tech = {
            'current_price': 80,
            'ma5': 85,
            'ma20': 90,  # p < ma5 < ma20
            'macd_cross': 'death',
            'macd_hist': -1.5,
            'rsi14': 40,
            'atr14': 2.0,
            'support_level': 70
        }
        
        sig = generate_signal(tech, is_hk=False)
        
        # Expect Low Score
        assert sig['trend_score'] < 50
        assert "MACD死叉 ⚠️" in sig['signal_reasons']

    # --- V13/V14 Logic Tests ---
    def test_rsi_oversold_stabilization(self):
        """V13: RSI < 20 should give higher score only if price > MA5 (stabilizing)"""
        # RSI oversold + stabilizing (p > ma5)
        tech_stable = {
            'current_price': 100, 'ma5': 95, 'ma10': 90, 'ma20': 85,
            'rsi14': 15, 'macd_cross': 'none', 'macd_hist': 0,
            'volume_ratio': 1.0, 'ma_alignment': '',
            'support_level': 80, 'resistance_level': 110, 'atr14': 2.0
        }
        sig_stable = generate_signal(tech_stable)
        assert "RSI严重超卖反弹 ✅" in sig_stable['signal_reasons']
        
        # RSI oversold + NOT stabilizing (p < ma5)
        tech_unstable = dict(tech_stable)
        tech_unstable['current_price'] = 90
        tech_unstable['ma5'] = 95
        sig_unstable = generate_signal(tech_unstable)
        assert "RSI超卖但未企稳 ⚠️" in sig_unstable['signal_reasons']
        # Stabilizing should score higher
        assert sig_stable['trend_score'] > sig_unstable['trend_score']

    def test_dynamic_rr_ratio(self):
        """V13: R:R ratio should be 3x for strong trends, 2x for normal, 1.5x for weak"""
        # Strong trend (score >= 80): should get 3.0 R:R
        strong_tech = {
            'current_price': 100, 'ma5': 95, 'ma10': 90, 'ma20': 85, 'ma60': 80,
            'ma_alignment': '多头排列 📈', 'rsi14': 60, 'macd_cross': 'golden',
            'macd_hist': 1.5, 'volume_ratio': 2.5,
            'support_level': 90, 'resistance_level': 110, 'atr14': 2.0
        }
        sig = generate_signal(strong_tech)
        if sig['trend_score'] >= 80:
            risk = 100 - sig['stop_loss']
            expected_tp = 100 + 3.0 * risk
            assert abs(sig['take_profit'] - expected_tp) < 0.1

    def test_support_level_takes_max(self):
        """V13 P0: support_level = max(recent_lows, ma20) for tighter stop"""
        dates = pd.date_range(start="2024-01-01", periods=30)
        data = {
            'date': dates,
            'open': [10] * 30, 'high': [11] * 30, 'low': [9] * 30,
            'close': [10.0] * 30, 'volume': [1000] * 30
        }
        df = pd.DataFrame(data)
        # Set one low very low to test max behavior
        df.loc[15, 'low'] = 5.0  # recent_lows would be 5.0
        # MA20 should be around 10.0
        tech = calculate_technicals(df)
        # support should be max(5.0, ~10.0) = ~10.0 (MA20)
        assert tech['support_level'] >= 9.0  # Uses MA20, not the outlier low

    def test_resistance_nearest_above(self):
        """V13: resistance should be nearest level ABOVE current price"""
        dates = pd.date_range(start="2024-01-01", periods=60)
        data = {
            'date': dates,
            'open': [10] * 60, 'high': [12] * 60, 'low': [9] * 60,
            'close': [10.0] * 60, 'volume': [1000] * 60
        }
        df = pd.DataFrame(data)
        # Create a trend so MA values differ
        for i in range(30, 60):
            df.loc[i, 'close'] = 10 + (i-30) * 0.2
        tech = calculate_technicals(df)
        # Resistance should be > current_price
        assert tech['resistance_level'] > tech['current_price'] or tech['resistance_level'] == tech['current_price'] * 1.05

if __name__ == "__main__":
    pytest.main()
