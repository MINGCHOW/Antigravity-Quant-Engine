import json
import uuid
import os

INPUT_FILE = "AH_Stock_V5_ATR_Pro.json"
OUTPUT_FILE = "AH_Stock_V6_AkShare.json"
PYTHON_SCRIPT_PATH = "d:/Antigravity-/v6_quant_engine.py" # 使用绝对路径更稳

# === Node Definitions ===

def create_global_context_node():
    return {
        "parameters": {
            "command": f"python {PYTHON_SCRIPT_PATH} --mode market"
        },
        "id": str(uuid.uuid4()),
        "name": "Global Context (AkShare)",
        "type": "n8n-nodes-base.executeCommand",
        "typeVersion": 1,
        "position": [-3800, 100], # 放在最前面
        "retryOnFail": True, # 【核心稳定性】失败自动重试
        "maxTries": 3,
        "waitBetweenTries": 5000
    }

def create_market_filter_node():
    return {
        "parameters": {
            "conditions": {
                "string": [
                    {
                        "value1": "={{ $json.market_status }}",
                        "operation": "notEqual",
                        "value2": "Bear"
                    }
                ]
            }
        },
        "id": str(uuid.uuid4()),
        "name": "Market Regime Filter",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [-3600, 100]
    }

def create_stock_analysis_node():
    # 嵌套执行命令，获取个股风控数据
    # 注意：这里需要引用上游 "Combine Technical Indicators" 的数据
    # 参数：code, price, atr
    cmd = f"python {PYTHON_SCRIPT_PATH} --mode stock --code {{{{ $json.code }}}} --price {{{{ $json.current_price }}}} --atr {{{{ $json.atr14 }}}}"
    
    return {
        "parameters": {
            "command": cmd
        },
        "id": str(uuid.uuid4()),
        "name": "Stock Risk Analysis",
        "type": "n8n-nodes-base.executeCommand",
        "typeVersion": 1,
        "position": [-1850, 450], # 放在技术指标合并之后
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 3000
    }

def create_merge_content_node():
    return {
        "parameters": {
            "mode": "combine",
            "combinationMode": "mergeByPosition",
            "options": {}
        },
        "id": str(uuid.uuid4()),
        "name": "Merge Analysis Data",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 2.1,
        "position": [-1650, 300]
    }

# === Main Build Logic ===

if not os.path.exists(INPUT_FILE):
    print(f"Error: {INPUT_FILE} not found.")
    exit(1)

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    workflow = json.load(f)

nodes = workflow.get('nodes', [])
connections = workflow.get('connections', {})

# 找到关键节点
trigger_node = next(n for n in nodes if n['type'].endswith('scheduleTrigger'))
read_list_node = next(n for n in nodes if n['name'] == '读取股票列表')
merge_tech_node = next(n for n in nodes if n['name'] == '合并技术指标')
tavily_node = next(n for n in nodes if n['name'] == 'Tavily新闻搜索')
feishu_node = next(n for n in nodes if n['name'] == '写入飞书')

# 1. 插入头部节点 (Global Context -> Filter)
global_ctx = create_global_context_node()
market_filter = create_market_filter_node()

nodes.append(global_ctx)
nodes.append(market_filter)

# 重连头部连接
# 原: Trigger -> Read List
# 新: Trigger -> Global Context -> Market Filter (True) -> Read List

# 删除旧连接
connections[trigger_node['name']]['main'][0] = [] 

# 建立新连接 (更新 Index 0)
connections[trigger_node['name']]['main'][0].append(
    {"node": global_ctx['name'], "type": "main", "index": 0}
)

connections[global_ctx['name']] = {
    "main": [[{"node": market_filter['name'], "type": "main", "index": 0}]]
}

connections[market_filter['name']] = {
    "main": [
        [{"node": read_list_node['name'], "type": "main", "index": 0}], # True -> Read List
        [] # False -> Stop (Implicit)
    ]
}

# 2. 插入循环体内节点 (Stock Analysis)
stock_analysis = create_stock_analysis_node()
merge_analysis = create_merge_content_node()

nodes.append(stock_analysis)
nodes.append(merge_analysis)

# 重连循环体连接
# 原: Merge Tech -> Tavily
# 新: Merge Tech -> Stock Analysis -> Merge Analysis (Input 2)
#     Merge Tech -> Merge Analysis (Input 1)
#     Merge Analysis -> Tavily

# 找到 Merge Tech 的原有连接并删除 (指向 Tavily 的)
# 注意：Merge Tech 可能连接多个，我们要精准替换去 Tavily 的那一条
old_target_index = -1
for i, conn_list in enumerate(connections[merge_tech_node['name']]['main']):
    for j, conn in enumerate(conn_list):
        if conn['node'] == tavily_node['name']:
            old_conn = connections[merge_tech_node['name']]['main'][i].pop(j)
            break

# 建立新连接
# Merge Tech -> Stock Analysis
connections[merge_tech_node['name']]['main'][0].append(
    {"node": stock_analysis['name'], "type": "main", "index": 0}
)

# Merge Tech -> Merge Analysis (Input 1) - 保留原始技术数据
connections[merge_tech_node['name']]['main'][0].append(
    {"node": merge_analysis['name'], "type": "main", "index": 0}
)

# Stock Analysis -> Merge Analysis (Input 2) - 新的风控数据
connections[stock_analysis['name']] = {
    "main": [[{"node": merge_analysis['name'], "type": "main", "index": 1}]]
}

# Merge Analysis -> Tavily
connections[merge_analysis['name']] = {
    "main": [[{"node": tavily_node['name'], "type": "main", "index": 0}]]
}

# 3. 更新写入飞书的参数 (增加 建议仓位, PE)
# 原有的 Body 是 V5.0 的，我们需要在 jsCode 里增加字段
# 只要之前的 Python 脚本写入了 'body' 参数，我们这里需要再次更新它
# 或者我们直接修改 nodes 列表里的对象

current_body = feishu_node['parameters']['body']
# 我们可以简单粗暴地用 replace 插入新字段
# 插入点: "ATR": ... 之前或之后
new_fields = r'''
        "建议仓位(手)": $json["risk_analysis"] ? $json["risk_analysis"]["suggested_position"] : 0,
        "市盈率TTM": $json["pe_ttm"],
        "大盘状态": $('Global Context (AkShare)').item.json.market_status,
'''

# 找到一个合适的插入点，例如 "ATR"
if '"ATR":' in current_body:
    updated_body = current_body.replace('"ATR":', new_fields + '"ATR":')
    feishu_node['parameters']['body'] = updated_body
    print("Updated Feishu Node with V6 fields.")

# 保存文件
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Success! Generated {OUTPUT_FILE}")
print(f"Nodes Added: Global Context, Market Filter, Stock Risk Analysis, Merge Analysis Data")
