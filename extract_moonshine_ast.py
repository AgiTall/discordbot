
import ast
import re

with open("bot.py", "r", encoding="utf-8") as f:
    source = f.read()

tree = ast.parse(source)

moonshine_nodes = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        if "moonshine" in node.name.lower() or "moonshiner" in node.name.lower():
            moonshine_nodes.append(node)
    elif isinstance(node, ast.AsyncFunctionDef):
        if "moonshine" in node.name.lower() or "moonshiner" in node.name.lower():
            moonshine_nodes.append(node)
    elif isinstance(node, ast.ClassDef):
        if "moonshine" in node.name.lower() or "moonshiner" in node.name.lower():
            moonshine_nodes.append(node)
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and ("moonshine" in target.id.lower() or "moonshiner" in target.id.lower()):
                moonshine_nodes.append(node)
                break

lines = source.split("\n")

def get_node_source(node):
    return "\n".join(lines[node.lineno - 1:node.end_lineno])

for node in moonshine_nodes:
    if hasattr(node, "name"):
        print(f"Found: {node.name}")
    else:
        print(f"Found assignment at {node.lineno}")

print(f"Total moonshine nodes: {len(moonshine_nodes)}")

