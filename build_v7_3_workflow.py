import json
import uuid
import os

INPUT_FILE = "AH_Stock_V6_Cloud.json"
OUTPUT_FILE = "AH_Stock_V7.3_FullStack.json"
DEMO_API_URL = "http://replace-with-your-cloud-run-url.com"

# --- V7 Node Definitions ---

def create_full_analysis_node():
    return {
        "parameters": {
            "url": f"{DEMO_API_URL}/analyze_full",
            "method": "POST",
            "authentication": "none",
            "sendBody": True,
            "contentType": "json",
            "bodyParameters": {
                "parameters": [
                    {"name": "code", "value": "={{ $json.code }}"},
                    {"name": "balance", "value": 100000},
                    {"name": "risk", "value": 0.01}
                ]
            },
            "options": {}
        },
        "id": str(uuid.uuid4()),
        "name": "Full Stack Analysis (API)",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [-1850, 450],
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 3000,
        "onError": "continueRegularOutput" # CRITICAL: Prevent workflow stop on API error
    }

def update_ai_prompt_code(node):
    new_code = r"""
const data = $json;
// Error Handling: If API failed, provide fallback data
if (data.error) {
    return { json: { prompt: "Error in analysis: " + JSON.stringify(data), raw_data: data } };
}

const tech = data.technical || {};
const sig = data.signal || {};
const risk = data.risk_ctrl || {};
const marketStatus = $('Global Context (API)').item.json.market_status || "Unknown";

// 获取新闻数据
let news_text = "未搜索到新闻";
try {
    const news = $('Tavily新闻搜索').item.json;
    if (news.results) {
        news_text = news.results.map(r => `- ${r.title}`).join('\n');
    } else if (news.answer) news_text = news.answer;
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

请基于以上数据，用简练的专业术语生成交易计划。
`;

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

return {
    json: {
        prompt: prompt + risk_instruction,
        raw_data: data
    }
};
"""
    node['parameters']['jsCode'] = new_code
    return node

def update_feishu_write(node):
    # Update mappings for new fields
    v7_body = r'''={{
JSON.stringify({
  "records": [
    {
      "fields": {
        "日期": new Date().getTime(),
        "代码": $('Full Stack Analysis (API)').item.json.code,
        "名称": $('Full Stack Analysis (API)').item.json.name,
        "大盘状态": $('Global Context (API)').item.json.market_status,
        
        "信号类型": $('Full Stack Analysis (API)').item.json.signal ? $('Full Stack Analysis (API)').item.json.signal.signal : "Error",
        "操作建议": $json.operation_advice, 
        "核心结论": $json.one_sentence,
        
        "建议仓位(手)": $('Full Stack Analysis (API)').item.json.risk_ctrl ? $('Full Stack Analysis (API)').item.json.risk_ctrl.suggested_position : 0,
        "止损价": $('Full Stack Analysis (API)').item.json.signal ? $('Full Stack Analysis (API)').item.json.signal.stop_loss : 0,
        "ATR": $('Full Stack Analysis (API)').item.json.technical ? $('Full Stack Analysis (API)').item.json.technical.atr14 : 0,
        "RSI": $('Full Stack Analysis (API)').item.json.technical ? $('Full Stack Analysis (API)').item.json.technical.rsi14 : 0,
        "量比": $('Full Stack Analysis (API)').item.json.technical ? $('Full Stack Analysis (API)').item.json.technical.volume_ratio : 0,
        "均线形态": $('Full Stack Analysis (API)').item.json.technical ? $('Full Stack Analysis (API)').item.json.technical.ma_alignment : "",
        
        "风险警报": $json.risk_alerts,
        "检查清单": $json.checklist
      }
    }
  ]
})
}}'''
    node['parameters']['body'] = v7_body
    return node

# === Build Logic ===

if not os.path.exists(INPUT_FILE):
    print(f"Error: {INPUT_FILE} not found.")
    exit(1)

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    workflow = json.load(f)

nodes = workflow.get('nodes', [])
connections = workflow.get('connections', {})

# 1. Removal List (Include all legacy + Filter + Merge)
nodes_to_remove = [
    "计算A股技术指标", "计算港股技术指标", "合并技术指标", 
    "Stock Risk Analysis (API)", "Stock Risk Analysis",
    "Merge Analysis Data",
    "判断市场类型", "腾讯财经_实时行情", "YahooFinance_港股数据",
    "解析腾讯数据", "解析Yahoo数据", "腾讯财经_K线数据",
    "Market Regime Filter", # Removed for Bear Mode
    "合并推送结果" # Removed for Loop Fix
]

workflow['nodes'] = [n for n in nodes if n['name'] not in nodes_to_remove]
nodes = workflow['nodes']

