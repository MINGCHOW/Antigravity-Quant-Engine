import json
import uuid
import os

INPUT_FILE = "AH_Stock_V7.2_FullStack.json" # Use as template for nodes
OUTPUT_FILE = "AH_Stock_V7.4_Linear.json"
DEMO_API_URL = "https://jpthermjdexc.ap-northeast-1.clawcloudrun.com"

# --- V7.4 Universal Node Definitions ---

def create_universal_card_node():
    js_code = r"""
// 【V7.4 通用卡片构建器】
// 无论什么信号，都走这唯一的通道。颜色和文案动态生成。
const root = $json || {};
const feishuFields = root.data?.records?.[0]?.fields || {};
const getVal = (keyCN, keyEN, defaultVal) => feishuFields[keyCN] || root[keyCN] || root[keyEN] || defaultVal;

// 1. 提取核心变量
const signal = getVal('信号类型', 'signal_type', "无信号");
const score = getVal('综合评分', 'sentiment_score', 0);
const advice = getVal('操作建议', 'operation_advice', "暂无建议");
const summary = getVal('核心结论', 'one_sentence', "无详细结论");
const stockName = getVal('名称', 'name', "股票");
const code = getVal('代码', 'code', "");
const dateVal = new Date().toISOString().split('T')[0];

// 2. 动态颜色逻辑 (Linear Logic)
let color = 'grey'; // 默认观望
const sigStr = signal.toString();

if (sigStr.includes('买入') || sigStr.includes('Buy')) {
    color = 'green'; // 强心剂
} else if (sigStr.includes('卖出') || sigStr.includes('减仓')) {
    color = 'red';   // 警报
} else if (sigStr.includes('风险') || sigStr.includes('Warn')) {
    color = 'orange';
}

// 3. 构建通用卡片
const cardContent = [
  {
    tag: 'div',
    text: {
      tag: 'lark_md',
      content: `**${signal}** | 评分: **${score}**/100 | ${advice}`
    }
  },
  {
    tag: 'hr'
  },
  {
    tag: 'div',
    text: {
      tag: 'lark_md',
      content: `💡 **核心结论**：\n${summary}`
    }
  },
  // 把技术指标简化显示，防止卡片太长
  {
    tag: 'div',
    text: {
      tag: 'lark_md',
      content: `💰 现价: **${getVal('现价', 'current_price', 0)}** | 止损: ${getVal('止损价', 'stop_loss', 0)} | 目标: ${getVal('目标价', 'take_profit', 0)}`
    }
  },
  {
    tag: 'action',
    actions: [
      {
        tag: 'button',
        text: { tag: 'plain_text', content: '📊 查看完整数据表' },
        type: (color === 'green') ? 'primary' : 'default', // 只有买入才高亮按钮
        url: 'https://xcnf59usubzt.feishu.cn/base/RVghbRvYgacqs3s82qkcl83bn7e?table=tblvrNDNrjAZwBZc'
      }
    ]
  },
  {
    tag: 'note',
    elements: [
      {
        tag: 'plain_text',
        content: `V7.4 Linear | ${stockName}(${code})`
      }
    ]
  }
];

return {
  json: {
    card_color: color,
    card_content: cardContent,
    header_title: `📊 ${stockName} 每日分析`
  }
};
"""
    return {
        "parameters": {
            "mode": "runOnceForEachItem",
            "jsCode": js_code
        },
        "id": str(uuid.uuid4()),
        "name": "构建通用卡片",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-8600, 1780],
        # Ironclad Settings
        "onError": "continueRegularOutput",
        "alwaysOutputData": True
    }

def create_universal_msg_node():
    return {
        "parameters": {
            "resource": "message",
            "operation": "message:send",
            "receive_id_type": "user_id",
            "receive_id": "bg99a8dc",
            "msg_type": "interactive",
            "content": "={{\nJSON.stringify({\n  \"config\": {\n    \"wide_screen_mode\": true\n  },\n  \"header\": {\n    \"template\": $json.card_color,\n    \"title\": {\n      \"content\": $json.header_title,\n      \"tag\": \"plain_text\"\n    }\n  },\n  \"elements\": $json.card_content\n})\n}}"
        },
        "id": str(uuid.uuid4()),
        "name": "发送通用消息",
        "type": "n8n-nodes-feishu-lite.feishuNode",
        "typeVersion": 1,
        "position": [-8400, 1780],
        "credentials": {
            "feishuCredentialsApi": {
                "id": "RcP0KB4O5l2Y95Bs",
                "name": "Feishu account 2"
            }
        },
        # Ironclad Settings
        "onError": "continueRegularOutput",
        "alwaysOutputData": True,
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 2000
    }

