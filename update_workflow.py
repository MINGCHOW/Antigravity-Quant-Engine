
import json
import os

file_path = r'd:\Antigravity-\A_H Stock Intelligent Analysis System.json'

if not os.path.exists(file_path):
    print(f"Error: File not found at {file_path}")
    exit(1)

with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 1. Update "计算A股技术指标"
new_code_indicators = r"""// 【资深操盘手版】计算A股技术指标 - V5.0 (引入ATR与EMA)

// 1. 数据获取与防御逻辑
let code;
try {
  code = $('判断市场类型').item.json.code.toString();
} catch (e) {
  code = $json.code ? $json.code.toString() : ""; 
}
if (!code) return [{ json: { error: "无法找到股票代码" } }];

let apiResponse = $json.data; 
if (typeof apiResponse === 'string') {
  try { apiResponse = JSON.parse(apiResponse); } catch(e) {}
}
const stockMap = apiResponse.data || apiResponse; 
const marketPrefix = code.startsWith('6') ? 'sh' : 'sz';
const key = `${marketPrefix}${code}`;
const stockData = stockMap[key];

if (!stockData || !stockData.qfqday) {
  return [{ json: { error: `未找到K线数据`, code: code } }];
}

const klines = stockData.qfqday; 
// 提取数据列 (腾讯接口: 0日期, 1开, 2收, 3高, 4低, 5量)
const closes = klines.map(k => parseFloat(k[2]));
const highs = klines.map(k => parseFloat(k[3]));
const lows = klines.map(k => parseFloat(k[4]));
const volumes = klines.map(k => parseFloat(k[5]));

// --- 🛠️ 核心算法升级区域 ---

// 1. 基础 MA 计算
function calculateMA(data, period) {
  if (data.length < period) return 0;
  const sum = data.slice(-period).reduce((a, b) => a + b, 0);
  return sum / period;
}

// 2. ⭐ 新增：EMA 计算 (对近期价格更敏感)
function calculateEMA(data, period) {
  if (data.length < period) return data[data.length - 1];
  const k = 2 / (period + 1);
  let ema = data[0];
  for (let i = 1; i < data.length; i++) {
    ema = data[i] * k + ema * (1 - k);
  }
  return ema;
}

// 3. ⭐ 新增：ATR 计算 (真实波幅，用于动态止损)
function calculateATR(highs, lows, closes, period) {
  if (highs.length < period + 1) return 0;
  let trs = [];
  for(let i=1; i<highs.length; i++) {
    const hl = highs[i] - lows[i];
    const hc = Math.abs(highs[i] - closes[i-1]);
    const lc = Math.abs(lows[i] - closes[i-1]);
    trs.push(Math.max(hl, hc, lc));
  }
  // 简单移动平均计算 ATR
  if (trs.length < period) return 0;
  return trs.slice(-period).reduce((a,b)=>a+b,0) / period;
}

// 4. RSI 计算
function calculateRSI(closes, period) {
  if (closes.length < period + 1) return 50;
  let gains = 0, losses = 0;
  for (let i = closes.length - period; i < closes.length; i++) {
    const change = closes[i] - closes[i-1];
    if (change > 0) gains += change;
    else losses -= change;
  }
  const avgGain = gains / period;
  const avgLoss = losses / period;
  if (avgLoss === 0) return 100;
  return Math.round(100 - (100 / (1 + avgGain / avgLoss)));
}

// --- 指标计算执行 ---

const currentPrice = closes[closes.length - 1];
const ma5 = calculateMA(closes, 5);
const ma10 = calculateMA(closes, 10);
const ma20 = calculateMA(closes, 20);
const ma60 = calculateMA(closes, 60);

// ⭐ 计算 EMA (EMA13 是经典的操盘线)
const ema13 = calculateEMA(closes, 13);
const ema26 = calculateEMA(closes, 26); // 相当于 MACD 的慢线

// ⭐ 计算 ATR (14周期)
const atr14 = calculateATR(highs, lows, closes, 14);

// 乖离率 (使用 EMA13 更准，但为了兼容性保留 MA5)
const biasMA5 = ma5 > 0 ? ((currentPrice - ma5) / ma5 * 100).toFixed(2) : 0;
const rsi14 = calculateRSI(closes, 14);

// 量比 & 资金流向初筛
const avgVolume5 = calculateMA(volumes.slice(0, -1), 5);
const currentVolume = volumes[volumes.length - 1];
const volumeRatio = avgVolume5 > 0 ? (currentVolume / avgVolume5).toFixed(2) : 1.0;
// 判定是否放量阳线
const isBullishVolume = (currentPrice > closes[closes.length-2]) && (currentVolume > avgVolume5 * 1.2);

// --- 🤖 智能信号生成逻辑 (升级版) ---

let signal = "观望 ⚪";
let signalReasons = [];
let riskFactors = [];
let trendScore = 50;

// 1. 趋势评分 (引入 EMA 权重)
if (ema13 > ema26) trendScore += 20; // 中期趋势向上
if (currentPrice > ma60) trendScore += 20; // 长期趋势向上
if (ma5 > ma10 && ma10 > ma20) trendScore += 20; // 均线完美排列
if (rsi14 > 50 && rsi14 < 70) trendScore += 10; // 动能充沛且未超买

// 2. 买入信号判定
const isConsolidating = Math.abs(ma5 - ma20) / ma20 < 0.05; // 均线粘合
const isBreakout = currentPrice > ma5 && currentPrice > ma20; // 突破均线

// 策略 A: 均线多头排列 + 缩量回踩 (最佳买点)
if (ma5 > ma10 && ma10 > ma20 && currentPrice > ma20) {
    if (parseFloat(biasMA5) < 3 && parseFloat(biasMA5) > -2) {
        signal = "买入 🟢";
        signalReasons.push("多头趋势中的健康回踩(乖离率低)");
    } else if (parseFloat(biasMA5) >= 5) {
        riskFactors.push("多头趋势但短期超买(乖离率>5%)，勿追高");
    }
}

// 策略 B: 底部均线粘合后放量突破 (起爆点)
if (isConsolidating && isBreakout && isBullishVolume) {
    signal = "强烈买入 🚀";
    signalReasons.push("均线粘合后放量突破，主力启动迹象");
    trendScore += 15;
}

// 3. 风险预警
if (currentPrice < ma20 && ma5 < ma20) {
    signal = "卖出 🔴";
    riskFactors.push("跌破MA20生命线，趋势转弱");
}
if (rsi14 > 80) riskFactors.push("RSI严重超买，随时回调");

// --- 💰 动态止盈止损计算 (ATR战法) ---

// 止损：多头趋势下，使用 2倍 ATR 作为安全垫
// 如果 ATR 很小(波动小)，止损就紧；ATR 大，止损就松
const stopLossLevel = (currentPrice - 2.0 * atr14).toFixed(2);

// 目标：至少 1.5倍 的盈亏比
const riskPerShare = currentPrice - stopLossLevel;
const takeProfitLevel = (currentPrice + 1.5 * riskPerShare).toFixed(2);

// 支撑压力 (保留传统算法作为辅助)
const supportLevel = Math.max(ma20, parseFloat(stopLossLevel)).toFixed(2);
const resistanceLevel = Math.max(...highs.slice(-20)).toFixed(2);

// 获取股票名称
const stockName = $('判断市场类型').item.json.name || code;

return [{
  json: {
    code: code,
    market: 'A',
    name: stockName,
    current_price: currentPrice.toFixed(2),
    ma5: ma5.toFixed(2),
    ma10: ma10.toFixed(2),
    ma20: ma20.toFixed(2),
    ma60: ma60.toFixed(2),
    bias_ma5: parseFloat(biasMA5),
    rsi14: rsi14,
    volume_ratio: parseFloat(volumeRatio),
    atr14: parseFloat(atr14.toFixed(2)), // 输出ATR供AI参考
    ma_alignment: ema13 > ema26 ? "趋势向上 📈" : "趋势向下 📉",
    trend_score: trendScore,
    signal: signal,
    signal_reasons: signalReasons,\n    risk_factors: riskFactors,
    support_level: parseFloat(supportLevel),
    resistance_level: parseFloat(resistanceLevel),
    stop_loss: parseFloat(stopLossLevel), // 使用动态止损
    take_profit: parseFloat(takeProfitLevel), // 使用动态止盈
    data_source: '腾讯财经',
    currency: 'CNY'
  }
}];"""

