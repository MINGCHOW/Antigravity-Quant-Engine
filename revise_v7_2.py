import json
import os

FILE_PATH = "AH_Stock_V7.2_FullStack.json"

def revise_workflow():
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        return

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])
    connections = workflow.get('connections', {})

    # 1. Modify SplitInBatches (Set Batch Size = 1)
    split_node = next((n for n in nodes if n['name'] == '循环处理每只股票'), None)
    if split_node:
        print("Setting SplitInBatches batchSize to 1...")
        # Ensure parameters options exists
        if 'parameters' not in split_node: split_node['parameters'] = {}
        if 'options' not in split_node['parameters']: split_node['parameters']['options'] = {}
        split_node['parameters']['options']['reset'] = False
        split_node['parameters']['batchSize'] = 1

    # 2. Remove Merge Node (Fix Deadlock)
    merge_node = next((n for n in nodes if n['name'] == '合并推送结果'), None)
    
    if merge_node:
        print(f"Removing Merge node: {merge_node['name']} to prevent deadlock...")
        workflow['nodes'] = [n for n in nodes if n['name'] != merge_node['name']]
        
        # We need to re-route connections that went TO Merge node, directly TO Loop node
        # Sources to Merge: '飞书发送消息_买入', '飞书发送消息_其他'
        # Target: '循环处理每只股票'
        
        # Loop through all connections to find those pointing to Merge Node
        target_node_name = split_node['name']
        
        for source_name, output_conns in connections.items():
            if 'main' in output_conns:
                new_main = []
                for output_branch in output_conns['main']:
                    new_branch = []
                    for conn in output_branch:
                        if conn['node'] == merge_node['name']:
                            # Redirect to Split Loop Node
                            print(f"Redirecting {source_name} -> Loop Node")
                            new_branch.append({
                                "node": target_node_name,
                                "type": "main",
                                "index": 0
                            })
                        else:
                            new_branch.append(conn)
                    new_main.append(new_branch)
                connections[source_name]['main'] = new_main
        
        # Remove the Merge Node entry itself from connections (inputs of Split Loop were connected here)
        if merge_node['name'] in connections:
            # Merge node connected to Split Loop. We don't need this anymore as we redirected sources above.
            del connections[merge_node['name']]

    # 3. Ensure "Market Regime Filter" is still gone (Just in case)
    workflow['nodes'] = [n for n in nodes if n['name'] != "Market Regime Filter"]
    if "Market Regime Filter" in connections: del connections["Market Regime Filter"]

    # 4. Save
    workflow['connections'] = connections
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Successfully revised {FILE_PATH}")

if __name__ == "__main__":
    revise_workflow()
