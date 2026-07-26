import random
import unittest
from datetime import datetime, timezone

from src.collector_logic import (
    COLLECTIONS, COLLECTION_ITEMS, COLLECTOR_PLANTS, DETECTOR_PRICE,
    SHOVEL_PRICE, begin_search, buy_plant, default_collector_data, grant_find,
    normalize_collector_data, progress, sell_individual_items, sell_set,
    sell_all_collections, simple_search_collections,
)

class CollectorLogicTests(unittest.TestCase):
    def test_all_nine_collections_have_items(self):
        self.assertEqual(9, len(COLLECTIONS))
        self.assertTrue(all(COLLECTION_ITEMS[key] for key in COLLECTIONS))

    def test_search_has_no_level_or_tool_gate(self):
        data = default_collector_data()
        data["maps"]["fossils"] = 1
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

    def test_reference_tool_and_map_prices(self):
        self.assertEqual(350, SHOVEL_PRICE)
        self.assertEqual(700, DETECTOR_PRICE)
        self.assertEqual(
            {
                "tarot": 14,
                "bottles": 13,
                "flowers": 12.50,
                "eggs": 19,
                "heirlooms": 14.50,
                "arrowheads": 18,
                "coins": 27,
                "jewelry": 26,
                "fossils": 30,
            },
            {key: rule["map_price"] for key, rule in COLLECTIONS.items()},
        )

    def test_shop_contains_only_reference_plants(self):
        expected = {
            "Корень лопуха",
            "Тысячелистник агавоподобный",
            "Индейский табак",
            "Молочай",
            "Фиолетовый подснежник",
            "Дикий пиретрум",
            "Пустынный мак",
            "Тысячелистник",
            "Олеандр",
            "Женьшень",
            "Смородина",
            "Шалфей",
        }
        self.assertEqual(expected, set(COLLECTOR_PLANTS))

    def test_plant_inventory_is_normalized_and_incremented(self):
        data = normalize_collector_data(
            {"plants": {"Олеандр": "2", "Одежда": 10}}
        )
        self.assertEqual({"Олеандр": 2}, data["plants"])
        self.assertEqual(3, buy_plant(data, "Олеандр"))
        with self.assertRaises(ValueError):
            buy_plant(data, "Одежда")

    def test_simple_search_opens_every_collection_immediately(self):
        data = default_collector_data()
        self.assertEqual(set(COLLECTIONS), set(simple_search_collections(data)))

    def test_sell_all_prioritizes_complete_sets(self):
        data = default_collector_data()
        for item in COLLECTION_ITEMS["flowers"]:
            data["inventory"][item] = 1
        extra = COLLECTION_ITEMS["tarot"][0]
        data["inventory"][extra] = 2
        result = sell_all_collections(data)
        self.assertEqual(1, result["sets"])
        self.assertEqual(len(COLLECTION_ITEMS["flowers"]) + 2, result["count"])
        self.assertEqual({}, {
            key: qty for key, qty in data["inventory"].items() if qty
        })

if __name__ == "__main__": unittest.main()
