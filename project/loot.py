"""
loot.py

This file contains a simple loot system used when
the player defeats a monster.
"""

import random


def generate_loot() -> tuple[str, int]:
    """
    Return a random loot item and quantity.

    Items have different drop weights:
    - Gold is common and drops in stacks
    - Equipment is rarer and drops as a single item
    """
    items = ["Gold", "Potion", "Armor", "Sword"]
    weights = [50, 25, 15, 10]
    item = random.choices(items, weights=weights, k=1)[0]

    if item == "Gold":
        return ("Gold", random.randint(5, 25))
    return (item, 1)

