BLECHTRIBE 1.5.0 und die App 1.5.0.

**Neu**
- Ladeanimation und Startbild von der Karte
  - Was: die Firmware liest die Ladeanimation aus `KORG/blechtribe/Media/loading.blla`, ohne neue `SYSTEM.VSB` und ohne SOFTWARE UPDATE. Unter BLECH > CUSTOMIZATION > SPLASH stellst du LOADING ANIM ein (CARD, BLECHY oder OFF, NO FILE ohne Datei) und ANIM LOOP. SPLASH IMPORT und SPLASH DRAW speichern das Bild auch als `Media/splash.bmp`, ein neues `splash.bmp` landet beim nächsten Start im Flash. Die Seiten Ladeanimation und Startbild in der App schreiben die Dateien in den gewählten Kartenordner.
  - Gut zu wissen: der Patcher schreibt die Animation nicht mehr in die Firmware. Ohne `loading.blla` spielt Blechy. Rot.

## English

**New**
- Loading animation and start image from the card
  - What: the firmware reads the loading animation from `KORG/blechtribe/Media/loading.blla`, with no new `SYSTEM.VSB` and no SOFTWARE UPDATE. BLECH > CUSTOMIZATION > SPLASH sets LOADING ANIM (CARD, BLECHY or OFF, NO FILE without a file) and ANIM LOOP. SPLASH IMPORT and SPLASH DRAW also save the image as `Media/splash.bmp`, and a new `splash.bmp` goes into flash at the next start. The loading animation and start image pages of the app write the files into the card folder you pick.
  - Good to know: the patcher no longer writes the animation into the firmware. Without `loading.blla` Blechy plays. Red.
