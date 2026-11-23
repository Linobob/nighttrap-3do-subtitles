#!/usr/bin/env python3
"""Mini assemblatore ARMv3 big-endian (ARM60, 3DO), da usare come libreria Python.

Non legge file sorgente: le istruzioni si scrivono chiamando i metodi della classe Asm.
Gestisce etichette in avanti e all'indietro e un literal pool per caricare indirizzi
relativi al PC (codice che funziona ovunque venga caricato, senza rilocazione).

Esempio:
    from armasm import Asm
    A = Asm(0x24d94)                 # indirizzo dove andra' il codice
    A.label('somma')
    A.dp('add', 'r0', 'r0', 'r1')    # r0 = r0 + r1
    A.mov('pc', 'lr')                # ritorno
    codice = A.assemble()            # bytes big-endian

Da riga di comando c'e' solo una prova:  python3 armasm.py --prova
"""
import argparse
import struct

CC = {'eq': 0, 'ne': 1, 'cs': 2, 'cc': 3, 'mi': 4, 'pl': 5, 'vs': 6, 'vc': 7, 'hi': 8, 'ls': 9,
      'ge': 10, 'lt': 11, 'gt': 12, 'le': 13, '': 14}
OPS = {'and': 0, 'eor': 1, 'sub': 2, 'rsb': 3, 'add': 4, 'adc': 5, 'sbc': 6, 'rsc': 7,
       'tst': 8, 'teq': 9, 'cmp': 10, 'cmn': 11, 'orr': 12, 'mov': 13, 'bic': 14, 'mvn': 15}
SHIFT = {'lsl': 0, 'lsr': 1, 'asr': 2, 'ror': 3}


def reg(r):
    """'r0'..'r15', 'sp', 'lr', 'pc' oppure il numero del registro."""
    if isinstance(r, int):
        return r
    if r in ('sp', 'lr', 'pc'):
        return {'sp': 13, 'lr': 14, 'pc': 15}[r]
    if r[:1] == 'r' and r[1:].isdigit() and int(r[1:]) < 16:
        return int(r[1:])
    raise ValueError('registro non valido: %r' % (r,))


def imm8(v):
    """Codifica un immediato ARM (8 bit ruotati di un numero pari di posizioni)."""
    v &= 0xffffffff
    for rot in range(16):
        x = ((v << (2 * rot)) | (v >> (32 - 2 * rot))) & 0xffffffff if rot else v
        if x < 256:
            return (rot << 8) | x
    raise ValueError('immediato non codificabile in una sola istruzione: 0x%x' % v)


