"""
monster.py

This file defines the Monster class and a helper function
to create a random monster for the game.
"""

import random


class Monster:
    """
    Represents a monster with HP and attack power.
    """

    def __init__(self, name: str, hp: int, attack: int, random_position_index: int):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.attack = attack
        # Index used by the UI to choose a random on-screen position.
        self.random_position_index = random_position_index

    def take_damage(self, amount: int):
        """
        Reduce the monster's HP by the given amount.
        HP will not go below 0.
        """
        self.hp = max(0, self.hp - amount)

    def is_alive(self) -> bool:
        """Return True if the monster still has HP."""
        return self.hp > 0


def create_random_monster() -> Monster:
    """
    Create a monster with random stats.
    For a simple prototype, we just pick from a small list.
    """
    monster_templates = [
        {"name": "Slime", "hp": (30, 50), "attack": (5, 10)},
        {"name": "Goblin", "hp": (40, 60), "attack": (8, 15)},
        {"name": "Skeleton", "hp": (35, 55), "attack": (10, 18)},
    ]

    template = random.choice(monster_templates)
    hp = random.randint(*template["hp"])
    attack = random.randint(*template["attack"])
    # This index will be used by GameRoot to choose a random position.
    random_position_index = random.randint(0, 5)

    return Monster(
        name=template["name"],
        hp=hp,
        attack=attack,
        random_position_index=random_position_index,
    )

