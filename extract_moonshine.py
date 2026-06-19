
import re

with open("bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

def get_block(start_idx):
    indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    for i in range(start_idx + 1, len(lines)):
        if lines[i].strip() == "":
            continue
        curr_indent = len(lines[i]) - len(lines[i].lstrip())
        if curr_indent <= indent:
            if "def " in lines[i] or "class " in lines[i] or "@" in lines[i]:
                return start_idx, i
    return start_idx, len(lines)

def find_block(pattern):
    for i, line in enumerate(lines):
        if pattern in line:
            return get_block(i)
    return None, None

def find_all_blocks():
    # Identify all Moonshine blocks
    blocks = []
    
    # helper functions
    patterns = [
        "def moonshine_text_key",
        "class MoonshineOwnerView",
        "class MoonshineMashSelect",
        "class MoonshineMashView",
        "class MoonshineSpecialSelect",
        "class MoonshineSpecialView",
        "class MoonshineUpgradeView",
        "class MoonshineMainView",
        "@bot.tree.command(name=\"moonshine\"",
        "async def moonshine_ingredient_autocomplete"
    ]
    for p in patterns:
        for i, line in enumerate(lines):
            if p in line:
                # for autocomplete we want the decorator above it
                if "async def moonshine_ingredient_autocomplete" in line:
                    if "@moonshine_command.autocomplete" in lines[i-1]:
                        s, e = get_block(i-1)
                        blocks.append((s, e, p))
                        break
                elif "@bot.tree.command" in line:
                    # we need to get the whole command
                    s, e = get_block(i)
                    # wait, get_block might fail if it uses @app_commands.describe
                    # let us search for the def instead
                    pass
                else:
                    s, e = get_block(i)
                    blocks.append((s, e, p))
                    break
                    
    # specifically for moonshine command
    for i, line in enumerate(lines):
        if "@bot.tree.command(name=\"moonshine\"" in line:
            # find end
            indent = None
            for j in range(i, len(lines)):
                if "async def " in lines[j] and indent is None:
                    indent = len(lines[j]) - len(lines[j].lstrip())
                    continue
                if indent is not None and lines[j].strip():
                    curr_indent = len(lines[j]) - len(lines[j].lstrip())
                    if curr_indent <= indent and ("def " in lines[j] or "class " in lines[j] or "@" in lines[j][:4]):
                        blocks.append((i, j, "moonshine command"))
                        break
            break

    for s, e, p in blocks:
        print(f"{p}: {s} to {e}")

find_all_blocks()

