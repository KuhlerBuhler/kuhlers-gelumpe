Brouillon, partie des notes de 1.6.0 (API des plugins pour l’enregistrement intégré).

**Nouveautés pour les développeurs**
- API des plugins 41 :
  - `korg.audio.capture(25)` prend le Master, le mélange que le firmware envoie à la sortie. Pendant l’enregistrement intégré, le Master partage sa capture ; toute autre source renvoie alors 2 (occupé). Sampler seulement (Hacktribe et rouge), 6 sur le bleu.
  - Nouvelles valeurs en lecture seule : `korg.record.running`, `korg.record.seconds`, `korg.record.gaps`.
- Les apps qui captent le son (comme Spettro) se ferment toujours pendant un enregistrement ; seuls les plugins en arrière-plan partagent le Master.
