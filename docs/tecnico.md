# Come funziona

Note tecniche su come i sottotitoli vengono aggiunti a Night Trap 3DO. Gli indirizzi si riferiscono al
`Launchme` originale del disco 1 (quelli del disco 2 sono in `nighttrap/dischi.py`).

## 1. Il disco

Le ISO usano il filesystem **Opera** del 3DO (blocchi da 2048 byte).

- Blocco 0: etichetta del disco (`01 5A 5A 5A 5A 5A ...`); a +100 la lista delle copie ("avatar")
  della directory radice.
- La directory radice è registrata in **due copie** (disco 1: blocchi 297475 e 297476).
  Ogni voce: flag, id, tipo, dimensione blocco, **byte (+16)**, **blocchi (+20)**, nome (+32, 32 byte),
  indice ultimo avatar (+64), **avatar (+68)** = blocco dove inizia il file.
- I file che interessano: `Launchme` (l'eseguibile del gioco) e `disc1data.bin` / `disc2data.bin`
  (tutti i video, circa 600 MB).
- Dopo la directory, fino al blocco 330000, il disco è riempito con la stringa `iamaduck` ripetuta
  (il riempitivo dei tool di sviluppo 3DO): è spazio libero.

La patch scrive il **nuovo Launchme nello spazio libero** subito dopo la directory e aggiorna
byte, blocchi e avatar della voce `Launchme` in entrambe le copie della directory.
Il vecchio Launchme resta dov'era, inutilizzato. La dimensione della ISO non cambia.

## 2. Lo stream video

Il file dati è una sequenza di fotogrammi a **12 al secondo**, uno ogni 16 KB circa
(0x4000 o 0x4200 byte). In ogni fotogramma:

| Record | Firma | Contenuto |
|---|---|---|
| video | `81 nn 39 c8` | 14792 byte; byte 4-7 = timecode; byte 0xa = larghezza, 0xb = altezza (in blocchi da 8 pixel) |
| audio | `a2 00 06 30` | 1584 byte, PCM 8 bit con segno, ~18864 Hz; timecode HH MM SS FF |

Il record video sta 0x39cc byte prima di quello audio. Il **timecode è il tempo della partita**,
non della scena: le telecamere che riprendono stanze diverse nello stesso momento hanno lo stesso timecode.
Per questo non basta il timecode per sapere quale scena si sta guardando.

`dati/discoN_clip.json` contiene, per ogni scena ("clip"), la posizione del suo primo fotogramma
dentro il file dati e il numero di fotogrammi.

## 3. Come il gioco sa cosa scrivere

Nei byte 4-7 di ogni record video che deve avere un sottotitolo la patch scrive un **marcatore**:

```
5B  id_alto  id_basso  5D        ( "[" id "]" )
```

dove `id` è il numero della schermata di testo (1, 2, 3...). Il gioco non usa quei 4 byte (il timecode
che conta è quello del record audio), quindi sovrascriverli non cambia niente nel gioco.
Ogni fotogramma senza sottotitolo resta com'era.

I tempi dei sottotitoli (in secondi dall'inizio della scena) diventano numeri di fotogramma:
un fotogramma k ha il sottotitolo se il suo centro `(k + 0.5) / 12` cade fra inizio e fine.

## 4. Il nuovo Launchme

`Launchme` è un eseguibile **AIF** per l'ARM60 del 3DO, **big-endian**, caricato all'indirizzo 0.
Si auto-riloca all'avvio usando una tabella (dopo il codice di rilocazione, a RELOC+0xb8, terminata da -1).

Per aggiungere codice e testi senza rompere niente:

1. il blocco nuovo (codice + testi) viene **inserito alla fine della parte di sola lettura (RO)**, all'indirizzo 0x24d94;
2. tutto quello che viene dopo (dati, codice di rilocazione) si sposta di `delta` byte;
3. nella tabella di rilocazione e nelle parole che contengono indirizzi oltre RO si aggiunge `delta`;
4. si aggiornano la dimensione RO nell'intestazione AIF e la chiamata all'auto-rilocazione all'indirizzo 4.

Il codice nuovo usa solo indirizzi relativi al PC, quindi funziona dovunque venga caricato.

## 5. Disegnare il testo

Dentro `PlayStreamingVideo` c'è un blocco di **debug** che disegna testo sul fotogramma con le routine
di sistema (`MoveTo`, `SetFGPen`, `SetBGPen`, `DrawText8`), acceso da un byte (0x27d0c). La patch lo accende
e ne sostituisce il contenuto con i suoi hook:

- **hook1** (a 0x6370): legge i byte 4-7 del record video corrente; se c'è un marcatore salva l'`id`,
  altrimenti 0. Calcola anche dove sta il video sullo schermo:
  - scena a tutto schermo: bordo inferiore = 120 + altezza·4, bordo superiore = 120 − altezza·4;
  - finestra della telecamera: bordo superiore 16, inferiore 16 + altezza·8.
- **hook2** (a 0x63cc): se `id` ≠ 0 disegna le righe della voce `id` **dentro il bordo inferiore del video**,
  centrate, 14 pixel fra una riga e l'altra. Il testo deve stare dentro il riquadro del video: il fotogramma
  successivo lo ricopre e lo cancella; un pezzo fuori dal riquadro resterebbe sullo schermo. Per questo le
  righe sono larghe al massimo 260 pixel (la finestra della telecamera va da x=24 a x=297).

**Font proprio (dalla v1.1).** `DrawText8` usa il font del sistema operativo, che ha solo ASCII maiuscolo.
Dalla v1.1 hook2 non lo usa più: chiama `scrivi_riga`, una routine ARM (da `testo3do.py`, che viene dal
repository [retro-tools](https://github.com/Linobob/retro-tools)) che scrive direttamente nei pixel dello
schermo con un font bitmap (DejaVu Sans Bold 11, in `font/`), prima il bordo nero e poi le lettere.

- **Dove sono i pixel:** il gioco usa la `ScreenContext` di Lib3DO (a 0x2841c): dopo `sc_BitmapItems[6]`
  (0x28444) ci sono `sc_Bitmaps[6]` (0x2845c), puntatori alle `Bitmap`; nella `Bitmap` l'indirizzo dei pixel
  (`bm_Buffer`) è a +0x24. L'indice dello schermo su cui si disegna è a 0x2847c.
- **Formato dei pixel:** 320×240, 16 bit RGB555, righe a coppie: la parola a ((y>>1)·320 + x)·4 contiene il
  pixel della riga pari nei 16 bit alti e quello della riga dispari nei 16 bit bassi (confermato sul MiSTer).
  L'ARM60 non ha load/store a 16 bit: ogni pixel è una lettura-modifica-scrittura della parola.
- **Costo:** circa 2000 istruzioni per carattere; due righe piene ≈ 140.000 istruzioni per fotogramma,
  senza rallentamenti visibili sul MiSTer.

Tabelle nel nuovo Launchme:
- testi: per ogni voce il numero di righe, poi per ogni riga la posizione x (2 byte), gli indici dei
  caratteri (1 byte ciascuno) e uno zero;
- font: solo i caratteri usati dal disco (al massimo 255), con il disegno di ogni riga in una parola a 32 bit.

Le battute lunghe si dividono in schermate di 2 righe di lunghezza simile, di preferenza dopo un punto,
e il tempo della battuta si divide fra le schermate in proporzione ai caratteri (almeno 1,2 s ciascuna
quando c'è tempo).

## 6. Il colore del codice d'accesso

Il colore del codice cambia a ogni partita. Le frasi che lo annunciano sono **campioni audio separati**,
non dentro il video:

- `LoadCodePhrases` (0x1c7dc) estrae a caso i codici futuri e li mette nella struttura di stato
  (0x28b10 + 0x1d8, +0x1dc, +0x1e0, +0x1e4), poi carica il campione con il nome del colore.
  Indici dei colori: 0 verde, 1 rosso, 2 giallo, 3 viola, 4 arancione, 5 blu.
- `ReadyCodePhrase1/2/3` preparano la frase con una stanza e un momento (in fotogrammi);
  `GetNextAudio` la fa partire (`StartInstrument`) solo se il giocatore sta guardando quella stanza
  in quel momento.

| Frase | Stanza | Momento | Colore annunciato |
|---|---|---|---|
| disco 1, 1 | 6 | 0x76 | stato + 0x1d8 |
| disco 1, 2 (festa in soggiorno) | 4 | 0x93c | stato + 0x1dc |
| disco 1, 3 | 6 | 0xbc | stato + 0x1e0 |
| disco 2 | — | 0x6c | stato + 0x1d8 |

**hook4** (a 0x119dc, subito dopo `StartInstrument`): se la frase è partita, riconosce quale frase è dal
momento, legge il colore dalla struttura di stato e avvia un conto alla rovescia di 60 fotogrammi (5 secondi).
hook2 allora scrive in cima al video la frase del codice (es. «NUOVO CODICE: GIALLO») nel colore giusto,
con lo stesso font e il bordo nero.
Il conto alla rovescia scende solo quando c'è un video a schermo.

## 7. Il cambio disco

Alla fine del disco 1 `DoDiscChangeLogic` scrive lo stato in `/NVRAM/nitetrap.inf` (12 byte: tempo, stanza,
trappole possibili/catturate, codici) e chiede il disco 2. Il 3DO si riavvia al cambio disco; il disco 2
(`CheckForNVRAM`) controlla i valori, li carica e cancella il file. Il disco 2 ha i suoi hook agli indirizzi
equivalenti, quindi i sottotitoli continuano.

L'opzione `--test-cambio-disco` aggiunge un hook all'avvio della partita (0x19e18) che imposta uno stato
valido e salta subito al cambio disco: serve per provare il disco 2 senza giocare tutto il disco 1.

## 8. Immagini BIN (2352 byte per settore)

Le copie in formato BIN/CUE (es. Redump) hanno settori da 2352 byte: 16 di intestazione (sincronismo,
indirizzo, modo 1), 2048 di dati, poi EDC (CRC a 32 bit) e ECC (codici Reed-Solomon P e Q).
`immagine.py` legge i dati saltando l'intestazione, così il resto del codice vede sempre una ISO a 2048.
Quando un settore viene modificato, EDC ed ECC vengono ricalcolati. Prima di scrivere, lo strumento
ricalcola EDC/ECC di alcuni settori originali e controlla che coincidano con quelli dell'immagine.

## 9. Le patch BPS

Le modifiche sono poche e note in anticipo (nuovo Launchme, voci di directory, marcatori), quindi
`bps.py` scrive la ISO nuova e la patch BPS in un solo passaggio: "copia dalla sorgente" per le parti uguali,
"byte nuovi" per quelle cambiate. Circa 300 KB per disco.

## 10. Come sono stati fatti i sottotitoli

Non fanno parte di questo repository, ma per chi vuole rifarli:

1. audio di ogni scena estratto dal file dati (record audio, PCM 8 bit con segno);
2. trascrizione con Whisper (`medium.en`), poi con i tempi parola per parola
   (`--word_timestamps True --condition_on_previous_text False`);
3. revisione e traduzione delle battute;
4. tempi delle battute ricalcolati dalle parole di Whisper, con una durata minima per la lettura;
5. ascolto delle battute dubbie.
