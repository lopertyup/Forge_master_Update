# PATCH NOTES — Corrections moteur de simulation PvP

> Document généré depuis l'analyse comparative log simulé vs combat réel.
> Référence : Blackgun (P, 73.4% atk spd) vs Quantumstaff (O, 0% atk spd).
> Combat réel : début à 2:29, premier swing à 3:81, premier impact \~4:33.

\---

## État des patches

|#|Patch|Sévérité|Statut|
|-|-|-|-|
|P1|Combat start delay|🔴 Majeur|🔲 À faire|
|P2|Double hit — second projectile décalé|🔴 Majeur|🔲 À faire|
|P3|Lifesteal à l'impact, pas au tir|🔴 Majeur|🔲 À faire|
|P4|swing\_time\_double — POST\_ATTACK\_FIXED en trop|🔴 Majeur|🔲 À faire|
|P5|Travel time — distance effective PvP|🟠 Important|🔲 À faire|
|P6|Skills — INITIAL\_SKILL\_DELAY incorrect|🟠 Important|🔲 À faire|
|P7|Skills — timer init = cooldown au lieu de delay|🟠 Important|🔲 À faire|
|P8|PvP HP pool — double application health\_pct|🟡 Mineur|🔲 À faire|
|P9|Init log — cycle affiché incohérent|🟡 Mineur|🔲 À faire|

\---

## P1 — Combat start delay

### Problème

Le simulateur démarre les swings à `t=0`. En réalité les combattants se
déplacent vers l'adversaire avant d'attaquer.

### Données réelles

* Combat démarre à `2:29`
* Fighters s'arrêtent et commencent le windup à `3:81` → **1.52s de déplacement**
* Premier tir à `4:28` → **0.47s de windup** après l'arrêt

### Correction

Ajouter un `COMBAT\_START\_DELAY` avant le premier `\_start\_swing()` dans
`simulate()`. La valeur est fixe pour le PvP (les deux fighters parcourent
la même distance).

```python
# constants.py
COMBAT\_START\_DELAY = 1.52   # secondes avant le premier swing

# simulation.py — Fighter.\_\_init\_\_
self.\_swing\_timer = -COMBAT\_START\_DELAY   # swing démarre après le délai
```

Valeur à affiner — `1.52s` est une mesure unique, imprécision possible.
Plage raisonnable : `1.3s – 1.7s`.

\---

## P2 — Double hit : second projectile non décalé

### Problème

Quand un double hit se déclenche, les deux projectiles sont enqueués
**au même timestamp** dans `\_perform\_attack()`. Ils atterrissent donc
simultanément, ce qui est incorrect.

### Données réelles

* Tir 1 à `4:28`, tir 2 (double) à `4:48` → gap **0.20s**
* Impact 1 à `4:33`, impact 2 à `4:53`

Le gap entre les deux tirs = `floor(0.25 / mult \* 10) / 10`.
À 73.4% speed (mult=1.734) : `floor(0.25/1.734 \* 10) / 10 = floor(1.44)/10 = 0.10s`.

**Mais le réel montre 0.20s** → à 0% speed (O, mult=1.0) :
`floor(0.25/1.0 \* 10) / 10 = 0.20s` ✅ cohérent avec les données de O.

### Correction

Dans `\_perform\_attack()` (ou là où les hits du double sont générés),
le second hit doit être enqueué avec un timestamp décalé :

```python
# Pour un double hit :
gap = math.floor(DOUBLE\_ATTACK\_GAP / self.\_speed\_mult \* 10) / 10
hit1\_time = current\_time + self.projectile\_travel\_time
hit2\_time = current\_time + gap + self.projectile\_travel\_time

pending.append({"target": target, "dmg": dmg1, "time": hit1\_time, ...})
pending.append({"target": target, "dmg": dmg2, "time": hit2\_time, ...})
```

