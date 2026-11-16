"""Corta a narração: tira os "Bloco N", as tentativas repetidas e o silêncio longo; devolve
o áudio editado e a duração de cada bloco (para o vídeo acompanhar a voz)."""
import json, subprocess, sys
src, transcript, out_wav, out_json = sys.argv[1:5]
WINDOWS = [(2.7, 12.2), (15.8, 27.4), (31.9, 45.6), (51.0, 71.7), (76.0, 86.9), (143.1, 167.1), (171.2, 181.8)]
LEAD, IN_GAP, BLOCK_GAP, SPLIT, PRE, POST, TAIL = 0.5, 0.40, 0.85, 0.60, 0.10, 0.18, 2.0
words = [w for s in json.load(open(transcript))['segments'] for w in s.get('words', [])
         if w.get('probability', 1) >= 0.05 and w['end'] - w['start'] > 0.02]
pieces, block_starts, t = [], [], 0.0          # pieces: (start, end, gap_before)
for bi, (a, b) in enumerate(WINDOWS):
    ws = [w for w in words if a <= w['start'] < b]
    phrases = []
    for w in ws:
        if phrases and w['start'] - phrases[-1][1] < SPLIT:
            phrases[-1][1] = w['end']
        else:
            phrases.append([w['start'], w['end']])
    for pi, (s, e) in enumerate(phrases):
        s, e = max(a, s - PRE), min(b, e + POST)
        gap = (LEAD if bi == 0 else BLOCK_GAP) if pi == 0 else IN_GAP
        if pi == 0:
            block_starts.append(t + gap if bi else LEAD)
        pieces.append((s, e, gap)); t += gap + (e - s)
total = t + TAIL
inputs, chain, labels = ['-i', src], [], []
for i, (s, e, gap) in enumerate(pieces):
    chain.append(f'anullsrc=r=48000:cl=mono,atrim=0:{gap:.3f}[g{i}]')
    chain.append(f'[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st={e-s-0.04:.3f}:d=0.04[p{i}]')
    labels += [f'[g{i}]', f'[p{i}]']
chain.append(f'anullsrc=r=48000:cl=mono,atrim=0:{TAIL:.3f}[tail]'); labels.append('[tail]')
chain.append(''.join(labels) + f'concat=n={len(labels)}:v=0:a=1[out]')
subprocess.run(['ffmpeg', '-y', '-v', 'error', *inputs, '-filter_complex', ';'.join(chain), '-map', '[out]', '-ar', '48000', out_wav], check=True)
bounds = [0.0] + block_starts[1:] + [total]
blocks = [bounds[i + 1] - bounds[i] for i in range(len(WINDOWS))]
json.dump(blocks, open(out_json, 'w'))
print('blocos:', ' '.join(f'{x:.1f}' for x in blocks), f'total {total:.1f}s')
