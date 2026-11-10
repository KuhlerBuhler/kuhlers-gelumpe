# Plugins pour l’Electribe

Version française | [Version anglaise](plugins.en.md) | [Version allemande](plugins.md)

Référence au 2026-11-09. Cette page décrit le langage et l’API des plugins, leurs fichiers,
le menu BLECH et leur utilisation dans l’éditeur. Les identifiants de code et les inscriptions
de l’appareil restent inchangés. Les mesures détaillées citées sont en allemand.
Les indications **mesuré dans l’émulateur**, **déduit** et **non vérifié sur l’appareil**
ne constituent pas une confirmation sur le matériel réel.

Un plugin ajoute une fonction à l’Electribe : animation de LED, jeu à l’écran ou page de menu.
Il se charge depuis la carte SD. Son code utilise un sous-ensemble de JavaScript, compilé
par l’éditeur en bytecode exécuté par une petite machine virtuelle dans le firmware.
Une erreur désactive le plugin et affiche un message dans BLECH ; l’Electribe continue de fonctionner.

Les plugins se chargent et démarrent à l’allumage. Ceux qui commandent uniquement des LED
ou réaffectent des boutons n’exigent aucune action dans le menu. L’écran appartient au firmware.
Un plugin doté d’un écran est une **application**, inscrite dans GAMES ou TOOLS : ENTER l’ouvre,
EXIT la ferme toujours. Un plugin peut aussi demander temporairement l’écran avec
`korg.display.take()`. Charger un plugin ne dessine jamais à l’écran.

## Référence du langage

### Structure

Le corps du plugin, au premier niveau du code, s’exécute une fois au démarrage : déclaration
des variables, initialisation et enregistrement des gestionnaires. Ensuite, seuls les gestionnaires
s’exécutent lorsqu’un événement arrive.

```js
korg.app("Zaehler", "TOOLS");
let count = 0;

function show() {
  korg.display.clear();
  korg.display.number(count, 0, 16);
}

korg.onEvent("open", () => show());
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) { count += 1; show(); }
});
```

`korg.onEvent("event", handler)` se déclare au premier niveau, avec un seul gestionnaire par
événement et par plugin. Le gestionnaire est une fonction fléchée ou le nom d’une fonction.
Il peut recevoir moins d’arguments que l’événement n’en fournit. Les gestionnaires deviennent
actifs une fois le corps terminé sans erreur.

### Applications et écran

Un plugin ne dessine que s’il possède l’écran. Il peut l’obtenir de deux façons, qui se terminent
toutes deux avec EXIT. Le filtre d’entrée du firmware traite EXIT avant le plugin : celui-ci
ne peut ni l’intercepter ni le bloquer. Les appels de dessin sans possession de l’écran sont
ignorés sans message. Le chargement et l’import d’un plugin ne prennent jamais l’écran.

**Application dans le menu.** `korg.app("Name", "Group")` s’inscrit une seule fois au premier
niveau, hors d’une fonction. Le nom contient 1 à 15 caractères ASCII ; le groupe vaut `"GAMES"`
ou `"TOOLS"`. Le plugin et ses gestionnaires démarrent immédiatement, même lorsque l’application
est fermée ; seul `frame` est réservé à son ouverture.

ENTER, c’est-à-dire MENU, ouvre l’application depuis BLECH. L’écran est effacé, le firmware affiche
sa page principale et le plugin reçoit `open`, puis `frame`, avec le droit de dessiner.
Les boutons appartiennent alors à l’application. Les encodeurs, potentiomètres, pads et pavé tactile
restent au firmware pour permettre de jouer. **PLAY, STOP et REC** atteignent aussi le firmware
et restent transmis au plugin par `buttonPress` et `buttonRelease`. Les autres boutons, y compris
ceux de sélection de partie, ne modifient plus le firmware. EXIT ferme l’application, lui envoie
`close` et rend l’écran au firmware. Quitter autrement la page principale ferme également l’application.

```js
// Application Snake : ouverture dans GAMES, nouvelle partie à chaque ouverture.
korg.app("Snake", "GAMES");
// ... état et fonctions du jeu comme dans le plugin Snake ...
korg.onEvent("open", () => { reset(); frames = 0; draw(); });
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.PART_LEFT) dir = (dir + 3) % 4;
  if (key == korg.key.PART_RIGHT) dir = (dir + 1) % 4;
});
korg.onEvent("frame", () => { frames += 1; if (frames >= 3) { frames = 0; step(); } draw(); });
```

**Prise temporaire de l’écran.** Un plugin qui n’est pas une application peut appeler
`korg.display.take()` depuis un événement si le firmware affiche sa page principale et si
personne ne possède l’écran. La fonction renvoie 1 en cas de succès, sinon 0. Le plugin dessine
jusqu’à `korg.display.release()` ou EXIT ; EXIT lui envoie `close`. Une application s’ouvre
par le menu et n’utilise pas cette prise. Aucun écran n’est disponible dans le corps du plugin.

```js
// Message à l’écran pendant le maintien de PLAY.
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.PLAY && korg.display.take()) korg.display.text("PLAY aktiv", 0, 0);
});
korg.onEvent("buttonRelease", (key) => {
  if (key == korg.key.PLAY) korg.display.release();
});
```

**Marges.** Les textes et indications gardent 4 pixels à gauche et à droite, 2 pixels en haut
et en bas, comme les menus du firmware. Une ligne supérieure commence à `y = 2`, une ligne
inférieure à `y = 55` ; un texte aligné à droite finit à `x = 123`. Un terrain de jeu ou une image
peut atteindre les bords. Les plugins du catalogue respectent ces marges.

Réserve la prise temporaire aux fonctions sans entrée de menu adaptée : elle conserve l’écran
et les boutons jusqu’à EXIT. Un plugin qui ne commande que des boutons ou des LED n’en a pas besoin.

### Langage

- **Valeurs :** entiers signés sur 32 bits, de `-2147483648` à `2147483647`, ou hexadécimaux
  jusqu’à `0xFFFFFFFF`, et textes courts. `true` vaut 1, `false` vaut 0.
- **Texte :** littéral entre guillemets, ASCII et ä, ö, ü, de 31 caractères au maximum, ou variable
  contenant un tel littéral. Il peut être comparé avec `==` ou `!=` et transmis à `korg.*`,
  mais ni concaténé ni découpé. `korg.display.number` affiche les nombres.
- **Variables :** `let` et `const`. Une constante de valeur fixe ne consomme pas d’emplacement.
  Chaque variable utilise un emplacement fixe de 4 octets. La zone est dimensionnée selon les
  variables et tableaux déclarés. Le format autorise 65536 emplacements par plugin ; sur
  l’appareil, blocs, variables et entrées de plugins partagent 128 Kio, voir « Limites ».
- **Tableaux :** `const a = new Array(16);` ou `const a = [1, 2, 3];`, uniquement au premier
  niveau, taille fixe de 1 à 65535 éléments numériques. Opérations : `a[i]`, `a[i] = x`,
  `a[i] += x`, `a.length`. Un index hors limites termine le plugin avec une erreur.
  Un littéral contenant seulement des valeurs de 0 à 255, par exemple pour `korg.display.bitmap`,
  est stocké comme octets dans le bloc sans coût de code. Sinon, chaque valeur non nulle
  est initialisée par du code.
- **Calcul :** `+ - * / %`, `& | ^ << >> ~`, comparaisons `== != === !== < <= > >=`,
  `&& || !`, `? :`. Les opérations débordent sur 32 bits. `/` tronque vers zéro, contrairement
  à JavaScript ; `%` conserve le signe du dividende. Le décalage utilise les 5 bits faibles
  du nombre de positions ; `>>` conserve le signe. `&&` et `||` renvoient l’une des deux
  valeurs, comme en JavaScript.
- **Instructions :** affectations `= += -= *= /= %= &= |= ^= <<= >>=`, `++` et `--` comme
  instructions autonomes, `if` / `else`, `while`, `for`, `break`, `continue`, `return`, blocs.
  Chaque instruction se termine par `;`.
- **Fonctions :** `function name(a, b) { ... }` au premier niveau, arguments et résultat
  numériques. `return;` et la fin d’une fonction renvoient 0. La fonction accède à ses variables
  et à celles du premier niveau, sans fermeture lexicale. Toute récursion, même indirecte,
  est interdite puisque les variables occupent des emplacements fixes.
- **Non pris en charge :** nombres décimaux, objets personnels, `var`, `switch`, `do`, exceptions,
  chaînes de modèle, `null` et affectation dans une expression. Les objets représentant
  l’Electribe sont une syntaxe spéciale du compilateur, décrite plus bas.

Une erreur de compilation indique la ligne, la colonne et la correction attendue. Les diagnostics
suivent la langue choisie dans l’application. Cette langue n’étend pas le jeu de caractères de l’écran.

### Événements

| Événement | Arguments | Déclenchement |
|---|---|---|
| `ready` | | Une fois, à la première trame après le démarrage |
| `frame` | | 25 fois par seconde ; une application le reçoit uniquement lorsqu’elle est ouverte |
| `buttonPress`, `buttonRelease` | `key` | Appui ou relâchement ; comparer `key` à `korg.key.TAP`, par exemple ; voir les noms des boutons et des LED |
| `knob` | `index`, `value` | Mouvement d’un potentiomètre, valeur brute de 0 à 255 |
| `encoder` | `index`, `delta` | Rotation d’un encodeur |
| `pad` | `index`, `down`, `velocity` | Appui ou relâchement d’un pad |
| `touch` | `x`, `y`, `first` | Contact ou mouvement sur le pavé tactile ; valeurs brutes de 0 à 1023, Y vers le haut, non vérifié sur l’appareil. `first` vaut 1 à la première position d’un contact, sinon 0. `buttonPress` avec `korg.key.TOUCHPAD` ne contient pas de position ; le `touch` suivant la fournit avec `first`. Deux arguments X/Y restent compatibles avec l’API 1 ; recevoir `first` exige l’API 6 |
| `step` | `step` | Pas du séquenceur, à la double croche |
| `beat` | | Temps, à la noire |
| `play`, `stop`, `rec` | | Changement du transport |
| `patternChange` | `index` | Changement de pattern |
| `partChange` | `part` | Changement de partie |
| `mute` | `part`, `muted` | Changement de l’état muet d’une partie |
| `tempo` | `tenthsBpm` | Changement de tempo |
| `save` | | WRITE dans Global et extinction |
| `menu` | `id`, `value` | Rotation de la molette principale sur une page créée avec `korg.menu.add` |
| `open`, `close` | | Réservés aux applications et aux plugins ayant pris l’écran : ouverture depuis le menu, fermeture par EXIT ou départ de la page principale. Ils ne sont transmis qu’au plugin concerné |

À chaque trame, le point d’interception compare les états du firmware à ceux de la trame précédente :
transport, tempo, pattern, partie, pas de la partie 0 et états muets. Il met un événement en file
pour chaque changement. La résolution est donc de 40 ms. À 300 BPM, soit 20 pas par seconde,
chaque pas arrive encore. Plusieurs changements entre deux trames ne produisent qu’un changement
visible. La première lecture après activation définit l’état initial sans événement.

`step` fournit le compteur de la partie 0, de 0 à 63. `beat` arrive tous les quatre pas ; avec
BEAT 8, cela correspond à une blanche au tempo réel. `play` correspond au transport 1, `stop`
à 0 ou 2, `rec` à une transition vers 3 ou 4. `mute` arrive une fois par partie modifiée,
avec son nouvel état. Le plugin voit aussi ses propres actions : `korg.tempo` provoque `tempo`.
Un changement de pattern applique son tempo, puis déclenche `tempo`.

