
import ast
import re

with open("bot.py", "r", encoding="utf-8") as f:
    source = f.read()

tree = ast.parse(source)

logic_nodes = []
# We only want pure data constants and helper functions. 
# We DO NOT want Views or discord app commands!
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        name = node.name.lower()
        if "moonshine" in name and not name.endswith("_command"):
            logic_nodes.append(node)
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and "moonshine" in target.id.lower():
                logic_nodes.append(node)
                break

lines = source.split("\n")

extracted_lines = []
nodes_to_remove = []

for node in logic_nodes:
    start_lineno = node.lineno
    if hasattr(node, "decorator_list") and node.decorator_list:
        start_lineno = node.decorator_list[0].lineno
    end_lineno = node.end_lineno
    
    extracted_lines.extend(lines[start_lineno - 1:end_lineno])
    extracted_lines.append("")
    extracted_lines.append("")
    nodes_to_remove.append((start_lineno - 1, end_lineno))

nodes_to_remove = sorted(nodes_to_remove, key=lambda x: x[0])

merged_remove = []
for s, e in nodes_to_remove:
    if not merged_remove:
        merged_remove.append([s, e])
    else:
        last_s, last_e = merged_remove[-1]
        if s <= last_e + 1: # combine if adjacent or overlapping
            merged_remove[-1][1] = max(last_e, e)
        else:
            merged_remove.append([s, e])

new_bot_lines = []
for i, line in enumerate(lines):
    in_remove = False
    for s, e in merged_remove:
        if s <= i < e:
            in_remove = True
            break
    if not in_remove:
        new_bot_lines.append(line)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write("\n".join(new_bot_lines))

with open("src/moonshiner_logic.py", "w", encoding="utf-8") as f:
    f.write("import time\nimport math\nimport random\nimport json\nimport discord\nfrom discord import app_commands\n\n")
    f.write("\n".join(extracted_lines))

print(f"Extracted {len(logic_nodes)} nodes to src/moonshiner_logic.py")

