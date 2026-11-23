#!/usr/bin/env python3
"""Testo con font proprio nel framebuffer del 3DO: routine in assembly ARM + dati del font.

Serve a scrivere sottotitoli (o altro testo) in un gioco 3DO senza usare DrawText8 del sistema,
che ha solo ASCII maiuscolo. Con questa routine il testo può avere qualsiasi carattere del font
(accenti, minuscole, Latin-2...) e un bordo scuro di 1 pixel per leggerlo su qualsiasi sfondo.

Come si usa (da Python, dentro lo strumento che costruisce la patch):

    from font import Font
    import testo3do
    F = Font('dejavu-sans-bold-11.txt')
    T = testo3do.Testi(F)                         # raccoglie i caratteri usati
    riga = T.riga('È così strano...', x=40)       # bytes da mettere nei dati della patch
    ...
    tabella = T.tabella_font()                    # bytes: font ridotto ai soli caratteri usati
    testo3do.emetti_routine(A, 'scrivi_riga')     # A = armasm.Asm del codice della patch

La routine (convenzione APCS, non chiama niente e non usa lo stack oltre ai registri salvati):

    scrivi_riga(r0 = contesto, r1 = x, r2 = y, r3 = riga)

    contesto: 6 parole
      +0   indirizzo del framebuffer (bm_Buffer della Bitmap corrente)
      +4   larghezza in pixel (320)
      +8   altezza in pixel (240)
      +12  indirizzo della tabella del font (tabella_font())
      +16  colore del testo (RGB555, es. 0x7fff bianco)
      +20  colore del bordo (es. 0x0000 nero)
    x, y: angolo in alto a sinistra della riga (y = cima delle lettere)
    riga: indici dei glifi terminati da 0 (quello che restituisce Testi.indici())

I pixel fuori dallo schermo vengono saltati. La routine disegna prima tutto il bordo e poi il
testo, così il bordo di una lettera non copre quella accanto.

Formato del framebuffer 3DO: le righe sono a coppie; la parola a ((y>>1)*larghezza + x)*4
contiene il pixel (x, y pari) nei 16 bit alti e (x, y dispari) nei 16 bit bassi.
L'ARM60 non ha load/store a 16 bit: ogni pixel è una lettura-modifica-scrittura di una parola.

Riga di comando:
  python3 testo3do.py anteprima FONT "testo" prova.png [--scala 3]
esegue la routine ARM in un emulatore su un framebuffer finto e salva il risultato in PNG.
"""
import argparse
import os
import struct
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
for _c in ('../../cpu/arm', '../../font'):
    sys.path.insert(0, os.path.normpath(os.path.join(QUI, _c)))

from armasm import Asm  # noqa: E402

SPAZIATURA = 1          # pixel fra un carattere e l'altro (la routine lo aggiunge sempre)


class Testi:
    """Raccoglie i caratteri usati e li numera (1..255); costruisce righe e tabella del font."""
    def __init__(self, font):
        self.F = font
        self.indice = {}            # codepoint del glifo -> indice
        self.glifi = []             # glifi nell'ordine degli indici

    def _idx(self, ch):
        g = self.F.carattere(ch)
        if g is None:
            raise ValueError('il font non ha né "%s" né "?"' % ch)
        if g.cp not in self.indice:
            if len(self.glifi) >= 255:
                raise ValueError('più di 255 caratteri diversi: serve una tabella più grande')
            self.glifi.append(g)
            self.indice[g.cp] = len(self.glifi)
        return self.indice[g.cp]

    def indici(self, testo):
        """Indici dei glifi del testo, terminati da 0."""
        return bytes(self._idx(c) for c in testo) + b'\0'

    def larghezza(self, testo):
        return self.F.larghezza(testo, SPAZIATURA)

    def tabella_font(self):
        """Parola 0: altezza H. Parole 1..n: distanza (in byte dall'inizio) del glifo i.
        Glifo: avanzamento (1 byte), sinistra+1 (1 byte), 2 byte liberi, poi H+4 parole: due righe
        vuote, le H righe del disegno, due righe vuote. In ogni riga il bit 30 è la prima colonna
        del disegno (il bit 31 resta libero per il bordo)."""
        H = self.F.altezza
        n = len(self.glifi)
        testa = bytearray(struct.pack('>I', H) + b'\0' * (4 * n))
        corpo = bytearray()
        base = len(testa)
        for i, g in enumerate(self.glifi, 1):
            if g.larghezza > 29:
                raise ValueError('glifo U+%04X troppo largo (%d pixel, massimo 29)' % (g.cp, g.larghezza))
            if not -1 <= g.sinistra <= 250:
                raise ValueError('glifo U+%04X: spostamento a sinistra non gestito (%d)' % (g.cp, g.sinistra))
            struct.pack_into('>I', testa, 4 * i, base + len(corpo))
            corpo += bytes((g.avanz, g.sinistra + 1, 0, 0))
            righe = [0, 0]
            for y in range(H):
                v = 0
                for x in range(g.larghezza):
                    if g.bit(x, y):
                        v |= 1 << (30 - x)
                righe.append(v)
            righe += [0, 0]
            corpo += b''.join(struct.pack('>I', r) for r in righe)
        return bytes(testa + corpo)


