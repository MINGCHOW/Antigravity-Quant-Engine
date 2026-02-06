import json
import os

file_path = 'AH_Stock_V5_ATR_Pro.json'

if not os.path.exists(file_path):
    print(f"Error: File {file_path} not found.")
    exit(1)

with open(file_path, 'r', encoding='utf-8') as f:
    try:
        data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}")
        exit(1)

nodes = data.get('nodes', [])
node_map = {n['name']: n for n in nodes}

expected_nodes = [
    '计算A股技术指标',
    '计算港股技术指标',
    '构建AI提示词',
    '解析AI分析结果',
    '写入飞书'
]

print(f"Total nodes: {len(nodes)}")

for name in expected_nodes:
    if name not in node_map:
        print(f"ERROR: Node '{name}' missing!")
        continue
    
    node = node_map[name]
    js_code = node.get('parameters', {}).get('jsCode', '')
    body = node.get('parameters', {}).get('body', '')
    
    if name == '计算A股技术指标':
        if 'calculateATR' in js_code and 'ema13 > ema26' in js_code:
            print(f"MATCH: {name} (ATR/EMA/Algo V5 detected)")
        else:
            print(f"FAIL: {name} content mismatch")
            
    elif name == '计算港股技术指标':
        if 'calculateATR' in js_code and 'stopLossLevel' in js_code and '2.5 * atr14' in js_code:
            print(f"MATCH: {name} (ATR/EMA/HK-Specific Algo detected)")
        else:
            print(f"FAIL: {name} content mismatch - check stop loss multiplier or ATR function")

    elif name == '构建AI提示词':
        if '市场波动率(ATR)' in js_code and 'dynamic stop loss' in js_code.lower() or '动态止损' in js_code:
            print(f"MATCH: {name} (New Prompt detected)")
        else:
            print(f"FAIL: {name} content mismatch")

    elif name == '解析AI分析结果':
        if 'try {' in js_code and 'technical =' in js_code:
             print(f"MATCH: {name} (Robust parsing detected)")
        else:
            print(f"FAIL: {name} content mismatch")

    elif name == '写入飞书':
        if '"ATR": Number' in body:
             print(f"MATCH: {name} (ATR Field detected)")
        else:
            print(f"FAIL: {name} content mismatch")

print("Validation complete.")
