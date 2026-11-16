// BETTER ACCENT v2 by alarykko, from the BLECH Discord, inspired by the TD-3-MO: a step with velocity above 96 is an
// accent and opens the filter through EG INT, DECAY and LEVEL. SHIFT + EG INT, DECAY or LEVEL set the accent values of
// the selected part. It acts on all 16 parts (maxParts = 15, the last part's index); the step handler reads only what it
// needs, so all 16 stay within the watchdog.
const baseEgInt = new Array(16);
const baseDecay = new Array(16);
const baseLevel = new Array(16);
//const baseGlide = new Array(16);
const egIntAccAmount = new Array(16);
const decayAccAmount = new Array(16);
const levelAccAmount = new Array(16);
//const glideOnTies = 40;



const maxParts = 15;
const defaultVelocity = 96;
const stepCount = 64;


const levelKnobIndex = 0;
//const pitchGlideKnobIndex = 2;
const egIntKnobIndex = 4;
const decayKnobIndex = 8;


let shiftPress = 0;
let lastMillis = 0;




//setta le basi
function setNewBases(){
  for(let part = 0; part <= maxParts; part++){
    baseEgInt[part] = korg.parts[part].egInt;
    baseDecay[part] = korg.parts[part].decay;
    baseLevel[part] = korg.parts[part].level;
    //baseGlide[part] = korg.parts[part].glide;
  }
}


function restoreBases(){
  for(let part = 0; part <= maxParts; part++){
    korg.parts[part].egInt = baseEgInt[part];
    korg.parts[part].decay = baseDecay[part];
    korg.parts[part].level = baseLevel[part];
    //korg.parts[part].glide = baseGlide[part];
  }
}

function setAccentedAmounts(){
  for(let part = 0; part <= maxParts; part++){
    egIntAccAmount[part] = korg.parts[part].egInt;
    decayAccAmount[part] = korg.parts[part].decay;
    levelAccAmount[part] = korg.parts[part].level;
  }
}



function applyAccent(){

  

  for(let part = 0; part <= maxParts; part++){

    const currentStep = korg.read.step(part);
    const isStepOn = korg.seq.getOn(part, currentStep);
    const stepVelocity = korg.seq.getVelocity(part, currentStep);

    //
    if(isStepOn == 1){
      if(stepVelocity > defaultVelocity){
      korg.parts[part].egInt = egIntAccAmount[part];
      korg.parts[part].decay = decayAccAmount[part];
      korg.parts[part].level = levelAccAmount[part];
      }
      else{
      korg.parts[part].egInt = baseEgInt[part];
      korg.parts[part].decay = baseDecay[part]; 
      korg.parts[part].level = baseLevel[part];
      }
    }
  }
}





korg.onEvent("ready", () => {
    setNewBases();
    setAccentedAmounts();
    korg.display.popups(0);
});

korg.onEvent("patternChange", () => {
    setNewBases();
    setAccentedAmounts();
});

korg.onEvent("buttonPress", (key) => {
    
    if(key == 10){ 
      shiftPress = 1;
      korg.knobHold(egIntKnobIndex, 1);
      korg.knobHold(decayKnobIndex, 1);
      korg.knobHold(levelKnobIndex, 1);
    }

    if(key == 1){
      restoreBases();
    } 

});


korg.onEvent("buttonRelease", (key) => {

    if(key == 10){
      shiftPress = 0;
      korg.knobHold(egIntKnobIndex, 0);
      korg.knobHold(decayKnobIndex, 0);
      korg.knobHold(levelKnobIndex, 0);
    }
});


korg.onEvent("frame", () => {
    if( (korg.millis() - lastMillis) > 50){
      korg.display.release();
    }
    
});




korg.onEvent("step", () => {

    applyAccent();
    
});


korg.onEvent("knob", (index, value) => {
    let currentPart = korg.read.part();


    //Aggiorna tutti i valori per gli step accentati/TIEati
    if(index == egIntKnobIndex && shiftPress == 0) baseEgInt[currentPart] = (value/2)-63;
    if(index == decayKnobIndex && shiftPress == 0) baseDecay[currentPart] = value/2;
    if(index == levelKnobIndex && shiftPress == 0) baseLevel[currentPart] = value/2;
    //if(index == pitchGlideKnobIndex && shiftPress == 1) baseGlide[currentPart] = (value/2);
    


    //Aggiorna e mostra i valori per gli step accentati
    if(index == egIntKnobIndex && shiftPress == 1){
      egIntAccAmount[currentPart] = (value/2)-64;
      korg.display.take();
      korg.display.clear();
      lastMillis = korg.millis();
      korg.display.text("AccentEgInt",10,22);
      korg.display.number(egIntAccAmount[currentPart],10, 32);
      
      
    }

    if(index == decayKnobIndex && shiftPress == 1){
      decayAccAmount[currentPart] = value/2;
      korg.display.take();
      korg.display.clear();
      lastMillis = korg.millis();
      korg.display.text("AccentDecay",10,22);
      korg.display.number(decayAccAmount[currentPart],10,32);
      
      
    }
    
    if(index == levelKnobIndex && shiftPress == 1){
      levelAccAmount[currentPart] = value/2;
      korg.display.take();
      korg.display.clear();
      lastMillis = korg.millis();
      korg.display.text("AccentLevel",10,22);
      korg.display.number(levelAccAmount[currentPart],10,32);
      
      
    }
    
});
