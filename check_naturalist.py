
import ast
import re

with open("bot.py", "r", encoding="utf-8") as f:
    source = f.read()

tree = ast.parse(source)

naturalist_nodes = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.ClassDef):
        name = node.name.lower()
        if "naturalist" in name:
            naturalist_nodes.append(node.name)
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and "naturalist" in target.id.lower():
                naturalist_nodes.append(target.id)
                break

print("Found", len(naturalist_nodes), "nodes:")
for name in naturalist_nodes:
    print(name)