`save` vient de l’entrée de la fonction d’écriture des réglages. Pendant l’extinction, le moteur
continue environ une seconde ; `korg.store` n’écrit cependant plus car la fenêtre Power Off
est ouverte. [Détails des points d’interception](plugins.md#ereignisse), en allemand.

Hormis `ready` et `frame`, les événements utilisent un tampon circulaire de 64 places. S’il est
plein, le nouvel événement est perdu et compté. Deux mouvements immédiats du même potentiomètre
ne conservent que la dernière valeur. Les gestionnaires d’une trame disposent ensemble de 5 ms ;
un dépassement désactive le plugin responsable. Plus de 0,5 ms pour un gestionnaire est un
avertissement. Les autres plugins, entrées restantes et gestionnaires de trame continuent à la
trame suivante ; les événements déjà livrés ne sont pas répétés. Un gestionnaire qui n’a pas
encore commencé lorsque le temps manque est reporté sans être désactivé.

Un cycle transmet d’abord `ready` une fois par plugin, collecte les entrées en attente et transmet
`frame` en dernier. Les nouvelles entrées attendent le cycle suivant. Un nouveau plugin reçoit
`ready` après la fin du cycle précédent.

### L’Electribe sous forme d’objets

Les propriétés permettent de lire et régler l’Electribe comme des variables : `korg.tempo`,
`korg.tempo = 1280;`, `korg.parts[3].muted = 1;`. Ce ne sont pas des objets que l’on peut stocker
dans une variable. Le compilateur transforme chaque accès en appel de la table ci-dessous ;
le bytecode est identique. La compatibilité, les limites et événements sont ceux de cet appel,
y compris sur BLECHTRIBE 1.2. Comme `korg.tempo(…)`, une affectation `korg.tempo = …`
est interdite dans le corps.

| Propriété | Lecture | Écriture | Équivalent |
|---|---|---|---|
| `korg.tempo` | Tempo en dixièmes de BPM, 1280 signifie 128,0 | 100 à 3000 | `korg.read.tempo()`, `korg.tempo(x)` |
| `korg.transport` | 0 arrêté, 1 lecture, 2 pause, 3 REC armé, 4 enregistrement | Non ; utiliser `korg.play()` et `korg.stop()` | `korg.read.transport()` |
| `korg.selectedPattern` | Pattern sélectionné, 0 à 249 | Sélection d’un autre pattern | `korg.read.pattern()`, `korg.pattern(x)` |
| `korg.viewedPattern` | Pattern affiché, 0 à 249, depuis l’API 18. La molette peut consulter un autre pattern pendant que le premier continue de jouer | Non | `korg.read.viewedPattern()` |
| `korg.nextPattern` | Prochain pattern confirmé, démarrant en fin de séquence, 0 à 249 ; -1 sans attente, depuis l’API 18 | Non | `korg.read.nextPattern()` |
| `korg.selectedPart` | Partie sélectionnée, 0 à 15, 16 pour toutes | 0 à 15 | `korg.read.part()`, `korg.part(x)` |
| `korg.parts[i].step` | Compteur de pas, 0 à 63 | Non | `korg.read.step(i)` |
| `korg.parts[i].muted` | 1 si la partie est muette | 1 muette, 0 audible | `korg.read.mute(i)`, `korg.mute(i, x)` |
| `korg.knobs.LEVEL`, `korg.knobs[i]` | Dernière valeur du potentiomètre, 0 avant son premier mouvement | Non | `korg.read.knob(i)` |
| `korg.store[i]` | Valeur enregistrée de l’emplacement 0 à 15, sinon 0 | Oui, sur la carte après `korg.store.save()` | `korg.store.get(i, 0)`, `korg.store.set(i, x)` |
| `korg.led.TAP`, `korg.leds[i]` | Non | Luminosité de 0 à 255 | `korg.led(i, x)` |
| `korg.chainMode` | 1 si CHAIN MODE est activé dans Global, condition nécessaire à l’enchaînement | Non | `korg.read.chainMode()` |
| `korg.pattern.current.tempo`, aussi `korg.current.tempo`, et les valeurs décrites ci-dessous | Pattern en lecture, modifications non enregistrées comprises | Oui, via la fonction du menu Pattern ; `korg.pattern.current` depuis l’API 21, `korg.current` depuis l’API 15 | `korg.read.patternValue(-1, -1, value)`, `korg.seq.setPatternValue(value, x)` |
| `korg.patterns[i].tempo` et les valeurs ci-dessous | Pattern enregistré `i`, de 0 à 249 | Non | `korg.read.patternValue(i, -1, value)` |
| `korg.parts[i].cutoff` et les valeurs de partie ci-dessous | Partie `i`, de 0 à 15, du pattern en lecture | Oui depuis l’API 14 ; `voiceAssign` et `mfxSend` depuis 21 ; `sample`, `ifxOn`, `ifxType`, `ampEg` depuis 23 ; `lastStep` à `grooveDepth` depuis 24 | `korg.read.patternValue(-1, i, value)`, `korg.seq.setPartValue(i, value, x)` |

**Valeurs de pattern** (`korg.pattern.current.…`, `korg.current.…`, `korg.patterns[i].…`) :
`tempo` en dixièmes de BPM, `swing` de -48 à 48, `length` de 1 à 4 mesures, `beat`
(0 doubles croches, 1 triples croches, 2 triolets de croches, 3 triolets de doubles croches,
4 croches avec BLECHTRIBE), `key` de 0 C à 11 B, `scale`, `chordSet`, `level`, `mfxType`,
`chainTo` (0 à 249, -1 sans enchaînement), `chainRepeat` (au moins 1), `gateArp` (page GATE ARP,
0 désactivé), `syncGroup` (0 désactivé, 1 à 999, depuis l’API 21). Depuis l’API 24 :
`alternate1314`, `alternate1516`, `mfxHold` (1 activé), `mfxPadX`, `mfxPadY`
(position du pavé tactile en mode MFX, 0 à 127).

**Valeurs de partie** (`korg.parts[i].…`) : `sample` (emplacement), `filterType`, `cutoff`,
`resonance`, `egInt` (-63 à 63), `modType`, `modSpeed`, `modDepth`, `attack`, `decay`, `level`,
`pan` (-63 à gauche, 63 à droite), `ifxOn`, `ifxType`, `ifxEdit`, `pitch` (-63 à 63), `glide`,
`voiceAssign`, `oscEdit`, `mfxSend`, `ampEg` (1 activé, depuis l’API 23). Depuis l’API 24 :
`lastStep` (1 à 15, 0 signifie 16), `motionMode` (0 désactivé, 1 lissé, 2 maintien au déclenchement),
`padVelocity`, `scaleMode` (1 activé), `priority` (1 haute), `grooveType`, `grooveDepth`.

Les valeurs utilisent les unités de l’appareil, généralement 0 à 127. Le pattern en lecture et ses
parties sont modifiables par `korg.seq.setPatternValue` et `korg.seq.setPartValue` ; un pattern
stocké dans `korg.patterns[i]` est en lecture seule. Les détails des écritures de `sample`,
`ifxOn`, `ifxType`, `ampEg` depuis l’API 23 et des ajouts de l’API 24 sont décrits avec ces appels.
La liste et l’origine des champs sont dans `data/script/contract.mjs`, sous `PATTERN_FIELDS`
et `PART_FIELDS` ; leurs positions mesurées sont dans `data/map/pattern.mjs`. Lecture depuis l’API 8.

`+=`, `-=`, les autres affectations composées, `++` et `--` fonctionnent sur les propriétés
lisibles et modifiables. `korg.tempo += 10;` lit le tempo et ajoute 1,0 BPM. Dans ces opérations,
l’index entre crochets ne doit pas contenir d’appel de fonction. `korg.led.TAP` seul reste le
numéro de la LED, comme dans `korg.led(korg.led.TAP, 255)` ; il ne règle la LED qu’à gauche
d’une affectation.

Les potentiomètres portent les noms du panneau : `LEVEL`, `PAN`, `PITCH`, `RESONANCE`, `EG_INT`,
`MOD_DEPTH`, `ATTACK`, `IFX_EDIT`, `DECAY`, `OSC_EDIT`, `MOD_SPEED`, numérotés de 0 à 10 dans cet ordre.

```js
// À partir du pas 16 de la partie 1, rendre la partie 4 muette, à chaque mesure.
korg.onEvent("step", (step) => {
  korg.parts[3].muted = korg.parts[0].step >= 15 ? 1 : 0;
});
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) korg.tempo += 10;
  korg.led.TAP = korg.transport == 1 ? 255 : 0;
});
```

Les appels explicites restent valides et les anciens plugins fonctionnent sans modification.
Les actions restent des appels : dessiner, appuyer sur PLAY, inscrire une application ou sauvegarder.

### Arbre d’objets de l’Electribe (API 10, BLECHTRIBE 1.3.8)

Depuis l’API 10, les réglages de l’Electribe et de BLECHTRIBE sont accessibles par des chemins.
Le compilateur traduit chaque lecture ou écriture en `korg.get` ou `korg.set`, avec le numéro
de la feuille : la longueur du nom ne coûte rien sur l’appareil. Le bloc exige l’API 10
et est refusé par un ancien firmware.
Les appels directs sont `korg.get(id)` pour lire et `korg.set(id, value)` pour écrire la feuille
numérique correspondante ; la syntaxe de propriété évite de manipuler ces identifiants.

Une valeur dynamique hors plage est ramenée à la borne la plus proche et comptée dans
`korg.system.repairs` ; le plugin continue. Une valeur constante hors plage ou un chemin
inconnu provoque une erreur de compilation, qui indique les noms disponibles. Au démarrage,
les valeurs stockées invalides sont limitées ou réinitialisées à la valeur d’usine et comptées
également, quelle que soit leur origine.

| Chemin | Lecture | Écriture | Plage |
|---|---|---|---|
| `korg.menu.blech.customizations.display.intensity` | Luminosité du rétroéclairage, comme INTENSITY | Oui, immédiatement ; WRITE la conserve | 0 (éteint) à 15 (maximum) |
| `korg.system.repairs` | Nombre de valeurs corrigées depuis le démarrage | Non | 0 à 2147483647 |
| `korg.system.testMode` | Mode de test actif : écran, rétroéclairage et LED éteints, arrêt automatique suspendu | Non, uniquement par USB ; RAM seulement, désactivé au redémarrage | 0 à 1 |
| `korg.system.keepAwake()` | Appel, pas une valeur | Relance les 4 heures avant arrêt automatique comme un bouton physique | |
| `korg.menu.blech.customizations.display.red` | Rouge du rétroéclairage ; BACKLIGHT HUE, SAT, BRIGHT affichent teinte, saturation, luminosité ; les trois canaux à 0 signifient blanc d’origine | Oui, comme la page | 0 à 15 |
| `korg.menu.blech.customizations.display.green` | Vert du rétroéclairage | Oui, comme la page | 0 à 15 |
| `korg.menu.blech.customizations.display.blue` | Bleu du rétroéclairage | Oui, comme la page | 0 à 15 |
| `korg.menu.blech.customizations.display.invert` | Inversion de l’écran, comme DISPLAY INVERT | Oui, comme la page | 0 à 1 |
| `korg.menu.blech.customizations.led.mode` | LED inférieures : 0 vu-mètre, 1 couleur fixe, 2 éteintes, comme BOTTOM LEDS | Oui, comme la page | 0 à 2 |
| `korg.menu.blech.customizations.led.red` | Rouge des LED inférieures, pages LED HUE, SAT, BRIGHT ; les trois canaux à 0 signifient couleurs d’origine | Oui, comme la page | 0 à 15 |
| `korg.menu.blech.customizations.led.green` | Vert des LED inférieures | Oui, comme la page | 0 à 15 |
| `korg.menu.blech.customizations.led.blue` | Bleu des LED inférieures | Oui, comme la page | 0 à 15 |
| `korg.menu.blech.customizations.led.meter.still` | METER STILL : 0 origine ; 1 à 7 blanc, rouge, vert, bleu, jaune, cyan, rose ; 8 arc-en-ciel ; 9 éteint | Oui, comme la page | 0 à 9 |
| `korg.menu.blech.customizations.led.meter.low` | METER LOW : 0 origine, 1 à 7 comme ci-dessus | Oui, comme la page | 0 à 7 |
| `korg.menu.blech.customizations.led.meter.mid` | METER MID : 0 origine, 1 à 7 comme ci-dessus | Oui, comme la page | 0 à 7 |
| `korg.menu.blech.customizations.led.meter.loud` | METER LOUD : 0 origine, 1 à 7 comme ci-dessus, 8 arc-en-ciel | Oui, comme la page | 0 à 8 |
| `korg.menu.blech.customizations.padColor.part` | PAD COLOR : 0 rouge, 1 bleu, 2 rose ; toujours différent de SELECT COLOR ; une égalité permute les deux | Oui, comme la page | 0 à 2 |
| `korg.menu.blech.customizations.padColor.select` | SELECT COLOR : mêmes couleurs et règle que PAD COLOR | Oui, comme la page | 0 à 2 |
| `korg.menu.blech.customizations.padColor.overlap` | OVERLAP, couleur d’un pad allumé et sélectionné : 0 couleur restante, 1 rouge, 2 bleu, 3 rose | Oui, comme la page | 0 à 3 |
| `korg.menu.blech.customizations.powerSave.displayLight` | DISPLAY LIGHT en économie d’énergie : 0 atténuation du firmware, 1 à 15 intensité choisie | Oui, comme la page | 0 à 15 |
| `korg.menu.blech.customizations.powerSave.ledDimming` | LED DIMMING, indice des atténuations 0, 10, 20, 30, 40, 50, 60, 70, 75, 80, 90, 100 % | Oui, comme la page | 0 à 11 |
| `korg.menu.blech.features.mfx2` | MFX 2 activé ; effet au démarrage suivant, indiqué sur la page | Oui | 0 à 1 |
| `korg.menu.blech.features.patternConfirm` | PATTERN CONFIRM, changement soumis à une seconde pression | Oui, comme la page | 0 à 1 |
| `korg.menu.blech.features.tapMotion` | TAP MOTION : 0 désactivé, 1 activé, 2 une fois | Oui, comme la page | 0 à 2 |
| `korg.menu.blech.features.noteAssist` | NOTE ASSIST, pads indiquant les notes adaptées | Oui, comme la page | 0 à 1 |
| `korg.menu.blech.features.lastPattern` | LAST PATTERN, retrouver le dernier pattern à l’allumage | Oui, comme la page | 0 à 1 |
| `korg.menu.blech.features.stereo1Pad` | STEREO 1 PAD, un sample stéréo occupe seulement son pad | Oui, comme la page | 0 à 1 |
| `korg.menu.blech.features.initPattern` | SET INIT PATTERN, modèle copié par INITIALIZE PATTERN ; 0 modèle du firmware | Oui, comme la page | 0 à 250 |
| `korg.menu.blech.write()` | Appel, pas une valeur | Demande l’enregistrement des réglages BLECH sur la carte, comme WRITE ; voir ci-dessous | |
| `korg.global.triggerMode` | GLOBAL PARAMETERS > TRIGGER MODE : 0 Normal, 1 Seq 1st, 2 Seq Play | Oui, par la fonction du menu | 0 à 2 |
| `korg.global.velocityCurve` | VELOCITY CURVE : 0 Heavy, 1 Normal, 2 Light, 3 Const96 | Oui, par la fonction du menu | 0 à 3 |
| `korg.global.clockMode` | CLOCK MODE : 0 Internal, 1 Auto, 2 External USB, 3 External MIDI, 4 External Sync | Oui, par la fonction du menu | 0 à 4 |
| `korg.global.midiChannel` | GLOBAL MIDI CH. : 0 à 15 pour les canaux 1 à 16 | Oui, par la fonction du menu | 0 à 15 |
| `korg.global.receiveFilter` | MIDI RECEIVE FILTER : 0 Off, 1 Short, 2 Short + Program | Oui, par la fonction du menu | 0 à 2 |
| `korg.global.sendFilter` | MIDI SEND FILTER : mêmes valeurs | Oui, par la fonction du menu | 0 à 2 |
| `korg.global.syncPolarity` | SYNC POLARITY : 0 Hi, 1 Lo | Oui, par la fonction du menu | 0 à 1 |
| `korg.global.syncResolution` | SYNC UNIT : 0 1 Step, 1 2 Steps | Oui, par la fonction du menu | 0 à 1 |
| `korg.global.metronome` | METRONOME : 0 Off, 1 Rec 0, 2 Rec 1, 3 Rec 2, 4 On | Oui, par la fonction du menu | 0 à 4 |
| `korg.global.tempoLock` | TEMPO LOCK : 0 Off, 1 On | Oui, par la fonction du menu | 0 à 1 |
| `korg.global.knobMode` | KNOB MODE : 0 Jump, 1 Catch, 2 Value Scale | Oui, par la fonction du menu | 0 à 2 |
| `korg.global.touchScaleRange` | TOUCH SCALE RANGE : nombre d’octaves ; 0 joue la fondamentale seule | Oui, par la fonction du menu | 0 à 4 |
| `korg.global.lcdContrast` | LCD CONTRAST : 18 à 42, affichés comme 1 à 25 | Oui, par la fonction du menu | 18 à 42 |
| `korg.global.audioInThru` | AUDIO IN THRU : 0 Off, 1 On | Oui, par la fonction du menu | 0 à 1 |
| `korg.global.batteryType` | BATTERY TYPE : 0 Ni-MH, 1 Alkali | Oui, par la fonction du menu | 0 à 1 |
| `korg.global.autoPowerOff` | AUTO POWER OFF : 0 Disable, 1 4 hours | Oui, par la fonction du menu | 0 à 1 |
| `korg.global.powerSave` | POWER SAVE MODE : 0 Disable, 1 Auto, 2 Enable | Oui, par la fonction du menu | 0 à 2 |
| `korg.global.patternChangeLock` | PTN. CHANGE LOCK : 0 Off, 1 On | Oui, par la fonction du menu | 0 à 1 |
| `korg.global.chainMode` | CHAIN MODE : 0 Off, 1 On | Oui, par la fonction du menu | 0 à 1 |

```js
// Éclairage éteint dans l’application, puis restauré à la fermeture.
let light = 15;
korg.app("Dark", "TOOLS");
korg.onEvent("open", () => {
  light = korg.menu.blech.customizations.display.intensity;
  korg.menu.blech.customizations.display.intensity = 0;
});
korg.onEvent("close", () => {
  korg.menu.blech.customizations.display.intensity = light;
});
```

**Pages de BLECHTRIBE, API 17.** Toutes les pages de CUSTOMIZATION et FEATURES ont une feuille,
ainsi que SET INIT PATTERN dans DATA UTILITY. Une telle feuille exige l’API 17. L’écriture
appelle la fonction d’application de la page : réglages d’apparence pour l’écran, le rétroéclairage
et les LED ; patch des couleurs de pads pour PAD COLOR, SELECT COLOR, OVERLAP et LED DIMMING ;
mot lu par le patch pour PATTERN CONFIRM, TAP MOTION et NOTE ASSIST. La page affiche ensuite
la nouvelle valeur.

Les pages présentent teinte, saturation et luminosité, mais les valeurs stockées et les feuilles
restent rouge, vert et bleu de 0 à 15. Un mot jamais écrit par un patch, comme LAST PATTERN
ou STEREO 1 PAD, se lit comme la valeur d’usine. Les actions SPLASH IMPORT, DRAW, RESET,
les exports, PLUGIN RUNTIME et SYNC GROUP ne sont pas des feuilles : SYNC GROUP appartient
au pattern, et désactiver son propre moteur empêcherait les plugins au prochain démarrage.

**RAM jusqu’à WRITE.** Les réglages agissent immédiatement mais restent en RAM jusqu’à WRITE
sur une page BLECH, qui écrit `settings.a.bin` ou `settings.b.bin`. Le redémarrage retrouve
la dernière sauvegarde. Avec AUTO SAVE, quitter BLECH écrit aussi le fichier si les réglages
ont changé depuis son ouverture. Exception : SET INIT PATTERN est stocké dans les paramètres
Global du firmware, enregistrés à l’extinction.

`korg.menu.blech.write()` demande une sauvegarde, réalisée un peu plus tard, uniquement sur
la page principale ou dans BLECH, au moins 2 secondes après l’écriture précédente. Plusieurs
appels durant l’attente constituent une seule demande. Sans carte ou en cas d’erreur,
aucune autre action n’est réalisée, comme avec WRITE. Réserve l’appel aux valeurs que
l’utilisateur souhaite conserver.

```js
// Inverser l’écran à l’ouverture et conserver le réglage.
korg.app("Invert", "TOOLS");
korg.onEvent("open", () => {
  korg.menu.blech.customizations.display.invert = 1 - korg.menu.blech.customizations.display.invert;
  korg.menu.blech.write();
});
```

Le mode de test donne l’impression d’un appareil éteint alors qu’il tourne : écran et éclairage
éteints, toutes les LED à 0 même si le firmware, Blechy ou un plugin les règle, et arrêt
automatique suspendu. Les commandes fonctionnent et l’image reste lisible par USB. Seul
l’ordinateur active ce mode par USB ; un plugin lit seulement `korg.system.testMode` pour
éviter de laisser l’appareil sombre à chaque démarrage. À la sortie, éclairage et LED
retrouvent leur état normal, y compris les dernières valeurs données par un plugin.
Voir le [mode de test](test-modus.md), en allemand.

**Paramètres Global, `korg.global`, API 20.** Chaque page connue de GLOBAL PARAMETERS
possède une feuille en camelCase, avec les valeurs stockées par le firmware :
`korg.global.midiChannel` de 0 à 15 représente les canaux 1 à 16. Les bornes sont celles
du menu. Les marqueurs de début et de fin, octets inchangés par les menus et emplacements
247 à 249 utilisés par BLECHTRIBE sont exclus. Nommer une feuille exige l’API 20.

L’écriture appelle la même fonction que la rotation sur la page correspondante : octet,
moteur audio, affichage et MIDI sont mis à jour ; `tempoLock` réapplique ensuite le tempo.
L’effet est immédiat sans redémarrage, et la page reflète la valeur à sa prochaine ouverture.
Comme dans le menu, `clockMode` refuse une écriture si le transport est dans les états 6 à 9.
Une valeur hors plage est limitée et comptée ; une valeur stockée invalide est réparée au
démarrage à la borne la plus proche, sans appeler la fonction du firmware. Mesuré dans
l’émulateur sur Hacktribe, Korg rouge et bleu, pas sur l’appareil :
[mesure API 20](messungen/2026-11-05-plugin-api20-globals.md).

**Sauvegarde des Global.** Aucun appel spécifique. Le firmware les enregistre à l’extinction
et avec WRITE dans GLOBAL PARAMETERS, comme le dernier pattern. Avec BLECH > FEATURES >
AUTO SAVE, quitter GLOBAL PARAMETERS les enregistre aussi s’ils diffèrent de l’état sauvegardé
([mesure](messungen/2026-11-09-auto-save.md)). Une valeur modifiée par un plugin peut donc
survivre à son arrêt ou sa suppression. Pour un effet temporaire, rétablis la valeur initiale
comme dans l’exemple de luminosité.

**Autorisation.** Une écriture Global n’exige pas d’autorisation supplémentaire. Un plugin
externe, sans bit « probed », nécessite déjà WRITE=ALLOW ; cette autorisation lui permet aussi
de modifier durablement ces réglages.

```js
// Métronome activé et contraste augmenté d’un cran, puis valeurs restaurées.
let metro = 0;
let contrast = 0;
korg.app("Metronome", "TOOLS");
korg.onEvent("open", () => {
  metro = korg.global.metronome;
  contrast = korg.global.lcdContrast;
  korg.global.metronome = 4;
  korg.global.lcdContrast = contrast + 1;
});
korg.onEvent("close", () => {
  korg.global.metronome = metro;
  korg.global.lcdContrast = contrast;
});
```

`korg.pattern.current` désigne le pattern en lecture dans l’arbre ; `korg.current` reste un
synonyme des mêmes valeurs.

### Temporisateurs (API 11, BLECHTRIBE 1.3.8)

Un plugin ne peut pas attendre : les gestionnaires partagent 5 ms par trame et un `wait(ms)`
bloquerait l’appareil. Un temporisateur confie une fonction au moteur, qui l’appelle plus tard.

| Appel | Effet |
|---|---|
| `korg.after(ms, fn)` | Appelle `fn` une fois dès que `ms` millisecondes se sont écoulées, de 0 à 86400000 |
| `korg.every(ms, fn)` | Appelle `fn` toutes les `ms` millisecondes, de 1 à 86400000, jusqu’à `korg.cancel` |
| `korg.afterSteps(n, fn)` | Appelle `fn` une fois après `n` pas supplémentaires du séquenceur, doubles croches, de 1 à 65535 |
| `korg.cancel(number)` | Annule le temporisateur portant ce numéro |

`fn` est une fonction sans paramètres ou une flèche `() => { ... }`. Elle ne voit que les variables
globales, pas les variables locales de l’endroit qui crée le temporisateur. Les trois créations
renvoient un numéro utilisable par `korg.cancel`. Chaque plugin possède 8 places ; si elles sont
pleines, l’appel renvoie -1 sans autre effet. Un temporisateur ponctuel libère sa place après
exécution. Un ancien numéro ne supprime jamais le temporisateur qui a réutilisé sa place.
`korg.cancel(-1)` ne fait rien : le résultat d’un appel refusé peut être transmis sans risque.

Les temporisateurs sont examinés au début de chaque trame de 40 ms. L’appel survient au plus
tôt après `ms`, au plus tard une trame après : `korg.after(1000, fn)` arrive entre 1000 et 1040 ms.
`korg.every` conserve sa grille ; une trame tardive ne décale pas l’échéance suivante. Relancer
`korg.after` depuis `fn` repart au contraire de la trame courante et peut dériver de 40 ms par tour.
Ils fonctionnent même si l’application est fermée et ne concernent que leur plugin. Ils sont
autorisés partout, y compris dans le corps, sauf dans `save`.

`korg.afterSteps` compte les événements `step` : STOP suspend le compteur, PLAY le reprend,
le tempo reste suivi. Le rappel arrive dans la trame du `step` déclencheur, juste après celui-ci.
Deux pas dans une trame très rapide ne comptent que pour un ; à 300 BPM, les pas sont espacés
de 50 ms et les trames de 40 ms.

```js
// LED TAP toutes les 500 ms ; message à l’écran après 2 secondes.
let on = 0;
function blink() {
  on = 1 - on;
  korg.led(korg.led.TAP, on * 255);
}
korg.onEvent("ready", () => {
  korg.every(500, blink);
  korg.after(2000, () => { korg.display.take(); korg.display.text("HELLO", 0, 0); });
});
```

```js
// Rendre la partie 1 muette 16 pas après PLAY ; STOP avant cela annule.
let timer = -1;
korg.onEvent("play", () => { timer = korg.afterSteps(16, () => { korg.mute(0, 1); }); });
korg.onEvent("stop", () => { korg.cancel(timer); });
```

Les temporisateurs et `korg.millis()` utilisent Timer3 à 150 MHz, qui boucle chaque seconde.
Le moteur actualise son temps à chaque trame ; les secondes entières perdues entre deux appels,
notamment avant la première trame, proviennent du compteur système à la milliseconde.
Mesuré dans l’émulateur : trames toutes les 40 ms, au plus 46 ms, y compris lors d’un changement
de pattern. Le chargement des samples précède la première trame et le démarrage des plugins de
la carte ; un temporisateur du corps arrive donc à temps. Non vérifié sur l’appareil.
[Mesure des temporisateurs](messungen/2026-10-29-plugin-timer.md).

### Fonctions de l’Electribe

Les noms commencent par `korg.`. Un argument numérique hors plage termine le plugin avec
une erreur. « Comme `korg.led` » signifie : dans tous les événements, sauf le corps et `save`.
La colonne d’autorisation s’applique aussi à la syntaxe de propriété équivalente.

| Appel | Effet | Autorisation |
|---|---|---|
| `korg.led(index, level)` | Met une commande de LED en file : index 0 à 87, de préférence `korg.led.TAP` ou une autre constante ; niveau 0 à 255 | Tous les événements sauf corps et `save` |
| `korg.millis()` | Millisecondes depuis le premier appel, depuis Timer3 à 150 MHz bouclant tous les 150 millions de cycles ; les secondes entières entre appels proviennent du compteur système | Partout |
| `korg.after(ms, fn)`, `korg.every(ms, fn)`, `korg.afterSteps(n, fn)`, `korg.cancel(number)` | Temporisateurs décrits ci-dessus, depuis l’API 11 | Partout sauf `save` |
| `korg.app(name, group)` | Inscrit l’application : nom de 1 à 15 caractères, groupe `"GAMES"` ou `"TOOLS"`. Renvoie son numéro, ou -1 si les 8 places sont occupées. Une instruction autonome au premier niveau, une fois par plugin, vérifiée par le compilateur | Corps uniquement |
| `korg.file.frame(array, file, index)` | Lit l’image `index`, 0 à 65535, de `KORG/blechtribe/Gif/GIFnn.E2G`, avec `file` de 0 à 99 pour nn. Un octet par élément du tableau, d’au moins 1024 éléments ; `korg.display.bitmap(array, 0, 0, 128)` l’affiche directement. Renvoie le délai en ms, au moins 1 ; 0 après la dernière image ; -1 sans fichier, fichier invalide ou tronqué, ou hors de la page principale. Après -1, le dernier quart du tableau peut avoir changé. Depuis l’API 7 | Comme `korg.led` |
| `korg.display.take()` | Demande l’écran hors application ; renvoie 1 si obtenu, 0 si application, autre propriétaire ou hors page principale | Comme `korg.led` |
| `korg.display.release()` | Rend l’écran au firmware | Comme `korg.led` |
| `korg.display.popups = 0` | Supprime la fenêtre de paramètre ouverte par `korg.seq.setPartValue`, pour les appels de ce plugin uniquement ; 1 la réactive, valeur initiale après chargement. Appel équivalent : `korg.display.popups(on)`. `korg.knob` conserve la fenêtre car il simule le potentiomètre. Lecture par `korg.display.popups` ou `korg.read.popups()`. Depuis l’API 24 | Comme `korg.led` |
| `korg.display.clear()` | Efface l’écran ; seuls les dessins du propriétaire, application ouverte ou plugin ayant pris l’écran, agissent | Comme `korg.led` |
| `korg.display.text(text, x, y)` | Texte dont le coin supérieur gauche est à X de 0 à 127, Y de 0 à 63 | Comme `korg.led` |
| `korg.display.number(value, x, y)` | Affiche un nombre | Comme `korg.led` |
| `korg.display.pixel(x, y, on)` | Règle un pixel ; `on` vaut 0 ou 1 | Comme `korg.led` |
| `korg.display.textNumber(text, value, x, y)` | Texte suivi directement d’un nombre, sans compter les chiffres ; 6 pixels par caractère. Équivalent à `text` puis `number`. Depuis l’API 6 | Comme `korg.led` |
| `korg.display.bitmap(array, x, y, width)` | Image issue d’un tableau global, X de -128 à 127, Y de -64 à 63 ; les débordements sont coupés. Format et coût ci-dessous. Depuis l’API 6 | Comme `korg.led` |
| `korg.display.rect(x, y, width, height)` | Rectangle plein | Comme `korg.led` |
| `korg.display.clearRect(x, y, width, height)` | Efface un rectangle | Comme `korg.led` |
| `korg.store.get(slot, default)` | Valeur enregistrée de l’emplacement 0 à 15 du plugin, ou `default` s’il n’a jamais été enregistré | Partout, corps compris |
| `korg.store.set(slot, value)` | Modifie la valeur en RAM, sans écrire immédiatement sur la carte | Partout |
| `korg.store.save()` | Met une sauvegarde en attente | Comme `korg.led` |
| `korg.read.transport()` | 0 arrêté, 1 lecture, 2 pause, 3 REC armé, 4 enregistrement | Partout |
| `korg.read.tempo()` | Dixièmes de BPM ; 1600 signifie 160,0 | Partout |
| `korg.read.pattern()` | Pattern sélectionné, de 0 à 249 | Partout |
| `korg.read.viewedPattern()` | Pattern affiché, de 0 à 249 : celui consulté dans la banque pendant la navigation et après MENU, sinon celui en lecture. Correspond aux pads et à la ligne d’informations. Depuis l’API 18 | Partout |
| `korg.read.nextPattern()` | Prochain pattern confirmé en attente de fin de séquence, de 0 à 249, sinon -1. `VIEW:` seul ne compte pas, MENU donnant `NEXT:` compte. Reste -1 si PATTERN CONFIRM est désactivé ou EXIT maintenu au démarrage. Depuis l’API 18 | Partout |
| `korg.read.part()` | Partie sélectionnée, de 0 à 15, ou 16 pour toutes | Partout |
| `korg.read.step(part)` | Compteur de pas de la partie, de 0 à 63 | Partout |
| `korg.read.mute(part)` | 1 si la partie est muette | Partout |
| `korg.read.knob(index)` | Dernière valeur brute observée du potentiomètre 0 à 19, sinon 0 | Partout |
| `korg.read.chainMode()` | 1 si CHAIN MODE est activé dans Global. Depuis l’API 8 | Partout |
| `korg.read.patternValue(pattern, part, value)` | `pattern` : -1 en lecture, 0 à 249 stocké ; `part` : -1 pour le pattern, 0 à 15 pour une partie ; `value` : numéro dans `PATTERN_FIELDS` ou `PART_FIELDS`. Les noms, comme `korg.current.tempo`, sont plus lisibles. Depuis l’API 8 | Partout |
| `korg.play()` | Appuie puis relâche PLAY par le chemin normal du firmware | Comme `korg.led` |
| `korg.stop()` | Appuie puis relâche STOP | Comme `korg.led` |
| `korg.pattern(index)` | Sélectionne un pattern, de 0 à 249 | Comme `korg.led` |
| `korg.tempo(tenthsBpm)` | Règle le tempo, de 100 à 3000 | Comme `korg.led` |
| `korg.part(part)` | Sélectionne une partie, de 0 à 15 | Comme `korg.led` |
| `korg.mute(part, muted)` | 1 rend la partie muette, 0 la rend audible. Le firmware ne connaissant que la bascule, le moteur ne presse le pad que si l’état doit changer | Comme `korg.led` |
| `korg.backlight(red, green, blue)` | Active ou désactive chaque canal du rétroéclairage avec 1 ou 0 par les GPIO du firmware. Sur piles avec Power Save Auto, l’atténuation du firmware peut réécrire la couleur. Une couleur du menu avec des niveaux de 1 à 14 est également réappliquée par son PWM | Comme `korg.led` |
| `korg.menu.add(name, min, max, value)` | Crée une page BLECH, renvoie son numéro ou -1 si les 12 places sont pleines. Nom de 15 caractères maximum, valeur limitée à min/max et magnitude inférieure à 100 millions ; la page affiche aussi le nom du plugin. La molette déclenche `menu`(numéro, valeur). Même nom et même plugin désignent la même page. min supérieur à max est une erreur d’argument | Corps et `ready` uniquement |
| `korg.ledHold(on)` | 1 empêche le firmware de réécrire les LED du panneau : pads, boutons et RGB inférieures montrent les valeurs du plugin. 0 les rend au firmware et force leur réémission. Si le dernier plugin actif échoue, le moteur les rend lui-même | Comme `korg.led` |
| `korg.padHold(on)` | 1 retient les appuis de pads : ni son ni modification de pas pour le firmware, mais événement `pad` pour le plugin. 0 retire la retenue de ce plugin ; les pads ne reviennent au firmware que lorsqu’aucun plugin actif ne les retient. Une fermeture d’application libère aussi cette retenue. Un plugin arrêté ne retient rien. Le relâchement suit toujours le sort de l’appui. Depuis l’API 12 | Comme `korg.led` |
| `korg.knobHold(index, on)` | 1 retient le potentiomètre 0 à 10, OSC EDIT est 9 ; le paramètre du firmware ne change plus, mais `knob` conserve la valeur brute. 0 retire la retenue du plugin ; la retenue d’un autre reste active. L’arrêt du plugin libère la retenue, pas la fermeture de son application : le filtre peut fonctionner sans écran. Agit hors BLECH. Depuis l’API 13 | Comme `korg.led` |
| `korg.passKeys(key, on)` | Pour une application ouverte, 1 laisse atteindre le firmware au bouton 0 à 33, par exemple `korg.key.PART_MUTE` ; 0 le bloque, y compris REC, STOP et PLAY, normalement transmis par défaut. Le plugin reçoit toujours `buttonPress` et `buttonRelease`. Le relâchement suit l’appui. EXIT ferme toujours l’application. La fermeture rétablit les valeurs par défaut. Depuis l’API 14 | Comme `korg.led` |
| `korg.touchLockX(x)` | Fige X reçu par le firmware à 0 à 127 ; Y reste celui du doigt. -1 libère. Master FX et Touch Scale arrondissent X à l’entier pair inférieur, donc 127 devient 126 ; Gate Arp utilise la valeur exacte. Un X brut r donne `x = r >> 3`. Le plugin reçoit le vrai X dans `touch`. Effet au prochain message tactile, hors BLECH ; libération à l’arrêt du plugin. Mesuré dans l’émulateur sur Hacktribe, rouge et bleu, dans les trois modes ; pas sur l’appareil. Depuis l’API 15 | Comme `korg.led` |
| `korg.keyHold(key, on)` | 1 bloque le bouton 0 à 33 pour le firmware même sans application ouverte, en conservant les événements du plugin. 0 libère seulement sa propre retenue ; les autres plugins peuvent maintenir la leur. Le relâchement suit l’appui. Retenir EXIT termine le plugin avec une erreur pour garder les applications fermables. Depuis l’API 19, modifie un bit du masque propre au plugin, `korg.keyMask`. Agit hors BLECH. Mesuré dans l’émulateur sur les trois firmwares, pas sur l’appareil. Depuis l’API 15 | Comme `korg.led` |
| `korg.pressKey(key)` | Courte pression du bouton 0 à 33 : appui dans la file du panneau immédiatement, relâchement à la trame suivante. Un marqueur contourne réaffectation, `korg.keyHold`, application et plugins ; aucun plugin ne reçoit `buttonPress`. Une seconde pression avant le relâchement ou une file pleine perd la demande. EXIT ferme d’abord l’application, puis atteint le firmware. PLAY et STOP vérifiés dans l’émulateur sur les trois firmwares ; pas sur l’appareil. Depuis l’API 15 | Comme `korg.led` |
| `korg.keyMask(low, high)` | Remplace le masque propre au plugin : bit n de low pour le bouton n, 0 à 31, par exemple `1 << korg.key.PLAY` ; bit n de high pour 32+n, high de 0 à 3. Retient les boutons définis, libère les autres sans modifier les autres plugins. Les événements continuent. EXIT dans le masque termine le plugin avec une erreur. Conflits détaillés ci-dessous. Mesuré dans l’émulateur sur les trois firmwares, pas sur l’appareil. Depuis l’API 19 | Comme `korg.led` |
| `korg.keyDown(key)` | Presse le bouton 0 à 33 jusqu’à `korg.keyUp`, permettant appui long et combinaison SHIFT. Le message normal du panneau contourne réaffectation, `korg.keyHold`, `korg.passKeys`, application, raccourcis de BLECHTRIBE et plugins ; aucun `buttonPress` propre. Une seconde demande du même bouton n’envoie rien. EXIT ferme d’abord l’application, puis atteint le firmware. Voir la section sur les gestes physiques. Mesuré dans l’émulateur sur les trois firmwares, pas sur l’appareil. Depuis l’API 25 | Comme `korg.led` |
| `korg.keyUp(key)` | Relâche le bouton pressé par `korg.keyDown` ; ne fait rien si ce plugin ne le maintient pas | Depuis l’API 25, comme `korg.led` |
| `korg.padDown(pad, velocity)` | Presse le pad 0 à 15 avec une vélocité de 1 à 127 jusqu’à `korg.padUp`. TRIGGER joue et sélectionne la partie, SEQUENCER bascule le pas, KEYBOARD et CHORD jouent des notes, PART MUTE maintenu bascule l’état muet. `korg.padHold` ne le bloque pas ; le plugin ne reçoit pas son propre `pad`. Mesuré dans l’émulateur sur les trois firmwares, pas sur l’appareil. Depuis l’API 25 | Comme `korg.led` |
| `korg.padUp(pad)` | Relâche le pad pressé par `korg.padDown` | Depuis l’API 25, comme `korg.led` |
| `korg.encoder(index, delta)` | Tourne l’encodeur 0 VALUE, 1 SAMPLE/OSC, 2 CUTOFF, 3 MOD TYPE ou 4 IFX TYPE de -127 à 127 crans, négatif vers la gauche ; 0 n’envoie rien. Le message normal du panneau avec SHIFT maintenu par `korg.keyDown(korg.key.SHIFT)` agit comme SHIFT et rotation. Mesuré dans l’émulateur sur les trois firmwares, pas sur l’appareil. Depuis l’API 25 | Comme `korg.led` |
| `korg.touch(x, y)` | Pose un doigt sur le pavé, valeurs brutes de 0 à 1023. Le premier appel presse TOUCHPAD et transmet la position ; les suivants déplacent le doigt ; X à -1 le lève. Aucun événement `touch` propre et aucun effet de `korg.touchLockX` sur ce doigt. Mesuré dans l’émulateur sur Hacktribe, rouge et bleu, en Master FX et Touch Scale ; pas sur l’appareil. Depuis l’API 25 | Comme `korg.led` |
| `korg.knob(index, value)` | Transmet une valeur de 0 à 255 au potentiomètre 0 à 10 par son gestionnaire normal. Associé à `korg.knobHold`, permet de filtrer un potentiomètre instable. `korg.read.knob` conserve la valeur physique. Pattern, écran, LED et MIDI comparés au message physique dans l’émulateur sur les trois firmwares ; pas sur l’appareil. Depuis l’API 13 | Comme `korg.led` |
| `korg.remapKey(from, to)` | Réaffecte un bouton vers un autre, 0 à 33, par exemple `korg.key.PART_ERASE`, avant lecture par le firmware et les plugins. Le firmware réagit comme à la cible. Une seule réaffectation globale, la dernière l’emporte ; from égal à to l’annule. EXIT ne peut pas être réaffecté. Depuis l’API 8 | Corps et `ready` uniquement |

Les commandes du séquenceur utilisent les mêmes règles d’autorisation : « Comme `korg.led` »
exclut le corps et `save`.

| Appel | Effet | Autorisation |
|---|---|---|
| `korg.seq.setStep(part, step, note, velocity)` | Écrit le pas 0 à 63 de la partie 0 à 15 du pattern en lecture. Note de 0 à 127 et vélocité de 1 à 127 activent le pas avec cette note au premier emplacement, les trois autres étant vidés. Note -1 ou vélocité 0 le désactivent. La gate est conservée. Le déclenchement est actif, sauf depuis l’API 22 si le pas précédent est actif et lié par une gate supérieure à 96 : une chaîne liée de même note joue alors une seule note au lieu de réattaquer à chaque pas. Régler d’abord la gate du pas précédent. [Mesure](messungen/2026-11-06-step-trigger.md). Depuis l’API 9 | Comme `korg.led` |
| `korg.seq.setGate(part, step, gate)` | Gate de 0 à 127 ; 96 couvre un pas entier, toute valeur supérieure lie à la note suivante. Le firmware traite également 127 et le 255 présent dans certains patterns comme TIE. Depuis l’API 9 | Comme `korg.led` |
| `korg.seq.clearPart(part)` | Désactive les 64 pas, sans effacer notes, gates ni vélocités. Depuis l’API 9 | Comme `korg.led` |
| `korg.seq.getOn(part, step)` | Lit l’octet d’activation du pas 0 à 63 de la partie 0 à 15 du pattern en lecture : 1 actif, 0 inactif. Lecture seule, sans redessiner les pads. [Mesuré dans l’émulateur](messungen/2026-11-06-plugin-api22-step-getters.md) sur Hacktribe, rouge et bleu. Depuis l’API 22 | Partout |
| `korg.seq.getGate(part, step)` | Lit l’octet brut : 0 à 96 pour la durée. L’édition du firmware écrit 127 pour TIE et l’écran affiche TIE pour toute valeur supérieure à 96. Un 255 stocké est renvoyé tel quel ; le séquenceur le joue comme 127, mesuré dans l’émulateur sur Hacktribe. Depuis l’API 22 | Partout |
| `korg.seq.getNote(part, step, slot)` | Note MIDI de l’emplacement 0 à 3 ; -1 si vide. Le pattern stocke note+1 et 0 pour vide. Depuis l’API 22 | Partout |
| `korg.seq.getVelocity(part, step)` | Lit l’octet brut de vélocité du pas. Depuis l’API 22 | Partout |
| `korg.seq.setPartValue(part, value, x)` | Règle un champ de `PART_FIELDS` dans une partie, valeur limitée à sa plage, par les fonctions du firmware ; détails ci-dessous. Syntaxe lisible : `korg.parts[i].cutoff = x`. Depuis l’API 14 | Comme `korg.led` |
| `korg.seq.setPatternValue(value, x)` | Règle un champ de `PATTERN_FIELDS` du pattern en lecture, comme `korg.read.patternValue` avec partie -1 ; valeur limitée à sa plage et fonction du menu Pattern. Détails ci-dessous. Depuis l’API 15 | Comme `korg.led` |
| `korg.read.patternBytes(array, pattern, offset)` | Copie les octets d’un pattern dans un tableau, un octet par élément. Pattern -1 pour la RAM, 0 à 249 pour la banque ; offset de 0 à 16383 dans un bloc de 16384 octets. Lit jusqu’à la limite du tableau ou du bloc et renvoie le nombre d’octets. Dans `data/map/pattern.mjs`, la partie p commence à 2048 + 816 × p et son pas s à 48 + 12 × s dans la partie. Depuis l’API 14 | Partout |
| `korg.seq.writeSteps(array, part, first)` | Écrit des pas entiers à partir du pas first, 0 à 63, dans la partie du pattern en lecture. 12 éléments par pas : activation, gate, vélocité, déclenchement, quatre notes et quatre octets laissés intacts. S’arrête à la fin du tableau ou au pas 63. Limite activation/déclenchement à 0 ou 1, gate à 0 à 127, vélocité à 1 à 127, notes à 0 à 128. L’activation est écrite en dernier. Renvoie le nombre de pas. Depuis l’API 14 | Comme `korg.led` |

**Écriture des paramètres de partie.** `korg.seq.setPartValue` appelle les fonctions qu’utilisent
les potentiomètres : le pattern en RAM et le son changent comme lors d’une rotation. Pour la
partie sélectionnée, la fenêtre de paramètre apparaît. Depuis l’API 21, `voiceAssign` et `mfxSend`
passent par les fonctions du menu VOICE ASSIGN et du bouton MFX SEND : pattern et copie du
moteur audio sont mis à jour sur les trois firmwares, sans fenêtre de paramètre.

Depuis l’API 23, `ifxOn` et `ampEg` empruntent les chemins d’IFX ON et AMP EG : pattern,
copie audio et LED correspondent au bouton physique ; `mfxSend` règle aussi sa LED.
La LED ne s’allume que pour la partie sélectionnée, comme avec le bouton.
[Mesure API 23](messungen/2026-11-07-plugin-api23-part-writes.md), dans l’émulateur sur les trois firmwares.

Depuis l’API 24, l’appel envoie le même CC MIDI que le potentiomètre, l’encodeur CUTOFF
ou le bouton IFX ON/MFX SEND, sur le canal de la partie. `ifxType` passe par l’édition de partie
comme l’encodeur IFX, avec la même fenêtre ; il s’arrête au dernier numéro du firmware
au lieu de reboucler : 58 sur Hacktribe, 47 sur rouge, 37 sur bleu avec BLECHTRIBE. Cette borne est
lue à l’exécution : un catalogue étendu peut l’augmenter.

`sample` transmet le numéro entier, de 0 à 999, par l’édition de partie comme SAMPLE,
mais seulement pour un emplacement où le potentiomètre s’arrête ; un emplacement vide n’est
pas écrit. Le modèle bleu n’a pas de samples : `sample` n’y écrit rien.

Chaque valeur atteint aussi le moteur audio comme sa commande physique : les potentiomètres
et CUTOFF appliquent ensuite le paramètre du firmware ; `sample`, `modType`, `ifxType`,
`filterType` déclenchent le rafraîchissement des encodeurs ou boutons de filtre ; `mfxSend`
utilise 127, pas 1, comme son bouton. `filterType` règle LPF, HPF et BPF pour la partie sélectionnée ;
`modType` affiche la fenêtre MOD. Mesuré dans l’émulateur sur les trois firmwares,
[résultats de la PR #401](messungen/2026-11-09-plugin-part-dsp.md).

Depuis l’API 24, sélectionner un sample découpé règle aussi sa tranche comme une rotation
ascendante de SAMPLE. Vérifié avec un sample découpé synthétique dans l’émulateur, dont la carte
ne contient pas de vrai sample découpé. Le modèle bleu utilise désormais aussi l’édition de partie
avec fenêtre. Les champs LAST STEP à SCALE MODE et GROOVE passent par leurs fonctions de menu
et produisent le même état qu’une rotation. Vérifié dans l’émulateur, pas sur l’appareil :
[mesure Pattern/Part](messungen/2026-11-06-plugin-api21-pattern-parts.md),
[mesure API 24](messungen/2026-11-08-plugin-api24-part-cc.md).

**Écriture des paramètres de pattern.** `korg.seq.setPatternValue` passe par la fonction du menu
Pattern et laisse le même octet qu’une rotation. MFX TYPE est limité à 31 sur le modèle bleu.
`syncGroup`, champ 12 depuis l’API 21, n’est pas connu du firmware : l’appel écrit directement
comme la page SYNC GROUP. Depuis l’API 24, `alternate1314` et `alternate1516` utilisent les
fonctions ALTERNATE ; `mfxHold` presse MFX HOLD si la valeur change, ce qui règle LED, effet et
pavé tactile comme le bouton, avec mise à jour du bloc à la trame suivante. `mfxPadX` et
`mfxPadY` modifient la position et transmettent les CC MIDI comme le pavé, sur le canal global.
Le nom du pattern n’est pas modifiable. Vérifié dans l’émulateur sur les trois firmwares,
pas sur l’appareil : [mesure API 15](messungen/2026-11-03-plugin-api15.md).
La table par firmware est `PATTERN_SETTERS` dans `tools/patch/script_hooks.py`.

**Écriture des pas.** Depuis l’API 9, `korg.seq.*` écrit dans le pattern en RAM, en lecture ou
en édition, comme la génération aléatoire SHIFT + PART ERASE. Les octets des pas sont écrits
directement sans passer par le panneau. Les notes modifiées sont jouées au passage suivant,
même pendant la lecture, ce qui a été mesuré dans l’émulateur.

Le pattern devient modifié mais non enregistré : seul WRITE le conserve. Charger un autre
pattern perd les changements. Ni flash ni carte ne sont modifiés ; SHIFT + EDIT< n’annule rien.
Les pads montrent la section de mesure sélectionnée ; après des écritures dans une trame,
le moteur demande une seule actualisation en fin de trame, sur l’écran principal, sinon à la
prochaine trame sur cet écran. Un pas au-delà de la longueur du pattern ou de LAST STEP est
écrit mais non joué. Les notes sont MIDI : 48 est la fondamentale C, à laquelle s’ajoute
`korg.current.key`. [Mesure de la génération aléatoire](messungen/2026-10-16-wuerfeln.md).

```js
// TAP écrit fondamentale, tierce, quinte et octave dans la partie sélectionnée
// dans la tonalité du pattern, une double croche sur deux, sur toute sa longueur.
const chord = [0, 4, 7, 12];
korg.onEvent("buttonPress", (key) => {
  if (key != korg.key.TAP) return;
  let part = korg.selectedPart;
  if (part > 15) return;
  korg.seq.clearPart(part);
  for (let step = 0; step < korg.current.length * 16; step += 2) {
    let note = 48 + korg.current.key + chord[(step / 2) % 4];
    korg.seq.setStep(part, step, note, step % 8 == 0 ? 110 : 80);
    korg.seq.setGate(part, step, 40);
  }
});
```

Un arpégiateur évoluant pendant la lecture écrit le prochain pas depuis `step`. Les coûts
sont faibles : `setStep` 6 unités, `setGate` 4, `clearPart` 30 ; 64 pas tiennent dans une trame.

**Copie de patterns, API 14.** `korg.read.patternBytes` lit les pas d’un pattern stocké,
`korg.seq.writeSteps` les écrit dans celui en lecture et `korg.seq.setPartValue` reporte les
paramètres de partie. WRITE reste nécessaire pour enregistrer. Dans l’émulateur, une copie
comprenant les 64 pas et paramètres, puis WRITE, survit à un aller-retour vers un autre pattern
à l’octet près, dans `tools/emu/plugin_edit_cases.py`. Les notes sont stockées comme MIDI+1,
0 signifie vide. L’absence d’enregistrement dans la motion sequence par ce chemin est une
déduction ; l’envoi de CC depuis l’API 24 est décrit ci-dessus.

```js
// TAP copie la partie 1 du pattern 5 dans la partie sélectionnée : pas et paramètres.
const steps = new Array(768);
const fields = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 18];
korg.onEvent("buttonPress", (key) => {
  if (key != korg.key.TAP) return;
  const part = korg.read.part();
  if (part > 15) return;
  korg.read.patternBytes(steps, 4, 2048 + 48);
  korg.seq.writeSteps(steps, part, 0);
  for (let i = 0; i < 15; i = i + 1) korg.seq.setPartValue(part, fields[i], korg.read.patternValue(4, 0, fields[i]));
});
```

**Affichage sur l’appareil.** Le moteur maintient une image propre de 1024 octets, huit pages
de 128 colonnes, bit 0 en haut. Les coordonnées hors écran sont coupées, jamais rebouclées.
Seul le propriétaire dessine : application ouverte ou plugin ayant pris l’écran. En sa présence,
le moteur copie son image dans la RAM écran du firmware après les widgets, une fois par trame,
uniquement sur la page principale. Sans propriétaire, il ne touche pas à l’écran. Les menus
et fenêtres restent dessinés par le firmware et invisibles au plugin.

La police propre au projet mesure 5 × 7 pixels, avec 6 pixels par caractère. Le navigateur et
l’appareil utilisent la même table ; 70 cas ont été comparés pixel par pixel dans l’émulateur.
Le texte est limité à 31 caractères et les nombres sont affichés en décimal.

**Images depuis un tableau, `korg.display.bitmap`.** Chaque élément contient les huit pixels
d’une colonne, bit faible en haut ; seuls les huit bits faibles comptent. Une bande de width
éléments va de gauche à droite, les bandes se suivent de haut en bas. La hauteur vaut huit fois
le nombre de bandes entières, soit longueur du tableau divisée par width, reste ignoré.
La largeur maximale vaut 128. Seuls les pixels actifs sont dessinés ; utiliser `clearRect`
au préalable si nécessaire. Y n’a pas besoin d’être multiple de 8 : un élément peut alors
couvrir deux pages de la RAM écran. Exemple d’image 8 × 8 :

    const gesicht = [0x3C, 0x42, 0xA5, 0x81, 0xA5, 0x99, 0x42, 0x3C];
    korg.display.bitmap(gesicht, 10, 5, 8);

Seul un nom de tableau global est accepté, `const picture = [...]` ou `new Array(n)`.
Pour une largeur constante, le compilateur vérifie qu’au moins une bande tient dans le tableau.
À chaque appel, la VM contrôle les limites de la zone des variables, sinon `BAD_VAR`.
Les zéros d’un littéral ne coûtent pas de code puisque les variables sont effacées au chargement.
Le coût est de 14 unités plus 3 par élément : une image 41 × 56, 287 éléments, coûte 875 unités.
Il vient du comptage d’instructions ARM mesuré dans l’émulateur. Les éléments vides ou hors écran
coûtent en réalité moins que cette borne.

`textNumber` est compté comme `text`, avec une borne de 250, alors que le travail réel est
supérieur, environ 4900 instructions pour cinq caractères et trois chiffres. La limite de 5 ms
par trame reste applicable.

**Position tactile.** Le panneau envoie deux valeurs de 16 bits, reprises sans limitation par
le filtre d’entrée, mesuré dans l’émulateur. Le bouton 34, `0x22`, arrive sans position et
ne produit pas `touch`. L’appui réinitialise la détection ; la première position reçue donne
`first = 1`, même sans appui préalable, puis le lever du doigt réinitialise cet état.
Un tampon circulaire plein peut perdre aussi le premier `touch`.

L’alignement du pavé et de l’écran reste **non mesuré sur l’appareil**. L’éditeur et l’émulateur
utilisent 0 à 1023 sur tout le pavé, Y vers le haut ; Blechy suppose que `x / 8` donne la colonne.

**Erreur affichée.** Si le propriétaire de l’écran échoue, trois lignes remplacent son image :
nom du plugin, `Line` et ligne source, puis code d’erreur comme `DIV_ZERO`. L’erreur d’un autre
plugin reste sur sa page BLECH, par exemple `DIV_ZERO L3`, sans toucher à l’écran. Le firmware
reste utilisable et les autres plugins continuent.

Aucun dessin dans le corps : le firmware réécrit les LED au démarrage et aucun écran n’y est
disponible. Les sorties vont dans `ready`, `frame`, `open` ou un gestionnaire d’entrée.

**Commandes de LED.** La dernière demande par LED l’emporte ; zéro est aussi une demande explicite.
Les doublons d’une trame sont fusionnés. Maximum 16 paquets par trame, cinq octets par paquet,
en laissant au moins 256 octets libres dans la file du firmware. C’est une limite déduite,
pas un débit mesuré sur l’appareil : 16 paquets à 25 Hz font 400 paquets par seconde.
Le firmware peut encore changer les LED. Chaque trame oublie donc le dernier envoi et ne
réémet rien seule. Pour imposer une valeur à chaque trame, la redemander dans `frame`.
[Détails](plugins.md#funktionen-der-electribe), en allemand.

### Retenir les entrées du firmware (API 19)

`korg.keyMask` et `korg.keyHold` retiennent les boutons, `korg.padHold` les pads,
`korg.knobHold` les potentiomètres. Chaque plugin a son masque et ne modifie que celui-ci.
Le filtre transmet chaque entrée à tous les plugins actifs possédant un gestionnaire,
puis décide si le firmware doit aussi la recevoir.

- Si deux plugins retiennent la même commande, les deux la reçoivent ; le firmware ne la reçoit
  pas tant qu’au moins un plugin actif la retient. Libérer une retenue ne supprime pas l’autre.
- Un plugin désactivé, en erreur ou supprimé cesse de contribuer aux masques à la fin de la
  trame suivante. Ses retenues exclusives reviennent au firmware.
- Fermer une application libère les pads de tous les plugins, comme auparavant ; les retenues
  de boutons et potentiomètres restent actives.
- Un relâchement suit son appui : si l’appui a été bloqué, son relâchement le reste même si
  la retenue est levée entre-temps. Un appui transmis a son relâchement transmis.
- Retenir EXIT avec `korg.keyHold` ou `korg.keyMask` termine le plugin avec une erreur afin
  de conserver la fermeture des applications.
- Mesuré avec deux plugins dans l’émulateur sur Hacktribe, rouge et bleu,
  `tools/emu/plugin_api19_cases.py`, pas sur l’appareil. Gate Hold reste compatible.

### Commander l’appareil comme avec un doigt (API 25)

`korg.keyDown`, `korg.keyUp`, `korg.padDown`, `korg.padUp`, `korg.encoder`, `korg.touch`
transmettent les messages normaux du panneau par sa file. Ils reproduisent les gestes
sur boutons, pads, encodeurs et pavé tactile.

- Le marqueur de ces messages contourne réaffectation, `korg.keyHold`, `korg.keyMask`,
  `korg.passKeys`, `korg.padHold`, `korg.touchLockX`, application ouverte et raccourcis de BLECHTRIBE.
  Aucun plugin, y compris l’émetteur, ne reçoit ces événements. Ainsi, un plugin peut retenir
  les pads physiques avec `korg.padHold` et jouer ses propres frappes avec `korg.padDown`.
- Un second appui identique n’envoie rien, ni un relâchement sans appui. À l’arrêt du plugin,
  désactivation, erreur ou suppression, le moteur relâche ses commandes et son doigt tactile
  en fin de trame. Le dernier plugin ayant pressé une commande compte.
- Une file pleine perd le message ; l’appui n’est alors pas comptabilisé.
- Le message part pendant la trame du plugin et arrive une trame après un message physique
  envoyé au même moment.
- Depuis l’API 25, EXIT avec `korg.keyDown` ou `korg.pressKey` ferme d’abord l’application,
  puis atteint le firmware. `korg.keyHold`, `korg.keyMask` et `korg.remapKey` refusent toujours EXIT.
- Mesuré dans l’émulateur sur les trois firmwares, comparé chaque fois au même geste physique ;
  non vérifié sur l’appareil.

### Noms des boutons et des LED

Les constantes expriment l’intention à la place de `key == 11` ou `korg.led(20, 255)`.

```js
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) korg.led(korg.led.TAP, 255);
  if (key == korg.key.PART_LEFT) korg.led(korg.led.PAD_1_RED, 255);
});
```

`korg.key.NAME` est le code reçu dans `key` par `buttonPress` et `buttonRelease`.
`korg.led.NAME` est le premier argument numérique de `korg.led`. Le compilateur remplace
chaque constante par son numéro : noms et nombres donnent exactement le même bloc et
la même taille, sans modifier sa version. `test/script-names.test.mjs` le vérifie sur les
exemples. Les nombres restent acceptés, ainsi que les constantes dans les expressions :
`const BASE = korg.led.PAD_1_RED;`, puis `BASE + 2`. Un nom inconnu provoque une erreur
avec des suggestions. `korg.led(...)` est un appel ; `korg.led.NAME` est une constante.

Les noms reprennent les inscriptions en majuscules avec soulignements : GATE ARP devient
`GATE_ARP`, les flèches Part deviennent `PART_LEFT`, `PART_RIGHT`, les flèches Edit
`EDIT_LEFT`, `EDIT_RIGHT`, et les boutons 1 à 4 `BAR_1` à `BAR_4`. Une seconde LED ajoute
sa couleur : `PLAY_BLUE`, `BAR_1_BLUE`, `PAD_1_RED` à `PAD_16_BLUE`. Le bleu des pads
indique la partie sélectionnée. Les LED rouges sont espacées de 2 : `PAD_1_RED + 2`
désigne `PAD_2_RED`. Les origines mesurées ou déduites de Freetribe sont dans `data/panel.mjs`.

**Boutons** (`korg.key`) :

| Nom | Numéro | Bouton |
|---|---|---|
| `korg.key.REC` | 0 | REC |
| `korg.key.STOP` | 1 | STOP |
| `korg.key.PLAY` | 2 | PLAY |
| `korg.key.TAP` | 3 | TAP |
| `korg.key.GATE_ARP` | 4 | GATE ARP |
| `korg.key.TOUCH_SCALE` | 5 | TOUCH SCALE |
| `korg.key.MASTER_FX` | 6 | MASTER FX |
| `korg.key.MFX_HOLD` | 7 | MFX HOLD |
| `korg.key.EDIT_LEFT` | 8 | ◄ Edit |
| `korg.key.MENU` | 9 | MENU |
| `korg.key.SHIFT` | 10 | SHIFT |
| `korg.key.PART_LEFT` | 11 | ◄ Part |
| `korg.key.EDIT_RIGHT` | 12 | Edit ► |
| `korg.key.EXIT` | 13 | EXIT |
| `korg.key.WRITE` | 14 | WRITE |
| `korg.key.PART_RIGHT` | 15 | Part ► |
| `korg.key.PART_MUTE` | 16 | PART MUTE |
| `korg.key.PART_ERASE` | 17 | PART ERASE |
| `korg.key.LPF` | 18 | LPF |
| `korg.key.TRIGGER` | 19 | TRIGGER |
| `korg.key.HPF` | 20 | HPF |
| `korg.key.SEQUENCER` | 21 | SEQUENCER |
| `korg.key.BPF` | 22 | BPF |
| `korg.key.KEYBOARD` | 23 | KEYBOARD |
| `korg.key.CHORD` | 24 | CHORD |
| `korg.key.STEP_JUMP` | 25 | STEP JUMP |
| `korg.key.MFX_SEND` | 26 | MFX SEND |
| `korg.key.PATTERN_SET` | 27 | PATTERN SET |
| `korg.key.BAR_1` | 28 | bouton 1 |
| `korg.key.BAR_2` | 29 | bouton 2 |
| `korg.key.BAR_3` | 30 | bouton 3 |
| `korg.key.BAR_4` | 31 | bouton 4 |
| `korg.key.AMP_EG` | 32 | AMP EG |
| `korg.key.IFX_ON` | 33 | IFX ON |
| `korg.key.TOUCHPAD` | 34 | contact sur le pavé tactile |

Les boutons 1 à 4 et TOUCHPAD produisent `buttonPress` comme les autres. Le contact tactile
fournit sa position par `touch`. Encodeurs, potentiomètres et pads ne produisent pas
`buttonPress`, mais `encoder`, `knob`, `pad`, avec leur index.

**Potentiomètres** (`index` de `knob`, `korg.read.knob(index)`, `korg.knobs.NAME`) :

| Index | Nom | Potentiomètre |
|---|---|---|
| 0 | `korg.knobs.LEVEL` | LEVEL |
| 1 | `korg.knobs.PAN` | PAN |
| 2 | `korg.knobs.PITCH` | PITCH / GLIDE |
| 3 | `korg.knobs.RESONANCE` | RESONANCE |
| 4 | `korg.knobs.EG_INT` | EG INT. |
| 5 | `korg.knobs.MOD_DEPTH` | MOD. DEPTH |
| 6 | `korg.knobs.ATTACK` | ATTACK |
| 7 | `korg.knobs.IFX_EDIT` | IFX EDIT |
| 8 | `korg.knobs.DECAY` | DECAY / RELEASE |
| 9 | `korg.knobs.OSC_EDIT` | OSC EDIT |
| 10 | `korg.knobs.MOD_SPEED` | MOD. SPEED |

Les indices 11 à 19 ne correspondent à aucun potentiomètre et restent à 0.
CUTOFF est un encodeur, pas un potentiomètre.

**Encodeurs** (`index` de `encoder`) :

| Index | Encodeur |
|---|---|
| 0 | VALUE / PATTERN (molette principale) |
| 1 | SAMPLE / OSC |
| 2 | CUTOFF |
| 3 | MOD. TYPE |
| 4 | IFX TYPE |

**Pads** (`index` de `pad`) : 0 à 15 correspondent aux pads 1 à 16.
Les numéros proviennent de `data/panel.mjs` et des mesures du panneau qui y sont citées.

**LED** (`korg.led`) :

| Nom | Numéro | LED |
|---|---|---|
| `korg.led.REC` | 18 | REC |
| `korg.led.STOP` | 19 | STOP |
| `korg.led.PLAY` | 9 | PLAY |
| `korg.led.PLAY_BLUE` | 21 | PLAY, LED bleue |
| `korg.led.TAP` | 20 | TAP |
| `korg.led.GATE_ARP` | 26 | GATE ARP |
| `korg.led.TOUCH_SCALE` | 27 | TOUCH SCALE |
| `korg.led.MASTER_FX` | 28 | MASTER FX |
| `korg.led.MFX_HOLD` | 29 | MFX HOLD |
| `korg.led.EDIT_LEFT` | 5 | ◄ Edit |
| `korg.led.MENU` | 7 | MENU |
| `korg.led.SHIFT` | 10 | SHIFT |
| `korg.led.PART_LEFT` | 30 | ◄ Part |
| `korg.led.EDIT_RIGHT` | 6 | Edit ► |
| `korg.led.EXIT` | 8 | EXIT |
| `korg.led.WRITE` | 11 | WRITE |
| `korg.led.PART_RIGHT` | 31 | Part ► |
| `korg.led.PART_MUTE` | 32 | PART MUTE |
| `korg.led.PART_ERASE` | 33 | PART ERASE |
| `korg.led.LPF` | 12 | LPF |
| `korg.led.TRIGGER` | 34 | TRIGGER |
| `korg.led.HPF` | 13 | HPF |
| `korg.led.SEQUENCER` | 35 | SEQUENCER |
| `korg.led.BPF` | 14 | BPF |
| `korg.led.KEYBOARD` | 36 | KEYBOARD |
| `korg.led.CHORD` | 37 | CHORD |
| `korg.led.STEP_JUMP` | 38 | STEP JUMP |
| `korg.led.MFX_SEND` | 15 | MFX SEND |
| `korg.led.PATTERN_SET` | 39 | PATTERN SET |
| `korg.led.BAR_1` | 40 | bouton 1 |
| `korg.led.BAR_1_BLUE` | 22 | bouton 1, LED bleue |
| `korg.led.BAR_2` | 41 | bouton 2 |
| `korg.led.BAR_2_BLUE` | 23 | bouton 2, LED bleue |
| `korg.led.BAR_3` | 42 | bouton 3 |
| `korg.led.BAR_3_BLUE` | 24 | bouton 3, LED bleue |
| `korg.led.BAR_4` | 43 | bouton 4 |
| `korg.led.BAR_4_BLUE` | 25 | bouton 4, LED bleue |
| `korg.led.AMP_EG` | 16 | AMP EG |
| `korg.led.IFX_ON` | 17 | IFX ON |
| `korg.led.VALUE_PATTERN` | 0 | VALUE / PATTERN |
| `korg.led.SAMPLE_OSC` | 1 | SAMPLE / OSC |
| `korg.led.CUTOFF` | 2 | CUTOFF |
| `korg.led.MOD_TYPE` | 3 | MOD. TYPE |
| `korg.led.IFX_TYPE` | 4 | IFX TYPE |
| `korg.led.PAD_n_RED` | 44 + 2 (n - 1) | pad n, LED rouge (n = 1 à 16) |
| `korg.led.PAD_n_BLUE` | 45 + 2 (n - 1) | pad n, LED bleue, indique la partie sélectionnée (n = 1 à 16) |

La même liste est disponible sous l’éditeur avec un filtre. Un clic insère la constante
au curseur. Un nombre ressemblant à un code de bouton ou de LED, dans `key == 11` ou
`korg.led(20, ...)`, affiche son nom sous le code. Après `korg.key.` et `korg.led.`,
la complétion propose les constantes correspondantes.

### Limites

| Élément | Limite |
|---|---|
| Zone de variables par plugin | 65536 emplacements de 4 octets maximum, dimensionnés selon les déclarations |
| Blocs, variables et entrées de plugins | 128 Kio partagés |
| Nombre de plugins | Aucun plafond fixe tant que la mémoire partagée suffit |
| Tableau | 1 à 65535 éléments |
| Textes distincts | 64, de 31 caractères maximum chacun |
| Nombres distincts négatifs ou supérieurs à 255 | 256 |
| Code | 16 Kio |
| Pile d’expressions | 32 valeurs |
| Appels imbriqués | 8 |
| Budget par exécution | 20000 unités de coût |

Chaque plugin consomme son bloc arrondi à 4 octets, quatre octets par variable et une entrée,
actuellement de 292 octets. La pile, les tampons de vérification, l’état global et le tampon
circulaire des événements sont hors du pool. Un plugin désactivé conserve mémoire et état d’erreur.

Si le pool ne suffit pas, le bloc est refusé avant l’initialisation des variables et l’exécution
du corps, avec `POOL_BUDGET` et le message de budget global insuffisant. La mémoire occupée
et les plugins chargés restent inchangés. Le compilateur vérifie seulement les déclarations,
avec une limite par défaut de 32768 emplacements, déduite des 128 Kio divisés par quatre.
Un bloc compilé peut donc être refusé au chargement. Les limites de format 65536/65535 ne
promettent pas qu’un tel tableau tienne réellement dans le pool de l’appareil.

Le pool occupe la zone FF de l’image entre `0xC01D7000` et `0xC01F7000`, soit 131072 octets.
La lecture hors ligne des images personnelles y a trouvé FF ; cela prouve une zone libre dans
l’image, pas son absence d’utilisation sur l’appareil.
[Mesure](messungen/2026-10-14-skript-haken.md). Le bloc de Blechy est hors du pool, à
`0xC0184000`, dans la plage FF `0xC01720B0` à `0xC01A0000` partagée avec le changement de
pattern et la barre de chargement. La mesure historique citait 12668 octets ; la version
intégrée décrite plus bas en utilise 15476. Ces emplacements n’ont pas été validés sur l’appareil.
Les opérandes 16 bits du format 2 ajoutent environ 9 % d’instructions ARM par opération,
valeur déduite, non mesurée séparément : [format et coûts](plugins.md#format-2-und-die-kosten).

### Gestion des erreurs

Le vérificateur examine avant chargement destinations de saut, constantes, variables,
appels, hauteur de pile, profondeur d’appel et fonctions autorisées par événement.
La VM termine un plugin en cas de boucle infinie dépassant budget ou temps, index de tableau
invalide, division par zéro ou argument hors plage. Le plugin est désactivé ; le message
indique son nom, la ligne et l’erreur. Les autres continuent. Les codes sont définis dans
`data/script/contract.mjs`.

## Carte SD et format des fichiers

### Fichiers de la carte

Les plugins arrivent par la carte SD, jamais intégrés à la VSB. Le dossier est
`KORG/blechtribe/Plugin/`, au singulier, identique sur les modèles rouge et bleu.
Prépare ce dossier pour une copie manuelle. Avec l’appareil connecté, la page Plugins peut
aussi écrire le fichier par USB : commande SysEx BLECHTRIBE `0x67`, PLUGIN BEGIN, nom composé
de lettres, chiffres, `_`, `-`, avec 16 caractères maximum. Il est ensuite accessible dans
BLECH > PLUGINS.

- `e2sPlugin.all` est la collection lue au démarrage. En-tête little endian de 16 octets :
  marqueur `GSAL`, version de fichier 1 en u16, nombre de blocs en u16, taille totale en u32,
  CRC-32 en u32 de tout le contenu à partir de l’octet 16. Les blocs de format 2 suivent
  sans modification, chacun avec taille et CRC. Leur taille est multiple de 4, sans remplissage
  entre blocs. Un bloc est limité à 32752 octets par le tampon du chargeur.
- `<name>.blech` contient un bloc, une description facultative et la source. Après le bloc :
  `GDSC`, longueur en u32, description ASCII dont les lignes de 20 caractères maximum finissent
  par `\n`, au maximum 2047 octets ; puis `GSRC`, longueur en u32 et source UTF-8.
  La description vient des lignes `//` tout en haut du code ; une ligne `//` vide sépare
  les paragraphes, les caractères allemands sont transcrits ae, oe, ue, ss. Sans ces commentaires,
  pas de `GDSC`. Le firmware affiche cette description sur DESCRIPTION ; l’éditeur récupère
  la source pour rouvrir le plugin.

Le chargeur s’exécute une fois après `e2sSample.all`. Avec EXIT maintenu à l’allumage, sans
carte ou sans fichier, il ne fait rien et laisse le démarrage normal. En-tête, CRC ou fichier
tronqué invalident la collection entière. Un seul bloc refusé, pour CRC, budget ou code,
est ignoré sans bloquer les autres. Le corps `start` des plugins chargés est ensuite exécuté,
puis le moteur est activé. `ready` arrive à la première trame après la page principale.
Le bloc de contrôle conserve `cardStatus`, `cardLoaded`, `cardRejected`, `cardFirstError`.

L’éditeur écrit ces formats avec `src/script/archive.mjs`. Un fichier seulement copié sur
la carte attend le prochain démarrage ; MANAGE PLUGINS le montre aussi comme OFF et permet
son chargement immédiat en le réactivant.

**Indicateur PROBED.** Dans l’en-tête, `flags` est un u16 à l’octet 34. Son bit 0, PROBED,
est posé à l’export après essai du texte par `markProbed`, dans `src/script/blob.mjs`, avec
nouveau CRC. Tous les autres bits sont interdits : navigateur et firmware refusent le bloc
s’ils sont définis. Sans PROBED, le bloc est externe : chargé, mais exécuté seulement après
une autorisation sur l’appareil. C’est une indication, pas une protection : chacun peut le poser.

**Images, `korg.file.frame`.** `KORG/blechtribe/Gif/GIF00.E2G` à `GIF99.E2G` sont little endian :
`GGIF`, version 1 en u16, nombre d’images en u16, puis délai de chaque image en ms en u16,
deux octets nuls et 1024 octets d’écran. Octet `(y / 8) * 128 + x`, bit `y % 8`.
`tools/gif/gif2e2g.py` convertit un GIF avec Pillow, ou plusieurs images, par exemple BMP,
en une image par entrée dans l’ordre fourni. `src/script/gif.mjs` lit le format dans le navigateur.
Chaque appel ouvre, cherche, lit et ferme le fichier avec FatFs, dont `f_lseek` à `0xC009E404`,
`0xC008AF5C` sur bleu, et l’objet fichier du chargeur. Lecture seulement sur l’écran principal.
La durée de lecture de 1 Kio sur l’appareil n’est pas mesurée ; les 5 ms par trame restent la limite.

### Valeurs persistantes

Chaque plugin dispose de 16 entiers persistants, isolés par nom de plugin. `korg.store.get`
les lit dès le corps, avant les gestionnaires ; `korg.store.set` modifie seulement la RAM.
Seul `korg.store.save()` demande une écriture sur carte. Le moteur n’écrit jamais de lui-même,
pas même à l’extinction. Utiliser ces fonctions impose l’API 2 au bloc ; sinon il peut rester en 1.

Les fichiers `KORG/blechtribe/Plugin/store.a.bin` et `store.b.bin` alternent les générations.
Au démarrage, la génération valide la plus récente l’emporte. Si un fichier manque ou est
endommagé, l’autre sert de repli ; sans fichier, les valeurs par défaut de `get` s’appliquent.
Format : en-tête de 16 octets, puis 84 octets par plugin, nom, masque des emplacements utilisés,
16 valeurs ; au plus 194 entrées. Les plugins momentanément absents de la carte gardent leurs
entrées lors d’une sauvegarde. [Détails](plugins.md#dauerhafte-werte).

Écriture au plus tôt 50 trames, soit 2 secondes, après la précédente, uniquement sur la page
principale ou dans BLECH, y compris les pages `korg.menu.add`. Un nouvel appel `save()` reste
en attente. Un échec, carte absente ou pleine, incrémente `storeErrors` sans nouvelle tentative
automatique. Dans le navigateur, les valeurs persistent uniquement jusqu’au rechargement de la page.

## Menu BLECH de l’appareil

Le patch ajoute BLECH, écran `0x2D`, vers la fin de l’anneau EDIT après Event. Trois niveaux
reprennent le style de Data Util : police, positions et indication `press  [ Enter ]`.

- Dans l’anneau rouge, BLECH est la page 31/32, suivie de Blechy 32/32, puis du menu Pattern.
  SYNC GROUP est la page 16/32, après CHAIN REPEAT et avant Part, dont la première page devient 17.
  Sur bleu, sans menu Sample : SYNC GROUP 16/31, BLECH 30/31, Blechy 31/31 ; l’anneau passe
  de 28 à 31 pages, contre 29 à 32 sur rouge. EDIT gauche/droite le parcourt.
  EXIT maintenu à l’allumage supprime ces pages et laisse l’anneau d’origine.
- Dans GLOBAL PARAMETERS, PLUGIN RUNTIME suit XY CALIBRATION et devient Global 21/21.
  Dans DATA UTILITY, EXPORT ALL CUSTOMIZATIONS, EXPORT ALL PLUGINS, EXPORT ALL EFFECTS et
  SET INIT PATTERN suivent SOFTWARE UPDATE, pages 15/18 à 18/18. Sur bleu, sans collection
  d’effets et avec 11 fonctions d’origine, les trois pages restantes sont 12/14 à 14/14.
  Ce sont des pages BLECH atteintes par EDIT aux limites des menus du firmware ; leurs tables
  et machines à états restent intactes. EXIT et les compteurs suivent les menus d’origine.
- ENTER sur BLECH retrouve le dernier groupe visité, même après un passage dans d’autres menus.
  MENU sert d’ENTER. La liste des groupes affiche BLECH et compte les groupes, par exemple 2/3,
  jusqu’à cinq avec des applications. EDIT parcourt la liste circulairement.
- ENTER ouvre les pages du groupe. L’étiquette et le compteur concernent ce groupe uniquement,
  par exemple Plugins 3/5. EDIT tourne entre pages, la molette modifie, WRITE exécute ou sauvegarde.
- EXIT remonte d’un niveau, puis de l’anneau vers l’écran principal. MENU sur l’écran principal
  retrouve la position précédente, y compris dans un groupe.
- Les plugins ne reçoivent aucune entrée lorsque BLECH est ouvert : ils ne peuvent donc pas
  bloquer son accès en interceptant des boutons.

Ordre des entrées : fonctions intégrées, plugins, personnalisation, groupes enregistrés par
`korg.app`, puis VERSION, qui n’est pas un groupe.

| Entrée | Contenu |
|---|---|
| FEATURES | MFX 2, PATTERN CONFIRM, TAP MOTION, NOTE ASSIST ; LAST PATTERN si le patch last-pattern est présent ; STEREO 1 PAD avec stereo-pad sur rouge ; AUTO SAVE décrit plus bas |
| PLUGINS | Ouvre directement la liste MANAGE PLUGINS |
| CUSTOMIZATION | DISPLAY, LED, puis PAD COLOR, POWER SAVE et SPLASH selon les patches présents |
| GAMES | Une page par application inscrite ; absent sans application |
| TOOLS | Même principe que GAMES |
| VERSION | Version du jeu de patches, par exemple BLECH 1.3.7, via blech-version, puis HACKTRIBE, KORG RED ou KORG BLUE. Le suffixe décrit `KORG/blechtribe/Presets/e2sFx.all` au démarrage : FX chargé et IFX/MFX renvoyés immédiatement au DSP, FX off ignoré, FX fw? pour un autre firmware, FX bad invalide ; rien sans fichier. ENTER, WRITE et molette ne changent rien |

Les pages FEATURES utilisent ON/OFF, sauf TAP MOTION qui propose aussi ONCE. MFX 2 concerne
TOUCH SCALE et prend effet au démarrage suivant, avec l’indication ON, RESTART. Les autres
pages sont détaillées ci-dessous. ABOUT n’existe plus : il n’affichait que le nombre de plugins.

| Groupe ou page | Valeur et comportement |
|---|---|
| GLOBAL PARAMETERS, PLUGIN RUNTIME | ON/OFF pour les plugins de la carte ; effet au démarrage suivant, affiché par OFF, RESTART. Blechy est intégré et reste présent. Page 21/21 ; WRITE sauvegarde les réglages BLECH |
| PLUGINS, MANAGE PLUGINS | ENTER sur PLUGINS ouvre la liste directement. La page intermédiaire `press  [ Enter ]` n’apparaît qu’avec No Plugin ou le résultat de OFF/REMOVE ; ENTER y rouvre la liste. Lecture de `KORG/blechtribe/Plugin/`, maximum 64 fichiers ; au-delà, LIST FULL indique 64 files shown. Depuis 1.4.5, présentation du navigateur DATA UTILITY : trois lignes en grande police, icône fichier, noms longs coupés par « .. », triangle à gauche, défilement à droite. Retrouve le dernier plugin affiché. EXIT revient à PLUGINS ; jusqu’à 1.4.5, MANAGE PLUGINS constituait une page intermédiaire. Plugins chargés d’abord, puis fichiers `*.blech` non chargés, chaque nom une fois. Un plugin seulement dans `e2sPlugin.all` est chargé mais sans description. Blechy et les fonctions intégrées ne sont pas listés : leurs réglages appartiennent à FEATURES. [64 fichiers](messungen/2026-10-30-plugin-liste-64-entfernen.md), [navigateur](messungen/2026-11-08-plugin-liste-browser.md) |
| Ligne d’un plugin | Deux lignes de pixels signifient ON, une page vide OFF, y compris non chargé ou en erreur. État en petit : DIV_ZERO L3, WRITE=ALLOW ou résultat. Molette vers le bas : pause ; vers le haut : reprise. WRITE conserve l’état au redémarrage ; un plugin réactivé y exécute son corps. Un externe attend WRITE=ALLOW, seule WRITE l’autorise. Pour un fichier non chargé, monter charge et démarre, descendre ne fait rien. Résultats possibles : rejected, runtime off, ou attente d’autorisation. Un chargement ponctuel ne survit au redémarrage qu’après EXPORT ALL PLUGINS. ENTER ouvre ACTIVE (la molette y allume et éteint tout de suite, sans ENTER ni EDIT), DESCRIPTION, pages propres, OFF, REMOVE ; sans chargement, seulement ACTIVE, DESCRIPTION et REMOVE. EXIT revient à la liste |
| Plugin, DESCRIPTION | Description issue des commentaires `//` initiaux du fichier `*.blech`. Nom en haut, description plein écran, état en bas. Molette : ligne par ligne ; `^` et `v` indiquent la suite ; ENTER ne fait rien. Sans fichier ou description : no description |
| Plugin, page `korg.menu.add` | Valeur numérique ; la molette modifie et transmet `menu` au plugin |
| Plugin, OFF | ENTER demande Enter = off ; second ENTER arrête le plugin et réécrit `e2sPlugin.all` sans lui, même vide s’il était seul. Résultat off, file kept. Le `*.blech` reste, réapparaît OFF et peut être rechargé |
| Plugin, REMOVE | ENTER demande Enter = remove ; second ENTER fait OFF puis supprime le `*.blech` par `f_unlink`. Résultat removed. Pour un fichier seul, seul le fichier est supprimé ; pour une entrée seule dans la collection, seule la collection est réécrite. Sur bleu, sans `f_unlink`, le fichier reste : file stays on card. Si le dossier a changé depuis l’ouverture, aucune suppression : folder changed. [Mesure](messungen/2026-10-30-plugin-liste-64-entfernen.md) |
| DATA UTILITY, EXPORT ALL CUSTOMIZATIONS | Titre abrégé EXPORT ALL CUSTOM. ENTER ou WRITE enregistre `KORG/blechtribe/e2sCustom.all`, même structure que les réglages sans liste de CRC de plugins, puis exported. Aucun chargeur dédié ne le lit au démarrage ; le copier comme `settings.a.bin` restaure la personnalisation |
| DATA UTILITY, EXPORT ALL EFFECTS | ENTER ou WRITE réécrit les presets IFX/MFX et modulations actuellement en RAM dans `KORG/blechtribe/Presets/e2sFx.all`, avec positions et textes `.e2fx` conservés, puis nouveau CRC. Sans collection, crée des entrées sans texte, que l’Atelier ignore à l’import. Une collection existante doit avoir été chargée au démarrage : fichier remplacé ou invalide depuis lors, bad e2sFx.all et aucune écriture. Rouge seulement |
| DATA UTILITY, EXPORT ALL PLUGINS | ENTER ou WRITE exporte tous les plugins chargés dans `e2sPlugin.all`, à l’octet près comme le navigateur, puis sauvegarde leurs réglages, y compris les désactivations |
| GAMES ou TOOLS, application | ENTER=OPEN ; ENTER ou WRITE ouvre. Un plugin désactivé ou en erreur indique OFF ou FAULT |
| CUSTOMIZATION, DISPLAY | ENTER ouvre le rétroéclairage ; EXIT revient à DISPLAY |
| DISPLAY, BACKLIGHT HUE, SAT, BRIGHT | HUE 0 à 95, SAT/BRIGHT 0 à 15. Le cercle des teintes comprend six intervalles de 16 pas entre rouge, jaune, vert, cyan, bleu et magenta. Stockage inchangé en RGB 0 à 15, compatible avec les anciens réglages. Absence de réglage ou luminosité maximale sans saturation : STOCK, blanc d’origine. Un pas de même couleur est sauté. Effet immédiat. Après WRITE, les canaux s’allument au démarrage s’ils atteignent au moins la moitié du canal le plus fort : HUE 15, SAT 13, BRIGHT 14 démarre jaune. Rouge : avant l’image ; bleu : peu après son apparition ; niveaux intermédiaires après chargement du menu. [Mesure](messungen/2026-10-29-hintergrundlicht-beim-start.md) |
| DISPLAY, INTENSITY | 0 à 15, intensité commune sans modifier le mélange ; 0 éteint, 15 couleur pleine ; immédiat |
| DISPLAY, DISPLAY INVERT | OFF/ON, échange pixels clairs et sombres ; commandes écran `0xA7` pour inverser et `0xA6` pour restaurer. Immédiat. ON par défaut pour réduire les traînées ; un fichier 1.2 sans ce bit conserve OFF |
| CUSTOMIZATION, POWER SAVE | ENTER ouvre les pages d’économie d’énergie, sur piles seulement ; EXIT revient à POWER SAVE |
| POWER SAVE, DISPLAY LIGHT | STOCK ou 1 à 15. STOCK utilise l’atténuation du firmware ; 1 à 15 règlent la couleur propre, avec 1 correspondant à 3/15 et 15 au maximum |
| POWER SAVE, LED DIMMING | 0 à 100 % d’atténuation des LED de pads, boutons et encodeurs. 0 sans atténuation, 100 éteint, 75 par défaut laisse un quart de luminosité. Les LED d’encodeurs s’éteignent sauf à 0 %. Immédiat, conservé par WRITE |
| CUSTOMIZATION, LED | ENTER ouvre les LED inférieures ; EXIT revient à LED |
| LED, BOTTOM LEDS | METER vu-mètre, COLOR couleur fixe, OFF éteint ; immédiat sur les quatre LED RGB inférieures |
| LED, LED HUE, SAT, BRIGHT | Même sélection de couleur que le rétroéclairage. En METER sans couleur de zone propre, le niveau pilote la luminosité de cette couleur. STOCK conserve les couleurs du firmware ; immédiat |
| LED, METER STILL, LOW, MID, LOUD | STOCK, WHITE, RED, GREEN, BLUE, YELLOW, CYAN, PINK. STILL et LOUD ajoutent RAINBOW, STILL ajoute OFF. Zones comme le firmware : silence, faible, moyen, fort. STOCK : blanc, bleu, vert, rouge. RAINBOW parcourt le RGB en environ 3,5 s pour STILL et une mesure au tempo pour LOUD, environ 1,9 s à 128 BPM. STILL OFF laisse le silence sombre |
| CUSTOMIZATION, PAD COLOR | ENTER ouvre les couleurs de pads si pad-colors est présent |
| PAD COLOR, PAD COLOR | RED/BLUE/PINK remplace le rouge du firmware pour partie jouée, pad maintenu ou pas actif. RED par défaut ; immédiat, WRITE conserve. En SEQUENCER, une note liée au pas précédent laisse une traînée rose décroissante sur sa durée ; les luminosités des notes liées qui se chevauchent s’additionnent |
| PAD COLOR, SELECT COLOR | Couleur de la partie sélectionnée, jamais égale à PAD COLOR ; BLUE par défaut. Un pad joué et sélectionné utilise la troisième couleur |
| PAD COLOR, OVERLAP | AUTO, RED, BLUE, PINK pour un pad joué et sélectionné. AUTO choisit la couleur distincte des deux précédentes |
| CUSTOMIZATION, SPLASH | ENTER ouvre les trois pages de l’image de démarrage si l’éditeur d’image est présent ; EXIT revient à SPLASH |
| SPLASH, SPLASH IMPORT | Molette et ENTER. Fichiers `.bmp` directement dans `KORG/blechtribe/`, navigateur à trois lignes comme IMPORT SAMPLE. Extension masquée, noms de plus de 11 caractères coupés à 11 avec « .. », compteur de fichiers, NO .BMP FILE sans fichier. Pas de sous-dossier ni de nom commençant par un point, comme `._` sur macOS. Parcours dans l’ordre du dossier. ENTER lit une image 128 × 64, 1 bit, non compressée, couleur sombre dessinée, puis l’enregistre comme WRITE dans l’éditeur. Visible au prochain démarrage. Résultats loaded, no .bmp file, not 128x64 1 bit ; une erreur ne change rien. Pas sur bleu |
| SPLASH, SPLASH DRAW | ENTER ouvre l’éditeur, page Global accessible ici seulement. Molette horizontalement, SHIFT maintenu verticalement ; MENU inverse le pixel, maintenu peint sa nouvelle couleur au passage du curseur ; WRITE enregistre, EXIT quitte |
| SPLASH, SPLASH RESET | ENTER abandonne l’image importée ou dessinée ; le firmware retrouve immédiatement et aux démarrages suivants son image d’origine. Résultat original back |
| FEATURES, PATTERN CONFIRM | ON : pendant la lecture, le pattern consulté attend MENU puis démarre à la fin de la séquence. OFF : comportement du firmware sans patch de confirmation. Immédiat, ON par défaut même sans fichier ; OFF est le bit 2 des flags. MENU clignote pour VIEW:, même à l’arrêt avec modifications non enregistrées, puis reste allumé pour NEXT: jusqu’au changement. Les pads et informations OSC/Pitch montrent le pattern consulté. Les pads ont leur propre couleur ; PART MUTE règle ses états muets, emportés au changement. Le premier appui copie la partie dans le pattern en lecture par Copy Part, non muette et sans changement de pattern ; les suivants la rendent muette ou audible dans ce pattern. [Vue](messungen/2026-10-25-pattern-ansicht.md), [pads](messungen/2026-10-29-vorschau-pads.md), [copie](messungen/2026-10-30-vorschau-part-reinholen.md) |
| Anneau, SYNC GROUP | OFF, 1 à 999, page 16/32 après CHAIN REPEAT et avant Part, étiquette Pattern ; sur les deux modèles, bleu depuis le 24 octobre. La molette modifie le groupe du pattern en RAM ; WRITE ouvre la sauvegarde du pattern. En lecture, un autre pattern du même groupe démarre en fin de séquence sans MENU, NEXT: ; hors groupe, MENU reste nécessaire. À l’arrêt, chargement immédiat dans le groupe, même avec modifications non enregistrées. Un changement dans le groupe transporte états muets, son des parties, tempo, swing, niveau, pavé MFX et HOLD, y compris au retour ; types MFX 1/MFX 2, pas, motion, longueur, beat, tonalité, gamme et accords restent ceux du nouveau pattern. Transfert en RAM seulement. OFF, groupe 0, ne transporte rien. [Bleu](messungen/2026-10-24-blau-sync-group.md), [modifications](messungen/2026-10-25-sync-ungespeichert.md) |
| Menu Pattern, BEAT | 16, 32, 8 Tri, 16 Tri, 8. Le cinquième choix 8 donne une croche par pas : durée doublée, BEAT 8 à 160 BPM correspond à BEAT 16 à 80 BPM. Horloge MIDI et LED TAP restent au tempo réel, 12 impulsions par pas avec horloge externe. Stocké dans le pattern ; Gate Arp, export et tranches suivent le pas. Sans BLECHTRIBE, Korg joue ce réglage à un pas toutes les 2 ms. Rouge et bleu. [Mesure](messungen/2026-10-29-beat-achtel.md) |
| FEATURES, TAP MOTION | OFF/ON/ONCE. ON : TAP bascule la motion enregistrée de la partie sélectionnée ; appui de plus de 0,3 s seulement pendant le maintien, puis retour à l’état initial. ONCE : une motion activée par TAP joue jusqu’à la fin du pattern et s’éteint. OFF rend TAP au tap tempo du firmware. Immédiat, ON par défaut même sans fichier. OFF bit 3, ONCE bit 5 des flags ; bit 3 prioritaire |
| FEATURES, NOTE ASSIST | ON : en KEYBOARD, après une note, les notes adaptées brillent légèrement en rose selon leur compatibilité : unisson/quinte, puis tierces/quarte/degré de gamme, puis sixtes. Restent à l’arrêt/pause, s’estompent en lecture, les plus faibles d’abord. En CHORD, avec gammes de sept notes, indique les accords qui s’enchaînent bien. OFF rend le comportement du firmware. Immédiat, ON par défaut ; OFF bit 4 des flags |
| FEATURES, LAST PATTERN | ON démarre sur le dernier pattern sélectionné ; OFF sur 001, sans effacer le numéro mémorisé pour un futur ON. Effet au prochain allumage, WRITE conserve ; OFF bit 3 de l’octet 5 des réglages. ON sans fichier ; EXIT au démarrage force 001. Rouge et bleu avec last-pattern |
| FEATURES, STEREO 1 PAD | ON : sample stéréo sur son seul pad et une voix, pad voisin indépendant. OFF : comportement Korg où un stéréo sur les pads 1, 3, etc. occupe aussi le suivant. Immédiat, WRITE conserve ; OFF bit 2 de l’octet 5 ; ON sans fichier. EXIT à l’allumage restaure Korg. Rouge avec stereo-pad. [Mesure](messungen/2026-10-29-stereo-ein-pad.md) |
| FEATURES, AUTO SAVE | ON : quitter GLOBAL PARAMETERS, ou PLUGIN RUNTIME après lui, après une modification envoie la même demande de sauvegarde Global que WRITE, avec Writing... environ une seconde. Quitter BLECH après modification écrit ses réglages comme WRITE. Sans changement, pas d’écriture. Les patterns restent soumis à WRITE. OFF : seule WRITE sauvegarde. Immédiat, ON par défaut ; OFF bit 7 de l’octet 5, fichier refusé par BLECHTRIBE antérieur à 1.5. La désactivation d’AUTO SAVE elle-même exige WRITE pour être conservée. [Mesure](messungen/2026-11-09-auto-save.md) |
| DATA UTILITY, SET INIT PATTERN | FACTORY ou 1 à 250 : modèle copié par INITIALIZE PATTERN ; FACTORY utilise celui du firmware. Immédiat et persistant après extinction, octet Global 247, sans WRITE. Rouge avec init-pattern. [Mesure](messungen/2026-10-28-init-pattern.md) |

Les résultats, saved, no card, imported, 2 exported, remplacent la valeur jusqu’à une rotation
ou un changement de page. La troisième ligne du firmware, unité à partir de la colonne 28 de
la ligne de valeur, chevaucherait une valeur de plus d’un ou deux caractères. BLECH ne l’utilise
pas : environ 14 caractères dans la valeur et 18 dans le titre.

WRITE sur PLUGIN RUNTIME, FEATURES, CUSTOMIZATION et pour autoriser un plugin externe
sauvegarde `KORG/blechtribe/settings.a.bin` et `settings.b.bin`, en générations alternées.
AUTO SAVE le fait aussi en quittant le menu après modification. Format de 24 à 280 octets,
marqueur `GSET`, version 3 ; bit 0 d’un octet supplémentaire pour METER LOUD RAINBOW,
refusé par BLECHTRIBE antérieur à 1.3. Maximum 64 entrées, contre 16 en version 2 jusqu’à 1.3.7.
Un ancien BLECHTRIBE jusqu’à 1.3.7 ne lit pas la version 3 et reprend un éventuel fichier 2 plus
ancien ou les valeurs par défaut. Les formats 1 et 2 restent lisibles et deviennent 3 au
prochain WRITE.

La liste contient aussi le CRC inversé de chaque plugin désactivé ; un ancien BLECHTRIBE le traite
comme un CRC sans correspondance. Quand elle est pleine, l’entrée la plus ancienne sans
plugin chargé, plugin absent ou ancienne compilation, est supprimée d’abord ; sinon une
autorisation retire l’entrée la plus ancienne. Un marqueur qui ne trouve pas de place manque,
et le plugin peut donc redémarrer à l’allumage suivant.

Sans carte, sans fichier ou avec fichier endommagé, les valeurs par défaut s’appliquent :
fonctions activées, personnalisation d’origine. Résultats : saved, no card, card protected,
folder missing, write error. Ces réglages n’écrivent pas en flash.

**Personnalisation.** L’effet visuel est immédiat, le menu sert d’aperçu. WRITE conserve
l’état au redémarrage ; AUTO SAVE peut aussi le conserver à la sortie comme indiqué plus haut.
Power Save garde sa fonction, extinction des LED inférieures et atténuation du rétroéclairage ;
une retenue `korg.ledHold` reste prioritaire. EXIT à l’allumage restaure l’original.
Les niveaux RGB tous nuls signifient couleurs d’origine.
[Mesures et limites](messungen/2026-10-14-blech-anpassung.md).

L’absence de commutateur d’image de démarrage est volontaire : elle est affichée environ
290 ms avant que la carte soit lisible, trop tôt pour un réglage chargé depuis celle-ci.

## Blechy, dernière page de l’anneau

Blechy est intégré à BLECHTRIBE, pas chargé comme plugin de carte. Sa page est la dernière de
l’anneau EDIT, après Event et BLECH, avant Pattern : 32/32 sur rouge, 31/31 sur bleu.
Depuis la première page Pattern, EDIT gauche y mène. Il apparaît immédiatement, sans sous-menu
ni press Enter, sur tout l’écran ; le numéro de page est masqué.

- EDIT gauche va à BLECH, EDIT droite à Pattern, EXIT à la page principale. Molette, MENU et
  WRITE ne changent rien, comme la molette sur les autres pages de l’anneau.
  [Mesuré dans l’émulateur](messungen/2026-10-15-blechy.md).
- En arrivant, il reste immobile environ une seconde, puis salue : alternance toutes les
  220 ms pendant 1,76 s, quatre oscillations, une fois par arrivée. Quitter puis revenir
  relance le salut. Un tapotement pendant l’attente provoque d’abord la colère, puis le salut.
  Les images `blechy-wave-1.png` et `blechy-wave-2.png` dérivent de la pose calme, seuls bras
  droit et main changent, générés par `tools/art/make_blechy.py`. Ces durées sont des choix
  d’animation, pas des mesures sur le matériel.
- Après le salut, il traverse l’écran à un pixel toutes les 120 ms, environ 10 s d’un bord
  à l’autre, attend une seconde au bord et revient. L’image `blechy-walk.png` descend d’une
  ligne tous les deux pixels, limite du mouvement possible avec cette image. Tapoter ou caresser
  agit aussi pendant la marche ; il reprend ensuite.
- Au bord, il peut parler 3,5 s dans une bulle du côté libre. Première bulle après un peu plus
  de 12 s, suivantes toutes les 20 à 30 s : attente de 8 à 16 s, puis marche jusqu’au bord.
  Les phrases originales restent « yo, na du? », tempo favori compté par temps joué, à défaut
  « mein Tempo ist 150 bpm », durée depuis le premier PLAY ou depuis l’allumage, puis
  « Blech ist mein Ding », « bisschen mehr Bass? », « nicht so doll tippen », « Schranz ist Liebe ».
  La durée utilise les secondes avant une minute. Police propre 5 × 7, ASCII et ä, ö, ü.
  Textes, vitesse et attentes sont des choix non essayés sur l’appareil.
- PLAY le fait rejoindre le centre, un peu à gauche pour laisser la bulle, à deux pixels
  toutes les 70 ms. Il affiche « ich hör mir das kurz an » pendant 2,8 s, attend brièvement,
  puis danse à une image par croche tant que le pattern joue. L’ancienne attente de 12 s
  avant la danse et la question « wat machst'n du da atze? » ne s’appliquent plus.
  STOP termine la danse et reprend la marche.
- Tapoter près de lui sur le pavé le met en colère ; le caresser le rend heureux.
  Tempo favori et durées sont seulement en RAM et repartent de zéro à chaque allumage.
- Il ne figure ni dans GAMES ni dans PLUGINS, n’est pas compté ni exporté par EXPORT ALL PLUGINS,
  ne se désactive pas, ne nécessite ni carte ni `e2sPlugin.all`, et reste avec PLUGIN RUNTIME OFF.
  EXIT maintenu à l’allumage le supprime, avec sa page, et restaure l’anneau d’origine.
- Sur sa page, les plugins de carte ne reçoivent que le pavé tactile, bouton et position.
  Les autres entrées vont au firmware seul ; EDIT et EXIT ne peuvent pas être interceptés.
- Son bloc API 6 de 15476 octets, compilé et vérifié dans le navigateur par `tools/blechy-build.mjs`,
  reste à `0xC0184000` dans l’image. Seules entrée et variables occupent le pool, 15904 octets
  sur 128 Kio, pas le bloc. BLECHTRIBE le charge avant la carte comme application cachée, entrée 0
  d’un groupe sans menu, et exécute son corps. Afficher sa page donne `open` et l’écran ;
  quitter la page donne `close`. La source reste `data/script/blechy-source.mjs`.
  Démarrage d’environ 5,4 millions d’instructions dans l’émulateur, estimé à quelques dizaines
  de millisecondes sur l’appareil ; 70 % pour l’effacement octet par octet du moteur et des
  tables de vérification avec `mem_fill`, 8 % pour le CRC.

## Plugins d’exemple

Les dix applications sont dans le catalogue Plugins et `data/script/presets.mjs`.
Elles ont été exercées dans la VM de référence du navigateur avec entrées par
`test/script-plugins.test.mjs`, **pas vérifiées sur l’appareil**. Les coûts ci-dessous
sont les maxima observés par gestionnaire. Les durées sont **déduites** : 542 unités pour
Snake ont pris 0,103 ms dans l’émulateur, soit un avertissement de 0,5 ms vers 2630 unités.
Les tests vérifient cette borne pour les applications concernées ; le temps par unité
sur le matériel peut différer. Les lecteurs d’images dépassent cette borne comme indiqué.

| Application | Groupe | Commandes | Bloc | Gestionnaire le plus coûteux |
|---|---|---|---|---|
| BLECH Clicker | GAMES | Chaque pad incrémente le compteur et secoue le cristal ; compteur conservé avec `korg.store` | 1720 octets | 1041 unités, 0,20 ms |
| Set-Timer | TOOLS | Grand affichage mm:ss, puis h:mm:ss après une heure ; bouton 1 démarre, bouton 4 réinitialise après confirmation | 1996 octets | 2434 unités, 0,46 ms pour dessiner les chiffres ; 201 sans changement, rien par trame si fermé |
| Snake | GAMES | Part gauche et droite tournent | 1180 octets | Ouverture 2215 unités, trame 537 |
| Tetris | GAMES | Part gauche/droite déplacent, Edit droite tourne, Edit gauche maintenu accélère la chute, tout bouton redémarre après la fin | 3772 octets | 2305 unités, 0,44 ms |
| Game of Life | GAMES | Pavé tactile pour les cellules ; 1 démarre/pause avec LED, 2 avance d’une génération, 3 efface, 4 remplit aléatoirement | 2184 octets | 2484 unités, 0,47 ms |
| Pong | GAMES | Hauteur du doigt sur le pavé, Part gauche monte, Part droite descend, encodeur ; premier à 9. Balle et adversaire ne bougent qu’une trame sur deux pour rester visibles sur l’écran lent | 2120 octets | 1221 unités, 0,23 ms |
| Simon | GAMES | Les 16 pads jouent une séquence à reproduire, allongée d’un pas par tour. Durée de pas 0,72 s, raccourcie tous les quatre tours, minimum 0,4 s. L’écran indique tour, pas et action. Erreur de pad termine ; TAP ou pad relance | 2268 octets | Trame 1673 unités maximum à la fin, ouverture 1644 |
| Mandelbrot | GAMES | Pavé pour déplacer, Part droite et encodeur pour zoomer, Part gauche pour dézoomer ; 1/2 règlent 8 à 64 itérations, TAP réinitialise | 2436 octets | 2135 unités, 0,41 ms |
| GIF Player | TOOLS | Fichiers GIF00.E2G à GIF99.E2G de la carte ; encodeur choisit, Part gauche/droite divisent ou multiplient la vitesse par deux entre 25 et 400 %, TAP met en pause. Fichier absent signalé ; chaque image reste au moins 40 ms | 972 octets | 3762 unités par trame, environ 0,72 ms, dont image 3086 ; au-dessus de l’avertissement de 0,5 ms |
| Image Viewer | TOOLS | Images d’un fichier E2G une par une, par exemple plusieurs BMP réunis par `tools/gif/gif2e2g.py`. Part droite/gauche avancent/reculent en boucle ; encodeur change de fichier. Numéro comme 2/3 visible deux secondes après chaque changement ; total connu après parcours du fichier. TAP garde ou masque l’indication. Recul de la première vers la dernière seulement après découverte du nombre d’images | 1128 octets | 4414 unités maximum, deux lectures et dessin au-delà de la dernière image ; environ 0,84 ms déduit, au-dessus de 0,5 ms |

**Set-Timer** utilise `korg.millis()`, actualisé même application fermée. Il n’écoute que
`play`, boutons, `open`, `close` ; fermé, quelques opérations par bouton et aucune par trame.
Ouvert, seuls les chiffres changés sont redessinés. Le premier passage en PLAY démarre ;
ensuite PLAY/STOP ne changent rien. Il n’appelle ni `korg.play`, ni `korg.stop`, ni `korg.led`,
et ne lit pas les pads. Les boutons 1 et 4 n’agissent qu’ouvert. Après réinitialisation,
un nouveau PLAY nécessite une transition, donc un STOP préalable. Aucun stockage :
extinction, désactivation ou redémarrage interrompent ou remettent le compteur à zéro.

**Game of Life** stocke 32 cellules d’une ligne dans un entier de 32 bits et calcule la
ligne suivante en parallèle par opérations binaires. L’image est actualisée cellule par
cellule avant la génération suivante, afin de limiter chaque trame.
**Mandelbrot** utilise 14 bits fractionnaires, 1,0 vaut 16384, sans flottants. Quatre passes,
blocs de 8, 4, 2 puis 1 pixel ; un calcul de pixel trop long reprend à la trame suivante.
Premières images après une à trois secondes, image complète vers 3400 trames, un peu plus
de deux minutes comptées dans l’émulateur. Toute entrée reprend la passe grossière.
Zoom limité à 7 par la précision des 14 bits.

**BPM Glide** fonctionne en arrière-plan sans application. Avec Chain To et CHAIN MODE,
il fait glisser le tempo initial vers le tempo enregistré du prochain pattern sur
longueur × Chain Repeat. Le dernier pas atteint la cible sans saut au changement.
La chaîne est lue au premier pas après PLAY ou changement, lorsque la RAM est à jour.
STOP restaure le tempo initial. Page BPM GLIDE, 1 activé/0 désactivé, conservée avec
`korg.store`. `korg.tempo` modifie le pattern en RAM, donc celui-ci est non enregistré
jusqu’à STOP. Vérifié dans le simulateur, `test/script-bpm-glide.test.mjs`, pas sur l’appareil.

**Momentary Mute** exige l’API 15 et fonctionne en arrière-plan, comme le comportement
souhaité sur ESX. Les pads ne basculent les états muets que pendant PART MUTE ; relâché,
ils jouent et s’affichent comme TRIGGER. Le firmware conserve son mode après relâchement,
mesuré dans l’émulateur : le plugin presse seulement TRIGGER à ce moment avec `korg.pressKey`,
sans retenir boutons ni pads. TRIGGER s’allume donc. SHIFT + PART MUTE garde son fonctionnement ;
un autre mode choisi pendant le maintien est conservé. Page MOMENT MUTE, 1/0 ; désactivé,
PART MUTE reste un mode normal. `korg.store` conserve le réglage. Vérifié dans le simulateur,
`test/script-moment-mute.test.mjs`, et l’émulateur sur les trois firmwares,
`tools/emu/plugin_catalog15_cases.py`, pas sur l’appareil.
[Contexte](ideen/91-moment-mute.md).

**Filter Toggle**, ancien plugin API 14 jusqu’au 2026-11-08, est maintenant intégré :
SHIFT + LPF/HPF/BPF désactive le filtre de la partie sélectionnée ; la même combinaison
retrouve son dernier type, une autre retrouve le dernier type de ce bouton, par partie.
La fonction du firmware affiche FILTER TYPE, aussi sur bleu. Réglage BLECH > FEATURES >
FILTER TOGGLE ; plus dans le catalogue. Un ancien plugin encore présent et fermé réapplique
une trame plus tard le même type ; ouvert, il intercepte SHIFT + filtre et agit seul sans
fenêtre, déduit du code, non mesuré. Retirer l’ancien plugin ou désactiver la fonction intégrée.
[Mesure](messungen/2026-11-08-filter-toggle-eingebaut.md).

**Gate Hold**, API 15 en arrière-plan, garde en Gate Arp la note du premier contact :
`korg.touchLockX` fige X pour le firmware, Y suit le doigt. Le déplacement X choisit ensuite
le rythme Gate Arp du pattern, page GATE ARP de 0 à 49, par `korg.seq.setPatternValue`.
Lever le doigt restaure le rythme initial ; changer de pattern pendant le contact retient
celui du nouveau pattern. GATE ARP active le mode, MASTER FX et TOUCH SCALE le quittent ;
SHIFT + GATE ARP et SHIFT + MASTER FX ouvrent seulement leurs pages, mesuré dans l’émulateur.
Le plugin suit ces boutons et laisse Master FX/Touch Scale tranquilles. Page GATE HOLD, 1/0.
Une trame dure 40 ms : un mouvement durant les 40 premières ms peut encore atteindre le
firmware, déduit. Vérifié dans `test/script-gate-hold.test.mjs` et dans l’émulateur sur les
trois firmwares, `tools/emu/plugin_catalog15_cases.py`, pas sur l’appareil.
[Idée](ideen/72-gate-arp-note-halten.md), [mesure](messungen/2026-11-03-plugin-api15.md).

**Key Pads**, ancien plugin API 15 jusqu’au 2026-11-07, est intégré sous KEY PADS :
KEYBOARD maintenu + pad règle chromatiquement KEY, pad 1 C, 2 C#, jusqu’à 12 B ;
13 à 16 ne font rien. La fenêtre du firmware indique la valeur. Réglage BLECH > FEATURES >
KEY PADS ; plus dans le catalogue. [Mesure](messungen/2026-11-07-key-pads-eingebaut.md),
[ordre chromatique](messungen/2026-11-08-key-pads-chromatisch.md).

**Step Copy**, API 15 en arrière-plan, copie les 16 pas d’une mesure dans une autre du
pattern en lecture, longueur de 1 à 4 mesures. Pages STEP COPY FROM (1 à 4), STEP COPY TO
(1 à 4, 0 pour toutes les mesures après la source jusqu’à la longueur), STEP COPY
(1 partie sélectionnée, 2 toutes les 16 parties, 0 aucune action). Laisser la molette
0,6 s sur 1 ou 2 exécute ; les valeurs traversées ne copient pas. Revenir à 0 puis 1/2 pour répéter.
Copie activation, quatre notes, vélocité, gate et déclenchement via `korg.read.patternBytes`
et `korg.seq.writeSteps`. Une cible au-delà de la longueur l’allonge avec
`korg.seq.setPatternValue`, fonction LENGTH du menu ; le choix toutes les mesures après
ne l’allonge pas. Source hors longueur ou identique à la cible : aucune copie.
Motion sequence et paramètres de partie ne sont pas copiés : l’API lit les octets de motion,
mais ne les écrit pas. WRITE reste nécessaire. Le firmware d’origine a COPY PART dans
Part Util 1/4 et CLEAR SEQUENCE, pas de copie de mesure dans le pattern selon la
[liste mesurée](tastenkombinationen.md). Vérifié dans `test/script-step-copy.test.mjs`
et `tools/emu/plugin_catalog15_cases.py`, trois firmwares, pas sur l’appareil.

## Page Plugins de l’éditeur

Quatre pages : Catalogue, Mes plugins, Éditeur, Documentation. Le titre du fil d’Ariane
revient au catalogue.

**Catalogue.** Cartes des applications GAMES et TOOLS décrites ci-dessus et des plugins
Lauflicht, Pulsieren, Takt-Blinker, Momentary Mute, Gate Hold, Step Copy, dans
`data/script/presets.mjs`. Chaque carte montre l’écran après quelques trames, titre,
catégorie, description et auteur. La carte ouvre une page avec image, description,
catégorie, auteur, date et commandes ; téléchargement, transfert vers l’appareil et
ouverture comme plugin personnel. Aperçu et Code basculent entre simulation de l’Electribe
et source. Un ajout au catalogue se fait par pull request avec l’entrée correspondante.

**Mes plugins.** Cartes des plugins du navigateur, boutons de création, ouverture et
sauvegarde de tous. Une carte ouvre l’éditeur.

**Éditeur.** Pleine page, numéros de ligne, compilation et diagnostics ligne/colonne ;
un clic place le curseur sur l’erreur. Ouvrir et Enregistrer en haut, aperçu,
téléchargement et transfert sous le code. L’aperçu masque l’éditeur ; un clic à côté
ou sur X le ferme. La console est une section indépendante sous Appareil.
Les plugins personnels restent dans `localStorage`, sans quitter le navigateur.
Le nom de bloc utilise ASCII, commence par une lettre et comporte au maximum 15 caractères.

**Création.** Le dialogue demande le nom et le type : application GAMES, application TOOLS
avec `korg.app(name, group)`, ou arrière-plan sans écran ni entrée de menu. Le nom choisi
est aussi celui de l’application dans BLECH. Les modèles sont courts et fonctionnels,
avec `frame`, `buttonPress` et, pour les applications, `open`, ainsi que des constantes
comme `korg.key.TAP` et commentaires du modèle. Sources : `data/script/templates.mjs` ;
`test/script-templates.test.mjs` compile, essaie et vérifie nom et groupe.

**Édition du code.** CodeMirror 6, `site/app/script-editor.mjs`, bundle livré dans
`site/vendor/codemirror.mjs` : aucun chargement réseau, fonctionnement hors ligne.
Reconstruction avec `npm install`, puis `npm run build:codemirror`.

- Coloration des mots JavaScript, chaînes, nombres et commentaires ; `korg` et constantes
  de boutons/LED distincts. Numéros de ligne verts pour exécuté pendant l’essai, jaunes
  pour jamais exécuté, rouges pour erreur. Les exemples sont en lecture seule mais
  copiables ; l’ouverture comme plugin personnel crée une copie modifiable.
- Complétion après `korg.disp` avec paramètres, description traduite, plages et contextes.
  Entrée insère des champs, Tab passe au suivant. Après `korg.key.` et `korg.led.`,
  constantes avec numéro et inscription ; dans `korg.onEvent("`, événements et arguments,
  avec insertion du gestionnaire ; second argument de `korg.app`, groupes disponibles.
  Après `korg.menu.blech.`, chaque point propose ses branches ; une feuille affiche plage, écriture
  autorisée et version d’API. Les temporisateurs insèrent `() => { }`. Ctrl+Espace ouvre
  manuellement, Échap ferme.
- Aide au paramètre au-dessus du curseur, syntaxe et plage de l’argument courant.
  Survol d’un nom, événement ou argument de gestionnaire : même description. Un nombre
  reconnu comme bouton ou LED affiche son nom.
- Erreurs soulignées et listées sous le code, accessibles au clic. Chemin mal orthographié,
  feuille en lecture seule ou constante hors plage, comme `...display.intensity = 300`,
  sont signalés pendant la saisie avec le diagnostic du compilateur.
- Tab permet de quitter l’éditeur, sans piège de focus. Retrait avec Ctrl+] et Ctrl+[,
  Cmd sur Mac ; annulation avec Ctrl+Z. L’éditeur et la liste de complétion sont nommés
  et accessibles aux lecteurs d’écran.

Les fonctions, événements et valeurs viennent de `data/script/contract.mjs`, descriptions
traduites via `data/script/describe.mjs`, noms via `data/script/names.mjs`, arbre via
`data/script/objects.mjs`. `src/script/editor-model.mjs` construit complétion, aide et survol.
Un test impose une description par fonction/événement ; un autre parcourt chaque feuille
point par point. Une nouvelle feuille apparaît donc sans autre ajout dans la complétion.

**Aperçu.** `src/script/sim.mjs` simule l’appareil sur la VM de référence, écran 128 × 64,
police d’aperçu, pas celle du firmware, registre de LED et horloge en ms, une trame de 40 ms.
Boutons, pads, potentiomètres, encodeurs et pavé transmettent leurs événements.
L’écran montre le propriétaire, application ouverte ou plugin ayant pris l’écran, sinon
rien, là où l’appareil montrerait la page principale du firmware. Une application s’ouvre
comme avec ENTER ; la liste GAMES/TOOLS sous l’écran permet l’ouverture et EXIT ferme
avant transmission au plugin. Ce n’est pas le firmware : seul le budget de calcul s’applique,
pas la limite temporelle. Le vrai moteur dans le firmware est vérifié dans l’émulateur.

**Entrées et essai.** L’enregistrement mémorise les entrées avec leur numéro de trame.
L’essai charge le bloc dans une simulation neuve, rejoue ces entrées pendant au moins
100 trames et indique les lignes jamais exécutées. Une application est ouverte d’abord.
Sans entrée enregistrée, seuls `ready`, `open` et `frame` s’exécutent.

**Export.** Le fichier `.blech` avec source et la collection `e2sPlugin.all` de tous les
plugins exigent un essai de ce texte exact, vérifié par `src/script/gate.mjs`.
Toute modification invalide l’essai. Les lignes non exécutées provoquent une demande
unique de confirmation avec leur liste. Une erreur d’essai bloque l’export.

**Console.** `run("name")` lance un plugin personnel ou du catalogue dans l’aperçu.
Une ligne commençant par `korg.`, par exemple `korg.display.text("Hi", 0, 0)`, est exécutée
une fois comme code de plugin, application einzeiler dans TOOLS ouverte par l’aperçu.
Le reste est du JavaScript ordinaire avec la bibliothèque `KORG` pour l’émulateur.

## État des vérifications

Les mentions mesuré, déduit et ouvert ont le même sens que dans les mesures citées.

### Dans l’émulateur

Les résultats suivants proviennent du firmware réel 2.02 avec Hacktribe dans l’émulateur
avec carte virtuelle, ou d’Unicorn sans firmware, **pas de l’appareil**.

- Compilateur, vérificateur et VM JavaScript dans `src/script/`, page Plugins, exécution,
  essai et export : tests `test/script-*.test.mjs`, format de bloc 2, API 25.
- VM ARM `tools/patch/script_vm.s` : les 34 opcodes, 506 comparaisons identiques à la VM JS.
  [Mesure](messungen/2026-10-14-skript-arm-vm.md).
- Filtre d’entrée et point d’interception des trames `tools/patch/script_hooks.s` :
  tampon de 64 places, 25 Hz, budget partagé de 5 ms ; seul le plugin fautif s’arrête,
  firmware utilisable. [Mesure](messungen/2026-10-14-skript-haken.md).
- `korg.led` : `ready` transmet une fois zéro ; un appui transmet 255 puis 0, un paquet
  par valeur ; les 88 LED demandées ensemble produisent 88 paquets.
  [Mesure](messungen/2026-10-14-skript-led.md).
- Écran : 70 cas identiques au modèle navigateur à l’octet près, y compris les erreurs ;
  menus du firmware visibles. [Mesure](messungen/2026-10-14-skript-display.md).
- Chargeur : deux blocs chargés et exécutés, un bloc endommagé isolé ignoré. CRC, marqueur
  ou fichier tronqué invalides et EXIT à l’allumage laissent démarrer le firmware original.
  [Mesure](messungen/2026-10-14-skript-karte.md).
- Valeurs persistantes : compteur conservé après extinction/allumage via la carte virtuelle.
  [Mesure](messungen/2026-10-14-skript-speicher.md).
- Écriture des pas `tools/patch/script_seq.s` : notes écrites pendant la lecture,
  jouées dans l’ordre par la sortie MIDI de l’émulateur, octets identiques au modèle
  navigateur et pads actualisés. Pas d’écoute sur appareil.
  [Mesure](messungen/2026-10-26-plugin-steps.md).
- Horloge, lecture, actions, événements du séquenceur, rétroéclairage et retenue de LED.
  Le firmware ne proposant que la bascule muette, `korg.mute` lit d’abord l’état.
  [Mesure](messungen/2026-10-14-skript-hardware.md).
- Snake ouvert depuis le menu : 150 trames, RAM écran identique au modèle navigateur,
  `frame` au plus 0,103 ms. [Snake](messungen/2026-10-14-skript-snake.md),
  [applications](messungen/2026-10-14-plugin-apps.md).
- Applications : chargement sans dessin, ouverture GAMES/TOOLS puis dessin, EXIT ferme
  et retrouve la page principale pixel pour pixel. EXIT non interceptable, y compris
  avec `korg.display.take()` ; dessin sans écran ignoré.
  [Mesure](messungen/2026-10-14-plugin-apps.md).
- Blechy intégré sans carte, dernière page, salut après environ une seconde à chaque
  arrivée, tapotement, caresse, danse pendant lecture, bulle à STOP, EDIT/EXIT fonctionnels,
  absent avec EXIT à l’allumage ; trame maximale 0,28 ms.
  [Mesure](messungen/2026-10-15-blechy.md).
- Menu BLECH : groupes, compteurs, retour d’un niveau, WRITE, MENU/ENTER, réglages, plugins,
  applications, exports et modèle initial dans DATA UTILITY, PLUGIN RUNTIME dans GLOBAL,
  SYNC GROUP après CHAIN REPEAT, MANAGE PLUGINS, externes et `korg.menu.add`.
  Aucune troisième ligne, test de chevauchement pour chaque page.
  [Mesure](messungen/2026-10-14-blech-menue.md).
- Jeu de patches `data/patches/blech.json`, éditeur d’image initiale, MFX 2, moteur et menu
  de plugins, dossier blechtribe, image BLECH : construction et vérification dans l’émulateur.
  [Fichier pour l’appareil](geraetetests/blech-datei.md).

### Sur l’appareil

Le firmware avec moteur fonctionne sur l’appareil de mesure du projet. Le menu BLECH,
le chargement depuis PLUGIN EDIT et EXPORT ALL, anciens noms et emplacement sous PLUGINS
jusqu’à 1.3.7, ont été utilisés. Depuis 1.3.8, MANAGE PLUGINS et EXPORT ALL PLUGINS dans
DATA UTILITY n’ont pas encore été utilisés sur l’appareil selon ces mesures.
Le chargement et l’export ont utilisé `e2sPlugin.all` ; `korg.store` a lu et écrit
`store.a.bin` et `store.b.bin` sur sa carte.
Personnalisation, FEATURES, SPLASH IMPORT et DRAW ont aussi été utilisés.
Les demandes issues de ces essais figurent dans les mesures à partir du 18 octobre :
[plugin restant désactivé](messungen/2026-10-18-plugin-bleibt-aus.md),
[liste d’import](messungen/2026-10-19-plugin-import-liste.md),
[synchronisation et menus](messungen/2026-10-22-sync-und-menues.md).
Chaque mesure distingue ses essais sur émulateur des essais matériels.
Les procédures de vérification sont dans [carte](geraetetests/karte.md) et
[fichier firmware](geraetetests/blech-datei.md), en allemand.

### Points ouverts

- Temps réel par trame face au budget de 5 ms : non mesuré séparément sur appareil.
  Environ 0,17 ms pour une trame Snake est déduit. Écoute de coupures avec musique et Snake,
  rétroéclairage sur piles avec Power Save Auto, et retenue de LED restent à vérifier.
- Période d’une seconde de Timer3 mesurée dans l’émulateur, pas lue sur le matériel.
- Point d’interception `save` installé mais non déclenché dans l’émulateur, WRITE Global
  écrivant en flash ; effet vérifié seulement par test unitaire.
- Une écriture réelle sur carte peut dépasser une trame ; durée non mesurée. La restriction
  à l’écran principal protège contre les accès concurrents du firmware. Les observations
  historiques n’ont pas exercé l’absence du dossier `KORG/blechtribe/` dans ce scénario.
- Chargeur non vérifié avec un vrai `e2sSample.all`, aucune donnée Korg ne pouvant être
  incluse dans le dépôt. Le point d’interception vient d’un prototype mesuré avec un vrai
  fichier. [Carte SD virtuelle](hintergrund/virtuelle-sd.md).
- La borne de 400 paquets LED/s suppose environ 25 Hz. Un index définitivement refusé
  bloque les autres LED sans message. Désactiver les interruptions suppose le mode privilégié.
  [Mesure](messungen/2026-10-14-skript-led.md).
- Aucun commutateur d’image initiale ; noms longs tronqués ; MANAGE PLUGINS limite à 64
  fichiers et affiche LIST FULL. Ouverture avec beaucoup de fichiers non chronométrée
  sur appareil, 0,9 s pour 64 dans l’émulateur.
  [Menu](messungen/2026-10-14-blech-menue.md),
  [64 fichiers](messungen/2026-10-30-plugin-liste-64-entfernen.md).
- Les pages GLOBAL/DATA UTILITY appartiennent à BLECH et sont atteintes aux extrémités par
  les interceptions EDIT des écrans 9 et 15. DATA UTILITY utilise une machine à 40 états
  dans `0xC0061A24` ; y ajouter des pages nécessiterait des états propres.
  [Mesure, section DATA UTILITY](messungen/2026-10-14-blech-menue.md).
  Aucun chargeur de `e2sCustom.all` au démarrage.
- Ouverture/fermeture des applications, redessin de la page principale et boutons de
  l’application ouverte ont été exercés seulement dans l’émulateur.
- Surcoût des opérandes de 16 bits du format 2 déduit, pas mesuré séparément.

### Code source

Le nom interne reste `script` : `src/script/`, `data/script/`, `site/app/scripts.mjs`,
`tools/patch/script_*.s`. L’interface est `korg.*`. Les fichiers de mesure conservent `skript`
dans leur nom, comme `docs/messungen/2026-10-14-skript-*.md`.
Sur l’appareil, dans l’éditeur et dans cette documentation, le terme est plugin.