class Asm:
    def __init__(s, base):
        s.base = base        # indirizzo della prima istruzione
        s.items = []         # funzioni pc -> parola, oppure bytes (dati)
        s.lab = {}           # etichette -> indirizzo
        s.pool = []

    def label(s, n):
        s.lab[n] = s.pc()

    def pc(s):
        return s.base + sum(len(i) if isinstance(i, bytes) else 4 for i in s.items)

    def emit(s, f):
        s.items.append(f)

    def dp(s, op, rd, rn, o2, c='', S=0, sh=None):
        """Elaborazione dati: op rd, rn, o2  (o2 = immediato oppure registro, con sh=('lsl', n))."""
        def f(pc):
            w = (CC[c] << 28) | (OPS[op] << 21) | (S << 20) | (reg(rn) << 16) | (reg(rd) << 12)
            if op in ('cmp', 'cmn', 'tst', 'teq'):
                w |= 1 << 20
            if isinstance(o2, int):
                w |= (1 << 25) | imm8(o2)
            else:
                w |= reg(o2)
                if sh:
                    w |= (SHIFT[sh[0]] << 5) | (sh[1] << 7)
            return w
        s.emit(f)

    def mov(s, rd, o2, c=''):
        s.dp('mov', rd, 0, o2, c)

    def mul(s, rd, rm, rs, c='', ra=None):
        """mul rd, rm, rs  (rd = rm * rs); con ra: mla rd, rm, rs, ra (rd = rm * rs + ra).
        Sull'ARMv3 rd deve essere diverso da rm."""
        if reg(rd) == reg(rm):
            raise ValueError('mul: rd e rm devono essere registri diversi')
        def f(pc):
            w = (CC[c] << 28) | (reg(rd) << 16) | (reg(rs) << 8) | 0x90 | reg(rm)
            if ra is not None:
                w |= (1 << 21) | (reg(ra) << 12)
            return w
        s.emit(f)

    def ldst(s, L, B, rt, rn, off=0, c='', post=False, regoff=None, lsl=0):
        """ldr/str (L=1/0), byte (B=1) o parola (B=0). off puo' essere un numero o un'etichetta
        (solo con rn='pc'); regoff = registro di offset, con spostamento lsl."""
        def f(pc):
            o = off
            w = (CC[c] << 28) | (1 << 26) | ((0 if post else 1) << 24) | (L << 20) | (B << 22) | \
                (reg(rn) << 16) | (reg(rt) << 12)
            if regoff is not None:
                w |= (1 << 25) | (1 << 23) | reg(regoff) | (lsl << 7)
            else:
                if isinstance(o, str):
                    o = s.lab[o] - (pc + 8)
                if abs(o) >= 4096:
                    raise ValueError('offset troppo grande per ldr/str: %d' % o)
                w |= ((1 << 23) if o >= 0 else 0) | abs(o)
            return w
        s.emit(f)

    def b(s, t, c='', link=0):
        """Salto a un'etichetta o a un indirizzo assoluto."""
        def f(pc):
            tt = s.lab[t] if isinstance(t, str) else t
            off = (tt - (pc + 8)) >> 2
            return (CC[c] << 28) | (5 << 25) | (link << 24) | (off & 0xffffff)
        s.emit(f)

    def bl(s, t, c=''):
        s.b(t, c, 1)

    def stmfd(s, regs):
        s.emit(lambda pc: 0xe92d0000 | sum(1 << reg(r) for r in regs))

    def ldmfd(s, regs):
        s.emit(lambda pc: 0xe8bd0000 | sum(1 << reg(r) for r in regs))

    def addr(s, rd, target):
        """rd = indirizzo assoluto di target() (funzione senza argomenti), calcolato relativo al PC:
        ldr rd, =distanza ; add rd, pc, rd. Il valore va nel literal pool (vedi flush_pool)."""
        lit = '_lit%d_pool' % len(s.items)
        s.ldst(1, 0, rd, 'pc', lit)
        a = [None]

        def f(pc):
            a[0] = pc
            return 0xe08f0000 | (reg(rd) << 16) | (reg(rd) << 12) | reg(rd)     # add rd, pc, rd
        s.emit(f)
        s.pool.append((lit, lambda: (target() - (a[0] + 8)) & 0xffffffff))

    def word(s, v):
        s.emit(lambda pc, v=v: v)

    def data(s, b):
        s.items.append(bytes(b))

    def flush_pool(s):
        """Scrive qui il literal pool (va messo entro 4 KB dalle istruzioni che lo usano)."""
        for n, fn in s.pool:
            s.lab[n] = s.pc()
            s.emit(lambda pc, fn=fn: fn())
        s.pool = []

    def assemble(s):
        """Codifica tutto. Le etichette sono gia' note (vengono fissate mentre si scrive)."""
        out = bytearray()
        pc = s.base
        for it in s.items:
            if isinstance(it, bytes):
                out += it
                pc += len(it)
            else:
                out += struct.pack('>I', it(pc) & 0xffffffff)
                pc += 4
        return bytes(out)


def _prova():
    from armdis import dis
    A = Asm(0x1000)
    A.label('inizio')
    A.stmfd(['r4', 'lr'])
    A.dp('add', 'r0', 'r0', 'r1', sh=('lsl', 2))
    A.dp('cmp', 0, 'r0', 0x40)
    A.b('fine', 'gt')
    A.addr('r4', lambda: A.lab['dati'])
    A.ldst(1, 0, 'r0', 'r4', 4)
    A.label('fine')
    A.ldmfd(['r4', 'pc'])
    A.flush_pool()
    A.label('dati')
    A.word(0x12345678)
    A.word(0xcafe)
    codice = A.assemble()
    for i in range(0, len(codice), 4):
        w = struct.unpack('>I', codice[i:i + 4])[0]
        print('%06x: %08x  %s' % (0x1000 + i, w, dis(w, 0x1000 + i)[0]))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Mini assemblatore ARMv3 big-endian: si usa da Python '
                                 '(vedi il README di cpu/arm). Da riga di comando fa solo una prova.')
    ap.add_argument('--prova', action='store_true', help='assembla un piccolo esempio e lo mostra disassemblato')
    if ap.parse_args().prova:
        _prova()
    else:
        ap.print_help()
