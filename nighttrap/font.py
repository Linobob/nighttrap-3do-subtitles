#!/usr/bin/env python3
"""Font bitmap in formato testo: lettura, misure, a capo, anteprima PNG. Solo Python standard.

Formato del file (si può modificare a mano):

    nome DejaVu Sans Bold 11
    licenza ...
    altezza 14              righe di ogni glifo
    linea_base 11           riga della linea di base (dall'alto)

    glifo U+0041 A avanzamento 8 sinistra 0
    ........
    ...##...
    (una riga per ogni riga del glifo: '#' acceso, '.' spento)

`avanzamento` = di quanto si sposta la penna dopo il carattere; `sinistra` = di quanto il disegno
è spostato rispetto alla penna (può essere negativo, per esempio nella "j").

Uso da riga di comando:
  python3 font.py info FONT
  python3 font.py anteprima FONT "Testo di prova" prova.png [--scala 3] [--bordo]
  python3 font.py mancanti FONT FILE_DI_TESTO
"""
import argparse
import struct
import sys
import unicodedata
import zlib

SOSTITUZIONI = {' ': ' ', ' ': ' ', '‑': '-', '−': '-'}


class Glifo:
    def __init__(self, cp, avanz, sinistra, righe):
        self.cp = cp
        self.avanz = avanz
        self.sinistra = sinistra
        self.righe = righe                       # stringhe di '#' e '.'
        self.larghezza = max((len(r) for r in righe), default=0)

    def bit(self, x, y):
        r = self.righe[y]
        return x < len(r) and r[x] == '#'


class Font:
    def __init__(self, percorso):
        self.nome = ''
        self.licenza = ''
        self.altezza = 0
        self.linea_base = 0
        self.glifi = {}
        self._leggi(percorso)

    def _leggi(self, percorso):
        with open(percorso, encoding='utf-8') as f:
            righe = f.read().split('\n')
        i = 0
        while i < len(righe):
            r = righe[i]
            i += 1
            if not r.strip() or r.startswith('#'):
                continue
            parole = r.split(' ')
            if parole[0] == 'nome':
                self.nome = r[5:]
            elif parole[0] == 'licenza':
                self.licenza = r[8:]
            elif parole[0] == 'altezza':
                self.altezza = int(parole[1])
            elif parole[0] == 'linea_base':
                self.linea_base = int(parole[1])
            elif parole[0] == 'glifo':
                if not self.altezza:
                    raise ValueError('%s: "altezza" deve venire prima dei glifi' % percorso)
                cp = int(parole[1][2:], 16)
                val = dict(zip(parole[3::2], parole[4::2]))
                disegno = righe[i:i + self.altezza]
                i += self.altezza
                if len(disegno) < self.altezza or any(set(d) - set('#.') for d in disegno):
                    raise ValueError('%s: disegno del glifo U+%04X non valido' % (percorso, cp))
                self.glifi[cp] = Glifo(cp, int(val.get('avanzamento', 0)), int(val.get('sinistra', 0)), disegno)
            else:
                raise ValueError('%s: riga non riconosciuta: %s' % (percorso, r))

    # --- testo ---
    def carattere(self, ch):
        """Glifo per un carattere, con sostituzioni: senza accento, poi '?'."""
        ch = SOSTITUZIONI.get(ch, ch)
        g = self.glifi.get(ord(ch))
        if g:
            return g
        base = unicodedata.normalize('NFKD', ch)
        base = ''.join(c for c in base if not unicodedata.combining(c))
        if base and all(ord(c) in self.glifi for c in base) and len(base) == 1:
            return self.glifi[ord(base)]
        return self.glifi.get(ord('?'))

    def mancanti(self, testo):
        return sorted({c for c in testo if c not in '\n\r\t' and ord(SOSTITUZIONI.get(c, c)) not in self.glifi})

    def larghezza(self, testo, spaziatura=1):
        """Larghezza in pixel (spaziatura = pixel in più fra un carattere e l'altro)."""
        if not testo:
            return 0
        return sum(self.carattere(c).avanz for c in testo) + spaziatura * (len(testo) - 1)

    def a_capo(self, testo, larghezza_max, spaziatura=1):
        """Divide il testo in righe che stanno in larghezza_max pixel (a capo tra le parole)."""
        righe = []
        for par in testo.split('\n'):
            corrente = ''
            for parola in par.split():
                prova = (corrente + ' ' + parola) if corrente else parola
                if self.larghezza(prova, spaziatura) <= larghezza_max:
                    corrente = prova
                    continue
                if corrente:
                    righe.append(corrente)
                # parola troppo lunga da sola: si spezza
                while self.larghezza(parola, spaziatura) > larghezza_max and len(parola) > 1:
                    k = len(parola)
                    while k > 1 and self.larghezza(parola[:k], spaziatura) > larghezza_max:
                        k -= 1
                    righe.append(parola[:k])
                    parola = parola[k:]
                corrente = parola
            righe.append(corrente)
        return righe

    # --- disegno (per anteprime e prove) ---
    def disegna(self, tela, larg, alt, testo, x, y, colore, bordo=None, spaziatura=1):
        """Disegna su una tela (lista di liste di colori). Con bordo: contorno di 1 pixel."""
        punti = []
        px = x
        for c in testo:
            g = self.carattere(c)
            for gy in range(self.altezza):
                for gx in range(g.larghezza):
                    if g.bit(gx, gy):
                        punti.append((px + g.sinistra + gx, y + gy))
            px += g.avanz + spaziatura
        if bordo is not None:
            for (a, b) in punti:
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if 0 <= a + dx < larg and 0 <= b + dy < alt:
                            tela[b + dy][a + dx] = bordo
        for (a, b) in punti:
            if 0 <= a < larg and 0 <= b < alt:
                tela[b][a] = colore


