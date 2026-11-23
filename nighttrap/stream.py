"""Stream video Digital Pictures: trova i fotogrammi di una clip dentro il file dati.

Ogni fotogramma (12 al secondo) e' un blocco di ~16 KB con un record video
(81 nn 39 c8) e un record audio (a2 00 06 30); il video sta 0x39cc byte prima
dell'audio. I byte 4-7 del record video (timecode, non usato dal gioco) ospitano
il marcatore del sottotitolo: 5B id_alto id_basso 5D.
"""
import re

AUDIO = re.compile(rb'\xa2\x00\x06\x30')
VIDEO_PRIMA_DELL_AUDIO = 0x39cc
MAX_BLOCCO = 0x4200    # i fotogrammi sono a 0x4000 o 0x4200 byte l'uno dall'altro


def fotogrammi(f, inizio_dati, clip):
    """Posizioni (relative al file dati) dei record video della clip, in ordine."""
    f.seek(inizio_dati + clip['offset'])
    buf = f.read(clip['fotogrammi'] * MAX_BLOCCO + 16)
    pos = [m.start() for m in AUDIO.finditer(buf)][:clip['fotogrammi']]
    if not pos or pos[0] != 0 or len(pos) < clip['fotogrammi']:
        raise ValueError('clip %s non trovata dove previsto' % clip['clip'])
    out = []
    for p in pos:
        v = p - VIDEO_PRIMA_DELL_AUDIO
        out.append(clip['offset'] + v)
    return out


def marcatore(n):
    return bytes([0x5B, n >> 8, n & 255, 0x5D])
