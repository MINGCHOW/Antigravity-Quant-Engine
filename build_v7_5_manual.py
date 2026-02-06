import json
import uuid
import os

INPUT_FILE = "AH_Stock_V7.4_Linear.json"
OUTPUT_FILE = "AH_Stock_V7.5_ManualLoop.json"

# --- V7.5 Manual Loop Nodes ---

def create_init_loop_node():
    # Runs ONCE at workflow start to fetch data and reset index
    js = r"""
// 1. 获取所有股票数据
const items = $('读取股票列表').all();
// 2. 初始化全局游标
const staticData = getWorkflowStaticData('global');
staticData.nextIndex = 0;
staticData.total = items.length;
staticData.stockList = items.map(idx => idx.json); // 缓存纯JSON数据

console.log(`Initialized Manual Loop. Total items: ${items.length}`);
return { json: { status: "Loop Initialized", total: items.length } };
"""
    return {
        "parameters": {
            "jsCode": js
        },
        "id": str(uuid.uuid4()),
        "name": "初始化循环",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-9800, 1500],
        # Only run once not needed because wiring prevents re-run
    }

def create_loop_control_node():
    # The Heart: Checks index and emits ONE item or Stops
    js = r"""
const staticData = getWorkflowStaticData('global');
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
    print("Source V7.4 not found.")
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
conns["定时触发_工作日18点"] = {"main": [[{"node": "Global Context (API)", "type": "main", "index": 0}]]}
conns["Global Context (API)"] = {"main": [[{"node": "读取股票列表", "type": "main", "index": 0}]]}

# Read List -> Init Loop (Run once)
conns["读取股票列表"] = {"main": [[{"node": init_node['name'], "type": "main", "index": 0}]]}

# Init Loop -> Control Node
conns[init_node['name']] = {"main": [[{"node": ctrl_node['name'], "type": "main", "index": 0}]]}

# Control Node -> Full Stack Analysis (START OF CHAIN)
conns[ctrl_node['name']] = {"main": [[{"node": "Full Stack Analysis (API)", "type": "main", "index": 0}]]}

# Chain: Output of Ctrl -> API -> Tavily -> Prompt -> Agent -> Parse -> Write -> Card -> Send
# (Assume these nodes exist from V7.4 source)
conns["Full Stack Analysis (API)"] = {"main": [[{"node": "Tavily新闻搜索", "type": "main", "index": 0}]]}
conns["Tavily新闻搜索"] = {"main": [[{"node": "构建AI提示词", "type": "main", "index": 0}]]}
conns["构建AI提示词"] = {"main": [[{"node": "AI分析Agent", "type": "main", "index": 0}]]}
conns["AI分析Agent"] = {"main": [[{"node": "解析AI分析结果", "type": "main", "index": 0}]]}
conns["解析AI分析结果"] = {"main": [[{"node": "写入飞书", "type": "main", "index": 0}]]}
conns["写入飞书"] = {"main": [[{"node": "构建通用卡片", "type": "main", "index": 0}]]}
conns["构建通用卡片"] = {"main": [[{"node": "发送通用消息", "type": "main", "index": 0}]]}

# END OF CHAIN -> LOOP BACK TO CONTROL NODE
# Replaces the old Loop wiring
conns["发送通用消息"] = {"main": [[{"node": ctrl_node['name'], "type": "main", "index": 0}]]}

# Model wiring
conns["Google Gemini Chat Model"] = {"ai_languageModel": [[{"node": "AI分析Agent", "type": "ai_languageModel", "index": 0}]]}

# 4. Save
workflow = {
    "name": "AH Stock V7.5 Manual Loop (Nuclear)",
    "nodes": nodes,
    "connections": conns,
    "settings": source_wf.get("settings", {}),
    "meta": source_wf.get("meta", {})
}

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Success! Generated {OUTPUT_FILE} with Manual Code Loop.")
