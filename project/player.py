"""
player.py

This file defines the Player class, which stores
the player's basic stats like HP, attack, and defense.
"""


class Player:
    """
    Represents the player character.
    """

    def __init__(self, name: str, hp: int, attack: int, defense: int):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.attack = attack
        self.defense = defense

    def take_damage(self, amount: int):
        """
        Reduce the player's HP by the given amount.
        HP will not go below 0.
        """
        self.hp = max(0, self.hp - amount)

    def is_alive(self) -> bool:
        """Return True if the player still has HP."""
        return self.hp > 0

