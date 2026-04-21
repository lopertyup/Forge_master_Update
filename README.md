# ⚔️ Forge Master UI

Outil d'analyse et de simulation pour le jeu mobile **Forge Master**.  
Permet de prédire les victoires/défaites, comparer des équipements et optimiser ses substats — directement depuis ton PC.

---

## 📋 Fonctionnalités

- **Simulateur** — prédit ton win rate contre un adversaire donné
- **Comparateur d'équipements** — analyse automatiquement si un nouvel équipement est meilleur
- **Optimiseur de substats** — trouve la meilleure répartition de tes points de substats
- **Gestion des pets et montures**

---

## 🛠️ Installation

### 1. Installer Bluestacks

Forge Master est un jeu mobile. Pour y jouer sur PC, tu as besoin de **BlueStacks** (émulateur Android).

👉 Télécharge BlueStacks : https://www.bluestacks.com/fr/index.html

Lance BlueStacks, connecte-toi au Google Play Store et installe **Forge Master**.

---

### 2. Télécharger le code

Sur la page GitHub du projet, clique sur le bouton vert **Code** puis **Download ZIP**.

Extrais le dossier où tu veux sur ton PC.

---

### 3. Installer Python

👉 Télécharge Python : https://www.python.org/downloads/

> ⚠️ **Important** : lors de l'installation, coche bien la case **"Add Python to PATH"** avant de cliquer sur Install.

---

### 4. Installer les dépendances

Ouvre le **terminal** dans le dossier du projet :
- Sur Windows : clic droit dans le dossier → **Ouvrir dans le terminal**

Tape ensuite cette commande et appuie sur Entrée :

```
pip install customtkinter pillow
```

Attends que l'installation se termine.

---

### 5. Lancer l'application

Dans le même terminal, tape :

```
python main.py
```

L'application s'ouvre. 🎉

---

## 📸 Comment récupérer le texte depuis le jeu

L'outil fonctionne par **copier-coller de texte** depuis des captures d'écran.  
Windows dispose d'un outil intégré qui permet de capturer une zone d'écran et d'en extraire le texte automatiquement.

**Raccourci :** `Windows + Shift + T`  
Sélectionne la zone voulue → clique sur la notification → utilise **"Copier le texte"** dans l'outil de capture.

---

## 🎮 Comment utiliser l'outil

### Importer ton profil

Dans **Forge Master**, ouvre ton profil de personnage et capture la zone de statistiques.  
Le texte doit ressembler à ceci :

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

Colle ce texte dans la section **Dashboard** de l'application.

---

### Comparateur d'équipements

Dans le jeu, ouvre la comparaison entre ton équipement actuel et le nouveau.  
Capture la zone complète qui contient les **deux équipements** avec le tag **NEW!**.  
Le texte doit ressembler à ceci :

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

> ⚠️ Le texte doit impérativement contenir **NEW!** pour être reconnu.

Colle ce texte dans l'onglet **Équipements** — la simulation se lance automatiquement et te dit si le nouvel équipement est meilleur.

---

### Gestion des Pets

Dans le jeu, ouvre la page de ton pet et capture ses statistiques.  
Le texte doit ressembler à ceci :

```
Lv.1
[Ultimate] Enchanted Elk
855k Damage
6.84m Health
+5.97% Health Regen
+5.59% Ranged Damage
```

> 💡 **Important** : l'outil compare toujours les pets à leur **niveau 1**.  
> Pourquoi ? Parce que les stats principales (Damage et Health) augmentent avec le niveau, mais les substats (%, bonus) restent identiques.  
> En ramenant tout au niveau 1, deux pets peuvent être comparés équitablement peu importe leur niveau actuel.  
> La librairie interne connaît les stats de base au niveau 1 de chaque type de pet.

---

### Gestion des Montures

Même principe que les pets. Capture les stats de ta monture :

```
Lv.1
[Rare] Brown Horse
10.4k Damage
83.2k Health
+6.95% Health
```

> 💡 Même logique que les pets : tout est comparé au **niveau 1**.

---

### Simulateur de combat

1. Va dans l'onglet **Simulateur**
2. Entre les statistiques de ton adversaire (même méthode que pour ton profil) attention pense à indiquer ses skills et son type d'attauqe (distance/corp-a-corp).
3. Clique sur **Simuler** — l'outil lance 1000 combats et affiche ton win rate

---

### Optimiseur de substats

1. Va dans l'onglet **Optimiseur**
2. Choisis le nombre de générations et de simulations
3. Clique sur **Lancer** — l'outil teste des milliers de combinaisons de substats
4. À la fin, il t'affiche :
   - Les stats les plus importantes pour ton profil
   - Le meilleur build trouvé comparé à ton build actuel
   - Les stats à prioriser en priorité

---

## ❓ Problèmes fréquents

**`python` n'est pas reconnu dans le terminal**  
→ Réinstalle Python en cochant bien **"Add Python to PATH"**

**`pip install` échoue**  
→ Essaie avec : `pip install customtkinter pillow --break-system-packages`

**L'application ne s'ouvre pas**  
→ Vérifie que tu es bien dans le bon dossier dans le terminal avant de taper `python main.py`

**Le texte n'est pas reconnu**  
→ Assure-toi que la capture est nette et que le texte est bien copié sans caractères parasites

---

## 📌 Notes

- L'outil tourne entièrement en local sur ton PC, aucune donnée n'est envoyée
- Les simulations sont basées sur les statistiques que tu rentres — plus elles sont précises, plus les résultats sont fiables
- L'optimiseur peut prendre quelques minutes selon les paramètres choisis

---

*Projet open source — contributions bienvenues !*
