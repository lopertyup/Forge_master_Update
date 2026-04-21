# ⚔️ Forge Master UI

Analysis and simulation tool for the mobile game **Forge Master**.  
Predict win/loss outcomes, compare equipment and optimize your substats — directly from your PC.

---

## 📋 Features

- **Combat Simulator** — predicts your win rate against a given opponent
- **Equipment Comparator** — automatically analyzes whether new equipment is better
- **Substat Optimizer** — finds the best distribution of your substat points
- **Pets and Mounts management**

---

## 🛠️ Installation

### 1. Install Bluestacks

Forge Master is a mobile game. To play it on PC, you need **BlueStacks** (Android emulator).

👉 Download BlueStacks: https://www.bluestacks.com/index.html

Launch BlueStacks, sign in to the Google Play Store and install **Forge Master**.

---

### 2. Download the code

On the GitHub project page, click the green **Code** button then **Download ZIP**.

Extract the folder wherever you want on your PC.

---

### 3. Install Python

👉 Download Python: https://www.python.org/downloads/

> ⚠️ **Important**: during installation, make sure to check **"Add Python to PATH"** before clicking Install.

---

### 4. Install dependencies

Open the **terminal** in the project folder:
- On Windows: right-click in the folder → **Open in Terminal**

Then type the following command and press Enter:

```
pip install customtkinter pillow
```

Wait for the installation to complete.

---

### 5. Launch the application

In the same terminal, type:

```
python main.py
```

The application opens. 🎉

---

## 📸 How to get text from the game

The tool works by **copy-pasting text** from screenshots.  
Windows has a built-in tool that lets you capture a screen area and automatically extract the text.

**Shortcut:** `Windows + Shift + T`  
Select the desired area — the text is automatically copied to your clipboard.

---

## 🎮 How to use the tool

### Import your profile

In **Forge Master**, open your character profile and capture the stats area.  
The text should look like this:

```
Lv. 23 Forge
5.04m Total Damage
38.9m Total Health
+22.2% Critical Chance
+147% Critical Damage
+5.78% Health Regen
+69.8% Lifesteal
+116% Double Chance
+22.2% Damage
+16.1% Melee Damage
+14.8% Ranged Damage
+98.2% Attack Speed
+12.3% Health
```

Paste this text into the **Dashboard** section of the application.

---

![Profile Update](screenshots/profile_update.png)

### Equipment Comparator

In the game, open the comparison between your current equipment and the new one.  
Capture the full area containing **both items** with the **NEW!** tag.  
The text should look like this:

```
Equipped
Lv. 54
[Quantum] Gravity Gloves
144k Damage
+31.4% Attack Speed
+19.5% Lifesteal
4
Lv. 81
NEW!
[Quantum] Gravity Gloves
188k Damage
+19.9% Critical Damage
+4.34% Double Chance
```

> ⚠️ The text must contain **NEW!** to be recognized.

Paste this text into the **Equipment** tab — the simulation launches automatically and tells you whether the new equipment is better.

![Equipment Comparator](screenshots/equipment_comparator.png)

---

### Pets Management

![Pet Overview](screenshots/pet_overview.png)

In the game, open your pet's page and capture its stats.  
The text should look like this:

```
Lv.1
[Ultimate] Enchanted Elk
855k Damage
6.84m Health
+5.97% Health Regen
+5.59% Ranged Damage
```

> 💡 **Important**: the tool always compares pets at **level 1**.  
> Why? Because main stats (Damage and Health) scale with level, but substats (%, bonuses) remain identical.  
> By bringing everything to level 1, two pets can be compared fairly regardless of their current level.  
> The internal library knows the base stats at level 1 for each pet type.

![Pet Simulation](screenshots/pet_replacement_simulation.png)

---

### Mounts Management

Same principle as pets. Capture your mount's stats:

```
Lv.1
[Rare] Brown Horse
10.4k Damage
83.2k Health
+6.95% Health
```

> 💡 Same logic as pets: everything is compared at **level 1**.

![Mount Simulation](screenshots/mount_replacement_simulation.png)

---

### Combat Simulator

1. Go to the **Simulator** tab
2. Enter your opponent's statistics (same method as for your profile) — don't forget to specify their skills and attack type (melee/ranged)
3. Click **Simulate** — the tool runs 1000 fights and displays your win rate

---

### Substat Optimizer

1. Go to the **Optimizer** tab
2. Choose the number of generations and simulations
3. Click **Launch** — the tool tests thousands of substat combinations
4. At the end, it shows you:
   - The most important stats for your profile
   - The best build found compared to your current build
   - The stats to prioritize

---

## ❓ Common issues

**`python` is not recognized in the terminal**  
→ Reinstall Python making sure to check **"Add Python to PATH"**

**`pip install` fails**  
→ Try: `pip install customtkinter pillow --break-system-packages`

**The application doesn't open**  
→ Make sure you are in the correct folder in the terminal before typing `python main.py`

**The text is not recognized**  
→ Make sure the screenshot is clear and the text is copied without extra characters

---

## 📌 Notes

- The tool runs entirely locally on your PC, no data is sent anywhere
- Simulations are based on the statistics you enter — the more accurate they are, the more reliable the results
- The optimizer may take a few minutes depending on the chosen parameters

---

*Open source project — contributions welcome!*
