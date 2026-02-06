import json
import uuid
import os

INPUT_FILE = "AH_Stock_V5_ATR_Pro.json"
OUTPUT_FILE = "AH_Stock_V6_Cloud.json"

# 用户需要替换这个URL
DEMO_API_URL = "http://replace-with-your-cloud-run-url.com"

# === Node Definitions (Cloud Version) ===

def create_global_context_node():
    return {
        "parameters": {
            "url": f"{DEMO_API_URL}/market",
            "method": "GET",
            "authentication": "none",
            "options": {}
        },
        "id": str(uuid.uuid4()),
        "name": "Global Context (API)",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [-3800, 100],
        "retryOnFail": True,
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
    # 使用 HTTP POST 调用个股分析接口
    # Body 参数构造
    body_params = {
        "code": "={{ $json.code }}",
        "price": "={{ $json.current_price }}",
        "atr": "={{ $json.atr14 }}",
        "balance": 100000,
        "risk": 0.01
    }
    
    return {
        "parameters": {
            "url": f"{DEMO_API_URL}/stock",
            "method": "POST",
            "authentication": "none",
            "sendBody": True,
            "contentType": "json",
            "bodyParameters": {
                "parameters": [
                    {"name": k, "value": v} for k, v in body_params.items()
                ]
            },
            "options": {}
        },
        "id": str(uuid.uuid4()),
        "name": "Stock Risk Analysis (API)",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.1,
        "position": [-1850, 450],
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

# 1. 插入头部节点 (Global Context HTTP -> Filter)
global_ctx = create_global_context_node()
market_filter = create_market_filter_node()

nodes.append(global_ctx)
nodes.append(market_filter)

# 重连头部连接
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
        [] # False -> Stop
    ]
}

# 2. 插入循环体内节点 (Stock Analysis HTTP)
stock_analysis = create_stock_analysis_node()
merge_analysis = create_merge_content_node()

nodes.append(stock_analysis)
nodes.append(merge_analysis)

# 重连循环体连接
# 原: Merge Tech -> Tavily
# 新: Merge Tech -> Stock Analysis -> Merge Analysis (Input 2)

# 删除 Merge Tech -> Tavily
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

# Merge Tech -> Merge Analysis (Input 1)
connections[merge_tech_node['name']]['main'][0].append(
    {"node": merge_analysis['name'], "type": "main", "index": 0}
)

# Stock Analysis -> Merge Analysis (Input 2)
connections[stock_analysis['name']] = {
    "main": [[{"node": merge_analysis['name'], "type": "main", "index": 1}]]
}

# Merge Analysis -> Tavily
connections[merge_analysis['name']] = {
    "main": [[{"node": tavily_node['name'], "type": "main", "index": 0}]]
}

# 3. 更新写入飞书的参数
# 需要注意：HTTP节点返回的数据结构可能在 $json 根节点，也可能在 $json.data 取决于配置
# n8n HTTP Request 默认会将 Response Body 放在 json 中
# 所以字段映射逻辑不需要变: $json.risk_analysis, $json.pe_ttm
# 但我们需要确保大盘状态的引用是正确的: $('Global Context (API)').item.json.market_status

current_body = feishu_node['parameters']['body']
new_fields = r'''
        "建议仓位(手)": $json["risk_analysis"] ? $json["risk_analysis"]["suggested_position"] : 0,
        "市盈率TTM": $json["pe_ttm"],
        "大盘状态": $('Global Context (API)').item.json.market_status,
'''

if '"ATR":' in current_body:
    updated_body = current_body.replace('"ATR":', new_fields + '"ATR":')
    # 防止重复替换 (如果之前跑过 V6 build)
    if "建议仓位" not in current_body:
        feishu_node['parameters']['body'] = updated_body
    else:
        # 如果已经存在（例如多次运行），我们需要修正大盘节点的名称引用
        # 之前的节点名是 'Global Context (AkShare)', 现在是 'Global Context (API)'
        updated_body = current_body.replace('Global Context (AkShare)', 'Global Context (API)')
        feishu_node['parameters']['body'] = updated_body

    print("Updated Feishu Node with Cloud V6 fields.")

# 保存文件
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Success! Generated {OUTPUT_FILE}")
print(f"Cloud Nodes Added: Global Context (API), Market Regime Filter, Stock Risk Analysis (API)")
