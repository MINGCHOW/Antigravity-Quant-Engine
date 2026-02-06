
import json

def validate_workflow(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    nodes = data.get('nodes', [])
    connections = data.get('connections', {})
    
    node_names = {n['name'] for n in nodes}
    node_map = {n['name']: n for n in nodes}
    
    print(f"Total nodes found: {len(nodes)}")
    
    missing_nodes = set()
    
    # Check connections keys (source nodes)
    for source_node in connections.keys():
        if source_node not in node_names:
            print(f"MISSING SOURCE NODE in connections: {source_node}")
            missing_nodes.add(source_node)
            
        # Check targets
        for output_type, outputs in connections[source_node].items():
            for output in outputs:
                for target in output:
                    target_node = target['node']
                    if target_node not in node_names:
                        print(f"MISSING TARGET NODE in connections: {target_node} (referenced by {source_node})")
                        missing_nodes.add(target_node)

    # Check for suspected merged node
    suspect_node = node_map.get("解析AI分析结果")
    if suspect_node:
        params = suspect_node.get('parameters', {})
        if 'systemMessage' in params.get('options', {}) or 'promptType' in params:
            print("\nPOSSIBLE CORRUPTION DETECTED:")
            print(f"Node '解析AI分析结果' (type: {suspect_node.get('type')}) has 'systemMessage' or 'promptType' parameters.")
            print("This usually indicates a Merge Error where the definition of an AI/Prompt node was pasted over a Code node.")

    if not missing_nodes:
        print("\nAll connected nodes are present in the 'nodes' list.")
    else:
        print(f"\nTotal missing nodes referenced in connections: {len(missing_nodes)}")

validate_workflow(r'd:\Antigravity-\AH_Stock_V5_Final.json')
