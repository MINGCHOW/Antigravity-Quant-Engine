import json
import uuid
import os

INPUT_FILE = "AH_Stock_V7.4_Linear.json"
OUTPUT_FILE = "AH_Stock_V7.5_ManualLoop.json"

# --- V7.5 Manual Loop Nodes (FIXED) ---

def create_init_loop_node():
    # Use $getWorkflowStaticData global syntax
    js = r"""
// 1. 获取所有股票数据
const items = $('读取股票列表').all();

// 2. 初始化全局游标
// 尝试多种获取 staticData 的方式，确保兼容性
let staticData;
try {
    staticData = getWorkflowStaticData('global');
} catch(e) {
    try {
        staticData = $getWorkflowStaticData('global');
    } catch(e2) {
        console.log("Error getting static data: " + e2.message);
        // 如果这也失败，我们可能不在正确的 mode 下
        throw new Error("Unable to access getWorkflowStaticData. Ensure Code Node Mode is 'Run Once for All Items'.");
    }
}

staticData.nextIndex = 0;
staticData.total = items.length;
staticData.stockList = items.map(idx => idx.json); // 缓存纯JSON数据

console.log(`Initialized Manual Loop. Total items: ${items.length}`);
return { json: { status: "Loop Initialized", total: items.length } };
"""
    return {
        "parameters": {
            "mode": "runOnceForAllItems", # <--- CRITICAL FIX
            "jsCode": js
        },
        "id": str(uuid.uuid4()),
        "name": "初始化循环",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-9800, 1500]
    }

def create_loop_control_node():
    js = r"""
let staticData;
try {
    staticData = getWorkflowStaticData('global');
} catch(e) {
    staticData = $getWorkflowStaticData('global');
}

const idx = staticData.nextIndex || 0;
const list = staticData.stockList;

if (idx >= list.length) {
    // 循环结束
    console.log("Loop Finished.");
    return null; // Stop workflow branch
}

// 获取当前股票
const currentStock = list[idx];
console.log(`Processing Item ${idx + 1}/${list.length}: ${currentStock.code}`);

// 游标+1
staticData.nextIndex = idx + 1;

// 输出
return { json: currentStock };
"""
    return {
        "parameters": {
            "mode": "runOnceForAllItems", # <--- CRITICAL FIX
            "jsCode": js
        },
        "id": str(uuid.uuid4()),
        "name": "手工循环控制器",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-9500, 1500] 
    }

# --- Build Logic ---

if not os.path.exists(INPUT_FILE):
    # Fallback to V7.2 if V7.4 missing, but prefer 7.4 structure
    if os.path.exists("AH_Stock_V7.2_FullStack.json"):
        INPUT_FILE = "AH_Stock_V7.2_FullStack.json"
    else:
        print("Source file not found.")
        exit(1)

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    source_wf = json.load(f)

source_nodes = source_wf.get('nodes', [])

# 1. REMOVE OLD LOOP NODE
nodes = [n for n in source_nodes if n['name'] != "循环处理每只股票"]

# 2. ADD NEW NODES
init_node = create_init_loop_node()
ctrl_node = create_loop_control_node()
nodes.append(init_node)
nodes.append(ctrl_node)

# 3. RE-WIRE
conns = {}
def find_node(name): return next((n for n in nodes if n['name'] == name), None)

# Trigger -> Global -> Read List (Standard)
if find_node("定时触发_工作日18点"):
    conns["定时触发_工作日18点"] = {"main": [[{"node": "Global Context (API)", "type": "main", "index": 0}]]}
if find_node("Global Context (API)"):
    conns["Global Context (API)"] = {"main": [[{"node": "读取股票列表", "type": "main", "index": 0}]]}

# Read List -> Init Loop (Run once)
conns["读取股票列表"] = {"main": [[{"node": init_node['name'], "type": "main", "index": 0}]]}

# Init Loop -> Control Node
conns[init_node['name']] = {"main": [[{"node": ctrl_node['name'], "type": "main", "index": 0}]]}

# Control Node -> Full Stack Analysis (START OF CHAIN)
conns[ctrl_node['name']] = {"main": [[{"node": "Full Stack Analysis (API)", "type": "main", "index": 0}]]}

# Chain Wiring (Ensure nodes exist)
chain_names = ["Full Stack Analysis (API)", "Tavily新闻搜索", "构建AI提示词", "AI分析Agent", "解析AI分析结果", "写入飞书", "构建通用卡片", "发送通用消息"]
# If coming from V7.2, "构建通用卡片" and "发送通用消息" might NOT exist if we didn't run v7.4 build.
# We must inject them if missing.
# For safety, let's assume we are fixing V7.5 Manual Loop which WAS generated from V7.4.
# If V7.4 generation succeeded, we have the universal nodes.

# Restore chain wiring just in case
conns["Full Stack Analysis (API)"] = {"main": [[{"node": "Tavily新闻搜索", "type": "main", "index": 0}]]}
conns["Tavily新闻搜索"] = {"main": [[{"node": "构建AI提示词", "type": "main", "index": 0}]]}
conns["构建AI提示词"] = {"main": [[{"node": "AI分析Agent", "type": "main", "index": 0}]]}
conns["AI分析Agent"] = {"main": [[{"node": "解析AI分析结果", "type": "main", "index": 0}]]}
conns["解析AI分析结果"] = {"main": [[{"node": "写入飞书", "type": "main", "index": 0}]]}
conns["写入飞书"] = {"main": [[{"node": "构建通用卡片", "type": "main", "index": 0}]]}
conns["构建通用卡片"] = {"main": [[{"node": "发送通用消息", "type": "main", "index": 0}]]}

# END OF CHAIN -> LOOP BACK TO CONTROL NODE
conns["发送通用消息"] = {"main": [[{"node": ctrl_node['name'], "type": "main", "index": 0}]]}

# Model wiring
conns["Google Gemini Chat Model"] = {"ai_languageModel": [[{"node": "AI分析Agent", "type": "ai_languageModel", "index": 0}]]}

# 4. Save
workflow = {
    "name": "AH Stock V7.5 Manual Loop (Fixed Mode)",
    "nodes": nodes,
    "connections": conns,
    "settings": source_wf.get("settings", {}),
    "meta": source_wf.get("meta", {})
}

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Success! Generated {OUTPUT_FILE} with Manual Code Loop (Correct Mode).")
