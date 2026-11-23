# Night Trap (3DO) – sottotitoli

Sottotitoli in italiano per **Night Trap** (Digital Pictures, 1993), versione 3DO USA su due dischi.
I sottotitoli compaiono dentro il video, sia a tutto schermo sia nella finestra di gioco, e quando
viene annunciato un nuovo codice d'accesso compare anche il colore ("NUOVO CODICE: GIALLO").

> Bozza: README completo (italiano e inglese) e documentazione tecnica in arrivo.

## Cosa serve

- Le due ISO originali (TOSEC), a 2048 byte per settore:
  - `Night Trap (1993)(Digital Pictures)(US)(Disc 1 of 2)[!].iso`
  - `Night Trap (1993)(Digital Pictures)(US)(Disc 2 of 2)[!].iso`
- Python 3 (nessun pacchetto aggiuntivo).

## Creare le ISO sottotitolate

```
python3 crea_patch.py --iso1 "percorso/Disc 1 of 2.iso" --iso2 "percorso/Disc 2 of 2.iso" --bps
```

Nella cartella `uscita/` trovi, per ogni disco, la ISO con il suo `.cue` e (con `--bps`) la patch BPS.
Le ISO originali non vengono toccate. Si può fare anche un disco solo (`--iso1` oppure `--iso2`).

Altre opzioni:

| Opzione | Cosa fa |
|---|---|
| `--lingua it` | usa i testi di `lingue/it/` (predefinita) |
| `--uscita cartella` | dove scrivere i risultati |
| `--test-cambio-disco` | disco 1 di prova: appena inizia la partita chiede il disco 2 |

## Cambio disco

A metà partita il gioco chiede il disco 2 e salva lo stato nella NVRAM. Con il disco 2
sottotitolato la partita continua da lì, sottotitoli compresi.

## Altre lingue

1. Copia `lingue/it` in `lingue/xx`.
2. Traduci i testi in `disco1.json` e `disco2.json` (lascia `clip`, `inizio` e `fine` come sono)
   e in `lingua.json` (nomi dei colori e frase del codice).
3. `python3 crea_patch.py --lingua xx --iso1 ... --iso2 ...`

Il font del gioco ha solo lettere maiuscole senza accenti: in `lingua.json`, sotto
`sostituzioni`, si decide come scrivere le lettere accentate (per l'italiano `è` → `E'`).

## Struttura

```
crea_patch.py        lo strumento
nighttrap/           codice: filesystem 3DO (opera.py), stream video (stream.py),
                     nuovo eseguibile (launchme.py, armasm.py), testi (testo.py),
                     patch BPS (bps.py), dati dei due dischi (dischi.py)
dati/                posizione delle clip video nei due dischi
lingue/it/           sottotitoli italiani
test/                strumenti per i test
```
