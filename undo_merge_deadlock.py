import json
import os

FILE_PATH = "AH_Stock_V7.2_FullStack.json"

def undo_merge_deadlock():
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        return

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])
    connections = workflow.get('connections', {})

    # 1. IDENTIFY and REMOVE the "Loop End Collector" (Merge)
    # Also remove the original "合并推送结果" if it somehow survived
    deadlock_nodes = [n for n in nodes if n['type'] == 'n8n-nodes-base.merge']
    
    if not deadlock_nodes:
        print("No Merge nodes found. Topology might already be direct. Checking connections...")
    else:
        print(f"Found {len(deadlock_nodes)} Merge nodes. Removing them to prevent deadlock...")
        workflow['nodes'] = [n for n in nodes if n['type'] != 'n8n-nodes-base.merge']
        nodes = workflow['nodes']

    # 2. RE-WIRE Direct Connections (Feishu -> Loop)
    # Ensure Feishu nodes exist
    feishu_buy = next((n for n in nodes if n['name'] == '飞书发送消息_买入'), None)
    feishu_other = next((n for n in nodes if n['name'] == '飞书发送消息_其他'), None)
    loop_node = next((n for n in nodes if n['name'] == '循环处理每只股票'), None)

    if feishu_buy and feishu_other and loop_node:
        print("Re-wiring Feishu Nodes directly to SplitInBatches...")
        
        # Build the Connection Object (Loop Input)
        loop_conn = [{"node": loop_node['name'], "type": "main", "index": 0}]
        
        # Modify Connections Registry
        connections[feishu_buy['name']] = {"main": [loop_conn]}
        connections[feishu_other['name']] = {"main": [loop_conn]}
        
        # Clean up any reference to the deleted Merge node in connections
        # (Though reassigning above covers the outgoing keys)
        # We should also remove the 'Loop End Collector' key from connections if it exists as a source
        keys_to_remove = [k for k in connections if "Collector" in k or "合并" in k]
        for k in keys_to_remove:
            del connections[k]

    # 3. VERIFY CRITICAL SETTINGS (Double Check Ironclad)
    api_node = next((n for n in nodes if n['name'] == 'Full Stack Analysis (API)'), None)
    if api_node:
        api_node['onError'] = 'continueRegularOutput'
        api_node['alwaysOutputData'] = True
        print("Verified API Node Resilience.")

    # 4. Save
    workflow['connections'] = connections
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Successfully patched {FILE_PATH}: REMOVED DEADLOCK NODE.")

if __name__ == "__main__":
    undo_merge_deadlock()
