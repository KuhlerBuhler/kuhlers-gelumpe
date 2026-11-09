# Plugins pour l’Electribe

Version française | [Référence complète en anglais](plugins.en.md) | [Référence allemande](plugins.md)

Un plugin ajoute une fonction à l’Electribe : jeu, animation de LED, commande ou
page de menu. L’éditeur compile un sous-ensemble de JavaScript en bytecode, puis
le firmware exécute ce bytecode. Une erreur arrête le plugin et affiche son état
dans le menu BLECH ; l’Electribe continue de fonctionner.

Ce guide explique les parcours de l’éditeur et les bases de la programmation.
La référence anglaise décrit toutes les signatures de fonctions et les mesures
réalisées dans l’émulateur. Les noms inscrits sur l’appareil et les identifiants
du code restent ceux du firmware.

## Utiliser les plugins

### Catalogue

Ouvre la section Plugins, puis le catalogue. Une fiche présente la description,
la prévisualisation et le code du plugin. La prévisualisation tourne dans le
navigateur. Elle permet d’essayer le comportement avant de préparer le fichier
pour l’Electribe.

Les plugins personnels restent dans le stockage local du navigateur. Exporte une
copie de ceux que tu veux conserver avant de supprimer les données de l’application
ou de changer de navigateur.

### Éditeur

Crée un plugin ou ouvre un fichier existant. Les diagnostics indiquent la ligne et
la colonne du problème. Corrige les erreurs de compilation avant de continuer.
Les noms de fonctions, d’événements et de constantes ne se traduisent pas : garde
par exemple `korg.onEvent`, `buttonPress` et `korg.key.TAP` tels quels.

La prévisualisation ne remplace pas une vérification sur l’appareil. Un comportement
mesuré dans l’émulateur n’est pas automatiquement confirmé sur le matériel.

### Carte SD et chargement

Les plugins sont chargés au démarrage depuis la carte SD. Le fichier de collection
est `KORG/blechtribe/Plugin/e2sPlugin.all`. Utilise l’export de l’éditeur pour
préparer les fichiers plutôt que de modifier leur structure binaire à la main.

Les plugins démarrent dès leur chargement. Un plugin qui ne fait que modifier des
LED ou traiter des boutons n’a pas besoin d’ouvrir une application à l’écran.
Un plugin externe peut nécessiter une autorisation dans le menu BLECH.

### Réglages et sauvegarde

Dans le menu BLECH de l’appareil, tourner le bouton applique immédiatement les
réglages concernés. Pour les conserver, appuie sur WRITE depuis la page de réglage
et vérifie que « saved » apparaît. La carte SD doit être insérée et accessible.
Les réglages sont enregistrés dans `KORG/blechtribe/settings.a.bin` et
`KORG/blechtribe/settings.b.bin`, pas dans la mémoire flash.

## Programmer un plugin

### Structure

Le code placé au premier niveau s’exécute une fois au démarrage. Il initialise les
variables et déclare les gestionnaires d’événements. Ensuite, chaque gestionnaire
s’exécute lorsque son événement survient.

```js
korg.app("Compteur", "TOOLS");
let count = 0;

function show() {
  korg.display.clear();
  korg.display.number(count, 4, 16);
}

korg.onEvent("open", () => show());
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) { count += 1; show(); }
});
```

`korg.onEvent` se déclare au premier niveau, avec un gestionnaire par événement
et par plugin. Le gestionnaire peut être une fonction fléchée ou le nom d’une
fonction. Il peut recevoir moins d’arguments que l’événement n’en fournit.

### Applications et écran

L’écran appartient au firmware. Pour créer une application, déclare au premier
niveau `korg.app("Nom", "TOOLS")` ou `korg.app("Nom", "GAMES")`. Le nom comporte
de 1 à 15 caractères ASCII.

L’application apparaît dans le groupe TOOLS ou GAMES du menu BLECH. ENTER l’ouvre
et déclenche `open`. Elle reçoit alors les événements `frame` et peut dessiner.
EXIT la ferme, déclenche `close` et rend l’écran au firmware. Le plugin ne peut
pas intercepter EXIT.

