import json
import os
import uuid

FILE_PATH = "AH_Stock_V7.2_FullStack.json"

def fix_v7_2_structural():
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        return

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])
    connections = workflow.get('connections', {})

    # 1. Create Collector Node
    collector_id = str(uuid.uuid4())
    collector_name = "Loop End Collector"
    
    collector_node = {
        "parameters": {
           "mode": "wait" # Wait for any input to arrive before proceeding (standard loop closing)
           # Actually, for loop closing, we want "Pass Through" logic
           # In older n8n, Merge 'Append' or 'Wait' works.
           # Let's use a simple "NoOp" Code node or Merge.
           # Merge is safest visual indicator.
        },
        "id": collector_id,
        "name": collector_name,
        "type": "n8n-nodes-base.merge",
        "typeVersion": 2.1,
        "position": [-8200, 1800] # Place it nicely at the end
    }

    # Remove old Merge if exists (just in case)
    workflow['nodes'] = [n for n in nodes if n['name'] != collector_name]
    nodes = workflow['nodes']
    nodes.append(collector_node)

    # 2. Re-route Feishu Messages -> Collector
    feishu_buy = next(n for n in nodes if n['name'] == '飞书发送消息_买入')
    feishu_other = next(n for n in nodes if n['name'] == '飞书发送消息_其他')
    loop_node = next(n for n in nodes if n['name'] == '循环处理每只股票')

    # Connect Feishu Nodes to Collector
    connections[feishu_buy['name']] = {"main": [[{"node": collector_name, "type": "main", "index": 0}]]}
    connections[feishu_other['name']] = {"main": [[{"node": collector_name, "type": "main", "index": 1}]]} 
    # Merge node has input 0 and 1. We wire one to each.

    # 3. Connect Collector -> Loop
    # This closes the loop.
    connections[collector_name] = {"main": [[{"node": loop_node['name'], "type": "main", "index": 0}]]}

    workflow['connections'] = connections
    
    # 4. Save
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Successfully patched {FILE_PATH} with Structural Loop End!")

if __name__ == "__main__":
    fix_v7_2_structural()