# 2. Update "构建AI提示词"
new_prompt_code = r"""// 【修复版】构建AI提示词

// 1. 关键修改：明确指定去“合并技术指标”节点找回丢失的技术数据
// ⚠️ 如果报错，请确保你前面的节点名称确实叫 "合并技术指标"
const technical = $('合并技术指标').item.json;

// 2. 获取当前节点输入的新闻数据 (Tavily的输出)
const news = $json;

// 3. 构建提示词 (Prompt)
const prompt = `# 决策仪表盘分析请求

## 股票信息
- 代码：${technical.code}
- 名称：${technical.name || technical.code}
- 市场：${technical.market === 'A' ? 'A股' : '港股'}
- 日期：${new Date().toISOString().split('T')[0]}

## 技术面数据

### 价格与均线
| 指标 | 数值 |
|------|------|
| 当前价格 | ${technical.current_price} ${technical.currency || 'CNY'} |
| MA5 | ${technical.ma5} |
| MA10 | ${technical.ma10} |
| MA20 | ${technical.ma20} |
| MA60 | ${technical.ma60} |
| 乖离率(MA5) | ${technical.bias_ma5}% |
| RSI(14) | ${technical.rsi14} |
| 量比 | ${technical.volume_ratio} |

### 趋势判断
- 均线形态：${technical.ma_alignment}
- 趋势评分：${technical.trend_score}/100
- 系统信号：${technical.signal}

### 关键价位 (基于ATR动态风控)
- 动态止损位：${technical.stop_loss} (基于2倍ATR波动率计算)
- 建议目标价：${technical.take_profit} (1.5倍盈亏比)
- 市场波动率(ATR)：${technical.atr14}

### 买入理由
${technical.signal_reasons?.join('\n') || '无'}

### 风险因素
${technical.risk_factors?.join('\n') || '无'}

## 新闻舆情
${news.answer || news.results ? `
搜索结果：
${news.results?.map(r => `- ${r.title}: ${r.content?.substring(0, 100)}...`).join('\n') || '无详细新闻'}

AI摘要：${news.answer || '无'}
` : '未搜索到相关新闻'}

## 分析任务
请基于以上数据生成决策仪表盘。
**特别注意：**
1. **尊重动态止损**：请优先参考“动态止损位”作为风控线，而非仅仅看固定比例。
2. **识别起爆点**：如果 \`signal\` 显示 "强烈买入 🚀"，说明出现了【均线粘合后突破】，此时即使乖离率略高（如3-4%）也是允许的，因为这是趋势爆发初期。
3. **资金管理**：如果 ATR 数值很大，说明股性活跃，请在建议中提示“控制仓位，防范剧烈波动”。

必须给出具体的买入价、止损价、目标价。`;

// 将构造好的 prompt 和原始数据一起传递给下一个节点
return [{ 
    json: { 
        prompt: prompt, 
        technical: technical,
        news_data: news
    } 
}];"""

# Apply Updates
found_indicators = False
found_prompt = False

for node in data.get('nodes', []):
    if node.get('name') == '计算A股技术指标':
        node['parameters']['jsCode'] = new_code_indicators
        found_indicators = True
        print("Updated 计算A股技术指标")
    
    if node.get('name') == '构建AI提示词':
        node['parameters']['jsCode'] = new_prompt_code
        found_prompt = True
        print("Updated 构建AI提示词")

if found_indicators and found_prompt:
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Successfully saved changes to A_H Stock Intelligent Analysis System.json.")
else:
    print(f"Error: Indicators found? {found_indicators}, Prompt found? {found_prompt}")
