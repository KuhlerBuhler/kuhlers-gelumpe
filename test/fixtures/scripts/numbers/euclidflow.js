/*
 * EUCLID FLOW V1
 * Euclidean Rhythm Generator
 * Korg Electribe 2 / BLECHTRIBE
 * API 9 minimum
 *
 * From SLTK023 on the BLECH Discord. In the catalog the keys act only while the app is open (opened): the handlers of an
 * app run from the start, and TAP with the app closed would otherwise write the rhythm into the part.
 */

korg.app("EUCLID FLOW", "TOOLS");

let opened = 0;
let part = 0;
let hits = 5;
let rotation = 0;
let steps = 16;
let velocity = 100;
let gate = 96;

// Actualise la longueur du pattern
function updateSteps() {
    steps = korg.current.length * 16;

    if (steps < 16) steps = 16;
    if (steps > 64) steps = 64;

    if (hits > steps) hits = steps;
    if (rotation >= steps) rotation = 0;
}

// Affichage sur l'écran de la Korg
function draw() {
    updateSteps();

    korg.display.clear();

    korg.display.text("EUCLID FLOW", 4, 2);

    korg.display.text("PART", 4, 14);
    korg.display.number(part + 1, 38, 14);

    korg.display.text("HITS", 68, 14);
    korg.display.number(hits, 100, 14);

    korg.display.text("STEPS", 4, 26);
    korg.display.number(steps, 44, 26);

    korg.display.text("ROT", 68, 26);
    korg.display.number(rotation, 96, 26);

    korg.display.text("VEL", 4, 38);
    korg.display.number(velocity, 36, 38);

    korg.display.text("GATE", 68, 38);
    korg.display.number(gate, 100, 38);

    korg.display.text("EDIT = HITS", 4, 50);
    korg.display.text("TAP = GENERATE", 4, 58);
}

// Générateur euclidien
function generate() {
    updateSteps();

    let bucket = 0;

    // Efface les déclenchements de cette piste
    korg.seq.clearPart(part);

    for (let i = 0; i < steps; i++) {

        bucket += hits;

        if (bucket >= steps) {
            bucket -= steps;

            let position = i + rotation;

            if (position >= steps) {
                position -= steps;
            }

            let note = 48 + korg.current.key;

            korg.seq.setStep(
                part,
                position,
                note,
                velocity
            );

            korg.seq.setGate(
                part,
                position,
                gate
            );
        }
    }

    draw();
}

// Ouverture de l'application
korg.onEvent("open", () => {
    opened = 1;
    part = korg.selectedPart;

    if (part > 15) {
        part = 0;
    }

    draw();
});

korg.onEvent("close", () => {
    opened = 0;
});

// Commandes physiques
korg.onEvent("buttonPress", (key) => {
    if (opened == 0) return;

    // Choix de la piste
    if (key == 11) {
        part--;

        if (part < 0) {
            part = 15;
        }

        korg.part(part);
    }

    if (key == 15) {
        part++;

        if (part > 15) {
            part = 0;
        }

        korg.part(part);
    }

    // Nombre de coups
    if (key == 8) {
        hits--;

        if (hits < 1) {
            hits = 1;
        }
    }

    if (key == 12) {
        hits++;

        if (hits > steps) {
            hits = steps;
        }
    }

    // Rotation du rythme
    if (key == 4) {
        rotation++;

        if (rotation >= steps) {
            rotation = 0;
        }
    }

    if (key == 6) {
        rotation--;

        if (rotation < 0) {
            rotation = steps - 1;
        }
    }

    // Génération
    if (key == 3) {
        generate();
    }

    draw();
});