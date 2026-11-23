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
        return self.bilancia(self.F.a_capo(self.prepara(testo), LARGH_MAX))

    def bilancia(self, righe):
        """Due righe di lunghezza simile invece di una piena e una corta (di preferenza a capo dopo la punteggiatura)."""
        if len(righe) != 2:
            return righe
        parole = (righe[0] + ' ' + righe[1]).split()
        meglio, punti = righe, None
        for i in range(1, len(parole)):
            a, b = ' '.join(parole[:i]), ' '.join(parole[i:])
            la, lb = self.F.larghezza(a), self.F.larghezza(b)
            if la > LARGH_MAX or lb > LARGH_MAX:
                continue
            p = max(la, lb)
            if parole[i - 1].endswith(('.', '?', '!', '…', ':', ';', ',')):
                p -= 25
            if punti is None or p < punti:
                meglio, punti = [a, b], p
        return meglio

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


FINE_FRASE = ('.', '?', '!', '…', ':', ';')
DURATA_MIN = 1.2          # secondi minimi per pagina (se la battuta lo permette)


def _dividi(parole, n_pagine, testi):
    """Divide le parole in n_pagine pagine da al massimo 2 righe, il più possibile uguali,
    preferendo spezzare dopo un punto o una virgola. Restituisce le pagine (liste di righe) o None."""
    lung = [len(p) + 1 for p in parole]
    tot = sum(lung)
    obiettivo = tot / n_pagine
    N = len(parole)
    INF = float('inf')
    # costo[k][i] = costo migliore per mettere le prime i parole in k pagine
    costo = [[INF] * (N + 1) for _ in range(n_pagine + 1)]
    da = [[0] * (N + 1) for _ in range(n_pagine + 1)]
    costo[0][0] = 0
    for k in range(1, n_pagine + 1):
        for i in range(1, N + 1):
            for j in range(k - 1, i):
                if costo[k - 1][j] == INF:
                    continue
                pagina = ' '.join(parole[j:i])
                if len(testi.F.a_capo(pagina, LARGH_MAX)) > RIGHE_PER_PAGINA:
                    continue
                c = (sum(lung[j:i]) - obiettivo) ** 2
                if i < N:                                  # punto in cui si spezza
                    fine = parole[i - 1]
                    if fine.endswith(FINE_FRASE):
                        c -= (obiettivo * 0.6) ** 2
                    elif fine.endswith((',', '-', '–')):
                        c -= (obiettivo * 0.3) ** 2
                c += costo[k - 1][j]
                if c < costo[k][i]:
                    costo[k][i] = c
                    da[k][i] = j
    if costo[n_pagine][N] == INF:
        return None
    pagine, i = [], N
    for k in range(n_pagine, 0, -1):
        j = da[k][i]
        pagine.append(testi.bilancia(testi.F.a_capo(' '.join(parole[j:i]), LARGH_MAX)))
        i = j
    return pagine[::-1]


def pagine(testo, inizio, fine, testi):
    """Divide una battuta in pagine da 2 righe (il più possibile uguali, spezzando di preferenza
    a fine frase); il tempo si divide in proporzione ai caratteri, con una durata minima per pagina."""
    righe = testi.righe(testo)
    if len(righe) <= RIGHE_PER_PAGINA:
        return [(inizio, fine, righe)]
    parole = testi.prepara(testo).split()
    n = (len(righe) + RIGHE_PER_PAGINA - 1) // RIGHE_PER_PAGINA
    pg = None
    while pg is None:
        pg = _dividi(parole, n, testi)
        n += 1
    lun = [len(' '.join(p)) for p in pg]
    durata = fine - inizio
    # tempi proporzionali ai caratteri, ma nessuna pagina sotto DURATA_MIN (se c'è tempo)
    quote = [durata * l / sum(lun) for l in lun]
    if durata >= DURATA_MIN * len(pg):
        for _ in range(len(pg)):
            corte = [i for i, q in enumerate(quote) if q < DURATA_MIN]
            if not corte:
                break
            manca = sum(DURATA_MIN - quote[i] for i in corte)
            lunghe = [i for i in range(len(quote)) if i not in corte]
            disp = sum(quote[i] - DURATA_MIN for i in lunghe)
            for i in corte:
                quote[i] = DURATA_MIN
            for i in lunghe:
                quote[i] -= manca * (quote[i] - DURATA_MIN) / disp if disp > 0 else 0
    out, t = [], inizio
    for p, q in zip(pg, quote):
        out.append((t, t + q, p))
        t += q
    return out
