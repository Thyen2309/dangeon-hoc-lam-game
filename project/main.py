import os
from pathlib import Path

os.environ.setdefault("KIVY_NO_FILELOG", "1")

try:
    import cv2
except ModuleNotFoundError:
    cv2 = None

from dataclasses import dataclass
import random

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.image import Image as CoreImage
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.animation import Animation
from kivy.properties import NumericProperty

from camera import Camera
from player import Player
from monster import create_monster
from combat import player_attack, monster_attack
from loot import generate_loot

BASE_DIR = Path(__file__).resolve().parent
MONSTER_ART_DIR = BASE_DIR / "assets" / "monsters"
MONSTER_FRAME_DIR = BASE_DIR / "assets" / "monster_frames"
LOOT_ICON_DIR = BASE_DIR / "assets" / "loot_icons"
RESOURCE_DIR = BASE_DIR.parent / "tainguyen"
STAGES = [
    {"name": "Skeleton", "goal": 2},
    {"name": "Zombie", "goal": 3},
    {"name": "Golem", "goal": 2},
    {"name": "Goblin", "goal": 4},
]

MONSTER_SPRITE_SHEETS = {
    "Skeleton": {
        "path": RESOURCE_DIR / "skeleton.png",
        "frame_size": (32, 32),
        "idle_frames": [0, 1],
        "attack_frames": [2, 3, 4, 5],
    },
    "Zombie": {
        "path": RESOURCE_DIR / "zombie.png",
        "frame_size": (32, 32),
        "idle_frames": [0, 1],
        "attack_frames": [0, 1, 2],
    },
    "Golem": {
        "path": RESOURCE_DIR / "golem.png",
        "frame_size": (64, 64),
        "idle_frames": [0, 1],
        "attack_frames": [0, 1, 2, 3],
    },
}


@dataclass(frozen=True)
class DepthStyle:
    size_px: int
    monster_opacity: float
    shadow_opacity: float
    shadow_offset_px: tuple[int, int]


@dataclass(frozen=True)
class MonsterFrame:
    key: str
    texture: Texture | None = None
    source: str | None = None


