import json
import os

FILE_PATH = "AH_Stock_V7.2_FullStack.json"

def fix_v7_2_resilience():
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        return

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])

    # 1. FIX API NODE (The most likely culprit)
    api_node = next((n for n in nodes if n['name'] == 'Full Stack Analysis (API)'), None)
    if api_node:
        print("Adding error resilience to API node...")
        api_node['onError'] = 'continueRegularOutput' # CRITICAL fix
        api_node['alwaysOutputData'] = True # Ensure it always output something
        
        # Ensure parameters exist
        if 'parameters' not in api_node: api_node['parameters'] = {}
        if 'options' not in api_node['parameters']: api_node['parameters']['options'] = {}
        
    # 2. UPDATE AI PROMPT TO HANDLE API ERRORS
    # If API fails, it might output a JSON with error info, or empty.
    # We need to ensure the Prompt node doesn't crash accessing properties of undefined.
    prompt_node = next((n for n in nodes if n['name'] == '构建AI提示词'), None)
    if prompt_node:
        print("Updating AI Prompt to handle failed API responses...")
        new_js = r"""
const data = $json;
const marketStatus = $('Global Context (API)').item.json.market_status || "Unknown";

// --- 容错处理：如果 API 失败 ---
// 检查是否有 error 字段，或者 critical data (price) 缺失
let isError = false;
let errorMsg = "";

if (data.error) {
    isError = true;
    errorMsg = JSON.stringify(data.error);
} else if (!data.technical) {
    isError = true;
    errorMsg = "API returned no technical data. Possible timeout or server error.";
}

if (isError) {
    // 返回一个特殊的 Prompt，让 AI 生成一个错误报告卡片
    return {
        json: {
            prompt: `System Error Alert: The analysis API failed for stock ${data.code || 'unknown'}. Error: ${errorMsg}. Please generate a short report stating that data acquisition failed and human review is needed.`,
            raw_data: data,
            is_error: true
        }
    };
}

const tech = data.technical || {};
const sig = data.signal || {};
const risk = data.risk_ctrl || {};

// 获取新闻数据
let news_text = "未搜索到新闻";
try {
    const news = $('Tavily新闻搜索').item.json;
    if (news.results) {
        news_text = news.results.map(r => `- ${r.title}`).join('\n');
    } else if (news.answer) {
        news_text = news.answer;
    }
} catch(e) {}

const prompt = `# 决策仪表盘分析请求

## 股票基础
- 代码: ${data.code} (${data.market})
- 大盘环境: ${marketStatus}
- 现价: ${tech.current_price}

## 信号系统 (V7.1 Hybrid)
- 核心信号: ${sig.signal}
- 趋势评分: ${sig.trend_score}/100
- 理由: ${sig.signal_reasons ? sig.signal_reasons.join(', ') : '无'}

## 风控参数
- 止损价: ${sig.stop_loss}
- 目标价: ${sig.take_profit}
- ATR波动: ${tech.atr14}
- 建议仓位: ${risk.suggested_position} 手 (基于1%风险)

## 技术指标
- MA排列: ${tech.ma_alignment} (${tech.ma5}/${tech.ma20})
- EMA趋势: 13日线 ${tech.ema13} vs 26日线 ${tech.ema26}
- 乖离率: ${tech.bias_ma5}%
- RSI(14): ${tech.rsi14}
- 量比: ${tech.volume_ratio}

## 新闻摘要
${news_text}

请基于以上数据，用简练的专业术语生成交易计划。`;


// --- 动态风险提示逻辑 ---
let risk_instruction = "";
if (marketStatus === 'Bear' || marketStatus === 'Crash') {
    risk_instruction = `
!!! 🔴 严重警告：当前处于熊市/暴跌环境 (${marketStatus}) !!!
1. **严格标准**：仅允许评分>85且有重大利好的个股操作。
2. **强制轻仓**：建议仓位必须减半，或者直接建议空仓。
3. **寻找做空机会**：如果是港股，优先寻找做空逻辑；如果是A股，建议以“观望”为主。
4. **措辞严厉**：请在核心结论中用粗体强调大盘风险。`;
}

const final_prompt = prompt + risk_instruction;

return {
    json: {
        prompt: final_prompt,
        raw_data: data
    }
};
"""
        prompt_node['parameters']['jsCode'] = new_js

    # 3. Save
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Successfully patched {FILE_PATH} with API resilience!")

if __name__ == "__main__":
    fix_v7_2_resilience()
