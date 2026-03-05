"""
combat.py

This file contains simple functions for handling combat
between the player and a monster.
"""

import random

from player import Player
from monster import Monster


def player_attack(player: Player, monster: Monster) -> int:
    """
    Handle the player's attack against the monster.

    A very simple damage formula:
    - Base damage is the player's attack
    - We subtract a small random value to add variety

    Returns the damage dealt.
    """
    variation = random.randint(0, 5)
    damage = max(1, player.attack - variation)
    monster.take_damage(damage)
    return damage


def monster_attack(monster: Monster, player: Player, defending: bool = False) -> int:
    """
    Handle the monster's attack against the player.

    - Base damage is the monster's attack
    - If the player is defending, the damage is reduced
    - The player's defense is also subtracted

    Returns the damage dealt.
    """
    base_damage = monster.attack

    # If defending, cut the damage in half (rounded down).
    if defending:
        base_damage = base_damage // 2

    # Subtract the player's defense, but make sure damage is at least 1.
    damage = max(1, base_damage - player.defense)

    player.take_damage(damage)
    return damage