# 2. Add New Nodes
analysis_node = create_full_analysis_node()
workflow['nodes'].append(analysis_node)

# 3. Locate Key Nodes
trigger = next(n for n in nodes if n['name'] == '定时触发_工作日18点')
global_ctx = next(n for n in nodes if n['name'] == 'Global Context (API)')
read_list = next(n for n in nodes if n['name'] == '读取股票列表')
split_node = next(n for n in nodes if n['name'] == '循环处理每只股票')
tavily = next(n for n in nodes if n['name'] == 'Tavily新闻搜索')
prompt_node = next(n for n in nodes if n['name'] == '构建AI提示词')
feishu_write = next(n for n in nodes if n['name'] == '写入飞书')
feishu_buy = next(n for n in nodes if n['name'] == '飞书发送消息_买入')
feishu_other = next(n for n in nodes if n['name'] == '飞书发送消息_其他')

# 4. Updates
prompt_node = update_ai_prompt_code(prompt_node)
feishu_write = update_feishu_write(feishu_write)

# 5. Settings Update (Batch Size)
if 'parameters' not in split_node: split_node['parameters'] = {}
if 'options' not in split_node['parameters']: split_node['parameters']['options'] = {}
split_node['parameters']['options']['reset'] = False
split_node['parameters']['batchSize'] = 1

# 6. Wiring (The Clean Sequence)

conns = {} # Rebuild specific connections to be safe

# Trigger -> Global Context
conns[trigger['name']] = {"main": [[{"node": global_ctx['name'], "type": "main", "index": 0}]]}

# Global Context -> Read List (Direct)
conns[global_ctx['name']] = {"main": [[{"node": read_list['name'], "type": "main", "index": 0}]]}

# Read List -> SplitBatch
conns[read_list['name']] = {"main": [[{"node": split_node['name'], "type": "main", "index": 0}]]}

# SplitBatch -> Full Analysis
conns[split_node['name']] = {"main": [
    [{"node": analysis_node['name'], "type": "main", "index": 0}], # Loop
    [] # Done
]}

# Full Analysis -> Tavily
conns[analysis_node['name']] = {"main": [[{"node": tavily['name'], "type": "main", "index": 0}]]}

# Tavily -> Prompt
conns[tavily['name']] = {"main": [[{"node": prompt_node['name'], "type": "main", "index": 0}]]}

# Prompt -> AI Agent
ai_agent = next(n for n in nodes if n['name'] == 'AI分析Agent')
conns[prompt_node['name']] = {"main": [[{"node": ai_agent['name'], "type": "main", "index": 0}]]}

# AI Agent -> Parse (Existing in JSON)
parse_node = next(n for n in nodes if n['name'] == '解析AI分析结果')
conns[ai_agent['name']] = {"main": [[{"node": parse_node['name'], "type": "main", "index": 0}]]}

# Parse -> Feishu Write
conns[parse_node['name']] = {"main": [[{"node": feishu_write['name'], "type": "main", "index": 0}]]}

# Feishu Write -> Decision (Existing)
decision_node = next(n for n in nodes if n['name'] == '判断是否买入信号')
conns[feishu_write['name']] = {"main": [[{"node": decision_node['name'], "type": "main", "index": 0}]]}

# Decision -> Build Cards (Existing)
buy_card = next(n for n in nodes if n['name'] == '构建飞书卡片_买入')
other_card = next(n for n in nodes if n['name'] == '构建飞书卡片_其他')
conns[decision_node['name']] = {"main": [
    [{"node": buy_card['name'], "type": "main", "index": 0}],
    [{"node": other_card['name'], "type": "main", "index": 0}]
]}

# Build Cards -> Send Messages (Existing)
conns[buy_card['name']] = {"main": [[{"node": feishu_buy['name'], "type": "main", "index": 0}]]}
conns[other_card['name']] = {"main": [[{"node": feishu_other['name'], "type": "main", "index": 0}]]}

# Send Messages -> SplitBatch (CLOSING THE LOOP DIRECTLY)
# This is the fix for the deadlock
conns[feishu_buy['name']] = {"main": [[{"node": split_node['name'], "type": "main", "index": 0}]]}
conns[feishu_other['name']] = {"main": [[{"node": split_node['name'], "type": "main", "index": 0}]]}

# Preserve Gemini Model Connection
gemini_model = next((n for n in nodes if n['name'] == 'Google Gemini Chat Model'), None)
if gemini_model:
    conns[gemini_model['name']] = connections.get(gemini_model['name'], {})

workflow['connections'] = conns

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Success! Generated {OUTPUT_FILE} with loop fixes and error handling.")
