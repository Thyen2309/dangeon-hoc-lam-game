"""
monster.py

This file defines the Monster class and a helper function
to create a random monster for the game.
"""

import random


MONSTER_TEMPLATES = {
    "Skeleton": {"hp": (42, 58), "attack": (9, 15)},
    "Zombie": {"hp": (58, 76), "attack": (10, 16)},
    "Golem": {"hp": (82, 105), "attack": (13, 20)},
    "Goblin": {"hp": (46, 62), "attack": (11, 17)},
    "Slime": {"hp": (30, 50), "attack": (5, 10)},
}


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
    name = random.choice(list(MONSTER_TEMPLATES.keys()))
    return create_monster(name)


def create_monster(name: str, random_position_index: int | None = None) -> Monster:
    """
    Create a monster from a named template.
    """
    template = MONSTER_TEMPLATES.get(name)
    if template is None:
        raise ValueError(f"Unknown monster template: {name}")

    hp = random.randint(*template["hp"])
    attack = random.randint(*template["attack"])
    # This index will be used by GameRoot to choose a random position.
    if random_position_index is None:
        random_position_index = random.randint(0, 5)

    return Monster(
        name=name,
        hp=hp,
        attack=attack,
        random_position_index=random_position_index,
    )

