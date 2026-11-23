#!/usr/bin/env python3
"""Night Trap (3DO) - crea le ISO sottotitolate e le patch BPS.

Esempi:
  python3 crea_patch.py --iso1 "Night Trap (...)(Disc 1 of 2)[!].iso" --iso2 "Night Trap (...)(Disc 2 of 2)[!].iso"
  python3 crea_patch.py --iso1 disco1.iso --lingua it --uscita risultato --bps
  python3 crea_patch.py --iso1 disco1.iso --test-cambio-disco

Le ISO originali non vengono mai modificate: si crea una copia nella cartella di uscita.
Serve solo Python 3 (nessun pacchetto aggiuntivo).
"""
import argparse, hashlib, json, os, sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
from nighttrap import opera, stream, bps
from nighttrap.dischi import DISCHI, FPS
from nighttrap.testo import Testi, pagine
from nighttrap.launchme import costruisci

RIEMPITIVO = b'iamaduck'   # cosi' i tool 3DO riempiono lo spazio libero del disco


def errore(msg):
    sys.exit('ERRORE: ' + msg + '\nNessun file creato.')


def carica_json(percorso):
    with open(percorso, encoding='utf-8') as f:
        return json.load(f)


def prepara_disco(n, iso, lingua, cartella_lingua, test_cambio):
    """Legge la ISO, controlla che sia quella giusta e calcola tutte le modifiche."""
    C = DISCHI[n]
    sub = carica_json(os.path.join(cartella_lingua, 'disco%d.json' % n))
    indice = {c['clip']: c for c in carica_json(os.path.join(QUI, 'dati', 'disco%d_clip.json' % n))['clip']}
    T = Testi(lingua)

    # testi e tempi
    voci, tempi = [], []          # tempi: (clip, inizio, fine, id)
    for c in sub['clip']:
        if c['clip'] not in indice:
            errore('clip sconosciuta nel file della lingua: %s' % c['clip'])
        for b in c['battute']:
            if not b['testo'].strip():
                continue
            for s, e, righe in pagine(b['testo'], b['inizio'], b['fine'], T):
                voci.append(T.voce(righe))
                tempi.append((c['clip'], s, e, len(voci)))
    voci_colore = [T.riga(lingua['frase_codice'].format(colore=col)) for col in lingua['colori']]
    if len(voci_colore) != 6:
        errore('servono 6 colori in lingua.json')

    with open(iso, 'rb') as f:
        try:
            et, voci_radice = opera.radice(f)
        except opera.ErroreISO as e:
            errore('%s: %s' % (iso, e))
        per_nome = {v.nome: v for v in voci_radice}
        if 'Launchme' not in per_nome or C['file_dati'] not in per_nome:
            errore('%s non sembra il disco %d di Night Trap' % (iso, n))
        lm, dati = per_nome['Launchme'], per_nome[C['file_dati']]
        orig = opera.leggi_file(f, lm)
        if hashlib.sha1(orig).hexdigest() != C['launchme_sha1']:
            errore('%s: il Launchme non e\' quello atteso (versione diversa del gioco o ISO gia\' modificata?)' % iso)

        nuovo, _ = costruisci(orig, C, voci, voci_colore, test_cambio)

        # dove mettere il nuovo Launchme: subito dopo la directory radice, nello spazio libero
        blocco_nuovo = max(et['radice']) + 1
        f.seek(blocco_nuovo * opera.BLOCCO)
        zona = f.read(len(nuovo) + opera.BLOCCO)
        atteso = (RIEMPITIVO * (len(zona) // 8 + 1))[:len(zona)]
        if zona.strip(b'\0') and zona != atteso:
            errore('%s: lo spazio libero dopo la directory non e\' vuoto' % iso)

        # copie della voce di Launchme in tutti gli avatar della directory radice
        rel = lm.pos - et['radice'][0] * opera.BLOCCO
        n_blocchi = (len(nuovo) + opera.BLOCCO - 1) // opera.BLOCCO
        modifiche = [(blocco_nuovo * opera.BLOCCO, nuovo)]
        for blk in et['radice']:
            p = blk * opera.BLOCCO + rel
            f.seek(p + 32)
            if f.read(8) != b'Launchme':
                continue
            modifiche.append((p + 16, len(nuovo).to_bytes(4, 'big') + n_blocchi.to_bytes(4, 'big')))
            modifiche.append((p + 68, blocco_nuovo.to_bytes(4, 'big')))

        # marcatori nei fotogrammi
        inizio_dati = dati.blocco * opera.BLOCCO
        per_clip = {}
        for t in tempi:
            per_clip.setdefault(t[0], []).append(t)
        n_fot = 0
        for clip, tt in per_clip.items():
            info = indice[clip]
            try:
                pos = stream.fotogrammi(f, inizio_dati, info)
            except ValueError as e:
                errore('%s: %s' % (iso, e))
            for k, v in enumerate(pos):
                t = (k + 0.5) / FPS
                sid = 0
                for _, s, e, i in tt:
                    if s <= t < e:
                        sid = i
                if not sid:
                    continue
                f.seek(inizio_dati + v)
                if f.read(1) != b'\x81':
                    errore('%s: fotogramma inatteso nella clip %s' % (iso, clip))
                modifiche.append((inizio_dati + v + 4, stream.marcatore(sid)))
                n_fot += 1
    info = dict(battute=sum(len(c['battute']) for c in sub['clip']), pagine=len(voci), fotogrammi=n_fot,
                launchme=len(nuovo), blocco=blocco_nuovo)
    if T.non_convertiti:
        print('  attenzione: caratteri senza equivalente nel font, mostrati come "?": %s' % ' '.join(sorted(T.non_convertiti)))
    return modifiche, info


def main():
    ap = argparse.ArgumentParser(description='Night Trap 3DO: crea le ISO sottotitolate e le patch BPS.')
    ap.add_argument('--iso1', help='ISO originale del disco 1 (2048 byte per settore)')
    ap.add_argument('--iso2', help='ISO originale del disco 2')
    ap.add_argument('--lingua', default='it', help='cartella dentro lingue/ (predefinita: it)')
    ap.add_argument('--uscita', default='uscita', help='cartella dove scrivere i risultati')
    ap.add_argument('--bps', action='store_true', help='crea anche le patch BPS')
    ap.add_argument('--test-cambio-disco', action='store_true',
                    help='solo disco 1: appena inizia la partita chiede il disco 2 (per provare il cambio disco)')
    a = ap.parse_args()
    if not a.iso1 and not a.iso2:
        ap.error('indica almeno --iso1 o --iso2')
    cart_lingua = os.path.join(QUI, 'lingue', a.lingua)
    if not os.path.isdir(cart_lingua):
        errore('lingua "%s" non trovata in lingue/' % a.lingua)
    lingua = carica_json(os.path.join(cart_lingua, 'lingua.json'))
    sigla = lingua.get('codice', a.lingua).upper()
    for n, iso in ((1, a.iso1), (2, a.iso2)):
        if not iso:
            continue
        if not os.path.exists(iso):
            errore('non trovo %s' % iso)
        prova = a.test_cambio_disco and n == 1
        print('Disco %d: %s' % (n, os.path.basename(iso)))
        modifiche, info = prepara_disco(n, iso, lingua, cart_lingua, prova)
        print('  %(battute)d battute, %(pagine)d schermate di testo, %(fotogrammi)d fotogrammi marcati' % info)
        nome = 'Night Trap (3DO) - %s %s (%s)' % ('PROVA cambio disco' if prova else 'sottotitoli', sigla, DISCHI[n]['nome_iso'])
        dest = os.path.join(a.uscita, nome + '.iso')
        fbps = os.path.join(a.uscita, nome + '.bps') if a.bps else None
        os.makedirs(a.uscita, exist_ok=True)
        print('  scrivo la ISO (qualche secondo)...')
        crc_s, crc_t, _ = bps.crea(iso, dest, modifiche, fbps)
        with open(os.path.join(a.uscita, nome + '.cue'), 'w') as c:
            c.write('FILE "%s.iso" BINARY\n  TRACK 01 MODE1/2048\n    INDEX 01 00:00:00\n' % nome)
        print('  fatto: %s.iso + .cue%s' % (nome, ' + .bps' if fbps else ''))
        print('  CRC32 originale %08x, nuova %08x' % (crc_s, crc_t))


if __name__ == '__main__':
    main()
