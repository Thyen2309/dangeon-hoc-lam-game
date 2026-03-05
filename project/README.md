# AR-Style Dungeon Hunt Prototype (Python + Kivy + OpenCV)

This is a simple beginner-friendly prototype of an **AR-style dungeon hunting game**
using **Python**, **Kivy** for the UI, and **OpenCV** for the camera.

The camera feed is shown as the background, a monster image appears on top,
and the player can attack, defend, or run using on-screen buttons.

## Project Structure

- `main.py` – Starts the Kivy app and connects all modules.
- `camera.py` – Handles the OpenCV camera.
- `player.py` – Defines the `Player` class and stats.
- `monster.py` – Defines the `Monster` class and random monster creation.
- `combat.py` – Simple combat functions for player and monster attacks.
- `loot.py` – Generates random loot after defeating a monster.
- `ui.kv` – Kivy UI layout (camera view, monster overlay, HP labels, buttons).
- `requirements.txt` – Python dependencies.

## Setup

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Place a `monster.png` image in the same folder as `main.py`.
   - Any simple PNG works (for example, 200x200 pixels with a transparent background).

4. Run the game:

   ```bash
   python main.py
   ```

## Basic Controls

- **Attack** – Deal damage to the monster. The monster then attacks back.
- **Defend** – Reduce the damage taken from the monster's next attack.
- **Run** – Run away and spawn a new monster.

When a monster is defeated, you automatically receive random loot
(`Sword`, `Armor`, `Potion`, or `Gold`), and a new monster will appear.

