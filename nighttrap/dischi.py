"""Dati fissi dei due dischi di Night Trap (3DO, USA, 1993).

Gli indirizzi sono quelli del Launchme originale (eseguibile AIF ARM60 big-endian,
caricato all'indirizzo 0). Sono stati trovati con il reverse engineering:
vedi docs/ per il significato di ognuno.
"""

DISCHI = {
    1: dict(
        nome_iso='Disc 1',
        launchme_sha1='f4381e91d4909698992cd50633416bb7c4e923e3',
        file_dati='disc1data.bin',
        # struttura dell'eseguibile
        RO=0x24d94,          # fine della parte di sola lettura: qui si inserisce il codice nuovo
        RELOC=0x291d0,       # codice di auto-rilocazione (la tabella e' a RELOC+0xb8)
        # routine di disegno del testo usate dal gioco (blocco "debug" di PlayStreamingVideo)
        GCON=0x27dd0, SEL=0x2847c, BMS=0x28444,
        MOVETO=0x2331c, SETFG=0x23334, SETBG=0x23328, DRAW=0x234bc,
        FLAG=0x27d0c,        # byte che accende il blocco di disegno del testo
        CUR=0x27d78,         # parola libera usata per il sottotitolo corrente
        H1=0x6370, H2=0x63cc, H2B=0x63d0, DOPO=0x6420,
        # frasi del cambio codice: ReadyCodePhrase / GetNextAudio
        H4=0x119dc,          # subito dopo StartInstrument della frase
        STATO=0x28b10,       # struttura di stato del gioco (codici a +0x1d8...)
        ORA=0x289fc,         # momento (in fotogrammi) a cui parte la frase
        FRASI=[(0x76, 0x1d8), (0x93c, 0x1dc), (0xbc, 0x1e0)],   # (momento, colore annunciato)
        # solo per la prova del cambio disco
        TEMPO=0x24db0, VAR_A=0x24da8, VAR_B=0x24dac,
        CAMBIO_DISCO=0x1dd64, AVVIO_PARTITA=0x19e18,
    ),
    2: dict(
        nome_iso='Disc 2',
        launchme_sha1='fc8a6f1dddb7fbff26a6f6454d76f8c0f69c8053',
        file_dati='disc2data.bin',
        RO=0x23b28, RELOC=0x27b10,
        GCON=0x26b54, SEL=0x27300, BMS=0x272c8,
        MOVETO=0x220c8, SETFG=0x220e0, SETBG=0x220d4, DRAW=0x22268,
        FLAG=0x26a90, CUR=0x26afc,
        H1=0xc75c, H2=0xc7b8, H2B=0xc7bc, DOPO=0xc80c,
        H4=0x12184, STATO=0x27590, ORA=0x2747c,
        FRASI=[(0x6c, 0x1d8)],
    ),
}

# colori dei codici d'accesso, nell'ordine usato dal gioco (indice 0..5), in RGB555
RGB_COLORI = [0x03e0, 0x7c00, 0x7fe0, 0x611f, 0x7e40, 0x221f]   # verde rosso giallo viola arancione blu
DURATA_COLORE = 60   # fotogrammi (12 al secondo): circa 5 secondi
FPS = 12
