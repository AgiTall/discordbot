
import sys

def process():
    with open("bot.py", "r", encoding="utf-8") as f:
        lines = f.readlines()

    def find_end_of_block(start_idx):
        indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
        for i in range(start_idx + 1, len(lines)):
            if lines[i].strip() == "":
                continue
            curr_indent = len(lines[i]) - len(lines[i].lstrip())
            if curr_indent <= indent:
                return i
        return len(lines)

    for i, line in enumerate(lines):
        if "def blackjack_card_value" in line:
            print(f"blackjack_card_value: {i} to {find_end_of_block(i)}")
        if "class BlackjackView" in line:
            print(f"BlackjackView: {i} to {find_end_of_block(i)}")
        if "@bot.tree.command(name=\"blackjack\"" in line:
            print(f"blackjack command: {i} to {find_end_of_block(i+1)}")

process()

