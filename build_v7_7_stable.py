import json
import uuid
import os

INPUT_FILE = "AH_Stock_V7.6_DataFlowFixed.json"
OUTPUT_FILE = "AH_Stock_V7.7_Stable.json"

# --- V7.7 Wait Node ---

def create_wait_node():
    return {
        "parameters": {
            "amount": 3,
            "unit": "seconds"
        },
        "id": str(uuid.uuid4()),
        "name": "安抚反爬虫 (Wait 3s)",
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1,
        "position": [-9000, 1500] 
    }

# --- Build Logic ---

if not os.path.exists(INPUT_FILE):
    print(f"Source V7.6 not found: {INPUT_FILE}")
    exit(1)

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    workflow = json.load(f)

nodes = workflow.get('nodes', [])
conns = workflow.get('connections', {})

# 1. ADD WAIT NODE
wait_node = create_wait_node()
nodes.append(wait_node)

# 2. INCREASE API TIMEOUT
api_node = next((n for n in nodes if n['name'] == 'Full Stack Analysis (API)'), None)
if api_node:
    # Set timeout to 60s
    api_node['parameters']['options'] = api_node['parameters'].get('options', {})
    api_node['parameters']['options']['timeout'] = 60000 
    print("Increased API Timeout to 60s.")

# 3. RE-WIRE LOOP TO INCLUDE WAIT
# Original: "发送通用消息" -> "手工循环控制器"
# New: "发送通用消息" -> "Wait" -> "手工循环控制器"

send_node_name = "发送通用消息"
ctrl_node_name = "手工循环控制器"

# Remove old loop back connection
if send_node_name in conns:
    # Filter out direct connection to ctrl_node
    # Actually, simplest way is to overwrite
    # But wait, send_node might have other outputs? No.
    pass 

# Wire Send -> Wait
conns[send_node_name] = {"main": [[{"node": wait_node['name'], "type": "main", "index": 0}]]}

# Wire Wait -> Ctrl
conns[wait_node['name']] = {"main": [[{"node": ctrl_node_name, "type": "main", "index": 0}]]}

# 4. Save
workflow = {
    "name": "AH Stock V7.7 Stable (Throttled)",
    "nodes": nodes,
    "connections": conns,
    "settings": workflow.get('settings', {}),
    "meta": workflow.get('meta', {})
}

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Success! Generated {OUTPUT_FILE} with Loop Throttling.")
