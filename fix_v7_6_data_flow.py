import json
import os

INPUT_FILE = "AH_Stock_V7.5_ManualLoop.json"
OUTPUT_FILE = "AH_Stock_V7.6_DataFlowFixed.json"

def fix_data_flow():
    if not os.path.exists(INPUT_FILE):
        print(f"File not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])

    # === FIX 1: API Node Input ===
    # Currently uses: { "code": "={{ $json.code }}" }
    # This usually works if the previous node (Loop Controller) outputs { code: "..." }
    # But just in case, we verify Loop Controller Output.
    # The Loop Controller outputs: return { json: currentStock }; where currentStock has 'code'.
    # So $json.code SHOULD work. But let's make it robust by handling empty input.
    # Strategy: API node is likely fine, but checking error reporting.
    
    # === FIX 2: Feishu Write Node (The Big Fix) ===
    # Previous: $('Full Stack Analysis (API)').item.json.code
    # Problem: In Manual Loop, .item might index incorrectly. 
    # Solution: The node strictly follows "解析AI分析结果", which outputs the FINAL MERGED JSON including code, name, tech, signal, etc.
    # So we should validly use `={{ $json.code }}` directly from input!
    
    feishu_write_node = next((n for n in nodes if n['name'] == '写入飞书'), None)
    if feishu_write_node:
        print("Refactoring Feishu Write Node expressions...")
        # The 'body' parameter contains the complex mapping
        # We replace the explicit node reference "$('Full Stack Analysis (API)').item.json" 
        # with "$json" because the previous node (解析AI分析结果) ALREADY assembled everything.
        
        # Original body string is potentially complex. Let's construct a clean robust one.
        # The node "解析AI分析结果" returns a rich object: { code, name, signal_type, one_sentence, current_price, ... }
        
        new_body = r"""={{
JSON.stringify({
  "records": [
    {
      "fields": {
        "日期": new Date().getTime(),
        "代码": $json.code || "ERR",
        "名称": $json.name || "Unknown",
        "大盘状态": $json.market || "Unknown", 
        
        "信号类型": $json.signal_type || "无信号",
        "操作建议": $json.operation_advice, 
        "核心结论": $json.one_sentence,
        
        "建议仓位(手)": $json.advice_has_position, 
        "止损价": $json.stop_loss,
        "ATR": $json.atr14,
        "RSI": $json.rsi14,
        "量比": $json.volume_ratio,
        "均线形态": $json.ma_alignment,
        
        "风险警报": $json.risk_alerts,
        "检查清单": $json.checklist
      }
    }
  ]
})
}}"""
        feishu_write_node['parameters']['body'] = new_body

    # === FIX 3: Universal Card Node ===
    # It constructs card from $json.
    # Let's ensure it handles missing data gracefully (already looks robust in build script, but verifying).
    # The "构建通用卡片" node relies on $json coming from "写入飞书". 
    # "写入飞书" returns response from Feishu Base. 
    # WAIT! "写入飞书" output is the Feishu response (recordId), NOT the original data.
    # This is why downstream lacks signal data!
    # FIXED: "写入飞书" should Pass Through Input Data or we merge it.
    # Or, we make "构建通用卡片" reference "解析AI分析结果".
    
    # Better approach: Fix "写入飞书" to Output Input Data (unlikely option in feishu node).
    # Correct approach: Update "构建通用卡片" to use $('解析AI分析结果').first().json
    # BUT in loop, .first() is safer than .item.
    # OR, we wire "解析AI分析结果" directly to "构建通用卡片" as a second input? No, linear.
    
    # JS Code Fix in "构建通用卡片":
    # Explicitly pull data from '解析AI分析结果' node for this execution item.
    card_node = next((n for n in nodes if n['name'] == '构建通用卡片'), None)
    if card_node:
        print("Refactoring Universal Card Node to pull from '解析AI分析结果'...")
        # We inject a helper to grab the last run data of the Parse node
        current_js = card_node['parameters']['jsCode']
        
        # New JS Logic:
        # Instead of root = $json (which is Feishu response), use:
        # const sourceData = $('解析AI分析结果').last().json; 
        # Use .last() because in a loop, we want the most recent execution result.
        
        new_js = r"""
// 【V7.6 Data Flow Fix】
// 从上游 '解析AI分析结果' 节点获取原始分析数据，而不是依赖 '写入飞书' 的返回值
const sourceNode = $('解析AI分析结果');
let sourceData = {};

// 尝试获取最近一次运行的数据
if (sourceNode && sourceNode.last()) {
    sourceData = sourceNode.last().json;
} else {
    sourceData = $json; // Fallback
}

const root = sourceData; 

// --- 下面是通用的提取逻辑 (针对 root) ---
const signal = root.signal_type || "无信号";
const score = root.sentiment_score || 0;
const advice = root.operation_advice || "暂无建议";
const summary = root.one_sentence || "无详细结论";
const stockName = root.name || "股票";
const code = root.code || "";
const currentPrice = root.current_price || 0;
const stopLoss = root.stop_loss || 0;
const takeProfit = root.take_profit || 0;

// 动态颜色
let color = 'grey'; 
const sigStr = signal.toString();
if (sigStr.includes('买入') || sigStr.includes('Buy')) {
    color = 'green'; 
} else if (sigStr.includes('卖出') || sigStr.includes('减仓')) {
    color = 'red';   
} else if (sigStr.includes('风险') || sigStr.includes('Warn')) {
    color = 'orange';
}

// 构建卡片
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
  {
    tag: 'div',
    text: {
      tag: 'lark_md',
      content: `💰 现价: **${currentPrice}** | 止损: ${stopLoss} | 目标: ${takeProfit}`
    }
  },
  {
    tag: 'action',
    actions: [
      {
        tag: 'button',
        text: { tag: 'plain_text', content: '📊 查看完整数据表' },
        type: (color === 'green') ? 'primary' : 'default',
        url: 'https://xcnf59usubzt.feishu.cn/base/RVghbRvYgacqs3s82qkcl83bn7e?table=tblvrNDNrjAZwBZc'
      }
    ]
  },
  {
    tag: 'note',
    elements: [
      {
        tag: 'plain_text',
        content: `V7.6 DataFix | ${stockName}(${code})`
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
        card_node['parameters']['jsCode'] = new_js

    # === FIX 4: API Error Handling ===
    # User said "Full Stack Analysis (API) node has errors for some stocks"
    # We must ensure API node has "Continue On Fail" + "Always Output Data"
    api_node = next((n for n in nodes if n['name'] == 'Full Stack Analysis (API)'), None)
    if api_node:
        api_node['onError'] = 'continueRegularOutput'
        api_node['alwaysOutputData'] = True
        print("Verified API Node Error Resilience.")

    # 4. Save
    workflow = {
        "name": "AH Stock V7.6 Data Flow Fixed",
        "nodes": nodes,
        "connections": workflow.get('connections', {}),
        "settings": workflow.get('settings', {}),
        "meta": workflow.get('meta', {})
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Successfully generated {OUTPUT_FILE} with Data Flow Fixes.")

if __name__ == "__main__":
    fix_data_flow()
