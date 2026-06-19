
import ast
import re

with open("bot.py", "r", encoding="utf-8") as f:
    source = f.read()

tree = ast.parse(source)

bounty_nodes = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.ClassDef):
        name = node.name.lower()
        if "bounty" in name:
            bounty_nodes.append(node.name)
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and "bounty" in target.id.lower():
                bounty_nodes.append(target.id)
                break

print("Found", len(bounty_nodes), "nodes:")
for name in bounty_nodes:
    print(name)

