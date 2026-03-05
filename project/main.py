import cv2

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout

from camera import Camera
from player import Player
from monster import create_random_monster
from combat import player_attack, monster_attack
from loot import generate_loot


class GameRoot(BoxLayout):
    """
    Main game widget.

    This class connects:
    - The camera feed (from camera.py)
    - The player and monster data
    - The combat and loot systems
    - The Kivy UI defined in ui.kv
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Create a player with some default stats.
        self.player = Player(name="Hero", hp=100, attack=15, defense=5)

        # No monster at the start; we will spawn one.
        self.monster = None

        # Track whether the player chose to defend this turn.
        self.is_defending = False

        # Create the camera controller.
        self.camera = Camera()

        # Start updating the camera about 30 times per second.
        Clock.schedule_interval(self.update_camera, 1.0 / 30.0)

        # Spawn the first monster shortly after the UI is ready.
        Clock.schedule_once(lambda dt: self.spawn_monster(), 1.0)

        # Update the player HP label at the start.
        Clock.schedule_once(lambda dt: self.update_player_ui(), 0.1)

    # ---------------- CAMERA HANDLING ----------------
    def update_camera(self, dt):
        """
        Grab a frame from the camera and show it in the Image widget.
        """
        frame = self.camera.get_frame()
        if frame is None:
            return

        # Convert from BGR (OpenCV) to RGB (Kivy).
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        h, w, _ = frame.shape
        texture = Texture.create(size=(w, h), colorfmt="rgb")
        texture.blit_buffer(frame.tobytes(), colorfmt="rgb", bufferfmt="ubyte")
        texture.flip_vertical()

        # "camera_view" is the id of the Image widget in ui.kv.
        self.ids.camera_view.texture = texture

    def on_parent(self, widget, parent):
        """
        Called when the widget is added to the UI tree.
        Here we make sure the camera is released when the widget is removed.
        """
        if parent is None:
            self.camera.release()

    # ---------------- UI HELPERS ----------------
    def update_player_ui(self):
        """Update the label that shows the player's HP."""
        self.ids.player_hp_label.text = f"Player HP: {self.player.hp}"

    def update_monster_ui(self):
        """Update the label and image for the current monster."""
        if self.monster is None:
            self.ids.monster_hp_label.text = "Monster HP: -"
            self.ids.monster_image.opacity = 0.0
        else:
            self.ids.monster_hp_label.text = f"Monster HP: {self.monster.hp}"
            self.ids.monster_image.opacity = 1.0

    def show_message(self, text):
        """Show a message in the status / log area."""
        self.ids.status_label.text = text

    # ---------------- MONSTER / LOOT ----------------
    def spawn_monster(self):
        """
        Create a new random monster and place its image
        at a random position on the camera view.
        """
        self.monster = create_random_monster()
        self.update_monster_ui()

        # Choose a random position for the monster image.
        positions = [
            {"x": 0.1, "y": 0.1},
            {"x": 0.6, "y": 0.1},
            {"x": 0.3, "y": 0.3},
            {"x": 0.1, "y": 0.5},
            {"x": 0.5, "y": 0.5},
            {"x": 0.3, "y": 0.7},
        ]
        self.ids.monster_image.pos_hint = positions[self.monster.random_position_index]

        self.show_message(f"A wild {self.monster.name} appears!")

    def clear_monster(self):
        """Remove the current monster (used when running away or after defeat)."""
        self.monster = None
        self.update_monster_ui()

    # ---------------- COMBAT ACTIONS ----------------
    def monster_turn(self):
        """
        Let the monster attack the player after the player's action.
        """
        if self.monster is None:
            return

        damage = monster_attack(self.monster, self.player, defending=self.is_defending)
        self.update_player_ui()

        if self.player.hp <= 0:
            self.show_message("You were defeated! Game over.")
        else:
            if self.is_defending:
                self.show_message(
                    f"You defend! The monster hits you for {damage} damage."
                )
            else:
                self.show_message(f"The monster hits you for {damage} damage.")

        # Reset defending flag after monster turn.
        self.is_defending = False

    def on_attack(self):
        """
        Called when the Attack button is pressed.
        Player attacks first, then the monster responds.
        """
        if self.monster is None:
            self.show_message("No monster. Press Run to find a new one.")
            return

        self.is_defending = False
        damage = player_attack(self.player, self.monster)
        self.update_monster_ui()

        if self.monster.hp <= 0:
            # Monster defeated: generate loot and spawn a new monster later.
            loot = generate_loot()
            self.show_message(f"You defeated the monster! You found: {loot}.")
            self.clear_monster()
            # Spawn a new monster after a short delay.
            Clock.schedule_once(lambda dt: self.spawn_monster(), 1.0)
        else:
            self.show_message(f"You hit the monster for {damage} damage.")
            self.monster_turn()

    def on_defend(self):
        """
        Called when the Defend button is pressed.
        Player takes reduced damage on the next monster attack.
        """
        if self.monster is None:
            self.show_message("No monster to defend against.")
            return

        self.is_defending = True
        self.show_message("You raise your shield and defend!")
        self.monster_turn()

    def on_run(self):
        """
        Called when the Run button is pressed.
        The monster disappears and a new one appears shortly.
        """
        if self.monster is None:
            self.show_message("You look around... no monster here.")
        else:
            self.show_message("You ran away from the monster!")
            self.clear_monster()

        # Spawn a new monster after a short delay.
        Clock.schedule_once(lambda dt: self.spawn_monster(), 1.0)


class DungeonARApp(App):
    """
    The main Kivy application.
    """

    def build(self):
        # Load the UI layout from the .kv file.
        Builder.load_file("ui.kv")
        return GameRoot()

    def on_stop(self):
        """
        When the app closes, release the camera.
        """
        root = self.root
        if root is not None and hasattr(root, "camera"):
            root.camera.release()


if __name__ == "__main__":
    DungeonARApp().run()

