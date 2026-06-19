
import os

data_dir_code = "DATA_DIR = os.environ.get(\"DATA_DIR\", \"data\")"

# Fix bot.py
with open("bot.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("def __init__(self, db_path=\"data/economy.db\"):", "def __init__(self, db_path=os.path.join(os.environ.get(\"DATA_DIR\", \"data\"), \"economy.db\")):")
text = text.replace("def __init__(self, db_path=\"data/leveling.db\"):", "def __init__(self, db_path=os.path.join(os.environ.get(\"DATA_DIR\", \"data\"), \"leveling.db\")):")

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(text)

# Fix src/leveling.py
with open("src/leveling.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("LEVELING_DB = \"data/leveling.db\"", "LEVELING_DB = os.path.join(os.environ.get(\"DATA_DIR\", \"data\"), \"leveling.db\")")
text = text.replace("class LevelingDB:\n    def __init__(self, db_path=LEVELING_DB):", "import os\n\nclass LevelingDB:\n    def __init__(self, db_path=LEVELING_DB):")

with open("src/leveling.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed DATA_DIR")

