"""Crea la ISO modificata e (se richiesto) la patch BPS in un solo passaggio.

Le modifiche sono note in anticipo (posizione, byte nuovi), quindi la patch BPS
si scrive direttamente: SourceRead per le parti uguali, TargetRead per quelle cambiate.
Formato BPS: https://www.romhacking.net/documents/746/ (beat, byuu).
"""
import zlib

PEZZO = 1 << 22


def _num(n):
    out = bytearray()
    while True:
        x = n & 0x7f
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def unisci(modifiche):
    """Ordina e fonde le modifiche che si toccano o si sovrappongono (vince l'ultima)."""
    mod = sorted(modifiche, key=lambda m: m[0])
    out = []
    for pos, b in mod:
        if out and pos <= out[-1][0] + len(out[-1][1]):
            p0, b0 = out[-1]
            nuovo = bytearray(b0)
            fine = pos + len(b) - p0
            if fine > len(nuovo):
                nuovo += b'\0' * (fine - len(nuovo))
            nuovo[pos - p0:pos - p0 + len(b)] = b
            out[-1] = (p0, bytes(nuovo))
        else:
            out.append((pos, bytes(b)))
    return out


def crea(sorgente, destinazione, modifiche, file_bps=None, metadati=b''):
    """Copia sorgente in destinazione applicando le modifiche; scrive anche la BPS.
    Restituisce (crc sorgente, crc destinazione, dimensione destinazione)."""
    mod = unisci(modifiche)
    with open(sorgente, 'rb') as f:
        f.seek(0, 2)
        dim_s = f.seek(0, 2)
    dim_t = max([dim_s] + [p + len(b) for p, b in mod])
    crc_s = crc_t = 0
    azioni = bytearray()
    with open(sorgente, 'rb') as fs, open(destinazione, 'wb') as ft:
        pos = 0
        i = 0
        while pos < dim_t:
            # prossima modifica
            prossima = mod[i][0] if i < len(mod) else dim_t
            if pos < prossima:
                # tratto uguale alla sorgente (o zeri oltre la sua fine)
                n = prossima - pos
                copia = min(n, max(0, dim_s - pos))
                rest = n
                while rest:
                    k = min(rest, PEZZO)
                    if pos < dim_s:
                        fs.seek(pos)
                        dati = fs.read(min(k, dim_s - pos))
                        k = len(dati)
                        crc_s = zlib.crc32(dati, crc_s)
                    else:
                        dati = b'\0' * k
                    ft.write(dati)
                    crc_t = zlib.crc32(dati, crc_t)
                    pos += k
                    rest -= k
                if copia:
                    azioni += _num(((copia - 1) << 2) | 0)              # SourceRead
                if n - copia:
                    azioni += _num(((n - copia - 1) << 2) | 1) + b'\0' * (n - copia)   # TargetRead (zeri)
            else:
                _, b = mod[i]
                i += 1
                if pos < dim_s:
                    fs.seek(pos)
                    vecchi = fs.read(min(len(b), dim_s - pos))
                    crc_s = zlib.crc32(vecchi, crc_s)
                ft.write(b)
                crc_t = zlib.crc32(b, crc_t)
                azioni += _num(((len(b) - 1) << 2) | 1) + b           # TargetRead
                pos += len(b)
    if file_bps:
        p = bytearray(b'BPS1') + _num(dim_s) + _num(dim_t) + _num(len(metadati)) + metadati + azioni
        p += crc_s.to_bytes(4, 'little') + crc_t.to_bytes(4, 'little')
        p += zlib.crc32(p).to_bytes(4, 'little')
        with open(file_bps, 'wb') as fb:
            fb.write(p)
    return crc_s, crc_t, dim_t


def applica(sorgente_bytes, patch):
    """Applicatore BPS di controllo (tiene tutto in memoria: solo per i test)."""
    def num(p, i):
        d, s = 0, 1
        while True:
            x = patch[i]; i += 1
            d += (x & 0x7f) * s
            if x & 0x80:
                return d, i
            s <<= 7
            d += s
    assert patch[:4] == b'BPS1'
    i = 4
    dim_s, i = num(patch, i)
    dim_t, i = num(patch, i)
    m, i = num(patch, i)
    i += m
    out = bytearray()
    rel_s = rel_t = 0
    fine = len(patch) - 12
    while i < fine:
        d, i = num(patch, i)
        modo, n = d & 3, (d >> 2) + 1
        if modo == 0:
            out += sorgente_bytes[len(out):len(out) + n]
        elif modo == 1:
            out += patch[i:i + n]; i += n
        elif modo == 2:
            o, i = num(patch, i); rel_s += (-1 if o & 1 else 1) * (o >> 1)
            out += sorgente_bytes[rel_s:rel_s + n]; rel_s += n
        else:
            o, i = num(patch, i); rel_t += (-1 if o & 1 else 1) * (o >> 1)
            for _ in range(n):
                out.append(out[rel_t]); rel_t += 1
    assert len(out) == dim_t
    assert zlib.crc32(out) == int.from_bytes(patch[-8:-4], 'little')
    return bytes(out)
