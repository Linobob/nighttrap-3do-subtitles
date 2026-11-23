"""Preparazione dei testi: a capo in pixel con il font bitmap, pagine da 2 righe, codifica per la routine ARM."""
import os

from .font import Font
from .testo3do import Testi as TestiARM

QUI = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(QUI, '..', 'font', 'dejavu-sans-bold-11.txt')

LARGH_SCHERMO = 320
LARGH_MAX = 260          # pixel per riga: sta dentro la finestra del video (x 24..297) anche con il bordo
RIGHE_PER_PAGINA = 2


class Testi:
    """Testi di un disco: tutti i sottotitoli e le frasi del codice usano la stessa tabella di caratteri."""
    def __init__(self, lingua, percorso_font=FONT):
        self.F = Font(percorso_font)
        self.sost = lingua.get('sostituzioni', {})
        self.arm = TestiARM(self.F)

    @property
    def altezza(self):
        return self.F.altezza

    def prepara(self, t):
        for k, v in self.sost.items():
            t = t.replace(k, v)
        return t

    def mancanti(self, t):
        return self.F.mancanti(self.prepara(t))

    def righe(self, testo):
        return self.F.a_capo(self.prepara(testo), LARGH_MAX)

    def riga(self, t):
        """x (2 byte) + indici dei glifi + 0, centrata nello schermo."""
        t = self.prepara(t)
        x = max(0, (LARGH_SCHERMO - self.arm.larghezza(t)) // 2)
        return x.to_bytes(2, 'big') + self.arm.indici(t)

    def voce(self, righe):
        b = bytearray([len(righe)])
        for r in righe:
            b += self.riga(r)
        return bytes(b)

    def tabella_font(self):
        return self.arm.tabella_font()


def pagine(testo, inizio, fine, testi):
    """Divide una battuta in pagine da 2 righe; il tempo si divide in proporzione ai caratteri."""
    righe = testi.righe(testo)
    pg = [righe[i:i + RIGHE_PER_PAGINA] for i in range(0, len(righe), RIGHE_PER_PAGINA)]
    tot = sum(len(' '.join(p)) for p in pg) or 1
    out, t = [], inizio
    for p in pg:
        d = (fine - inizio) * len(' '.join(p)) / tot
        out.append((t, t + d, p))
        t += d
    return out
