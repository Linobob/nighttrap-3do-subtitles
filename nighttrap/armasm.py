# Mini assemblatore ARMv3 big-endian con etichette (solo quello che serve).
import struct
CC={'eq':0,'ne':1,'cs':2,'cc':3,'mi':4,'pl':5,'hi':8,'ls':9,'ge':10,'lt':11,'gt':12,'le':13,'':14}
OPS={'and':0,'eor':1,'sub':2,'rsb':3,'add':4,'orr':12,'mov':13,'bic':14,'mvn':15,'cmp':10,'cmn':11,'tst':8}
def reg(r):
    if r in ('sp','lr','pc'): return {'sp':13,'lr':14,'pc':15}[r]
    return int(r[1:]) if isinstance(r,str) else r
def imm8(v):
    v&=0xffffffff
    for rot in range(16):
        x=((v<<(2*rot))|(v>>(32-2*rot)))&0xffffffff if rot else v
        if x<256: return (rot<<8)|x
    raise ValueError('immediato non codificabile %x'%v)
class Asm:
    def __init__(s,base): s.base=base; s.items=[]; s.lab={}
    def label(s,n): s.lab[n]=s.base+4*len(s.items) if not s.items or True else None; s.lab[n]=s.pc()
    def pc(s): return s.base+sum(len(i) if isinstance(i,bytes) else 4 for i in s.items)
    def emit(s,f): s.items.append(f)
    def dp(s,op,rd,rn,o2,c='',S=0,sh=None):
        def f(pc):
            w=(CC[c]<<28)|(OPS[op]<<21)|(S<<20)|(reg(rn)<<16)|(reg(rd)<<12)
            if op in ('cmp','cmn','tst'): w|=1<<20
            if isinstance(o2,int): w|=(1<<25)|imm8(o2)
            else:
                w|=reg(o2)
                if sh: w|=({'lsl':0,'lsr':1,'asr':2}[sh[0]]<<5)|(sh[1]<<7)
            return w
        s.emit(f)
    def mov(s,rd,o2,c=''): s.dp('mov',rd,0,o2,c)
    def ldst(s,L,B,rt,rn,off=0,c='',post=False,regoff=None,lsl=0):
        def f(pc):
            o=off
            w=(CC[c]<<28)|(1<<26)|((0 if post else 1)<<24)|(L<<20)|(B<<22)|(reg(rn)<<16)|(reg(rt)<<12)
            if regoff is not None: w|=(1<<25)|(1<<23)|reg(regoff)|(lsl<<7)
            else:
                if isinstance(o,str): o=s.lab[o]-(pc+8)
                w|=((1<<23) if o>=0 else 0)|abs(o)
                assert abs(o)<4096
            return w
        s.emit(f)
    def b(s,t,c='',link=0):
        def f(pc):
            tt=s.lab[t] if isinstance(t,str) else t
            off=(tt-(pc+8))>>2
            return (CC[c]<<28)|(5<<25)|(link<<24)|(off&0xffffff)
        s.emit(f)
    def bl(s,t,c=''): s.b(t,c,1)
    def stmfd(s,regs): s.emit(lambda pc:(0xe92d0000|sum(1<<reg(r) for r in regs)))
    def ldmfd(s,regs): s.emit(lambda pc:(0xe8bd0000|sum(1<<reg(r) for r in regs)))
    def addr(s,rd,target):
        # rd = indirizzo assoluto di target (relativo al pc, nessuna rilocazione)
        lit='_lit%d'%len(s.items)
        s.ldst(1,0,rd,'pc',lit+'_pool')
        a=[None]
        def f(pc): a[0]=pc; return 0xe08f0000|(reg(rd)<<16)|(reg(rd)<<12)|reg(rd)  # add rd, pc, rd
        s.emit(f)
        s.pool=getattr(s,'pool',[])+[(lit+'_pool',lambda: (target()-(a[0]+8)) & 0xffffffff)]
    def word(s,v): s.emit(lambda pc,v=v:v)
    def data(s,b): s.items.append(bytes(b))
    def flush_pool(s):
        for n,fn in getattr(s,'pool',[]):
            s.lab[n]=s.pc(); s.emit(lambda pc,fn=fn: fn())
        s.pool=[]
    def assemble(s):
        # due passate: etichette poi codifica
        pc=s.base; s.lab_pos={}
        out=bytearray(); pc=s.base
        for it in s.items:
            if isinstance(it,bytes): out+=it; pc+=len(it)
            else: out+=struct.pack('>I',it(pc)&0xffffffff); pc+=4
        return bytes(out)
