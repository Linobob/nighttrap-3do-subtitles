"""Preparazione dei testi per il font del gioco (solo ASCII maiuscolo, ~9 pixel per carattere)."""
import textwrap

MAX_CARATTERI = 29   # per riga
LARGH_CAR = 9
LARGH_SCHERMO = 320
RIGHE_PER_PAGINA = 2

SOSTITUZIONI_BASE = {'–': '-', '—': '-', '’': "'", '‘': "'", '“': '"', '”': '"', '…': '...', '«': '"', '»': '"'}


class Testi:
    def __init__(self, lingua):
        self.sost = dict(SOSTITUZIONI_BASE)
        self.sost.update(lingua.get('sostituzioni', {}))
        self.non_convertiti = set()

    def ascii(self, t):
        for k, v in self.sost.items():
            t = t.replace(k, v)
        out = bytearray()
        for ch in t.upper():
            if ord(ch) < 128:
                out += ch.encode()
            else:
                self.non_convertiti.add(ch)
                out += b'?'
        return bytes(out)

    def riga(self, t):
        """x (byte) + testo + \\0, centrato."""
        a = self.ascii(t)
        x = max(0, (LARGH_SCHERMO - LARGH_CAR * len(a)) // 2)
        return bytes([x]) + a + b'\0'

    def voce(self, righe):
        b = bytearray([len(righe)])
        for r in righe:
            b += self.riga(r)
        return bytes(b)


def pagine(testo, inizio, fine, testi=None):
    """Divide una battuta in pagine da 2 righe; il tempo si divide in proporzione ai caratteri.
    Se si passa `testi`, si va a capo dopo la conversione per il font (es. "e'" occupa 2 caratteri):
    una riga troppo lunga uscirebbe dal video e lascerebbe un pezzo di lettera sul bordo."""
    if testi is not None:
        testo = testi.ascii(testo).decode('ascii')
    righe = textwrap.wrap(testo, MAX_CARATTERI)
    pg = [righe[i:i + RIGHE_PER_PAGINA] for i in range(0, len(righe), RIGHE_PER_PAGINA)]
    tot = sum(len(' '.join(p)) for p in pg)
    out, t = [], inizio
    for p in pg:
        d = (fine - inizio) * len(' '.join(p)) / tot
        out.append((t, t + d, p))
        t += d
    return out