# === Build Logic ===

if not os.path.exists(INPUT_FILE):
    print(f"Error: {INPUT_FILE} not found. Running from scratch?")
    # Fallback to basic template if needed, but let's assume it exists for node reuse
    exit(1)

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    source_wf = json.load(f)

source_nodes = source_wf.get('nodes', [])

# 1. HARVEST NODES (Keep the good ones, discard the branching ones)
keep_names = [
    "定时触发_工作日18点", "Global Context (API)", "读取股票列表",
    "循环处理每只股票", "Full Stack Analysis (API)", "Tavily新闻搜索",
    "构建AI提示词", "Google Gemini Chat Model", "AI分析Agent", 
    "解析AI分析结果", "写入飞书"
]
nodes = [n for n in source_nodes if n['name'] in keep_names]

# 2. CREATE NEW LINEAR NODES
univ_card = create_universal_card_node()
univ_msg = create_universal_msg_node()
nodes.append(univ_card)
nodes.append(univ_msg)

# 3. LOCATE NODES FOR WIRING
# Helper to find node by name
def find_node(name):
    return next((n for n in nodes if n['name'] == name), None)

# 4. RE-WIRE (THE LINEAR CHAIN)
conns = {}

# Trigger -> Global
conns[find_node("定时触发_工作日18点")['name']] = {"main": [[{"node": "Global Context (API)", "type": "main", "index": 0}]]}
# Global -> Read List
conns[find_node("Global Context (API)")['name']] = {"main": [[{"node": "读取股票列表", "type": "main", "index": 0}]]}
# Read List -> Loop
conns[find_node("读取股票列表")['name']] = {"main": [[{"node": "循环处理每只股票", "type": "main", "index": 0}]]}
# Loop -> Analysis (Loop Start)
conns[find_node("循环处理每只股票")['name']] = {"main": [[{"node": "Full Stack Analysis (API)", "type": "main", "index": 0}]]}
# Analysis -> Tavily
conns[find_node("Full Stack Analysis (API)")['name']] = {"main": [[{"node": "Tavily新闻搜索", "type": "main", "index": 0}]]}
# Tavily -> Prompt
conns[find_node("Tavily新闻搜索")['name']] = {"main": [[{"node": "构建AI提示词", "type": "main", "index": 0}]]}
# Prompt -> Agent
conns[find_node("构建AI提示词")['name']] = {"main": [[{"node": "AI分析Agent", "type": "main", "index": 0}]]}
# Agent -> Parse
conns[find_node("AI分析Agent")['name']] = {"main": [[{"node": "解析AI分析结果", "type": "main", "index": 0}]]}
# Parse -> Write Feishu
conns[find_node("解析AI分析结果")['name']] = {"main": [[{"node": "写入飞书", "type": "main", "index": 0}]]}
# Write Feishu -> Build Universal Card
conns[find_node("写入飞书")['name']] = {"main": [[{"node": univ_card['name'], "type": "main", "index": 0}]]}
# Build Card -> Send Message
conns[univ_card['name']] = {"main": [[{"node": univ_msg['name'], "type": "main", "index": 0}]]}
# Send Message -> Loop (Loop End) - DIRECT CLOSE
conns[univ_msg['name']] = {"main": [[{"node": "循环处理每只股票", "type": "main", "index": 0}]]}

# Agent Model Connection
conns["Google Gemini Chat Model"] = {"ai_languageModel": [[{"node": "AI分析Agent", "type": "ai_languageModel", "index": 0}]]}

# 5. ASSEMBLE OUTPUT
workflow = {
    "name": "AH Stock V7.4 Linear (Ironclad)",
    "nodes": nodes,
    "connections": conns,
    "settings": source_wf.get("settings", {}),
    "meta": source_wf.get("meta", {})
}

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Success! Generated {OUTPUT_FILE} (Linear Topology).")
