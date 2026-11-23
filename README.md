# Night Trap (3DO) – sottotitoli / subtitles

*[English below](#english)*

Sottotitoli in italiano per **Night Trap** (Digital Pictures, 1993), versione **3DO USA** su due dischi,
e lo strumento per crearli (anche in altre lingue).

- I sottotitoli compaiono **dentro il video**, sia nelle scene a tutto schermo sia nella finestra di gioco,
  con lettere **maiuscole e minuscole, accenti** e un **bordo nero** che li rende leggibili su ogni sfondo
  (dalla v1.1; la v1.0 usava il font di sistema, solo maiuscole senza accenti).
- Quando un personaggio annuncia il nuovo **codice d'accesso**, compare in cima al video il colore
  scelto dal gioco in quella partita (es. «NUOVO CODICE: GIALLO»), scritto nel suo colore.
- Funziona anche il **cambio disco**: la partita continua sul disco 2, sottotitoli compresi.
- Provato su **MiSTer FPGA** (core 3DO) con entrambi i dischi.

Disco 1: 373 battute in 32 scene. Disco 2: 324 battute in 45 scene. Le canzoni non sono sottotitolate.

## Giocare: applicare le patch BPS

Scarica le due patch dalla pagina **Releases** e applicale alle ISO originali con
[Floating IPS](https://www.romhacking.net/utilities/1040/) (o un altro programma che supporti BPS).

Servono le ISO **TOSEC** a 2048 byte per settore:

| Disco | File originale | CRC32 |
|---|---|---|
| 1 | `Night Trap (1993)(Digital Pictures)(US)(Disc 1 of 2)[!].iso` | `bf501e71` |
| 2 | `Night Trap (1993)(Digital Pictures)(US)(Disc 2 of 2)[!].iso` | `525d9730` |

Se hai le immagini **BIN/CUE** a 2352 byte (es. Redump), le patch BPS non vanno bene:
usa lo strumento qui sotto, che accetta anche quel formato e crea direttamente una BIN/CUE sottotitolata.

Per il MiSTer: crea per ogni disco un file `.cue` accanto alla ISO patchata
(lo strumento qui sotto lo crea da solo):

```
FILE "Night Trap (3DO) - sottotitoli IT (Disc 1).iso" BINARY
  TRACK 01 MODE1/2048
    INDEX 01 00:00:00
```

Al cambio disco il gioco salva lo stato nella NVRAM: sul MiSTer carica il disco 2 dal menu e la partita continua.

## Creare le ISO con lo strumento

Serve solo **Python 3**, nessun pacchetto aggiuntivo. Funziona con le ISO a 2048 byte e con le
immagini BIN/CUE a 2352 byte (MODE1): si può indicare la `.iso`, la `.bin` o il `.cue`.
Il risultato è nello stesso formato dell'originale (per le BIN vengono ricalcolati i codici
di correzione EDC/ECC dei settori modificati).

```
python3 crea_patch.py --iso1 "Night Trap (...)(Disc 1 of 2)[!].iso" --iso2 "Night Trap (...)(Disc 2 of 2)[!].iso" --bps
```

Nella cartella `uscita/` trovi per ogni disco l'immagine sottotitolata, il `.cue` e (con `--bps`) la patch BPS
(valida per quella specifica immagine di partenza).
Le ISO originali non vengono modificate. Si può fare anche un disco solo.

| Opzione | Cosa fa |
|---|---|
| `--lingua it` | usa i testi di `lingue/it/` (predefinita) |
| `--uscita cartella` | dove scrivere i risultati (predefinita `uscita`) |
| `--bps` | crea anche le patch BPS |
| `--test-cambio-disco` | disco 1 di prova: appena inizia la partita chiede il disco 2 |

Lo strumento controlla che le ISO siano quelle giuste e si ferma senza scrivere niente se non lo sono
(per esempio se la ISO è già stata modificata).

## Tradurre in un'altra lingua

1. Copia la cartella `lingue/it` in `lingue/xx` (xx = codice della lingua).
2. In `disco1.json` e `disco2.json` traduci solo i campi `testo`: lascia `clip`, `inizio` e `fine` come sono.
3. In `lingua.json` traduci i nomi dei sei colori (nell'ordine: verde, rosso, giallo, viola, arancione, blu)
   e la frase del codice (`{colore}` viene sostituito dal nome del colore).
4. `python3 crea_patch.py --lingua xx --iso1 ... --iso2 ... --bps`

Il font (DejaVu Sans Bold 11, in `font/`) ha minuscole, maiuscole e tutti gli accenti dell'Europa
occidentale e centrale (Latin-1 e Latin-2). Se una lettera manca, viene usata la stessa senza accento,
altrimenti `?`; lo strumento elenca i caratteri mancanti. In `lingua.json`, sotto `sostituzioni`, si possono
indicare sostituzioni proprie. Le righe vanno a capo da sole (al massimo 260 pixel, 2 righe per schermata);
le battute lunghe vengono divise in schermate di lunghezza simile, di preferenza a fine frase.

## Struttura

```
crea_patch.py        lo strumento
nighttrap/
  opera.py           filesystem del 3DO (Opera) letto direttamente dall'immagine
  immagine.py        lettura ISO (2048) e BIN (2352), EDC/ECC dei settori
  stream.py          fotogrammi dello stream video Digital Pictures
  launchme.py        nuovo eseguibile del gioco con il codice dei sottotitoli
  armasm.py          piccolo assemblatore ARM (big-endian, ARM60)
  testo3do.py        routine ARM che scrive il testo nel framebuffer con il font
  font.py            lettura del font bitmap, misure, a capo in pixel
  testo.py           pagine dei sottotitoli e codifica dei testi
  bps.py             creazione delle patch BPS
  dischi.py          indirizzi e dati fissi dei due dischi
dati/                posizione delle scene video nei due dischi
font/                font bitmap (DejaVu Sans Bold 11) e sua licenza
lingue/it/           sottotitoli italiani
docs/                documentazione tecnica
test/                strumenti per i test
```

Come funziona: vedi [docs/tecnico.md](docs/tecnico.md).

## Note

Il repository non contiene nessun file del gioco: lo strumento lavora sulle ISO originali, che devi avere tu.
Night Trap è un marchio dei rispettivi proprietari; questo è un progetto amatoriale senza scopo di lucro.
Codice sotto licenza MIT (vedi `LICENSE`). Il font bitmap deriva da DejaVu Sans Bold (vedi `font/LICENZE.md`).

---

<a name="english"></a>
# English

Italian subtitles for **Night Trap** (Digital Pictures, 1993), **US 3DO** two-disc release,
plus the tool that builds them (other languages welcome).

- Subtitles are drawn **inside the video**, both in full-screen scenes and in the in-game camera window,
  with upper/lower case, accented letters and a black outline (since v1.1).
- When a character announces the new **access code**, the colour picked by the game for that playthrough
  is shown at the top of the video (e.g. "NUOVO CODICE: GIALLO"), drawn in that colour.
- **Disc swap** works: the game continues on disc 2 with subtitles.
- Tested on **MiSTer FPGA** (3DO core) with both discs.

## Playing: applying the BPS patches

Download the two patches from **Releases** and apply them to the original ISOs with
[Floating IPS](https://www.romhacking.net/utilities/1040/) or any BPS-capable patcher.
You need the **TOSEC** 2048-byte-per-sector ISOs (CRC32 in the table above).
2352-byte BIN/CUE images (e.g. Redump) won't match the BPS patches: use the tool instead,
which accepts BIN/CUE too and outputs a subtitled BIN/CUE.

On MiSTer, put a `.cue` next to each patched ISO (see the example above; the tool writes it for you).

## Building the ISOs with the tool

Python 3 only, no extra packages. Accepts 2048-byte ISOs and 2352-byte MODE1 BIN/CUE
(pass the `.iso`, `.bin` or `.cue`); output is in the same format (EDC/ECC recomputed for BIN):

```
python3 crea_patch.py --iso1 "Night Trap (...)(Disc 1 of 2)[!].iso" --iso2 "Night Trap (...)(Disc 2 of 2)[!].iso" --bps
```

Output goes to `uscita/` (image, CUE and, with `--bps`, BPS for each disc). The original ISOs are never modified.
Options: `--lingua xx` (language folder in `lingue/`), `--uscita folder`, `--bps`,
`--test-cambio-disco` (test disc 1 that asks for disc 2 as soon as the game starts).

## Translating to another language

1. Copy `lingue/it` to `lingue/xx`.
2. In `disco1.json` and `disco2.json` translate only the `testo` fields (keep `clip`, `inizio`, `fine`).
3. In `lingua.json` translate the six colour names (green, red, yellow, purple, orange, blue, in this order)
   and the access-code sentence (`{colore}` is replaced by the colour name).
4. `python3 crea_patch.py --lingua xx --iso1 ... --iso2 ... --bps`

Since v1.1 subtitles use their own bitmap font (DejaVu Sans Bold 11, in `font/`) with upper and lower case,
Latin-1 and Latin-2 accented letters and a black outline. Missing letters fall back to the unaccented letter
or `?` (the tool lists them). Lines wrap automatically (260 pixels, 2 lines per screen).

Technical notes (in Italian): [docs/tecnico.md](docs/tecnico.md).

This repository contains no game data: the tool works on your own original ISOs.
Night Trap is a trademark of its respective owners; this is a non-commercial fan project.
Code released under the MIT license. The bitmap font is derived from DejaVu Sans Bold (see `font/LICENZE.md`).