def scrivi_png(percorso, tela, scala=1):
    """Salva una tela (righe di tuple RGB) come PNG, ingrandita 'scala' volte. Solo zlib."""
    alt = len(tela) * scala
    larg = len(tela[0]) * scala
    grezzo = bytearray()
    for riga in tela:
        r = bytearray()
        for (cr, cg, cb) in riga:
            r += bytes((cr, cg, cb)) * scala
        for _ in range(scala):
            grezzo += b'\0' + r

    def blocco(tipo, dati):
        return struct.pack('>I', len(dati)) + tipo + dati + struct.pack('>I', zlib.crc32(tipo + dati))
    with open(percorso, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + blocco(b'IHDR', struct.pack('>IIBBBBB', larg, alt, 8, 2, 0, 0, 0)) +
                blocco(b'IDAT', zlib.compress(bytes(grezzo), 9)) + blocco(b'IEND', b''))


def main():
    ap = argparse.ArgumentParser(description='Font bitmap in formato testo: informazioni, anteprime, caratteri mancanti.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('info', help='nome, altezza, numero di caratteri')
    p.add_argument('font')
    p = sub.add_parser('anteprima', help='disegna un testo in un PNG')
    p.add_argument('font')
    p.add_argument('testo')
    p.add_argument('png')
    p.add_argument('--scala', type=int, default=3, help='ingrandimento (predefinito 3)')
    p.add_argument('--bordo', action='store_true', help='contorno nero di 1 pixel')
    p = sub.add_parser('mancanti', help='caratteri di un file di testo che il font non ha')
    p.add_argument('font')
    p.add_argument('file')
    a = ap.parse_args()
    try:
        F = Font(a.font)
    except (OSError, ValueError) as e:
        sys.exit('ERRORE: %s' % e)
    if a.cmd == 'info':
        print('%s\naltezza %d, linea di base %d, %d caratteri\nlicenza: %s' % (F.nome, F.altezza, F.linea_base, len(F.glifi), F.licenza))
    elif a.cmd == 'anteprima':
        larg = F.larghezza(a.testo) + 8
        alt = F.altezza + 8
        tela = [[(90, 90, 110)] * larg for _ in range(alt)]
        F.disegna(tela, larg, alt, a.testo, 4, 4, (255, 255, 255), (0, 0, 0) if a.bordo else None)
        scrivi_png(a.png, tela, a.scala)
        print('%s: %d×%d pixel' % (a.png, larg, alt))
    else:
        with open(a.file, encoding='utf-8') as f:
            m = F.mancanti(f.read())
        print('caratteri mancanti (sostituiti con la lettera senza accento o con "?"):' if m else 'nessun carattere mancante')
        for c in m:
            print('  U+%04X %s %s' % (ord(c), c, unicodedata.name(c, '')))


if __name__ == '__main__':
    main()
