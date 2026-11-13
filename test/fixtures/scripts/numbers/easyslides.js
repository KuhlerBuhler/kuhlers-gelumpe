// EASY SLIDES v1 by alarykko, from the BLECH Discord: a TIE step (gate above 96) and the step after it get more glide,
// so the two notes slide. SHIFT + PITCH/GLIDE sets the base glide of the selected part. In the catalog the glide acts
// only on the parts whose glide it saved, 1 to 8 (maxParts), and STOP puts those back: the original also wrote parts 9
// to 16 on every step and set their glide to 0.
//Ancora da sistemare, implementare migliore logica per far si che glide rimanga attivo sia nello step con TIE e quello successivo così da dare il tempo alla nota di slideare

const baseGlide = new Array(16);
const pitchGlideKnobIndex = 2;
const maxParts = 8;
const glideOnTies = 35;
let shiftPressed = 0;


//Per evitare argomenti fuori da quelli ammessi
function limitUnsigned (value){
  if(value > 127) return 127;
  if(value < 0) return 0;
  return value;
}


function setNewBases(){
  for(let part = 0; part < maxParts; part++){
      baseGlide[part] = korg.parts[part].glide;
  }
}



function applySlide() {
  const stepCount = 64;
  
  //per ogni parte
  for (let part = 0; part < maxParts; part++) {

    const currentStep = korg.read.step(part);
    const previousStep = ((currentStep - 1) % stepCount + stepCount) % stepCount;
    const currentNote = korg.seq.getNote(part, currentStep, 1);
    const previousNote = korg.seq.getNote(part, previousStep, 1);
    
    
    //se lo step è tie oppure quello prima è tie applica il glide, in questo modo si da il tempo alla frequenza di glideare
    if (korg.seq.getGate(part, currentStep) > 96  || korg.seq.getGate(part, previousStep) > 96)   {
      korg.parts[part].glide = limitUnsigned(baseGlide[part] + glideOnTies); 
    }
    else korg.parts[part].glide = baseGlide[part];
  }
}






korg.onEvent("ready", () => {
    
    //registra i baseGlide all'accensione
    setNewBases();
    korg.display.popups(0);
    
});

korg.onEvent("patternChange", () => {
    setNewBases();
});


korg.onEvent("buttonPress", (key) => {
     
    //restora i glide correnti ai base, per evitare che se pausato proprio durante un accent cambino i baseGlide
    if(key == 1){
      for(let part = 0; part < maxParts; part++){
        korg.parts[part].glide = baseGlide[part];
      }
    }

    //semplice flag per shift premuto
    if(key == 10) shiftPressed = 1;
    
});



korg.onEvent("buttonRelease", (key) => {

  //idem come sopra con patate  
  if(key == 10) shiftPressed = 0;
    
});


korg.onEvent("step", () => {

    //applica lo slide ad ogni step
    applySlide();

});

//aggiorna i baseGlide quando giri il knob pitch tenendo premuto shift
korg.onEvent("knob", (index, value) => {
    
    let part = korg.read.part();    
    if(index == pitchGlideKnobIndex && shiftPressed == 1) baseGlide[part] = (value/2);
    
});