class GameRoot(BoxLayout):
    """
    Main game widget.

    This class connects:
    - The camera feed (from camera.py)
    - The player and monster data
    - The combat and loot systems
    - The Kivy UI defined in ui.kv
    """

    # Alpha của lớp flash đỏ khi quái tấn công (0..1).
    attack_flash_alpha = NumericProperty(0.0)
    scanline_alpha = NumericProperty(0.0)
    scanline_y = NumericProperty(0.22)
    aura_alpha = NumericProperty(0.0)
    aura_scale = NumericProperty(0.92)
    ground_glow_alpha = NumericProperty(0.0)
    ground_glow_scale = NumericProperty(0.9)
    atmosphere_alpha = NumericProperty(0.18)
    loot_pulse_scale = NumericProperty(1.0)

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

        self._monster_depth_style: DepthStyle | None = None

        # Inventory / loot drop state
        self.inventory: dict[str, int] = {}
        self._drop_item: tuple[str, int] | None = None
        self._loot_anim = None
        self._monster_idle_anim = None
        self._monster_attack_event = None
        self._monster_sprite_event = None
        self._monster_frames: list[MonsterFrame] = []
        self._monster_frame_index = 0
        self._sprite_sheet_cache: dict[str, list[MonsterFrame]] = {}
        self._scan_anim = None
        self._inventory_popup: Popup | None = None
        self._inventory_slot_buttons: list[Button] = []
        self._inventory_info_label: Label | None = None
        self._inventory_selected_name: str | None = None
        self._inventory_use_button: Button | None = None
        self._inventory_drop_button: Button | None = None
        self._result_popup: Popup | None = None
        self._camera_unavailable_notified = False
        self._bound_input_window = None
        self.stage_index = 0
        self.stage_kills = 0
        self.game_over = False

        # Start updating the camera about 30 times per second.
        Clock.schedule_interval(self.update_camera, 1.0 / 30.0)

        # Spawn the first monster after a short, random scan delay.
        self._pending_spawn_event = None
        Clock.schedule_once(lambda dt: self.schedule_spawn_monster(), 0.5)

        # Update the player HP label at the start.
        Clock.schedule_once(lambda dt: self.update_player_ui(), 0.1)
        Clock.schedule_once(lambda dt: self.update_stage_ui(), 0.1)

        # Bind shadow position after kv ids are ready.
        Clock.schedule_once(lambda dt: self._setup_monster_shadow_binding(), 0)
        Clock.schedule_once(lambda dt: self._setup_input_bindings(), 0)
        Clock.schedule_once(lambda dt: self.update_inventory_ui(), 0)
        Clock.schedule_once(lambda dt: self._start_scan_effect(), 0.1)

    def _setup_input_bindings(self):
        if self._bound_input_window is Window:
            return
        Window.bind(on_key_down=self._on_key_down)
        Window.bind(on_joy_button_down=self._on_joy_button_down)
        self._bound_input_window = Window

    def _handle_quick_pickup(self) -> bool:
        if self._drop_item is None:
            return False
        self.on_pickup_loot()
        return True

    def _on_key_down(self, _window, key, _scancode, _codepoint, _modifiers):
        if key in (13, 32, 101):
            return self._handle_quick_pickup()
        return False

    def _on_joy_button_down(self, _window, _stickid, buttonid):
        # Common Xbox mapping on Windows: A=0, B=1, X=2, Y=3.
        if buttonid in (0, 2):
            return self._handle_quick_pickup()
        return False

    def _setup_monster_shadow_binding(self):
        monster_image = self.ids.get("monster_image")
        monster_shadow = self.ids.get("monster_shadow")
        if monster_image is None or monster_shadow is None:
            return

        def sync_shadow(*_args):
            style = self._monster_depth_style
            if style is None:
                return
            monster_shadow.pos = (
                monster_image.x + style.shadow_offset_px[0],
                monster_image.y + style.shadow_offset_px[1],
            )

        monster_image.bind(pos=lambda *_: sync_shadow(), size=lambda *_: sync_shadow())

    def _start_scan_effect(self):
        Animation.cancel_all(self, "scanline_alpha", "scanline_y")
        self.scanline_alpha = 0.0
        self.scanline_y = 0.18
        anim = (
            Animation(scanline_alpha=0.65, scanline_y=0.78, duration=1.1, t="out_cubic")
            + Animation(scanline_alpha=0.0, duration=0.45, t="in_quad")
            + Animation(scanline_y=0.18, duration=0.25)
        )
        anim.repeat = True
        anim.start(self)
        self._scan_anim = anim

    # ---------------- CAMERA HANDLING ----------------
    def update_camera(self, dt):
        """
        Grab a frame from the camera and show it in the Image widget.
        """
        if cv2 is None:
            if not self._camera_unavailable_notified:
                self._camera_unavailable_notified = True
                self.show_message("Khong tim thay OpenCV (cv2). Game van chay, camera bi tat.")
                self.ids.camera_view.opacity = 0.25
            return

        frame = self.camera.get_frame()
        if frame is None:
            self.ids.camera_view.opacity = 0.25
            return

        self.ids.camera_view.opacity = 1.0

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

    def get_stage_data(self) -> dict:
        return STAGES[min(self.stage_index, len(STAGES) - 1)]

    def update_stage_ui(self):
        stage_data = self.get_stage_data()
        stage_number = self.stage_index + 1
        goal = stage_data["goal"]
        remaining = max(0, goal - self.stage_kills)
        self.ids.stage_label.text = f"Stage {stage_number}: {stage_data['name']}"
        self.ids.objective_label.text = (
            f"Objective: defeat {remaining}/{goal} {stage_data['name']}"
        )

    def get_monster_art_path(self, monster_name: str) -> str:
        image_path = MONSTER_ART_DIR / f"{monster_name.lower()}.png"
        if image_path.exists():
            return str(image_path)
        return str(BASE_DIR / "monster.png")

    def get_monster_frame_paths(self, monster_name: str) -> list[str]:
        frame_dir = MONSTER_FRAME_DIR / monster_name.lower()
        if not frame_dir.exists():
            return []
        return [str(path) for path in sorted(frame_dir.glob("*.png"))]

    def get_sheet_frames(self, monster_name: str) -> list[MonsterFrame]:
        if monster_name in self._sprite_sheet_cache:
            return self._sprite_sheet_cache[monster_name]

        config = MONSTER_SPRITE_SHEETS.get(monster_name)
        if config is None:
            return []

        sprite_path = config["path"]
        if not sprite_path.exists():
            return []

        try:
            texture = CoreImage(str(sprite_path)).texture
        except Exception:
            return []

        frame_width, frame_height = config["frame_size"]
        if frame_width <= 0 or frame_height <= 0:
            return []

        columns = int(texture.width // frame_width)
        rows = int(texture.height // frame_height)
        if columns <= 0 or rows <= 0:
            return []

        frames: list[MonsterFrame] = []
        frame_index = 0
        for row in range(rows):
            top_y = row * frame_height
            texture_y = int(texture.height - top_y - frame_height)
            for col in range(columns):
                texture_x = col * frame_width
                frame_texture = texture.get_region(
                    texture_x,
                    texture_y,
                    frame_width,
                    frame_height,
                )
                frames.append(
                    MonsterFrame(
                        key=f"{sprite_path.as_posix()}#{frame_index}",
                        texture=frame_texture,
                    )
                )
                frame_index += 1

        self._sprite_sheet_cache[monster_name] = frames
        return frames

    def get_monster_frames(self, monster_name: str, mode: str = "idle") -> list[MonsterFrame]:
        sheet_frames = self.get_sheet_frames(monster_name)
        if sheet_frames:
            config = MONSTER_SPRITE_SHEETS.get(monster_name, {})
            configured_indices = config.get("attack_frames" if mode == "attack" else "idle_frames", [])
            selected = [
                sheet_frames[index]
                for index in configured_indices
                if 0 <= index < len(sheet_frames)
            ]
            if selected:
                return selected
            return sheet_frames

        return [
            MonsterFrame(key=path, source=path)
            for path in self.get_monster_frame_paths(monster_name)
        ]

    def get_loot_icon_path(self, item_name: str) -> str:
        lookup = {
            "Gold": "gold.png",
            "Potion": "potion.png",
            "Sword": "sword.png",
            "Armor": "armor.png",
        }
        filename = lookup.get(item_name)
        if filename is None:
            return ""
        path = LOOT_ICON_DIR / filename
        if path.exists():
            return str(path)
        return ""

    def _set_monster_frame(self, frame: MonsterFrame | str):
        image = self.ids.get("monster_image")
        if image is None:
            return
        if isinstance(frame, str):
            frame = MonsterFrame(key=frame, source=frame)

        if frame.texture is not None:
            image.source = ""
            image.texture = frame.texture
            image.canvas.ask_update()
            return

        if frame.source and image.source != frame.source:
            image.source = frame.source
            image.reload()

    def _stop_monster_sprite_animation(self):
        if self._monster_sprite_event is not None:
            try:
                self._monster_sprite_event.cancel()
            except Exception:
                pass
            self._monster_sprite_event = None

    def _advance_monster_frame(self, *_args):
        if not self._monster_frames:
            return False
        self._monster_frame_index = (self._monster_frame_index + 1) % len(self._monster_frames)
        self._set_monster_frame(self._monster_frames[self._monster_frame_index])
        return True

    def _start_monster_sprite_animation(self, mode: str = "idle"):
        if self.monster is None:
            return

        frames = self.get_monster_frames(self.monster.name, mode)
        if not frames:
            self._monster_frames = []
            self._stop_monster_sprite_animation()
            self._set_monster_frame(self.get_monster_art_path(self.monster.name))
            return

        self._stop_monster_sprite_animation()
        self._monster_frames = frames
        self._monster_frame_index = 0
        self._set_monster_frame(frames[0])
        interval = 0.09 if mode == "attack" and len(frames) > 1 else 0.18
        if len(frames) > 1:
            self._monster_sprite_event = Clock.schedule_interval(
                self._advance_monster_frame, interval
            )

    def update_monster_ui(self):
        """Update the label and image for the current monster."""
        if self.monster is None:
            self.ids.monster_hp_label.text = "Monster HP: -"
            self.ids.monster_image.opacity = 0.0
            self.aura_alpha = 0.0
            self.ground_glow_alpha = 0.0
            self._stop_monster_sprite_animation()
            if "monster_shadow" in self.ids:
                self.ids.monster_shadow.opacity = 0.0
        else:
            self.ids.monster_hp_label.text = f"Monster HP: {self.monster.hp}"
            self._start_monster_sprite_animation("idle")
            self.ids.monster_image.opacity = 1.0
            if "monster_shadow" in self.ids:
                self.ids.monster_shadow.opacity = 1.0

    def show_message(self, text):
        """Show a message in the status / log area."""
        self.ids.status_label.text = text

    def update_inventory_ui(self):
        label = self.ids.get("inventory_label")
        if label is None:
            return

        if not self.inventory:
            label.text = "Rương: (trống)"
            return

        parts = []
        for name in sorted(self.inventory.keys()):
            qty = self.inventory[name]
            parts.append(f"{name} x{qty}")
        # Keep it short so it fits.
        text = "Rương: " + ", ".join(parts)
        if len(text) > 60:
            text = text[:57] + "..."
        label.text = text

        # Nếu popup đang mở thì cập nhật luôn.
        if self._inventory_popup is not None:
            self.refresh_inventory_popup()

    # ---------------- INVENTORY POPUP ----------------
    def open_inventory(self):
        if self._inventory_popup is None:
            self._create_inventory_popup()
        self.refresh_inventory_popup()
        self._inventory_popup.open()

    def _create_inventory_popup(self):
        popup = Popup(
            title="Rương đồ",
            size_hint=(0.9, 0.7),
            auto_dismiss=False,
        )

        root = BoxLayout(orientation="horizontal", spacing=8, padding=8)

        grid = GridLayout(cols=4, rows=3, spacing=4, size_hint=(0.6, 1))
        self._inventory_slot_buttons = []
        for _ in range(12):
            btn = Button(
                text="(trống)",
                font_size=14,
                halign="center",
                valign="middle",
            )
            btn.bind(on_press=self._on_inventory_slot_press)
            self._inventory_slot_buttons.append(btn)
            grid.add_widget(btn)

        right = BoxLayout(orientation="vertical", size_hint=(0.4, 1), spacing=6)
        info = Label(
            text="Chọn một ô vật phẩm.",
            halign="left",
            valign="top",
            size_hint=(1, 0.55),
            text_size=(0, 0),
        )
        # text_size được set trong on_size để wrap
        info.bind(
            size=lambda inst, *_: setattr(inst, "text_size", inst.size),
        )
        self._inventory_info_label = info

        use_btn = Button(
            text="Sử dụng",
            size_hint=(1, None),
            height=40,
        )
        use_btn.bind(on_press=lambda *_: self.on_inventory_use())
        self._inventory_use_button = use_btn

        drop_btn = Button(
            text="Vứt",
            size_hint=(1, None),
            height=40,
        )
        drop_btn.bind(on_press=lambda *_: self.on_inventory_drop())
        self._inventory_drop_button = drop_btn

        close_btn = Button(
            text="Đóng",
            size_hint=(1, None),
            height=40,
        )
        close_btn.bind(on_press=lambda *_: popup.dismiss())

        right.add_widget(info)
        right.add_widget(use_btn)
        right.add_widget(drop_btn)
        right.add_widget(close_btn)

        root.add_widget(grid)
        root.add_widget(right)

        popup.content = root
        self._inventory_popup = popup

    def refresh_inventory_popup(self):
        if not self._inventory_slot_buttons:
            return

        items = sorted(self.inventory.items())
        # Gán từng item vào 12 ô; dư thì để trống.
        for idx, btn in enumerate(self._inventory_slot_buttons):
            if idx < len(items):
                name, qty = items[idx]
                btn.text = f"{name}\\nx{qty}"
                btn.item_name = name  # thuộc tính động
                btn.disabled = False
            else:
                btn.text = "(trống)"
                btn.item_name = None
                btn.disabled = True

        # Reset selection info
        self._inventory_selected_name = None
        if self._inventory_info_label is not None:
            self._inventory_info_label.text = "Chọn một ô vật phẩm."
        if self._inventory_use_button is not None:
            self._inventory_use_button.disabled = True
        if self._inventory_drop_button is not None:
            self._inventory_drop_button.disabled = True

    def _on_inventory_slot_press(self, button: Button):
        name = getattr(button, "item_name", None)
        if not name:
            return

        qty = self.inventory.get(name, 0)
        self._inventory_selected_name = name

        # Thông tin item cơ bản
        description = ""
        if name == "Gold":
            description = "Tiền vàng dùng để mua đồ trong tương lai."
        elif name == "Potion":
            description = "Thuốc hồi máu. Mỗi lần sử dụng hồi 20 HP."
        elif name == "Sword":
            description = "Vũ khí cận chiến. Tăng sức tấn công."
        elif name == "Armor":
            description = "Giáp bảo vệ. Tăng chỉ số phòng thủ."
        else:
            description = "Vật phẩm bí ẩn."

        if self._inventory_info_label is not None:
            self._inventory_info_label.text = (
                f"{name} x{qty}\\n\\n{description}"
            )

        # Chỉ cho phép 'Sử dụng' với Potion, còn lại chỉ 'Vứt'.
        if self._inventory_use_button is not None:
            self._inventory_use_button.disabled = name != "Potion"
        if self._inventory_drop_button is not None:
            self._inventory_drop_button.disabled = False

    def on_inventory_use(self):
        name = self._inventory_selected_name
        if not name:
            return
        if name != "Potion":
            self.show_message("Hiện tại chỉ có thể sử dụng Potion.")
            return

        current_qty = self.inventory.get(name, 0)
        if current_qty <= 0:
            self.show_message("Không còn Potion trong rương.")
            return

        # Tiêu thụ 1 Potion và hồi 20 HP.
        self.inventory[name] = current_qty - 1
        if self.inventory[name] <= 0:
            del self.inventory[name]

        # Hồi máu cố định 20 thay vì theo apply_loot_effect.
        before = self.player.hp
        self.player.hp = min(self.player.max_hp, self.player.hp + 20)
        healed = self.player.hp - before
        self.update_player_ui()

        if healed > 0:
            self.show_message(f"Bạn dùng 1 Potion, hồi {healed} HP.")
        else:
            self.show_message("HP đã đầy, Potion không có tác dụng.")

        self.update_inventory_ui()

    def on_inventory_drop(self):
        name = self._inventory_selected_name
        if not name:
            return

        current_qty = self.inventory.get(name, 0)
        if current_qty <= 0:
            return

        # Vứt hết stack cho đơn giản.
        del self.inventory[name]
        self.show_message(f"Bạn đã vứt bỏ toàn bộ {name}.")
        self.update_inventory_ui()

    # ---------------- MONSTER / LOOT ----------------
    def schedule_spawn_monster(self):
        if self.game_over:
            return

        """
        Simulate \"quét camera tìm quái\": sau một khoảng thời gian ngẫu nhiên,
        quái mới xuất hiện tại vị trí sát \"mặt đất\" trong khung camera.
        """
        if self._pending_spawn_event is not None:
            try:
                self._pending_spawn_event.cancel()
            except Exception:
                pass

        delay = random.uniform(1.0, 4.0)
        self.update_stage_ui()
        self.show_message("Đang quét xung quanh tìm quái...")
        self._pending_spawn_event = Clock.schedule_once(lambda dt: self.spawn_monster(), delay)

    def spawn_monster(self):
        if self.game_over:
            return

        """
        Create a new random monster and place its image
        at a random position on the camera view.
        """
        self._pending_spawn_event = None
        self.stop_monster_attack_loop()

        stage_data = self.get_stage_data()
        self.monster = create_monster(stage_data["name"])
        self.update_monster_ui()
        self.update_stage_ui()

        # Choose a random position for the monster image.
        # Chỉ cho quái xuất hiện ở dải thấp (gần \"mặt đất\" của khung camera).
        positions = [
            {"x": 0.08, "y": 0.10},
            {"x": 0.28, "y": 0.12},
            {"x": 0.56, "y": 0.11},
            {"x": 0.14, "y": 0.21},
            {"x": 0.40, "y": 0.24},
            {"x": 0.68, "y": 0.20},
        ]
        self.ids.monster_image.pos_hint = positions[self.monster.random_position_index]
        if "monster_shadow" in self.ids:
            self.ids.monster_shadow.pos_hint = positions[self.monster.random_position_index]

        # Apply a simple "AR depth" style based on where the monster is placed
        # in the camera view (higher = farther, lower = closer).
        self.apply_monster_depth(positions[self.monster.random_position_index])

        self.show_message(f"A wild {self.monster.name} appears!")
        self._play_spawn_effect()
        self.start_monster_idle_animation()
        self.start_monster_attack_loop()

    def show_loot_drop(self, item: tuple[str, int], near_pos_hint: dict):
        name, qty = item
        loot_button = self.ids.get("loot_button")
        loot_icon = self.ids.get("loot_icon")
        if loot_button is None:
            return

        # Nếu đang có đồ trên đất chưa nhặt → cộng đồ mới thẳng vào rương, không ghi đè.
        if self._drop_item is not None:
            self.inventory[name] = self.inventory.get(name, 0) + qty
            self.update_inventory_ui()
            self.show_message(f"Nhặt thêm: {name} x{qty} (tự động vào rương).")
            return

        self._drop_item = item
        loot_button.disabled = False
        loot_button.opacity = 1.0
        self.loot_pulse_scale = 1.0

        # Keep the prompt in a consistent center-bottom area so touch/gamepad pickup
        # is easier than tapping a small moving target near the monster.
        x = float(near_pos_hint.get("x", 0.3))
        y = float(near_pos_hint.get("y", 0.3))
        center_x = max(0.28, min(0.72, x + 0.16))
        base_y = 0.05 if y < 0.2 else 0.09
        if loot_icon is not None:
            loot_icon.source = self.get_loot_icon_path(name)
            loot_icon.pos_hint = {"center_x": center_x, "y": base_y}
            loot_icon.opacity = 1.0
        loot_button.pos_hint = {"center_x": center_x, "y": base_y}
        loot_button.text = ""
        self._cancel_loot_animation()
        self.start_loot_bounce_animation()

    def _cancel_loot_animation(self):
        if self._loot_anim is not None:
            try:
                self._loot_anim.cancel(self.ids.get("loot_button"))
            except Exception:
                pass
            self._loot_anim = None

    def hide_loot_drop(self):
        self._cancel_loot_animation()
        loot_button = self.ids.get("loot_button")
        loot_icon = self.ids.get("loot_icon")
        if loot_button is not None:
            loot_button.opacity = 0.0
            loot_button.disabled = True
        if loot_icon is not None:
            loot_icon.opacity = 0.0
            loot_icon.source = ""
        self.loot_pulse_scale = 1.0
        self._drop_item = None

    def on_pickup_loot(self):
        if self._drop_item is None:
            return

        name, qty = self._drop_item
        self.inventory[name] = self.inventory.get(name, 0) + qty
        self.apply_loot_effect(name, qty)
        self.update_inventory_ui()
        self.hide_loot_drop()

    def apply_loot_effect(self, name: str, qty: int):
        """
        Khi nhặt vật phẩm, áp dụng luôn hiệu ứng:
        - Gold: chỉ lưu trong rương.
        - Potion: hồi máu.
        - Sword: tăng attack.
        - Armor: tăng defense.
        """
        if name == "Gold":
            self.show_message(f"Bạn nhặt được {qty} Gold.")
            return

        if name == "Potion":
            heal_each = 18
            total_heal = heal_each * qty
            before = self.player.hp
            self.player.hp = min(self.player.max_hp, self.player.hp + total_heal)
            healed = self.player.hp - before
            self.update_player_ui()
            if healed > 0:
                self.show_message(f"Bạn dùng Potion x{qty}, hồi {healed} HP.")
            else:
                self.show_message("HP đã đầy, Potion được cất vào rương.")
            return

        if name == "Sword":
            self.player.attack += 2 * qty
            self.show_message(
                f"Bạn nhặt Sword x{qty}! Sức tấn công tăng lên {self.player.attack}."
            )
            return

        if name == "Armor":
            self.player.defense += 1 * qty
            self.show_message(
                f"Bạn nhặt Armor x{qty}! Phòng thủ tăng lên {self.player.defense}."
            )
            return

        # Fallback cho item lạ
        self.show_message(f"Bạn nhặt được: {name} x{qty}.")

    def apply_monster_depth(self, pos_hint: dict):
        """
        Fake depth / perspective:
        - higher on screen -> smaller, more transparent
        - lower on screen  -> larger, more opaque
        """
        y = float(pos_hint.get("y", 0.5))
        # Normalize y into a "closeness" value in [0..1]
        # (y small is closer in our placement list, but we map using y itself
        # so it works even if you change the positions later).
        closeness = max(0.0, min(1.0, (y - 0.05) / 0.75))

        size_far = 120
        size_near = 300
        size_px = int(size_far + (size_near - size_far) * closeness)

        monster_opacity = 0.50 + 0.50 * closeness
        shadow_opacity = 0.12 + 0.42 * closeness
        shadow_offset = (int(12 + 14 * closeness), int(-18 - 10 * closeness))

        style = DepthStyle(
            size_px=size_px,
            monster_opacity=monster_opacity,
            shadow_opacity=shadow_opacity,
            shadow_offset_px=shadow_offset,
        )
        self._monster_depth_style = style

        self.ids.monster_image.size = (style.size_px, style.size_px)
        self.ids.monster_image.opacity = style.monster_opacity if self.monster else 0.0
        self.aura_alpha = 0.18 + 0.25 * closeness if self.monster else 0.0
        self.aura_scale = 0.84 + 0.30 * closeness
        self.ground_glow_alpha = 0.22 + 0.38 * closeness if self.monster else 0.0
        self.ground_glow_scale = 0.90 + 0.22 * closeness

        shadow = self.ids.get("monster_shadow")
        if shadow is not None:
            shadow.size = (int(style.size_px * 1.08), int(style.size_px * 0.46))
            shadow.opacity = style.shadow_opacity if self.monster else 0.0
            # position is synced via binding; force one sync now
            shadow.pos = (
                self.ids.monster_image.x + style.shadow_offset_px[0],
                self.ids.monster_image.y + style.shadow_offset_px[1],
            )

    def _play_spawn_effect(self):
        Animation.cancel_all(self, "aura_alpha", "aura_scale", "ground_glow_alpha", "ground_glow_scale")
        base_aura_alpha = self.aura_alpha
        base_aura_scale = self.aura_scale
        base_glow_alpha = self.ground_glow_alpha
        base_glow_scale = self.ground_glow_scale

        spawn_fx = (
            Animation(
                aura_alpha=min(0.75, base_aura_alpha + 0.25),
                aura_scale=base_aura_scale + 0.16,
                ground_glow_alpha=min(0.9, base_glow_alpha + 0.28),
                ground_glow_scale=base_glow_scale + 0.14,
                duration=0.18,
                t="out_quad",
            )
            + Animation(
                aura_alpha=base_aura_alpha,
                aura_scale=base_aura_scale,
                ground_glow_alpha=base_glow_alpha,
                ground_glow_scale=base_glow_scale,
                duration=0.45,
                t="out_cubic",
            )
        )
        spawn_fx.start(self)

    def stop_monster_idle_animation(self):
        self._stop_monster_sprite_animation()
        img = self.ids.get("monster_image")
        if img is not None:
            Animation.cancel_all(img)
            img.color = (1, 1, 1, 1)

        shadow = self.ids.get("monster_shadow")
        if shadow is not None:
            Animation.cancel_all(shadow)

        self._monster_idle_anim = None

    def start_monster_idle_animation(self):
        """
        Simple idle animation to make the monster feel more 3D:
        nh? nh?ng nh?n l?n xu?ng + scale.
        """
        img = self.ids.get("monster_image")
        shadow = self.ids.get("monster_shadow")
        if img is None or self.monster is None:
            return

        self.stop_monster_idle_animation()
        self._start_monster_sprite_animation("idle")

        base_x, base_y = img.pos
        base_w, base_h = img.size

        # Small drift + breathing to fake 3D hovering.
        down = Animation(
            x=base_x - 6,
            y=base_y - 8,
            size=(base_w * 1.05, base_h * 1.05),
            duration=0.8,
            t="in_out_sine",
        )
        side = Animation(
            x=base_x + 8,
            y=base_y + 6,
            size=(base_w * 0.98, base_h * 0.98),
            duration=0.9,
            t="in_out_sine",
        )
        up = Animation(
            x=base_x,
            y=base_y,
            size=(base_w, base_h),
            duration=0.75,
            t="in_out_sine",
        )
        anim = down + side + up

        def sync_shadow(*_args):
            if shadow is not None and self._monster_depth_style is not None:
                sx = img.x + self._monster_depth_style.shadow_offset_px[0]
                sy = img.y + self._monster_depth_style.shadow_offset_px[1] - 3
                shadow.pos = (sx, sy)
                shadow.size = (img.width * 1.1, img.height * 0.46)

        anim.bind(on_progress=lambda *_: sync_shadow())
        anim.repeat = True
        anim.start(img)
        self._monster_idle_anim = anim

    def start_loot_bounce_animation(self):
        """
        Simple bounce animation for the loot button so nó nhìn nổi hơn.
        """
        btn = self.ids.get("loot_button")
        if btn is None:
            return

        Animation.cancel_all(self, "loot_pulse_scale")
        anim = (
            Animation(loot_pulse_scale=1.08, duration=0.28, t="out_quad")
            + Animation(loot_pulse_scale=1.0, duration=0.28, t="in_out_quad")
        )
        anim.repeat = True
        self._loot_anim = anim
        anim.start(self)

    def clear_monster(self):
        """Remove the current monster (used when running away or after defeat)."""
        self.stop_monster_attack_loop()
        self.stop_monster_idle_animation()
        if self._pending_spawn_event is not None:
            try:
                self._pending_spawn_event.cancel()
            except Exception:
                pass
            self._pending_spawn_event = None
        self.monster = None
        self.update_monster_ui()

    # ---------------- COMBAT ACTIONS ----------------
    def start_monster_attack_loop(self):
        self.stop_monster_attack_loop()
        if self.monster is None:
            return
        self._monster_attack_event = Clock.schedule_interval(
            self._auto_monster_attack, 1.7
        )

    def stop_monster_attack_loop(self):
        if self._monster_attack_event is not None:
            try:
                self._monster_attack_event.cancel()
            except Exception:
                pass
            self._monster_attack_event = None

    def _auto_monster_attack(self, dt):
        if self.monster is None or self.player.hp <= 0:
            self.stop_monster_attack_loop()
            return False

        self.monster_turn()
        if self.monster is None or self.player.hp <= 0:
            self.stop_monster_attack_loop()
            return False
        return True

    def monster_turn(self):
        """
        Let the monster attack the player.
        """
        if self.monster is None or self.player.hp <= 0:
            return

        damage = monster_attack(self.monster, self.player, defending=self.is_defending)
        self.update_player_ui()
        self._play_monster_attack_animation(damage)

        if self.player.hp <= 0:
            self.stop_monster_attack_loop()
            self.game_over = True
            self.show_message("You were defeated! Game over.")
            self.show_game_over_popup()
        else:
            if self.is_defending:
                self.show_message(
                    f"You defend! The monster hits you for {damage} damage."
                )
            else:
                self.show_message(f"The monster hits you for {damage} damage.")

        # Reset defending flag after monster turn.
        self.is_defending = False

    def _play_monster_attack_animation(self, damage: int):
        """
        Simple hit feedback when qu?i t?n c?ng ng??i ch?i:
        - Qu?i lao m?nh t?i r?i l?i l?i.
        - To?n m?n h?nh nh?y ?? m?.
        """
        img = self.ids.get("monster_image")
        shadow = self.ids.get("monster_shadow")
        status_label = self.ids.get("status_label")
        if img is None:
            return

        self.stop_monster_idle_animation()
        self._start_monster_sprite_animation("attack")

        base_x, base_y = img.pos
        base_size = tuple(img.size)
        target_x = base_x + 42
        target_y = base_y + 14
        impact_size = (base_size[0] * 1.18, base_size[1] * 1.18)

        forward = Animation(
            x=target_x,
            y=target_y,
            size=impact_size,
            duration=0.11,
            t="out_quad",
        )
        impact = Animation(
            x=target_x + 10,
            y=target_y + 4,
            size=(impact_size[0] * 1.04, impact_size[1] * 1.04),
            duration=0.05,
            t="out_quad",
        )
        back = Animation(
            x=base_x,
            y=base_y,
            size=base_size,
            duration=0.18,
            t="in_out_cubic",
        )
        anim = forward + impact + back

        def sync_shadow(*_args):
            if shadow is not None and self._monster_depth_style is not None:
                sx = img.x + self._monster_depth_style.shadow_offset_px[0] + 4
                sy = img.y + self._monster_depth_style.shadow_offset_px[1] - 5
                shadow.pos = (sx, sy)
                shadow.size = (img.width * 1.08, img.height * 0.42)

        def restore_idle(*_args):
            if self.monster is not None:
                self.start_monster_idle_animation()

        anim.bind(on_progress=lambda *_: sync_shadow())
        anim.bind(on_complete=restore_idle)
        anim.start(img)

        if status_label is not None:
            base_color = status_label.color
            flash_lbl = Animation(color=(1, 0.2, 0.2, 1), duration=0.06) + Animation(
                color=base_color, duration=0.18
            )
            flash_lbl.start(status_label)

        intensity = max(0.25, min(0.75, damage / 28.0))
        flash_screen = (
            Animation(attack_flash_alpha=intensity, duration=0.04)
            + Animation(attack_flash_alpha=0.08, duration=0.08)
            + Animation(attack_flash_alpha=0.0, duration=0.22)
        )
        flash_screen.start(self)
        Animation(atmosphere_alpha=0.42, duration=0.06).start(self)
        (
            Animation(ground_glow_alpha=min(1.0, self.ground_glow_alpha + 0.18), duration=0.08)
            + Animation(ground_glow_alpha=max(0.18, self.ground_glow_alpha), duration=0.20)
        ).start(self)
        Animation(atmosphere_alpha=0.22, duration=0.20).start(self)

    def _play_player_attack_animation(self):
        """Player attack feedback: monster flashes red briefly when hit."""
        img = self.ids.get("monster_image")
        shadow = self.ids.get("monster_shadow")
        if img is None or self.monster is None:
            return

        self.stop_monster_idle_animation()
        self._start_monster_sprite_animation("attack")

        base_x, base_y = img.pos
        base_size = tuple(img.size)

        hit = Animation(
            color=(1, 0.25, 0.25, 1),
            x=base_x - 10,
            y=base_y + 8,
            size=(base_size[0] * 1.05, base_size[1] * 1.05),
            duration=0.07,
            t="out_quad",
        )
        recover = Animation(
            color=(1, 1, 1, 1),
            x=base_x,
            y=base_y,
            size=base_size,
            duration=0.12,
            t="in_out_cubic",
        )
        anim = hit + recover

        def sync_shadow(*_args):
            if shadow is not None and self._monster_depth_style is not None:
                shadow.pos = (
                    img.x + self._monster_depth_style.shadow_offset_px[0],
                    img.y + self._monster_depth_style.shadow_offset_px[1] - 4,
                )
                shadow.size = (img.width * 1.08, img.height * 0.44)

        def restore_idle(*_args):
            if self.monster is not None:
                self.start_monster_idle_animation()

        anim.bind(on_progress=lambda *_: sync_shadow())
        anim.bind(on_complete=restore_idle)
        anim.start(img)
        (
            Animation(aura_alpha=min(0.9, self.aura_alpha + 0.25), duration=0.05)
            + Animation(aura_alpha=max(0.16, self.aura_alpha), duration=0.18)
        ).start(self)

    def on_attack(self):
        """
        Called when the Attack button is pressed.
        Player attacks first, then the monster responds.
        """
        if self.game_over:
            return

        if self.monster is None:
            self.show_message("No monster. Press Run to find a new one.")
            return

        self.is_defending = False
        damage = player_attack(self.player, self.monster)
        self.update_monster_ui()
        self._play_player_attack_animation()

        if self.monster.hp <= 0:
            self.stage_kills += 1
            self.update_stage_ui()
            # Monster defeated: chance to drop loot (tap to pick up), then spawn a new monster.
            last_pos_hint = dict(self.ids.monster_image.pos_hint or {"x": 0.3, "y": 0.3})
            dropped = False
            if random.random() < 0.65:
                item = generate_loot()
                self.show_loot_drop(item, last_pos_hint)
                dropped = True

            if dropped:
                self.show_message("Hạ quái xong! Có đồ rơi — bấm NHẶT để lấy.")
            else:
                self.show_message("Hạ quái xong! Không rớt đồ lần này.")

            self.clear_monster()
            # Spawn quái mới theo thời gian ngẫu nhiên (1–4 giây).
            if self.stage_kills >= self.get_stage_data()["goal"]:
                self.advance_stage()
            else:
                Clock.schedule_once(lambda dt: self.schedule_spawn_monster(), 0.3)
        else:
            self.show_message(f"You hit the monster for {damage} damage.")

    def on_defend(self):
        """
        Called when the Defend button is pressed.
        Player takes reduced damage on the next monster attack.
        """
        if self.game_over:
            return

        if self.monster is None:
            self.show_message("No monster to defend against.")
            return

        self.is_defending = True
        self.show_message("You raise your shield and defend! Next monster hit will be reduced.")

    def on_run(self):
        """
        Called when the Run button is pressed.
        The monster disappears and a new one appears shortly.
        """
        if self.game_over:
            return

        if self.monster is None:
            self.show_message("You look around... no monster here.")
        else:
            self.show_message("You ran away from the monster!")
            self.clear_monster()

        # Spawn quái mới theo thời gian ngẫu nhiên.
        Clock.schedule_once(lambda dt: self.schedule_spawn_monster(), 0.3)

    def show_game_over_popup(self):
        if self._result_popup is not None:
            self._result_popup.dismiss()

        content = BoxLayout(orientation="vertical", spacing=10, padding=12)
        content.add_widget(
            Label(
                text="Ban da chet.\nNhan Choi lai de bat dau tu stage 1.",
                halign="center",
                valign="middle",
            )
        )
        replay_button = Button(text="Choi lai", size_hint=(1, None), height=44)
        replay_button.bind(on_press=lambda *_: self.restart_game())
        content.add_widget(replay_button)

        self._result_popup = Popup(
            title="Game Over",
            content=content,
            size_hint=(0.72, 0.42),
            auto_dismiss=False,
        )
        self._result_popup.open()

    def show_victory_popup(self):
        if self._result_popup is not None:
            self._result_popup.dismiss()

        content = BoxLayout(orientation="vertical", spacing=10, padding=12)
        content.add_widget(
            Label(
                text="Ban da qua het cac man.\nNhan Choi lai de choi tu dau.",
                halign="center",
                valign="middle",
            )
        )
        replay_button = Button(text="Choi lai", size_hint=(1, None), height=44)
        replay_button.bind(on_press=lambda *_: self.restart_game())
        content.add_widget(replay_button)

        self._result_popup = Popup(
            title="Chien thang",
            content=content,
            size_hint=(0.72, 0.42),
            auto_dismiss=False,
        )
        self._result_popup.open()

    def advance_stage(self):
        if self.stage_index >= len(STAGES) - 1:
            self.game_over = True
            self.show_message("Ban da pha dao tat ca stage.")
            self.show_victory_popup()
            return

        self.stage_index += 1
        self.stage_kills = 0
        self.update_stage_ui()
        self.show_message(f"Stage clear! Next enemy: {self.get_stage_data()['name']}.")
        Clock.schedule_once(lambda dt: self.schedule_spawn_monster(), 0.8)

    def restart_game(self):
        if self._result_popup is not None:
            self._result_popup.dismiss()
            self._result_popup = None

        self.stop_monster_attack_loop()
        self.stop_monster_idle_animation()
        self.hide_loot_drop()
        self.player = Player(name="Hero", hp=100, attack=15, defense=5)
        self.monster = None
        self.inventory = {}
        self.stage_index = 0
        self.stage_kills = 0
        self.game_over = False
        self.is_defending = False
        self.update_player_ui()
        self.update_monster_ui()
        self.update_stage_ui()
        self.update_inventory_ui()
        self.show_message("Bat dau lai Stage 1.")
        Clock.schedule_once(lambda dt: self.schedule_spawn_monster(), 0.5)


class DungeonARApp(App):
    """
    The main Kivy application.
    """

    def build(self):
        # Load the UI layout from the .kv file.
        Builder.load_file(str(BASE_DIR / "ui.kv"))
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

