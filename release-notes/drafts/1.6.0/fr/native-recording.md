BLECH 1.6.0 et l’application 1.6.0.

Brouillon : la validation sur appareil et le choix définitif du tampon restent ouverts. Les longs enregistrements ne sont pas encore validés.

**Nouveautés**
- Enregistrement natif sur SD pour les deux firmwares du sampler et le synthé bleu : activer NATIVE RECORDING dans Menü -> BLECH -> FEATURES, puis SHIFT+REC, source RECORD et REC pour démarrer ou arrêter. Sur le synthé, SHIFT+REC ouvre directement RECORD. OFF est la valeur par défaut ; WRITE conserve le réglage.
- Le mix master après MFX et la courbe de saturation, avec AUDIO IN/THRU, est enregistré en WAV stéréo sur le sampler ou mono sur le synthé, à 48 kHz et 16 bits dans `Recordings/REC0001.WAV`. Le métronome reste audible mais n’est pas enregistré. PLAY commande le pattern indépendamment.
- Les noms progressent sans écraser les fichiers existants. Un nouveau fichier commence juste avant 4 Gio. Le nom et la durée affichés concernent le fichier courant.
- Les sauvegardes intermédiaires synchronisent l’audio et la taille du fichier avant de mettre à jour les longueurs WAV. Carte pleine, retrait de carte et rupture de capture donnent une erreur visible ; les ruptures conservent un repère cue nommé.
- Les données des plugins et les réglages attendent pendant l’enregistrement. SAMPLING, RESAMPLING et les applications de capture telles que Spettro restent indisponibles jusqu’à la fermeture du fichier.

L’intégration de Sample Swap, la validation sur appareil et le rapport du testeur bleu restent ouverts. Le lecteur prévu plus tard ne fait pas partie de cette version de l’enregistrement.