**Important :** le cooldown du swing repart immédiatement après le release
du premier hit — il n'attend pas le second. C'est déjà le comportement
actuel (le `\_start\_swing()` suivant est appelé après le release), à ne pas
modifier.

\---

## P3 — Lifesteal appliqué au tir, pas à l'impact

### Problème

Le heal du lifesteal est calculé et appliqué au moment où l'attaquant
**tire** (`\_perform\_attack()`). Il devrait être appliqué quand le
**projectile atterrit** (résolution de la queue).

### Impact

Pour les armes melee (travel time = 0) l'écart est nul. Pour les armes
ranged, le tireur se heal de 0.05s à 0.35s trop tôt. Si le tireur meurt
entre le tir et l'impact, il reçoit quand même le heal — comportement
incorrect.

### Correction

Stocker les infos de lifesteal dans le dict de la queue d'impacts :

```python
# Lors de l'enqueue (pas d'application immédiate) :
pending.append({
    "target":    target,
    "attacker":  self,
    "dmg":       dmg,
    "lifesteal": dmg \* self.lifesteal,
    "time":      impact\_time,
})

# Lors de la résolution de l'impact :
def \_apply\_impact(imp):
    target.hp  = max(0, target.hp - imp\["dmg"])
    attacker   = imp\["attacker"]
    if imp\["lifesteal"] > 0 and attacker.hp > 0:
        attacker.hp = min(attacker.hp\_max, attacker.hp + imp\["lifesteal"])
```

**Règle déjà définie :** si le lanceur est mort avant l'impact, le lifesteal
ne s'applique pas (`attacker.hp > 0` check).

\---

## P4 — swing\_time\_double : POST\_ATTACK\_FIXED ajouté deux fois

### Problème

La formule actuelle dans `stats.py` :

```python
def swing\_time\_double(windup, recovery, attack\_speed\_pct=0.0):
    base = swing\_time\_discrete(windup, recovery, attack\_speed\_pct)
    gap  = \_step\_down(DOUBLE\_ATTACK\_GAP / mult)
    return base + gap + POST\_ATTACK\_FIXED   # ← POST ajouté une 2e fois
```

`swing\_time\_discrete` inclut déjà `POST\_ATTACK\_FIXED`. L'ajouter à nouveau
gonfle le cycle double de 0.20s.

### Vérification depuis la table (arme Blackgun, 73.4% speed)

```
cycle simple  = 0.70s (confirmé dans le log)
gap steppé    = floor(0.25 / 1.734 \* 10) / 10 = 0.10s
cycle double attendu = 0.70 + 0.10 = 0.80s ✅ (confirmé dans le log "×2: 0.80s")
cycle double actuel  = 0.70 + 0.10 + 0.20 = 1.00s ✗
```

### Correction

```python
def swing\_time\_double(windup, recovery, attack\_speed\_pct=0.0):
    mult = speed\_mult(attack\_speed\_pct)
    if mult <= 0:
        mult = 1.0
    base = swing\_time\_discrete(windup, recovery, attack\_speed\_pct)
    gap  = \_step\_down(DOUBLE\_ATTACK\_GAP / mult)
    return base + gap   # ← pas de second POST\_ATTACK\_FIXED
```

### Note sur les tables de breakpoints

La colonne `double\_attack\_cycle` des fichiers dans `helper/weapon atq speed/`
donne directement le cycle double par palier d'attack speed. Le simulateur
**peut** lire cette table pour valider ou remplacer le calcul — particulièrement
utile quand windup/recovery ne sont pas connus avec précision.

\---

## P5 — Travel time : distance effective PvP incorrecte

### Problème

`weapon\_projectiles.py` utilise `RANGE\_RANGED = 7.0` unités, ce qui donne
un travel time de `0.35s` pour Blackgun (speed 20).

### Données réelles

* Tir Blackgun (speed 20) → impact \~0.05s après
* Tir Quantumstaff (speed 30) → impact \~0.05s après

