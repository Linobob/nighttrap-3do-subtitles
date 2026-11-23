"""Costruisce il nuovo Launchme: aggiunge il codice dei sottotitoli e i testi.

Il codice nuovo viene inserito alla fine della parte di sola lettura (RO); tutto
quello che sta dopo (dati RW, codice di rilocazione) si sposta di `delta` byte e
la tabella di rilocazione viene corretta di conseguenza.
Gli hook:
  hook1  (in PlayStreamingVideo) legge il marcatore [id] scritto nel fotogramma e
         calcola dove sta il video sullo schermo;
  hook2  disegna il sottotitolo (e il colore del codice) con le routine di testo
         del gioco, al posto del suo blocco di debug;
  hook4  dopo che parte la frase del cambio codice, ricorda il colore annunciato;
  hook3  (solo prova) all'avvio salta subito al cambio disco.
"""
import struct
from .armasm import Asm
from .dischi import RGB_COLORI, DURATA_COLORE

PASSO_RIGA = 11   # pixel tra una riga e l'altra


def reloc_table(d, TAB):
    p = TAB; T = []
    while True:
        w = struct.unpack('>I', d[p:p+4])[0]; p += 4
        if w == 0xffffffff:
            return T
        T.append(w)


def costruisci(ORIG, C, voci, voci_colore, test_cambio=False):
    """ORIG: Launchme originale; C: dati del disco (dischi.py);
    voci: testi gia' pronti (Testi.voce), il primo ha id 1; voci_colore: 6 righe (Testi.riga).
    Restituisce (nuovo Launchme, etichette)."""
    RO=C['RO']; TAB=C['RELOC']+0xb8
    if len(voci)>65535: raise ValueError('troppi sottotitoli')
    # ---------- codice ----------
    A=Asm(RO)
    lab=A.lab
    delta_box=[0]
    RW=lambda a: (lambda: a+delta_box[0])          # indirizzi RW dopo lo spostamento
    CUR=RW(C['CUR']); GCON=RW(C['GCON']); SEL=RW(C['SEL']); BMS=RW(C['BMS'])
    MOVETO=C['MOVETO']; SETFG=C['SETFG']; SETBG=C['SETBG']; DRAW=C['DRAW']
    # hook1: salva altezza video (byte 0xb) e marcatore [id] del fotogramma (r4)
    A.label('hook1')
    A.addr('r1',CUR)
    A.ldst(1,1,'r0','r4',0xb)                     # altezza del video in righe di tile
    A.ldst(1,0,'r2','sp',0x24); A.dp('cmp',0,'r2',0)   # 0 = video nella finestra di gioco
    A.mov('r2',16,'eq');  A.dp('add','r0','r2','r0',c='eq',sh=('lsl',3))   # fondo = 16 + h*8
    A.mov('r2',120,'ne'); A.dp('add','r0','r2','r0',c='ne',sh=('lsl',2))   # fondo = 120 + h*4
    A.ldst(0,1,'r0','r1',4)
    A.ldst(1,1,'r0','r4',4); A.dp('cmp',0,'r0',0x5B)
    A.mov('r0',0,'ne'); A.b('h1s','ne')
    A.ldst(1,1,'r0','r4',5); A.ldst(1,1,'r2','r4',6)
    A.dp('orr','r0','r2','r0',sh=('lsl',8))
    A.label('h1s'); A.ldst(0,0,'r0','r1',0)
    # cima del video (per il sottotitolo del colore) e conto alla rovescia del colore
    A.ldst(1,1,'r0','r4',0xb)
    A.ldst(1,0,'r2','sp',0x24); A.dp('cmp',0,'r2',0)
    A.mov('r0',16,'eq')
    A.mov('r2',120,'ne'); A.dp('sub','r0','r2','r0',c='ne',sh=('lsl',2))   # cima = 120 - h*4
    A.addr('r1',lambda: lab['VARS']); A.ldst(0,0,'r0','r1',8)
    A.ldst(1,0,'r0','r1',0); A.dp('cmp',0,'r0',0)
    A.dp('sub','r0','r0',1,c='gt'); A.ldst(0,0,'r0','r1',0,c='gt')
    A.mov('r0','r4'); A.mov('pc','lr')
    # hook2: disegna il sottotitolo dentro il fondo del video
    A.label('hook2')
    A.stmfd(['r4','r5','r6','r7','r8','lr'])
    A.addr('r7',GCON)
    A.addr('r0',SEL); A.ldst(1,0,'r0','r0',0)
    A.addr('r1',BMS); A.ldst(1,0,'r8','r1',regoff='r0',lsl=2)
    # colore del codice appena annunciato, in cima al video
    A.addr('r5',lambda: lab['VARS']); A.ldst(1,0,'r0','r5',0); A.dp('cmp',0,'r0',0); A.b('dial','eq')
    A.ldst(1,0,'r6','r5',4); A.ldst(1,0,'r4','r5',8); A.dp('add','r4','r4',3)
    A.mov('r0','r7'); A.mov('r1',0); A.bl(SETBG)
    A.addr('r1',lambda: lab['COLS']); A.ldst(1,0,'r1','r1',regoff='r6',lsl=2)
    A.mov('r0','r7'); A.bl(SETFG)
    A.addr('r5',lambda: lab['CTAB']); A.dp('add','r5','r5','r6',sh=('lsl',6))
    A.ldst(1,1,'r1','r5',1,post=True)
    A.mov('r0','r7'); A.mov('r2','r4'); A.bl(MOVETO)
    A.mov('r0','r7'); A.mov('r1','r8'); A.mov('r2','r5'); A.bl(DRAW)
    A.label('dial')
    A.addr('r4',CUR); A.ldst(1,0,'r0','r4',0); A.dp('cmp',0,'r0',0); A.b('fine','eq')
    A.ldst(1,1,'r4','r4',4)                       # fondo del video (calcolato in hook1)
    A.addr('r5',lambda: lab['TABLE']); A.ldst(1,0,'r1','r5',regoff='r0',lsl=2); A.dp('add','r5','r5','r1')
    A.ldst(1,1,'r6','r5',1,post=True)             # numero di righe
    A.dp('add','r1','r6','r6',sh=('lsl',1)); A.dp('add','r1','r1','r6',sh=('lsl',3))  # n*11
    A.dp('sub','r4','r4','r1'); A.dp('sub','r4','r4',2)
    A.mov('r0','r7'); A.mov('r1',0); A.bl(SETBG)
    A.mov('r0','r7'); A.mov('r1',0x7f00); A.dp('orr','r1','r1',0xff); A.bl(SETFG)
    A.label('riga')
    A.dp('cmp',0,'r6',0); A.b('fine','eq')
    A.ldst(1,1,'r1','r5',1,post=True)             # x
    A.mov('r0','r7'); A.mov('r2','r4'); A.bl(MOVETO)
    A.mov('r0','r7'); A.mov('r1','r8'); A.mov('r2','r5'); A.bl(DRAW)
    A.label('salta'); A.ldst(1,1,'r0','r5',1,post=True); A.dp('cmp',0,'r0',0); A.b('salta','ne')
    A.dp('add','r4','r4',PASSO_RIGA); A.dp('sub','r6','r6',1)
    A.b('riga')
    A.label('fine'); A.ldmfd(['r4','r5','r6','r7','r8','pc'])
    if test_cambio:
        # PROVA: all'avvio della partita imposta uno stato valido per il disco 2 e chiama il cambio disco
        A.label('hook3')
        A.addr('r0',RW(C['TEMPO'])); A.mov('r1',0x2700); A.dp('orr','r1','r1',0x10); A.ldst(0,0,'r1','r0',0)   # tempo 10000
        A.mov('r1',0)
        A.addr('r0',RW(C['VAR_A'])); A.ldst(0,0,'r1','r0',0)
        A.addr('r0',RW(C['VAR_B'])); A.ldst(0,0,'r1','r0',0)
        A.addr('r0',RW(C['STATO'])); A.ldst(0,0,'r1','r0',0x7c); A.ldst(0,0,'r1','r0',0x78)
        A.ldst(1,0,'r1','r0',0x1e0); A.dp('cmp',0,'r1',5); A.mov('r1',1,'hi'); A.ldst(0,0,'r1','r0',0x1e0)
        A.b(C['CAMBIO_DISCO'])
    # hook4: dopo StartInstrument della frase del codice, ricorda quale colore e stato annunciato
    A.label('hook4')
    A.mov('r6','r0'); A.dp('cmp',0,'r0',0); A.mov('pc','lr','lt')
    A.addr('r1',RW(C['ORA'])); A.ldst(1,0,'r1','r1',0)
    A.addr('r2',lambda: lab['FRASI'])
    A.label('h4l')
    A.ldst(1,0,'r3','r2',4,post=True); A.dp('cmn',0,'r3',1); A.mov('pc','lr','eq')
    A.ldst(1,0,'r12','r2',4,post=True); A.dp('cmp',0,'r3','r1'); A.b('h4l','ne')
    A.addr('r0',RW(C['STATO'])); A.ldst(1,0,'r0','r0',regoff='r12')
    A.dp('cmp',0,'r0',5); A.mov('pc','lr','hi')
    A.addr('r1',lambda: lab['VARS']); A.ldst(0,0,'r0','r1',4)
    A.mov('r0',DURATA_COLORE); A.ldst(0,0,'r0','r1',0)
    A.mov('pc','lr')
    A.flush_pool()
    A.label('VARS'); A.word(0); A.word(0); A.word(0)
    A.label('FRASI')
    for t,o in C['FRASI']: A.word(t); A.word(o)
    A.word(0xffffffff)
    A.label('COLS')
    for c in RGB_COLORI: A.word(c)
    A.label('CTAB')
    for v in voci_colore:
        if len(v)>64: raise ValueError('frase del codice troppo lunga')
        A.data(v+b'\0'*(64-len(v)))
    # tabella: offset (dalla TABLE) di ogni voce; indice 0 non usato
    A.label('TABLE')
    n=len(voci); offs=[]; pos=4*(n+1)
    for v in voci: offs.append(pos); pos+=len(v)
    A.word(0)
    for o in offs: A.word(o)
    for v in voci: A.data(v)
    blob=A.assemble()
    pad=(-len(blob))%16; blob+=b'\0'*pad
    delta=len(blob); delta_box[0]=delta
    blob=A.assemble()+b'\0'*pad          # riassembla con gli indirizzi definitivi
    assert len(blob)==delta
    # ---------- ricollegamento ----------
    T=reloc_table(ORIG,TAB)
    d=bytearray(ORIG)
    # hook nel codice originale (prima dello spostamento: il RO non si muove)
    def put(a,w): d[a:a+4]=struct.pack('>I',w)
    def bl_to(a,t): return 0xeb000000|(((t-(a+8))>>2)&0xffffff)
    put(C['H1'], bl_to(C['H1'], lab['hook1']))
    put(C['H2'], bl_to(C['H2'], lab['hook2']))
    put(C['H2B'], 0xea000000|(((C['DOPO']-(C['H2B']+8))>>2)&0xffffff))
    d[C['FLAG']]=1                                 # accende il blocco di disegno del testo
    put(C['H4'], bl_to(C['H4'], lab['hook4']))   # frase del codice colore
    if test_cambio: put(C['AVVIO_PARTITA'], bl_to(C['AVVIO_PARTITA'], lab['hook3']))
    # valori rilocati che puntano a RW/ZI: + delta
    for l in set(T):
        v=struct.unpack('>I',d[l:l+4])[0]
        if v>=RO: put(l,v+delta)
    newT=[l+delta if l>=RO else l for l in T]
    # nuovo file: RO + blob + RW + codice di rilocazione + tabella
    nd=bytearray(d[:RO])+blob+d[RO:TAB]
    for l in newT: nd+=struct.pack('>I',l)
    nd+=struct.pack('>I',0xffffffff)
    assert len(ORIG)==TAB+4*len(T)+4, 'la tabella non e alla fine del file'
    # intestazione: dimensione RO e chiamata alla rilocazione
    nd[0x14:0x18]=struct.pack('>I',RO+delta)
    nd[0x04:0x08]=struct.pack('>I',bl_to(0x04,C['RELOC']+delta))
    return bytes(nd), lab

