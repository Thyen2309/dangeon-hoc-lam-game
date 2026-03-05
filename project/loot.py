"""
loot.py

This file contains a simple loot system used when
the player defeats a monster.
"""

import random


def generate_loot() -> str:
    """
    Return the name of a random loot item.
    For a simple prototype we just pick a random string.
    """
    loot_options = [
        "Sword",
        "Armor",
        "Potion",
        "Gold",
    ]
    return random.choice(loot_options)