Les gestionnaires du plugin fonctionnent aussi lorsque son application est fermée,
mais `frame` n’arrive que lorsqu’elle est ouverte. PLAY, STOP et REC continuent
de commander le séquenceur pendant que l’application est ouverte.

Un plugin sans application peut demander temporairement l’écran avec
`korg.display.take()` depuis un événement. La fonction renvoie 1 en cas de succès,
sinon 0. `korg.display.release()` ou EXIT rend l’écran au firmware. Ne prends pas
l’écran simplement pour commander des LED.

### Langage

- Les nombres sont des entiers signés sur 32 bits. La division tronque vers zéro.
- `true` vaut 1 et `false` vaut 0.
- Déclare les variables avec `let` et `const`.
- Les tableaux ont une taille fixe et des indices à partir de 0.
- Les fonctions sont déclarées au premier niveau et ne peuvent pas être récursives.
- Les conditions, boucles `while` et `for`, `break`, `continue` et `return` sont disponibles.
- Les chaînes sont courtes et ne prennent pas en charge la concaténation.
- Les nombres décimaux, objets personnels, exceptions et chaînes de modèle ne sont pas disponibles.

Les textes de l’écran du firmware ont un jeu de caractères limité. Une interface
française sur l’ordinateur ne signifie pas que l’écran de l’Electribe peut afficher
tous les caractères français. Utilise du texte ASCII dans les exemples destinés
à l’appareil.

### Événements

| Événement | Utilisation |
|---|---|
| `open`, `close` | Ouverture et fermeture de l’application ou de la prise d’écran |
| `frame` | Dessin pendant que l’application est ouverte |
| `buttonPress`, `buttonRelease` | Appui et relâchement d’un bouton |
| `pad` | Jeu sur les pads |
| `knob`, `encoder` | Mouvement d’un potentiomètre ou encodeur |
| `partChange` | Changement de partie |
| `mute` | Changement de l’état muet d’une partie |
| `tempo` | Changement de tempo |
| `save` | Sauvegarde des paramètres globaux ou extinction |
| `menu` | Modification d’une page ajoutée par le plugin |

Consulte la référence anglaise pour les arguments de chaque événement. Les
gestionnaires sont activés lorsque l’initialisation s’est terminée sans erreur.

### Dessiner et commander les LED

`korg.display.clear()` efface le dessin. `korg.display.text` affiche du texte et
`korg.display.number` un nombre. Le plugin doit posséder l’écran pour que ces
appels dessinent quelque chose.

Pour les textes, laisse une marge de 4 pixels à gauche et à droite, et de 2 pixels
en haut et en bas. Une image ou un terrain de jeu peut utiliser toute la surface.

`korg.led` commande une LED par son numéro ou une constante telle que
`korg.led.TAP`. Les constantes évitent de confondre le numéro d’un bouton et celui
de sa LED.

### Valeurs conservées

Les variables ordinaires sont réinitialisées au démarrage du plugin. Les valeurs
de `korg.store` sont conservées sur la carte avec `korg.store.save()`. Une
modification en RAM n’est pas, à elle seule, une sauvegarde persistante.

### Noms des boutons et des LED

La table ci-dessous est construite depuis les noms utilisés par le compilateur.
Cherche un bouton, une LED ou une commande pour retrouver son identifiant exact.
Les inscriptions de l’appareil, comme TAP et PART MUTE, restent inchangées.

## Vérifications et limites

Une compilation réussie confirme que le code respecte le langage pris en charge.
La prévisualisation permet d’observer son comportement dans le navigateur.
L’émulateur vérifie son exécution dans le firmware. Seul un essai sur l’appareil
confirme son comportement réel, notamment le son et les interactions physiques.

Les détails des limites de mémoire, des commandes, du format des fichiers et des
résultats de mesure figurent dans la référence complète. Les données de firmware,
les samples et les sauvegardes de patterns personnels ne font pas partie du dépôt.
