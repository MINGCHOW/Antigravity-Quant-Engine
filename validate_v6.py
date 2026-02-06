import json
import os

file_path = 'AH_Stock_V6_AkShare.json'

if not os.path.exists(file_path):
    print(f"Error: {file_path} not found.")
    exit(1)

with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = data.get('nodes', [])
connections = data.get('connections', {})
node_map = {n['name']: n for n in nodes}

print(f"Total V6 Nodes: {len(nodes)}")

# Check Key V6 Nodes
v6_nodes = ["Global Context (AkShare)", "Market Regime Filter", "Stock Risk Analysis", "Merge Analysis Data"]
for name in v6_nodes:
    if name in node_map:
        print(f"[OK] Node '{name}' found.")
        # Check specific config
        if name == "Global Context (AkShare)":
            cmd = node_map[name]['parameters']['command']
            if "python" in cmd and "--mode market" in cmd:
                 print(f"  -> Command verified: {cmd}")
        if name == "Stock Risk Analysis":
            cmd = node_map[name]['parameters']['command']
            if "python" in cmd and "--mode stock" in cmd and "{{ $json.code }}" in cmd:
                 print(f"  -> Command verified: {cmd}")
    else:
        print(f"[FAIL] Node '{name}' MISSING!")

# Check Connection Flow
# Trigger -> Global Context
trigger_node_name = "定时触发_工作日18点"
if connections.get(trigger_node_name, {}).get('main', [[]])[0][0]['node'] == "Global Context (AkShare)":
    print("[OK] Trigger connects to Global Context.")
else:
    print("[FAIL] Connection broken: Trigger -> Global Context")

# Merge Analysis -> Tavily
if connections.get("Merge Analysis Data", {}).get('main', [[]])[0][0]['node'] == "Tavily新闻搜索":
    print("[OK] Merge Analysis connects to Tavily.")
else:
    print("[FAIL] Connection broken: Merge Analysis -> Tavily")

# Check Feishu Update
feishu_body = node_map['写入飞书']['parameters']['body']
if "建议仓位(手)" in feishu_body and "大盘状态" in feishu_body:
    print("[OK] Feishu body updated with V6 fields.")
else:
    print("[FAIL] Feishu body missing V6 fields.")