def emetti_routine(A, nome='scrivi_riga'):
    """Scrive la routine nell'assemblatore A (armasm.Asm), con l'etichetta `nome`.
    Le etichette interne iniziano con nome + '_'."""
    L = lambda s: '%s_%s' % (nome, s)   # noqa: E731
    A.label(nome)
    A.stmfd(['r4', 'r5', 'r6', 'r7', 'r8', 'r9', 'r10', 'r11', 'lr'])
    A.stmfd(['r1', 'r3'])                          # x e riga, per ripartire al secondo passaggio
    A.ldst(1, 0, 'lr', 'r0', 4)                   # lr = larghezza
    A.mov('r4', 0)                                # r4 = passaggio (0 bordo, 1 testo)
    A.label(L('passaggio'))
    A.ldst(1, 0, 'r1', 'sp', 0)
    A.ldst(1, 0, 'r3', 'sp', 4)
    A.label(L('glifo'))
    A.ldst(1, 1, 'r12', 'r3', 1, post=True)       # c = *riga++
    A.dp('cmp', 0, 'r12', 0)
    A.b(L('fine_passaggio'), 'eq')
    A.ldst(1, 0, 'r5', 'r0', 12)                  # r5 = tabella del font
    A.ldst(1, 0, 'r6', 'r5', regoff='r12', lsl=2)
    A.dp('add', 'r5', 'r5', 'r6')                 # r5 = glifo
    A.dp('mvn', 'r6', 0, 0)                       # r6 = riga del glifo, da -1 ad H
    A.label(L('riga'))
    A.dp('add', 'r9', 'r2', 'r6')                 # r9 = Y
    A.ldst(1, 0, 'r12', 'r0', 8)
    A.dp('cmp', 0, 'r9', 'r12')
    A.b(L('riga_dopo'), 'cs')                     # fuori schermo (anche Y negativo)
    A.dp('add', 'r7', 'r5', 'r6', sh=('lsl', 2))  # r7 = glifo + 4*riga
    A.ldst(1, 0, 'r12', 'r7', 12)                 # disegno della riga
    A.dp('cmp', 0, 'r4', 0)
    A.ldst(1, 0, 'r8', 'r7', 8, c='eq')           # bordo: riga sopra...
    A.dp('orr', 'r12', 'r12', 'r8', c='eq')
    A.ldst(1, 0, 'r8', 'r7', 16, c='eq')          # ...e sotto
    A.dp('orr', 'r12', 'r12', 'r8', c='eq')
    A.dp('orr', 'r7', 'r12', 'r12', c='eq', sh=('lsl', 1))   # e un pixel a sinistra e a destra
    A.dp('orr', 'r7', 'r7', 'r12', c='eq', sh=('lsr', 1))
    A.mov('r7', 'r12', 'ne')
    A.dp('cmp', 0, 'r7', 0)
    A.b(L('riga_dopo'), 'eq')
    # colore e metà della parola (Y pari = 16 bit alti)
    A.dp('cmp', 0, 'r4', 0)
    A.ldst(1, 0, 'r11', 'r0', 20, c='eq')
    A.ldst(1, 0, 'r11', 'r0', 16, c='ne')
    A.dp('mvn', 'r10', 0, 0)
    A.dp('tst', 0, 'r9', 1)
    A.dp('mov', 'r10', 0, 'r10', c='eq', sh=('lsl', 16))
    A.dp('mov', 'r10', 0, 'r10', c='ne', sh=('lsr', 16))
    A.dp('mov', 'r11', 0, 'r11', c='eq', sh=('lsl', 16))
    # indirizzo della prima colonna (bit 31): X = x + sinistra + 1 - 2
    A.ldst(1, 1, 'r8', 'r5', 1)
    A.dp('add', 'r8', 'r1', 'r8')
    A.dp('sub', 'r8', 'r8', 2)
    A.mov('r12', 'r9')
    A.dp('mov', 'r12', 0, 'r12', sh=('lsr', 1))   # Y >> 1
    A.mul('r9', 'r12', 'lr')                      # (Y>>1) * larghezza
    A.dp('add', 'r9', 'r9', 'r8')
    A.ldst(1, 0, 'r12', 'r0', 0)
    A.dp('add', 'r9', 'r12', 'r9', sh=('lsl', 2)) # r9 = indirizzo della parola
    A.label(L('pixel'))
    A.dp('mov', 'r7', 0, 'r7', S=1, sh=('lsl', 1))   # carry = pixel acceso?
    A.b(L('pixel_dopo'), 'cc')
    A.dp('cmp', 0, 'r8', 'lr')                    # X dentro lo schermo? (senza segno)
    A.ldst(1, 0, 'r12', 'r9', 0, c='cc')
    A.dp('bic', 'r12', 'r12', 'r10', c='cc')
    A.dp('orr', 'r12', 'r12', 'r11', c='cc')
    A.ldst(0, 0, 'r12', 'r9', 0, c='cc')
    A.label(L('pixel_dopo'))
    A.dp('add', 'r8', 'r8', 1)
    A.dp('add', 'r9', 'r9', 4)
    A.dp('cmp', 0, 'r7', 0)
    A.b(L('pixel'), 'ne')
    A.label(L('riga_dopo'))
    A.dp('add', 'r6', 'r6', 1)
    A.ldst(1, 0, 'r12', 'r0', 12)
    A.ldst(1, 0, 'r12', 'r12', 0)                 # H
    A.dp('cmp', 0, 'r6', 'r12')
    A.b(L('riga'), 'le')
    A.ldst(1, 1, 'r12', 'r5', 0)                  # avanzamento
    A.dp('add', 'r1', 'r1', 'r12')
    A.dp('add', 'r1', 'r1', SPAZIATURA)
    A.b(L('glifo'))
    A.label(L('fine_passaggio'))
    A.dp('cmp', 0, 'r4', 0)
    A.mov('r4', 1, 'eq')
    A.b(L('passaggio'), 'eq')
    A.dp('add', 'sp', 'sp', 8)
    A.ldmfd(['r4', 'r5', 'r6', 'r7', 'r8', 'r9', 'r10', 'r11', 'pc'])


