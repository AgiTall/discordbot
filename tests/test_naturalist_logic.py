import unittest

from src.naturalist_logic import (
    ANIMALS,
    CATEGORIES,
    LEGENDARY_ANIMALS,
    NATURALIST_CAMP_PRICE,
    NATURALIST_LEGENDARY_REQUIRED_LEVEL,
    NATURALIST_PHEROMONE_PRICE,
    NATURALIST_REGIONS,
    NATURALIST_REVIVER_PRICE,
    NATURALIST_TRANQ_PACK_PRICE,
    NATURALIST_TRANQ_PACK_SIZE,
    add_legendary_pelt,
    anger_harriet,
    default_naturalist_data,
    get_naturalist_category_progress,
    get_legendary_pelt_capacity,
    get_naturalist_tranq_cap,
    has_full_naturalist_category,
    normalize_naturalist_data,
    pop_best_legendary_pelt,
    stamp_naturalist_samples,
)


class NaturalistLogicTests(unittest.TestCase):
    def test_reference_sample_rewards(self):
        self.assertTrue(all(animal["cash"] <= 4 for animal in ANIMALS.values()))
        self.assertTrue(all(animal["xp"] == 50 for animal in ANIMALS.values()))
        self.assertEqual(15.0, min(animal["cash"] for animal in LEGENDARY_ANIMALS.values()))
        self.assertEqual(60.0, max(animal["cash"] for animal in LEGENDARY_ANIMALS.values()))
        self.assertTrue(all(15 <= animal["cash"] <= 60 for animal in LEGENDARY_ANIMALS.values()))
        self.assertTrue(
            all(
                animal["xp"] == 350
                and animal["required_level"] == NATURALIST_LEGENDARY_REQUIRED_LEVEL
                for animal in LEGENDARY_ANIMALS.values()
            )
        )

    def test_sold_samples_create_persistent_category_stamps(self):
        data = default_naturalist_data()
        region_key = "forest"
        samples = {animal_key: 1 for animal_key in CATEGORIES[region_key]}
        stamp_naturalist_samples(data, samples)

        self.assertTrue(has_full_naturalist_category(data, region_key))
        self.assertEqual(
            (len(CATEGORIES[region_key]), len(CATEGORIES[region_key])),
            get_naturalist_category_progress(data, region_key),
        )

    def test_reference_page_rewards(self):
        self.assertEqual(
            {
                "forest": 160.0,
                "mountains": 140.0,
                "wetlands": 110.0,
                "desert": 80.0,
            },
            {key: region["payout"] for key, region in NATURALIST_REGIONS.items()},
        )

    def test_shop_prices_and_inventory_are_normalized(self):
        self.assertEqual(20, NATURALIST_TRANQ_PACK_SIZE)
        self.assertEqual(0.56, NATURALIST_TRANQ_PACK_PRICE)
        self.assertEqual(5.0, NATURALIST_REVIVER_PRICE)
        self.assertEqual(20.0, NATURALIST_PHEROMONE_PRICE)
        self.assertEqual(750.0, NATURALIST_CAMP_PRICE)

        data = normalize_naturalist_data(
            {
                "inventory": {
                    "tranquilizers": 999,
                    "pheromones": "2",
                    "clothes": 20,
                },
                "has_wilderness_camp": 1,
            }
        )
        self.assertEqual(
            get_naturalist_tranq_cap(data),
            data["inventory"]["tranquilizers"],
        )
        self.assertEqual(2, data["inventory"]["pheromones"])
        self.assertNotIn("clothes", data["inventory"])
        self.assertTrue(data["has_wilderness_camp"])

    def test_legendary_kill_stores_pelt_and_angers_harriet(self):
        class FixedRng:
            @staticmethod
            def randint(low, high):
                return low

        data = default_naturalist_data()
        materials = add_legendary_pelt(data, "bear_golden_spirit")
        anger = anger_harriet(data, FixedRng())

        self.assertEqual(62.5, materials)
        self.assertEqual(300, anger)
        self.assertIsNotNone(data["harriet_angry_until"])
        key, animal = pop_best_legendary_pelt(data)
        self.assertEqual("bear_golden_spirit", key)
        self.assertEqual(62.5, animal["pelt_materials"])
        self.assertEqual({}, data["legendary_pelts"])
        self.assertEqual(1, get_legendary_pelt_capacity({"naturalist": data}))
        self.assertEqual(
            5,
            get_legendary_pelt_capacity(
                {"naturalist": data, "trader": {"has_hunting_wagon": True}}
            ),
        )

    def test_catalog_uses_the_same_harriet_supply_prices(self):
        source = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "cogs"
            / "catalog.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"name": "Снотворные патроны (Варминт) x20"', source)
        self.assertIn('"base_price": 0.56', source)
        self.assertIn('"base_price": 5', source)


if __name__ == "__main__":
    unittest.main()
