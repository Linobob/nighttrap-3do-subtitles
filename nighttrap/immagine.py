"""Accesso all'immagine del disco, sia ISO (2048 byte per settore) sia BIN (2352, MODE1).

Il resto del codice ragiona sempre in byte "logici" (come in una ISO a 2048):
questa classe traduce le posizioni e, per le BIN, ricalcola EDC ed ECC dei settori modificati.
"""
import os

LOGICO = 2048
GREZZO = 2352
SYNC = b'\x00' + b'\xff' * 10 + b'\x00'

# --- EDC / ECC dei settori MODE1 (come da standard ECMA-130) ---
_EDC = []
for _i in range(256):
    _e = _i
    for _ in range(8):
        _e = (_e >> 1) ^ (0xD8018001 if _e & 1 else 0)
    _EDC.append(_e)
_ECC_F = [0] * 256
_ECC_B = [0] * 256
for _i in range(256):
    _j = ((_i << 1) ^ (0x11D if _i & 0x80 else 0)) & 0xff
    _ECC_F[_i] = _j
    _ECC_B[_i ^ _j] = _i


def _edc(dati):
    e = 0
    for b in dati:
        e = (e >> 8) ^ _EDC[(e ^ b) & 0xff]
    return e


def _ecc(src, major_count, minor_count, major_mult, minor_inc):
    size = major_count * minor_count
    out = bytearray(major_count * 2)
    f, bb = _ECC_F, _ECC_B
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            t = src[index]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= t
            b ^= t
            a = f[a]
        a = bb[f[a] ^ b]
        out[major] = a
        out[major + major_count] = a ^ b
    return out


def ripara_settore(s):
    """Ricalcola EDC ed ECC di un settore MODE1 da 2352 byte (bytearray, modificato sul posto)."""
    s[0x810:0x814] = _edc(s[0:0x810]).to_bytes(4, 'little')
    s[0x814:0x81C] = b'\0' * 8
    s[0x81C:0x8C8] = _ecc(s[0xC:], 86, 24, 2, 86)
    s[0x8C8:0x930] = _ecc(s[0xC:], 52, 43, 86, 88)
    return s


def file_da_cue(percorso):
    """Se viene indicato un .cue, restituisce il file dati (il primo FILE)."""
    if not percorso.lower().endswith('.cue'):
        return percorso
    with open(percorso, encoding='latin-1') as c:
        for riga in c:
            r = riga.strip()
            if r.upper().startswith('FILE'):
                nome = r[4:].strip()
                if nome.startswith('"'):
                    nome = nome[1:nome.index('"', 1)]
                else:
                    nome = nome.split()[0]
                return os.path.join(os.path.dirname(percorso), nome)
    raise ValueError('nel .cue non trovo la riga FILE')


class Immagine:
    """File-like in sola lettura con posizioni logiche (a 2048 byte per settore)."""
    def __init__(self, percorso):
        self.percorso = percorso
        self.f = open(percorso, 'rb')
        dim = os.path.getsize(percorso)
        testa = self.f.read(16)
        self.grezzo = dim % GREZZO == 0 and testa[:12] == SYNC
        if self.grezzo and testa[15] != 1:
            raise ValueError('immagine BIN non in MODE1')
        self.passo = GREZZO if self.grezzo else LOGICO
        self.pos = 0

    @property
    def estensione(self):
        return '.bin' if self.grezzo else '.iso'

    @property
    def modo_cue(self):
        return 'MODE1/2352' if self.grezzo else 'MODE1/2048'

    def seek(self, pos, da=0):
        self.pos = pos
        return pos

    def read(self, n):
        if not self.grezzo:
            self.f.seek(self.pos)
            d = self.f.read(n)
            self.pos += len(d)
            return d
        out = bytearray()
        while n > 0:
            sett, off = divmod(self.pos, LOGICO)
            k = min(n, LOGICO - off)
            self.f.seek(sett * GREZZO + 16 + off)
            d = self.f.read(k)
            if not d:
                break
            out += d
            self.pos += len(d)
            n -= len(d)
        return bytes(out)

    def settore_grezzo(self, sett):
        self.f.seek(sett * GREZZO)
        return bytearray(self.f.read(GREZZO))

    def controlla_ecc(self, settori):
        """Verifica che il calcolo di EDC/ECC dia gli stessi byte dell'immagine originale."""
        for s in settori:
            orig = self.settore_grezzo(s)
            if bytes(ripara_settore(bytearray(orig))) != bytes(orig):
                return False
        return True

    def modifiche_fisiche(self, modifiche):
        """Da modifiche logiche (pos, byte) a modifiche nel file (per le BIN: settori interi ricalcolati)."""
        if not self.grezzo:
            return modifiche
        per_settore = {}
        for pos, b in modifiche:
            i = 0
            while i < len(b):
                sett, off = divmod(pos + i, LOGICO)
                k = min(len(b) - i, LOGICO - off)
                per_settore.setdefault(sett, []).append((off, b[i:i + k]))
                i += k
        out = []
        for sett in sorted(per_settore):
            vecchio = self.settore_grezzo(sett)
            if len(vecchio) < GREZZO:
                raise ValueError('settore %d oltre la fine dell\'immagine' % sett)
            s = bytearray(vecchio)
            for off, b in per_settore[sett]:
                s[16 + off:16 + off + len(b)] = b
            ripara_settore(s)
            # solo i tratti cambiati (dati, EDC, ECC), cosi' la patch BPS resta piccola
            i = 0
            while i < GREZZO:
                if s[i] == vecchio[i]:
                    i += 1
                    continue
                j = i
                uguali = 0
                while j < GREZZO and uguali < 8:
                    uguali = uguali + 1 if s[j] == vecchio[j] else 0
                    j += 1
                fine = j - uguali
                out.append((sett * GREZZO + i, bytes(s[i:fine])))
                i = j
        return out

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
