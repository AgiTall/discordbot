
import re
with open("bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

def find_func_end(start_idx):
    indent = None
    for i in range(start_idx, len(lines)):
        if "def " in lines[i] and indent is None:
            indent = len(lines[i]) - len(lines[i].lstrip())
            continue
        
        if indent is not None and lines[i].strip():
            curr_indent = len(lines[i]) - len(lines[i].lstrip())
            if curr_indent <= indent:
                return i
    return len(lines)

for i, line in enumerate(lines):
    if "def build_card_deck()" in line:
        start = i
        end = find_func_end(start)
        print(f"build_card_deck: {start} to {end}")
        break

