"""Solo per i test: ricostruisce una ISO 'finta' ma strutturalmente uguale all'originale
partendo da layout.json (3dt unpack), dal Launchme e dal file dati estratti.
Le parti non ricostruite sono zeri (file sparso)."""
import json, struct, sys

def etichetta_da_layout(d):
    b = bytes([d['record_type']]) + bytes(d['volume_sync_bytes']) + bytes([d['volume_structure_version'], d['volume_flags']])
    b += d['volume_commentary'].encode().ljust(32, b'\0') + d['volume_identifier'].encode().ljust(32, b'\0')
    b += struct.pack('>7I', d['volume_unique_identifier'], d['volume_block_size'], d['volume_block_count'],
                     d['root_unique_identifier'], d['root_directory_block_count'], d['root_directory_block_size'],
                     d['root_directory_last_avatar_index'])
    av = d['root_directory_avatar_list'] + [0] * 8
    return b + b''.join(struct.pack('>I', a) for a in av[:8])

def crea(layout, etichetta, launchme, dati, nome_dati, uscita, blocchi_tot):
    L = json.load(open(layout))
    B = 2048
    with open(uscita, 'wb') as f:
        f.truncate(blocchi_tot * B)
        f.seek(0); f.write(etichetta_da_layout(L['disc_label']))
        radice = L['disc_label']['root_directory_avatar_list']
        # riempitivo dopo la directory fino al blocco 330000 (come nella ISO vera)
        f.seek((max(radice) + 1) * B)
        n = (330000 - max(radice) - 1) * B
        pez = b'iamaduck' * (1 << 17)
        while n > 0:
            k = min(n, len(pez)); f.write(pez[:k]); n -= k
        top = sorted([e for e in L['entries'] if '/' not in e['path']], key=lambda e: e['record_file_offset'])
        blk = bytearray(B)
        primo = top[0]['record_file_offset'] - radice[0] * B
        p = primo
        for i, e in enumerate(top):
            fl = e['flags'] | (0xC0000000 if i == len(top) - 1 else 0)
            r = struct.pack('>8I', fl, e['unique_identifier'], e['type'], e['block_size'], e['byte_count'],
                            e['block_count'], e['burst'], e['gap'])
            r += bytes.fromhex(e['filename_raw_hex'])[:32].ljust(32, b'\0')
            r += struct.pack('>I', e['last_avatar_index']) + b''.join(struct.pack('>I', a) for a in e['avatar_list'])
            assert radice[0] * B + p == e['record_file_offset'], e['path']
            blk[p:p + len(r)] = r; p += len(r)
        blk[0:20] = struct.pack('>5I', 0xffffffff, 0xffffffff, 0, p, primo)
        for a in radice:
            f.seek(a * B); f.write(blk)
        per = {e['path']: e for e in L['entries']}
        f.seek(per['Launchme']['avatar_list'][0] * B); f.write(open(launchme, 'rb').read())
        f.seek(per[nome_dati]['avatar_list'][0] * B)
        with open(dati, 'rb') as d:
            while True:
                x = d.read(1 << 24)
                if not x: break
                f.write(x)

if __name__ == '__main__':
    crea(*sys.argv[1:7], int(sys.argv[7]))
