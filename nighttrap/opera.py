"""Lettura minima del filesystem Opera (3DO) direttamente da una ISO a 2048 byte per settore.

Serve solo quello che usa la patch: l'etichetta del disco, la directory radice
(con le sue copie, gli "avatar") e le voci dei file.
"""
import struct

BLOCCO = 2048
ULTIMA_NEL_BLOCCO = 0x40000000
ULTIMA_NELLA_DIR = 0x80000000


class ErroreISO(Exception):
    pass


class Voce:
    """Voce di directory Opera (72 byte + avatar aggiuntivi)."""
    def __init__(self, raw, pos):
        (self.flags, self.uid, self.tipo, self.dim_blocco, self.byte, self.blocchi,
         self.burst, self.gap) = struct.unpack('>8I', raw[0:32])
        self.nome = raw[32:64].split(b'\0')[0].decode('latin-1')
        self.ultimo_avatar = struct.unpack('>I', raw[64:68])[0]
        self.avatar = list(struct.unpack('>%dI' % (self.ultimo_avatar + 1), raw[68:68 + 4 * (self.ultimo_avatar + 1)]))
        self.pos = pos                      # posizione nella ISO (byte) della voce
        self.lunghezza = 68 + 4 * (self.ultimo_avatar + 1)

    @property
    def blocco(self):
        return self.avatar[0]


def leggi_etichetta(f):
    f.seek(0)
    b = f.read(132)
    if len(b) < 132 or b[0] != 1 or b[1:6] != b'ZZZZZ':
        raise ErroreISO("non sembra una ISO 3DO (etichetta Opera mancante). "
                        "Serve l'immagine a 2048 byte per settore, non un .bin a 2352.")
    dim_blocco, n_blocchi = struct.unpack('>II', b[76:84])
    radice_blocchi, radice_dim = struct.unpack('>II', b[88:96])
    ultimo = struct.unpack('>I', b[96:100])[0]
    avatar = list(struct.unpack('>%dI' % (ultimo + 1), b[100:100 + 4 * (ultimo + 1)]))
    if dim_blocco != BLOCCO or radice_dim != BLOCCO:
        raise ErroreISO('dimensione dei blocchi inattesa (%d)' % dim_blocco)
    return {'blocchi': n_blocchi, 'radice_blocchi': radice_blocchi, 'radice': avatar}


def leggi_directory(f, blocco, n_blocchi=1):
    """Restituisce le voci della directory che inizia al blocco indicato."""
    voci = []
    for k in range(n_blocchi):
        base = (blocco + k) * BLOCCO
        f.seek(base)
        b = f.read(BLOCCO)
        primo = struct.unpack('>I', b[16:20])[0]
        p = primo
        while p + 72 <= BLOCCO:
            v = Voce(b[p:], base + p)
            voci.append(v)
            if v.flags & (ULTIMA_NEL_BLOCCO | ULTIMA_NELLA_DIR):
                break
            p += v.lunghezza
        if voci and voci[-1].flags & ULTIMA_NELLA_DIR:
            break
    return voci


def radice(f):
    """Etichetta + voci della directory radice (lette dalla prima copia)."""
    et = leggi_etichetta(f)
    return et, leggi_directory(f, et['radice'][0], et['radice_blocchi'])


def leggi_file(f, voce):
    f.seek(voce.blocco * BLOCCO)
    return f.read(voce.byte)
