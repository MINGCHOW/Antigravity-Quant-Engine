import json
import os

file_path = 'AH_Stock_V6_Cloud.json'

if not os.path.exists(file_path):
    print(f"Error: {file_path} not found.")
    exit(1)

with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = data.get('nodes', [])
node_map = {n['name']: n for n in nodes}

print(f"Total Cloud Nodes: {len(nodes)}")

# Check Key V6 Cloud Nodes
cloud_nodes = ["Global Context (API)", "Market Regime Filter", "Stock Risk Analysis (API)", "Merge Analysis Data"]
for name in cloud_nodes:
    if name in node_map:
        if "API" in name:
            if node_map[name]['type'] == "n8n-nodes-base.httpRequest":
                 print(f"[OK] Node '{name}' found and is HTTP Request.")
            else:
                 print(f"[FAIL] Node '{name}' SHOULD be HTTP Request.")
        else:
             print(f"[OK] Node '{name}' found.")
    else:
        print(f"[FAIL] Node '{name}' MISSING!")

# Check Logic
if node_map['Global Context (API)']['parameters']['url'].endswith('/market'):
    print("[OK] Global Context API URL seems correct (/market).")
else:
    print("[FAIL] Global Context API URL mismatch.")
    
if node_map['Stock Risk Analysis (API)']['parameters']['url'].endswith('/stock'):
    print("[OK] Stock Logic API URL seems correct (/stock).")
else:
    print("[FAIL] Stock Logic API URL mismatch.")

print("Cloud Workflow Validation Complete.")
