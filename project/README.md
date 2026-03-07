# Game San Quai AR (Python + Kivy + OpenCV)

Day la mot prototype game san quai kieu AR viet bang **Python**.
Game dung:

- `Kivy` de ve giao dien
- `OpenCV` de lay hinh tu camera

Nen game la camera, quai vat se xuat hien ben tren, va nguoi choi co the `Attack`, `Defend`, hoac `Run`.

## Cau truc project

- `main.py`: file chay chinh cua game
- `camera.py`: xu ly camera bang OpenCV
- `player.py`: thong tin nguoi choi
- `monster.py`: tao quai vat ngau nhien
- `combat.py`: logic tan cong / phong thu
- `loot.py`: logic roi do sau khi ha quai
- `ui.kv`: giao dien Kivy
- `requirements.txt`: danh sach thu vien can cai

## Cai dat

Luu y: tren may nay nen dung `Python 3.11`. Khong nen dung `Python 3.14` vi dang thieu / khong khop thu vien.

### 1. Cai package truoc khi chay

Neu dang dung PowerShell trong thu muc `project`, chay:

```powershell
py -m pip install -r requirements.txt
```

Neu muon chi ro dung `Python 3.11`, chay:

```powershell
& C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe -m pip install -r requirements.txt
```

Hai package can co la:

```text
kivy
opencv-python
```

### 2. Chay game

Sau khi cai xong, chay mot trong cac cach sau:

```powershell
py main.py
```

Hoac:

```powershell
.\run_game.cmd
```

Neu dang o thu muc goc `E:\dangeon-hoc-lam-game` thi chay:

```powershell
.\run_game.cmd
```

## Neu gap loi

### Loi `No module named 'kivy'`

Ban chua cai package, hoac dang chay sai Python.
Hay cai lai bang:

```powershell
& C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe -m pip install -r requirements.txt
```

Sau do chay lai:

```powershell
& C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe .\main.py
```

### Loi camera

Neu may khong co camera hoac OpenCV khong mo duoc camera, game van co the mo len nhung nen camera se khong hien.

## Dieu khien co ban

- `Attack`: tan cong quai, quai se danh lai neu chua chet
- `Defend`: giam sat thuong o dot danh tiep theo cua quai
- `Run`: bo chay va tim quai moi

Khi ha quai, ban co the nhan do roi nhu `Sword`, `Armor`, `Potion`, hoac `Gold`.
