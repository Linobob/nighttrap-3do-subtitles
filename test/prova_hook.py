"""Prova del disegno dei sottotitoli: esegue hook2 del nuovo Launchme in un emulatore ARM
su un framebuffer finto e salva un PNG. Serve il Launchme originale (estratto dal disco).

  python3 test/prova_hook.py LAUNCHME DISCO ID_SOTTOTITOLO uscita.png [--sfondo foto.png]
"""
import argparse, os, struct, sys, json
QUI = os.path.dirname(os.path.abspath(__file__))
RAD = os.path.dirname(QUI)
sys.path[:0] = [RAD, os.path.join(RAD, 'nighttrap'),
                os.path.join(RAD, '..', 'retro-tools', 'cpu', 'arm')]   # armemu.py da retro-tools
from nighttrap.dischi import DISCHI
from nighttrap.launchme import costruisci
from nighttrap.testo import Testi, pagine
from nighttrap import testo3do
from armemu import CPU
from font import scrivi_png

ap = argparse.ArgumentParser()
ap.add_argument('launchme'); ap.add_argument('disco', type=int); ap.add_argument('id', type=int); ap.add_argument('png')
ap.add_argument('--colore', type=int, default=-1, help='indice del colore del codice da mostrare (0-5)')
ap.add_argument('--fondo', type=int, default=160, help='fondo del video (160 = finestra di gioco)')
ap.add_argument('--cima', type=int, default=16)
a = ap.parse_args()
C = DISCHI[a.disco]
lingua = json.load(open(os.path.join(RAD, 'lingue/it/lingua.json')))
sub = json.load(open(os.path.join(RAD, 'lingue/it/disco%d.json' % a.disco)))
T = Testi(lingua); voci = []
for c in sub['clip']:
    for b in c['battute']:
        for s, e, r in pagine(b['testo'], b['inizio'], b['fine'], T):
            voci.append(T.voce(r))
vc = [T.riga(lingua['frase_codice'].format(colore=x)) for x in lingua['colori']]
orig = open(a.launchme, 'rb').read()
nuovo, lab = costruisci(orig, C, voci, vc, T.tabella_font(), T.altezza)
delta = len(nuovo) - len(orig)
mem = bytearray(0x200000)
cpu = CPU(mem, 0)
cpu.carica(0, nuovo)
FB, BM = 0x180000, 0x170000
sel = C['SEL'] + delta; bms = C['BMS'] + 0x18 + delta; cur = C['CUR'] + delta
cpu.scrivi32(sel, 0); cpu.scrivi32(bms, BM); cpu.scrivi32(BM + 0x24, FB)
cpu.scrivi32(cur, a.id); cpu.scrivi8(cur + 4, a.fondo)
if a.colore >= 0:
    v = lab['VARS']; cpu.scrivi32(v, 60); cpu.scrivi32(v + 4, a.colore); cpu.scrivi32(v + 8, a.cima)
cpu.carica(FB, testo3do.fb_vuoto(320, 240, 0x5294))
cpu.chiama(lab['hook2'], sp=0x16fff0, max_passi=5_000_000)
fb = cpu.mem[FB:FB + 320 * 240 * 2]
scrivi_png(a.png, testo3do.fb_a_righe_rgb(fb, 320, 240), 2)
print('istruzioni:', cpu.passi)
