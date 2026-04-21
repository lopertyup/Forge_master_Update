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

## 🎮 Comment utiliser l'outil

### Importer ton profil

L'outil a besoin de tes statistiques de jeu. Pour les récupérer :

1. Dans **Forge Master** (sur BlueStacks), ouvre ton profil de personnage
2. Utilise l'**outil Capture d'écran de Windows** pour capturer l'écran
   - Raccourci : `Windows + Shift + S`ou boutton 'Impèc'
   - Sélectionne la zone avec tes stats
3. L'outil de capture inclut une fonction **OCR** (reconnaissance de texte) — copie le texte détecté
4. Colle ce texte dans la section **Dashboard** de l'application

---

### Simulateur de combat

1. Va dans l'onglet **Simulateur**
2. Entre les statistiques de ton adversaire (même méthode que pour ton profil)
3. Clique sur **Simuler** — l'outil lance 1000 combats et affiche ton win rate

---

### Comparateur d'équipements

1. Dans le jeu, ouvre la comparaison entre ton équipement actuel et le nouveau
2. Utilise `Windows + Shift + S` pour capturer l'écran et copier le texte
3. Colle le texte dans l'onglet **Équipements** — la simulation se lance automatiquement
4. L'outil te dit si le nouvel équipement est meilleur et te propose de l'appliquer

> Le texte doit contenir **NEW!** pour être reconnu.

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

---

## 📌 Notes

- L'outil tourne entièrement en local sur ton PC, aucune donnée n'est envoyée
- Les simulations sont basées sur les statistiques que tu rentres — plus elles sont précises, plus les résultats sont fiables
- L'optimiseur peut prendre quelques minutes selon les paramètres choisis

---

*Projet open source — contributions bienvenues !*
