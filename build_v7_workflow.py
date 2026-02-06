import json
import uuid
import os

# 这个脚本用于生成 V7 "All-in-One" 工作流
# 它会基于 V6 的结构，但大幅精简节点，因为大部分计算都移到了 Python API

INPUT_FILE = "AH_Stock_V6_Cloud.json" # 基于 V6 继续修改
OUTPUT_FILE = "AH_Stock_V7_FullStack.json"

# 用户部署的 API 地址 (占位符)
DEMO_API_URL = "http://replace-with-your-cloud-run-url.com"

# === New V7 Nodes ===

def create_full_analysis_node():
    # 调用 V7 的 /analyze_full 接口
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
        "waitBetweenTries": 3000
    }

# V7 需要一个新的 AI Prompt 节点逻辑，因为输入数据结构变了
def update_ai_prompt_code(node):
    # 以前是拼接 raw string，现在 API 已经帮我们把 key info 拼好了
    # 我们只需要简单组合一下
    new_code = r"""
const data = $json;
const tech = data.technical;
const sig = data.signal;
const risk = data.risk_ctrl;
const marketStatus = $('Global Context (API)').item.json.market_status;

// 获取新闻数据 (Tavily 节点在前面)
// 注意：V7 流程有变，我们假设 Tavily 节点还在 Analysis 之后
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
- 理由: ${sig.signal_reasons.join(', ') || '无'}

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
    node['parameters']['jsCode'] = new_code
    return node

# === Main Build Logic ===

if not os.path.exists(INPUT_FILE):
    print(f"Error: {INPUT_FILE} not found.")
    exit(1)

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    workflow = json.load(f)

nodes = workflow.get('nodes', [])
connections = workflow.get('connections', {})

# 1. 移除旧的复杂节点
# 我们需要移除: "计算A股技术指标", "计算港股技术指标", "合并技术指标", "Stock Risk Analysis (API)", "Merge Analysis Data"
# 保留: Trigger, Global Context, Filter, Read List, Tavily, AI Prompt, Parse AI, Feishu

nodes_to_remove = [
    "计算A股技术指标", "计算港股技术指标", "合并技术指标", 
    "Stock Risk Analysis (API)", "Stock Risk Analysis", # V6 Name
    "Merge Analysis Data",
    "判断市场类型", "腾讯财经_实时行情", "YahooFinance_港股数据",
    "解析腾讯数据", "解析Yahoo数据", "腾讯财经_K线数据",
    "Market Regime Filter" # User requested to bypass this circuit breaker
]

workflow['nodes'] = [n for n in nodes if n['name'] not in nodes_to_remove]
nodes = workflow['nodes'] # Update ref

# 2. 插入 "Full Stack Analysis (API)"
analysis_node = create_full_analysis_node()
workflow['nodes'].append(analysis_node)

# 3. 重连逻辑
# 流程: Trigger -> Global Context -> Read List -> SplitBatch -> Analysis...

trigger = next(n for n in nodes if n['name'] == '定时触发_工作日18点')
global_ctx = next(n for n in nodes if n['name'] == 'Global Context (API)')
read_list = next(n for n in nodes if n['name'] == '读取股票列表')
split_node = next(n for n in nodes if n['name'] == '循环处理每只股票')
tavily = next(n for n in nodes if n['name'] == 'Tavily新闻搜索')
prompt_node = next(n for n in nodes if n['name'] == '构建AI提示词')

# Connect Trigger -> Global Context
connections[trigger['name']] = {"main": [[
    {"node": global_ctx['name'], "type": "main", "index": 0}
]]}

# Connect Global Context -> Read List (Bypassing Filter)
connections[global_ctx['name']] = {"main": [[
    {"node": read_list['name'], "type": "main", "index": 0}
]]}

# Connect Read List -> SplitBatch
connections[read_list['name']] = {"main": [[
    {"node": split_node['name'], "type": "main", "index": 0}
]]}
# Connect SplitBatch -> Full Stack Analysis
# Note: SplitInBatches has 2 outputs (Loop, Done). We connect Loop (index 0).
connections[split_node['name']] = {"main": [
    [{"node": analysis_node['name'], "type": "main", "index": 0}], # Output 0: Loop
    [] # Output 1: Done
]}

connections[analysis_node['name']] = {"main": [[
    {"node": tavily['name'], "type": "main", "index": 0}
]]}

# Tavily -> AI Prompt (Existing connection usually fine, but let's ensure)
connections[tavily['name']] = {"main": [[
    {"node": prompt_node['name'], "type": "main", "index": 0}
]]}

# 4. 更新 AI Prompt 节点代码
prompt_node = update_ai_prompt_code(prompt_node)

# 5. 更新写入飞书
feishu = next(n for n in nodes if n['name'] == '写入飞书')
# V7 API 返回结构变了，我们需要适配
# $json.risk_ctrl.suggested_position
# $json.signal.signal
# $json.technical.atr14
# 以前的数据都在根节点或者混乱分布，现在很结构化

v7_body = r'''={{
JSON.stringify({
  "records": [
    {
      "fields": {
        "日期": new Date().getTime(),
        "代码": $('Full Stack Analysis (API)').item.json.code,
        "名称": $('Full Stack Analysis (API)').item.json.name,
        "大盘状态": $('Global Context (API)').item.json.market_status,
        
        "信号类型": $('Full Stack Analysis (API)').item.json.signal.signal,
        "操作建议": $json.operation_advice, 
        "核心结论": $json.one_sentence,
        
        "建议仓位(手)": $('Full Stack Analysis (API)').item.json.risk_ctrl.suggested_position,
        "止损价": $('Full Stack Analysis (API)').item.json.signal.stop_loss,
        "ATR": $('Full Stack Analysis (API)').item.json.technical.atr14,
        "RSI": $('Full Stack Analysis (API)').item.json.technical.rsi14,
        "量比": $('Full Stack Analysis (API)').item.json.technical.volume_ratio,
        "均线形态": $('Full Stack Analysis (API)').item.json.technical.ma_alignment,
        
        "风险警报": $json.risk_alerts,
        "检查清单": $json.checklist
      }
    }
  ]
})
}}'''

feishu['parameters']['body'] = v7_body

# Clean up connections dictionary (remove dead keys)
valid_node_names = [n['name'] for n in nodes]
clean_connections = {}
for source, conns in connections.items():
    if source in valid_node_names:
        clean_connections[source] = conns
workflow['connections'] = clean_connections

# Save
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Success! Generated {OUTPUT_FILE}")
print("Workflow Simplified: Removed legacy JS calculation nodes.")
print("Connected: Read List -> Full Analysis API -> Tavily")