# --- framebuffer finto (per prove e anteprime) ---

def fb_vuoto(larg=320, alt=240, colore=0x2108):
    v = (colore << 16) | colore
    return bytearray(struct.pack('>I', v) * (larg * alt // 2))


def fb_pixel(fb, larg, x, y):
    w = struct.unpack_from('>I', fb, ((y >> 1) * larg + x) * 4)[0]
    return (w & 0xffff) if y & 1 else (w >> 16)


def fb_a_righe_rgb(fb, larg, alt):
    def rgb(p):
        return (((p >> 10) & 31) * 255 // 31, ((p >> 5) & 31) * 255 // 31, (p & 31) * 255 // 31)
    return [[rgb(fb_pixel(fb, larg, x, y)) for x in range(larg)] for y in range(alt)]


def esegui(fb, larg, alt, tabella, riga, x, y, col_testo=0x7fff, col_bordo=0):
    """Esegue la routine ARM nell'emulatore e restituisce il framebuffer modificato e i passi."""
    from armemu import CPU
    A = Asm(0x1000)
    emetti_routine(A, 'scrivi_riga')
    codice = A.assemble()
    BASE = 0
    mem = bytearray(0x20000 + len(fb) + len(tabella) + len(riga))
    cpu = CPU(mem, BASE)
    cpu.carica(0x1000, codice)
    p_tab = 0x8000
    p_riga = p_tab + len(tabella) + 16
    p_ctx = p_riga + len(riga) + 16
    p_ctx += (-p_ctx) & 3
    p_fb = 0x20000
    cpu.carica(p_tab, tabella)
    cpu.carica(p_riga, riga)
    cpu.carica(p_ctx, struct.pack('>6I', p_fb, larg, alt, p_tab, col_testo, col_bordo))
    cpu.carica(p_fb, fb)
    cpu.chiama(0x1000, [p_ctx, x, y, p_riga], sp=0x7ff0)
    return bytearray(cpu.mem[p_fb:p_fb + len(fb)]), cpu.passi


def main():
    ap = argparse.ArgumentParser(description='Routine ARM di testo per il 3DO: anteprima eseguendo il codice in un emulatore.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('anteprima', help='esegue la routine su un framebuffer finto e salva un PNG')
    p.add_argument('font', help='font in formato testo (vedi font/)')
    p.add_argument('testo')
    p.add_argument('png')
    p.add_argument('--scala', type=int, default=3)
    a = ap.parse_args()
    from font import Font, scrivi_png
    try:
        F = Font(a.font)
    except (OSError, ValueError) as e:
        sys.exit('ERRORE: %s' % e)
    T = Testi(F)
    riga = T.indici(a.testo)
    larg = T.larghezza(a.testo) + 8
    larg += larg & 1
    alt = F.altezza + 6
    alt += alt & 1
    fb, passi = esegui(fb_vuoto(larg, alt), larg, alt, T.tabella_font(), riga, 4, 3)
    scrivi_png(a.png, fb_a_righe_rgb(fb, larg, alt), a.scala)
    print('%s: %d×%d pixel, %d istruzioni ARM' % (a.png, larg, alt, passi))


if __name__ == '__main__':
    main()
