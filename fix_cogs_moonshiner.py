
import re
with open("cogs/moonshiner.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix super().__init__(...) \n self.bot = bot issues inside MoonshineOwnerView and others where super init is split
text = re.sub(r"super\(\)\.__init__\(\n\s+self\.bot = bot", "super().__init__(", text)
text = re.sub(r"super\(\)\.__init__\(user_id\)\n\s+self\.bot = bot", "super().__init__(user_id)", text)

with open("cogs/moonshiner.py", "w", encoding="utf-8") as f:
    f.write(text)
print("fixed")

