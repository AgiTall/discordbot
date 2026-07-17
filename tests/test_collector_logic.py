import random
import unittest
from datetime import datetime, timezone

from src.collector_logic import (
    COLLECTIONS, COLLECTION_ITEMS, default_collector_data, normalize_collector_data,
    progress, begin_search, grant_find, sell_set, sell_individual_items,
)

class CollectorLogicTests(unittest.TestCase):
    def test_all_nine_collections_have_items(self):
        self.assertEqual(9, len(COLLECTIONS))
        self.assertTrue(all(COLLECTION_ITEMS[key] for key in COLLECTIONS))

    def test_locked_tool_and_successful_search(self):
        data = default_collector_data(); data["level"] = 20
        data["maps"]["fossils"] = 1
        blocked = begin_search(data, "fossils")
        self.assertEqual("tools", blocked["error"])
        data["tools"] = {"shovel": True, "detector": True}
        self.assertTrue(begin_search(data, "fossils")["ready"])
        found = grant_find(data, "fossils", random.Random(1))
        self.assertTrue(found["found"])
        self.assertEqual(1, sum(data["inventory"].values()))

    def test_sell_set_and_individual_items(self):
        data = default_collector_data()
        for item in COLLECTION_ITEMS["flowers"]: data["inventory"][item] = 2
        self.assertEqual(COLLECTIONS["flowers"]["payout"], sell_set(data, "flowers"))
        count, reward = sell_individual_items(data, "flowers")
        self.assertEqual(len(COLLECTION_ITEMS["flowers"]), count)
        self.assertGreater(reward, 0)
        self.assertEqual((0, len(COLLECTION_ITEMS["flowers"])), progress(data, "flowers"))

    def test_normalize_discards_unknown_items(self):
        data = normalize_collector_data({"inventory": {"fake": 10}})
        self.assertEqual({}, data["inventory"])

if __name__ == "__main__": unittest.main()
