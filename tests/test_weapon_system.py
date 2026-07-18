import unittest

from src.weapon_system import (
    ammo_capacity,
    ammo_total,
    condition_stat_multiplier,
    equip_weapon,
    has_usable_ammo,
    normalize_weapon_state,
    unequip_weapon,
    use_weapon_shot,
    WEAPON_EMOJI_IDS,
    weapon_emoji,
)


ITEMS = {
    "revolver_one": {"category": "revolvers"},
    "revolver_two": {"category": "revolvers"},
    "pistol_one": {"category": "pistols"},
    "repeater_one": {"category": "carbines"},
    "rifle_one": {"category": "rifles"},
    "shotgun_one": {"category": "shotguns"},
}


class WeaponSystemTests(unittest.TestCase):
    def account(self, *owned):
        account = {"inventory": {key: 1 for key in owned}}
        normalize_weapon_state(account, ITEMS)
        return account

    def test_sidearms_must_share_one_class(self):
        account = self.account("revolver_one", "pistol_one")
        self.assertEqual(account["weapon_loadout"]["sidearms"], ["revolver_one"])
        ok, _ = equip_weapon(account, "pistol_one", ITEMS)
        self.assertFalse(ok)
        self.assertTrue(unequip_weapon(account, "revolver_one"))
        ok, _ = equip_weapon(account, "pistol_one", ITEMS)
        self.assertTrue(ok)

    def test_two_revolvers_double_capacity_but_longarms_do_not(self):
        account = self.account("revolver_one", "revolver_two", "repeater_one", "rifle_one")
        self.assertEqual(ammo_capacity(account, "revolver", ITEMS), 400)
        self.assertEqual(ammo_capacity(account, "repeater", ITEMS), 200)
        self.assertEqual(ammo_capacity(account, "rifle", ITEMS), 100)

    def test_only_two_longarms_can_be_equipped(self):
        account = self.account("repeater_one", "rifle_one", "shotgun_one")
        self.assertEqual(len(account["weapon_loadout"]["longarms"]), 2)
        ok, _ = equip_weapon(account, "shotgun_one", ITEMS)
        self.assertFalse(ok)

    def test_menu_can_replace_weapon_when_slots_are_full(self):
        account = self.account("repeater_one", "rifle_one", "shotgun_one")
        ok, message = equip_weapon(account, "shotgun_one", ITEMS, replace=True)
        self.assertTrue(ok)
        self.assertIn("shotgun_one", account["weapon_loadout"]["longarms"])
        self.assertIn("заменён", message)

    def test_owned_unequipped_weapon_still_provides_ammo_capacity(self):
        account = self.account("rifle_one")
        account["weapon_loadout"]["longarms"] = []
        self.assertEqual(ammo_capacity(account, "rifle", ITEMS), 100)

    def test_unrelated_ammo_cannot_start_combat(self):
        account = self.account("rifle_one", "revolver_one")
        account["weapon_loadout"]["sidearms"] = []
        account["weapon_loadout"]["longarms"] = ["rifle_one"]
        account["ammo"]["revolver"]["normal"] = 20
        self.assertFalse(has_usable_ammo(account, ITEMS))
        account["ammo"]["rifle"]["normal"] = 1
        self.assertTrue(has_usable_ammo(account, ITEMS))

    def test_shot_consumes_best_ammo_and_wears_weapon(self):
        account = self.account("rifle_one")
        account["ammo"]["rifle"]["normal"] = 10
        account["ammo"]["rifle"]["express"] = 2
        account["selected_ammo"]["rifle"] = "express"
        shot = use_weapon_shot(account, ITEMS)
        self.assertEqual(shot["ammo_type"], "express")
        self.assertEqual(account["ammo"]["rifle"]["express"], 1)
        self.assertEqual(account["weapon_condition"]["rifle_one"], 98.5)
        self.assertEqual(ammo_total(account, "rifle"), 11)

    def test_selected_ammo_is_used_before_other_types(self):
        account = self.account("rifle_one")
        account["ammo"]["rifle"]["normal"] = 2
        account["ammo"]["rifle"]["explosive"] = 2
        account["selected_ammo"]["rifle"] = "normal"
        shot = use_weapon_shot(account, ITEMS)
        self.assertEqual(shot["ammo_type"], "normal")
        self.assertEqual(account["ammo"]["rifle"]["explosive"], 2)

    def test_condition_reduces_stats(self):
        self.assertEqual(condition_stat_multiplier(100), 1.0)
        self.assertEqual(condition_stat_multiplier(0), 0.6)

    def test_every_catalog_weapon_has_a_discord_emoji(self):
        self.assertEqual(len(WEAPON_EMOJI_IDS), 23)
        self.assertEqual(
            weapon_emoji("pistol_mauser"),
            "<:gun:1527598229410287648>",
        )


if __name__ == "__main__":
    unittest.main()
