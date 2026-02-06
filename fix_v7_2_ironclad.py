import json
import os

FILE_PATH = "AH_Stock_V7.2_FullStack.json"

def fix_v7_2_ironclad():
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        return

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])

    # The Loop Chain Nodes - ALL of them must survive execution
    loop_nodes = [
        "Full Stack Analysis (API)",
        "Tavily新闻搜索",
        "构建AI提示词",
        "AI分析Agent",
        "解析AI分析结果",
        "写入飞书",
        "判断是否买入信号",
        "构建飞书卡片_买入",
        "构建飞书卡片_其他",
        "飞书发送消息_买入",
        "飞书发送消息_其他"
    ]

    print("Applying IRONCLAD error tolerance to all loop nodes...")
    
    for node in nodes:
        if node['name'] in loop_nodes:
            # 1. Continue on Error (The Shield)
            node['onError'] = 'continueRegularOutput'
            
            # 2. Always Output (The Bridge)
            # Ensures even if it produces no data, it passes an empty item to keep flow moving
            node['alwaysOutputData'] = True
            
            print(f"  - Secured node: {node['name']}")
            
            # 3. Add Retry to Fragile Network Nodes (AI, Feishu)
            # API already has it. Let's add it to others.
            if node['type'] in ['n8n-nodes-base.httpRequest', '@n8n/n8n-nodes-langchain.agent', 'n8n-nodes-feishu-lite.feishuNode']:
                node['retryOnFail'] = True
                node['maxTries'] = 3
                node['waitBetweenTries'] = 2000
                print(f"    + Added Retry Policy to {node['name']}")

    # 4. Save
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Successfully patched {FILE_PATH} with IRONCLAD resilience!")

if __name__ == "__main__":
    fix_v7_2_ironclad()
