import json
import os

FILE_PATH = "AH_Stock_V7.2_FullStack.json"

def patch_workflow():
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        return

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])
    connections = workflow.get('connections', {})

    # 1. Identify Nodes
    global_ctx = next((n for n in nodes if n['name'] == 'Global Context (API)'), None)
    read_list = next((n for n in nodes if n['name'] == '读取股票列表'), None)
    prompt_node = next((n for n in nodes if n['name'] == '构建AI提示词'), None)
    filter_node = next((n for n in nodes if n['name'] == 'Market Regime Filter'), None)

    if not all([global_ctx, read_list, prompt_node]):
        print("Critical nodes missing.")
        return

    # 2. Bypass Market Regime Filter
    # Connect Global Context directly to Read List
    if filter_node:
        print(f"Removing filter node: {filter_node['name']}")
        workflow['nodes'] = [n for n in nodes if n['name'] != filter_node['name']]
        
        # Update connections
        # Remove connection FROM global_ctx TO filter
        # Add connection FROM global_ctx TO read_list
        connections[global_ctx['name']] = {
            "main": [[
                {"node": read_list['name'], "type": "main", "index": 0}
            ]]
        }
        
        # Remove connections FROM filter (if any remain in dictionary)
        if filter_node['name'] in connections:
            del connections[filter_node['name']]

    # 3. Update AI Prompt with Dynamic Risk Logic
    current_js = prompt_node['parameters'].get('jsCode', '')
    if "risk_instruction" not in current_js:
        print("Injecting dynamic risk logic into AI Prompt...")
        # We need to inject the logic before the final return
        injection = r"""
// --- 动态风险提示逻辑 ---
let risk_instruction = "";
if (marketStatus === 'Bear' || marketStatus === 'Crash') {
    risk_instruction = `
!!! 🔴 严重警告：当前处于熊市/暴跌环境 (${marketStatus}) !!!
1. **严格标准**：仅允许评分>85且有重大利好的个股操作。
2. **强制轻仓**：建议仓位必须减半，或者直接建议空仓。
3. **寻找做空机会**：如果是港股，优先寻找做空逻辑；如果是A股，建议以“观望”为主。
4. **措辞严厉**：请在核心结论中用粗体强调大盘风险。`;
}

const final_prompt = prompt + risk_instruction;

return {
    json: {
        prompt: final_prompt,
        raw_data: data
    }
};
"""
        # Replace the simple return with our logic
        # The prompt defines 'const prompt = ...' and ends with 'return { json: { prompt: prompt ... } };'
        # We replace the end.
        
        # Heuristic replacement
        if "return {" in current_js:
             # Find the last return
            parts = current_js.rsplit("return {", 1)
            new_js = parts[0] + injection
            prompt_node['parameters']['jsCode'] = new_js

    # 4. Deep Check Loop Connection
    loop_node = next((n for n in nodes if n['name'] == '循环处理每只股票'), None)
    analysis_node = next((n for n in nodes if n['name'] == 'Full Stack Analysis (API)'), None)
    
    if loop_node and analysis_node:
        loop_conn = connections.get(loop_node['name'], {})
        main_conns = loop_conn.get('main', [])
        # Ensure at least 1 output list exists
        if not main_conns:
            main_conns.append([])
        
        # Ensure output 0 connects to Analysis
        target_conn = {"node": analysis_node['name'], "type": "main", "index": 0}
        
        # Check if connected
        connected = False
        if len(main_conns) > 0:
            for c in main_conns[0]:
                if c['node'] == analysis_node['name']:
                    connected = True
                    break
        
        if not connected:
            print("Fixing broken Loop -> Analysis connection...")
            if len(main_conns) == 0: main_conns.append([])
            main_conns[0].append(target_conn)
            connections[loop_node['name']]['main'] = main_conns
            
    workflow['connections'] = connections
    
    # Save
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Successfully patched {FILE_PATH}")

if __name__ == "__main__":
    patch_workflow()