La distance effective en combat PvP est bien inférieure à 7.0 — les
fighters sont proches quand ils attaquent.

### Calcul

Si travel time réel ≈ 0.05-0.10s et speed = 20 :

```
distance = 0.075 × 20 = 1.5 unités (médiane)
```

### Correction

```python
# weapon\_projectiles.py
PVP\_COMBAT\_DISTANCE = 1.5   # unités — remplace RANGE\_RANGED = 7.0

def get\_travel\_time(weapon\_name, projectile\_lib=None):
    speed = get\_projectile\_speed(weapon\_name, projectile\_lib)
    if not speed:
        return 0.0
    return PVP\_COMBAT\_DISTANCE / speed
```

Résultats avec `PVP\_COMBAT\_DISTANCE = 1.5` :

|Arme|Speed|Travel time|
|-|-|-|
|Rock, Tomahawk|15|0.10s|
|Bow, Blackgun, etc.|20|0.075s|
|Crossbow, Blaster, etc.|25|0.06s|
|Staff, Quantumstaff, etc.|30|0.05s|

Valeur à affiner avec plus de combats réels — `1.0–2.0` est la plage de
confiance actuelle.

\---

## P6 — INITIAL\_SKILL\_DELAY trop long

### Problème

`INITIAL\_SKILL\_DELAY = 3.8s` dans `constants.py`. Les skills castent à
`3.00s` dans le log simulé, ce qui suggère que le delay réel appliqué n'est
pas `3.8s`.

### Données réelles

* Combat démarre à `2:29`
* Premier hit Lightning observé à `5:24` → **2.95s après le début**
* Le cast Lightning a lieu légèrement avant le premier hit (interval \~0.1s)
→ cast ≈ **2.85s après le début** du combat

### Correction

```python
# constants.py
INITIAL\_SKILL\_DELAY = 2.87   # secondes — valeur mesurée, à affiner
```

Plage de confiance : `2.5s – 3.1s` (une seule mesure, imprécision possible).

\---

## P7 — Skills : timer initialisé à cooldown au lieu de INITIAL\_SKILL\_DELAY

### Problème

Dans le log simulé, Worm et Morale castent à `8.00s` — soit 5 secondes
après Lightning (à `3.00s`). Ce gap correspond exactement au cooldown de
Worm/Morale, ce qui indique que chaque skill est initialisé avec
`timer = cooldown\_effectif` et déclenche son premier cast dès que
`timer >= cooldown`. Résultat : les skills à cooldown différent se
synchronisent au premier tick de leur propre cooldown, pas au même
`INITIAL\_SKILL\_DELAY`.

### Correction

Tous les skills doivent démarrer avec le même `INITIAL\_SKILL\_DELAY`,
indépendamment de leur cooldown :

```python
# SkillInstance.\_\_init\_\_
self.\_timer = INITIAL\_SKILL\_DELAY   # même pour tous les skills
# (pas self.\_timer = self.\_cooldown)
```

Après le premier cast, le timer repart sur `cooldown\_effectif` normalement.

\---

## P8 — PvP HP pool : double application de health\_pct

### Problème

HP pool de O affiché `205.00m` dans le log alors que `39m × 5 = 195m`.
Ratio : `205 / 195 = 1.051` — cohérent avec un `health\_pct` résiduel
appliqué une seconde fois lors du calcul du pool PvP.

### Cause probable

`pvp\_hp\_total()` reçoit `stats\["hp\_total"]` qui devrait être le total final.
Mais si quelque part le code passe `hp\_base` au lieu de `hp\_total`, ou
recalcule `hp\_base × (1 + health\_pct/100)` une fois de plus, le pool est
gonflé.

### Correction

Vérifier que `pvp\_hp\_total()` utilise bien `hp\_total` et non `hp\_base` :

