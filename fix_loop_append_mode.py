import json
import os
import uuid

FILE_PATH = "AH_Stock_V7.2_FullStack.json"

def fix_loop_append_mode():
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        return

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])
    connections = workflow.get('connections', {})

    # 1. CLEANUP (Remove any existing structural mess)
    # Remove old merge nodes or collectors to start fresh logic
    nodes = [n for n in nodes if n['type'] != 'n8n-nodes-base.merge']
    
    # 2. CREATE THE "CORRECT" MERGE NODE
    # Name: Loop End Collector
    # Mode: append (CRITICAL: Do not use 'wait' or default)
    collector_name = "Loop End Collector"
    collector_node = {
        "parameters": {
           "mode": "append" # <--- THIS IS THE FIX. 
           # "append" means: output data as soon as ANY input arrives. Perfect for OR logic.
        },
        "id": str(uuid.uuid4()),
        "name": collector_name,
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3, # Use latest version if possible, or 2.1
        "position": [-8100, 1850] 
    }
    nodes.append(collector_node)

    # 3. IDENTIFY KEY NODES
    feishu_buy = next(n for n in nodes if n['name'] == '飞书发送消息_买入')
    feishu_other = next(n for n in nodes if n['name'] == '飞书发送消息_其他')
    loop_node = next(n for n in nodes if n['name'] == '循环处理每只股票')

    # 4. WIRE FREISHU -> COLLECTOR
    # Important: Merge node has input 0 and 1.
    connections[feishu_buy['name']] = {"main": [[{"node": collector_name, "type": "main", "index": 0}]]}
    connections[feishu_other['name']] = {"main": [[{"node": collector_name, "type": "main", "index": 1}]]}

    # 5. WIRE COLLECTOR -> LOOP
    connections[collector_name] = {"main": [[{"node": loop_node['name'], "type": "main", "index": 0}]]}

    # 6. UPDATE WORKFLOW
    workflow['nodes'] = nodes
    workflow['connections'] = connections
    
    # 7. SAVE
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Successfully patched {FILE_PATH} with 'Append' Mode Merge Node!")

if __name__ == "__main__":
    fix_loop_append_mode()