```python
def pvp\_hp\_total(stats):
    # hp\_total = hp\_base × (1 + health\_pct/100) — déjà calculé
    # NE PAS refaire : hp\_base \* (1 + health\_pct/100) \* PVP\_HP\_MULTIPLIER
    return float(stats.get("hp\_total", 0.0) or 0.0) \* PVP\_HP\_MULTIPLIER
```

\---

## P9 — Init log : cycle affiché incohérent

### Problème

```
◆ O init · HP 205.00m · ATK 5.58m · swing 0.60s (×2: 0.70s)
▷ O swing start \[DOUBLE] · dur 0.70s   ← correct
```

O a `attack\_speed = 0%`, cycle primaire = `0.60s` affiché mais swings
réels à `0.70s`. Le `0.60s` correspond probablement à `windup + recovery`
sans le `POST\_ATTACK\_FIXED` (soit `1.1s base - 0.5s` quelque chose), ce
qui indique que l'affichage de l'init calcule le cycle différemment de
`\_start\_swing()`.

### Correction

S'assurer que le log d'init utilise exactement `swing\_time\_discrete()`
pour afficher le cycle :

```python
# Dans le log d'init du Fighter :
cycle\_display = swing\_time\_discrete(self.weapon\_windup, self.weapon\_recovery,
                                    self.\_attack\_speed\_pct)
double\_display = swing\_time\_double(self.weapon\_windup, self.weapon\_recovery,
                                   self.\_attack\_speed\_pct)
print(f"swing {cycle\_display:.2f}s (×2: {double\_display:.2f}s)")
```

\---

## Formule attack speed — confirmée correcte

L'analyse de la table de breakpoints (windup=1.0s, recovery=0.1s, base=1.1s)
confirme que la formule dans `stats.py` est **structurellement correcte** :

```python
stepped\_windup   = floor(windup   / mult \* 10) / 10
stepped\_recovery = floor(recovery / mult \* 10) / 10
cycle = stepped\_windup + stepped\_recovery + POST\_ATTACK\_FIXED
```

Les paliers `1.1s` et `1.2s` marqués "REACHED" à 0% sont des artefacts
normaux — cette arme ne peut pas atteindre ces paliers intermédiaires car
`recovery = 0.1s` est trop petit pour contribuer un step supplémentaire.
Il n'y a pas de bug à corriger ici.

\---

## Analyse skill cooldown — confirmée correcte

Comparaison Lightning (même skill, cooldown différent) :

||Joueur|Opponent|
|-|-|-|
|`skill\_cooldown`|0%|-9.47%|
|Gap cast 1→2 observé|6.42s|5.80s|
|Ratio observé|1.000|0.903|
|`1 - 0.0947`|—|**0.9053 ✅**|

La mécanique `cooldown\_effectif = cooldown\_base × (1 + skill\_cooldown/100)`
est correcte. La valeur de `cooldown\_base` de Lightning ultimate dans
`SkillLibrary.json` doit être vérifiée — le cooldown réel observé est
**\~6.42s**, à comparer avec la valeur du JSON.

\---

## Ordre d'implémentation recommandé

Les patches sont listés par ordre d'impact sur la précision de simulation :

1. **P4** — `swing\_time\_double` (5 min, 1 ligne) — corrige immédiatement les cycles
2. **P7** — `SkillInstance.\_\_init\_\_` timer (15 min) — désynchronise les skills
3. **P6** — `INITIAL\_SKILL\_DELAY` (2 min, 1 constante) — cale le premier cast
4. **P3** — Lifesteal à l'impact (30 min) — corrige le heal ranged
5. **P2** — Second projectile décalé (1h) — corrige le double hit ranged
6. **P1** — Combat start delay (30 min) — cale l'axe temporel global
7. **P5** — Travel time distance (5 min, 1 constante) — corrige la physique ranged
8. **P8** — HP pool health\_pct (investigation) — vérifier la source du bug
9. **P9** — Init log (15 min) — cosmétique

