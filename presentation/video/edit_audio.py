"""Corta a narração: tira os "Bloco N", as tentativas repetidas e os silêncios longos, e devolve o
áudio editado e a duração de cada bloco (para o vídeo acompanhar a voz).

Os cortes seguem a forma de onda, não só os timestamps do Whisper (que terminam cedo em sons
fracos como "s" e "f"): cada janela vai até logo antes do "Bloco N" seguinte, e o fim de cada
frase é estendido até haver 150 ms de silêncio de verdade, com margem. Se algum corte cair em
cima da voz, o script falha em vez de gerar o áudio.

  python edit_audio.py narracao.m4a transcript.json saida.wav blocos.json
"""
import json, subprocess, sys
import numpy as np

src, transcript, out_wav, out_json = sys.argv[1:5]
SR = 48000
# janelas no áudio original: do fim do "Bloco N" até 0,15 s antes do "Bloco N+1"
# (o bloco 6 usa a última tentativa, a completa)
WINDOWS = [(2.6, 13.30), (15.7, 28.75), (31.8, 47.25), (50.9, 73.10), (75.9, 88.50), (143.0, 169.05), (171.1, 183.27)]
LEAD, IN_GAP, BLOCK_GAP, TAIL = 0.5, 0.40, 0.85, 2.0

pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'],
                     capture_output=True, check=True).stdout
x = np.frombuffer(pcm, dtype=np.float32)
HOP, WIN = SR // 100, SR // 50                      # quadros de 10 ms, janela de 20 ms
n = (len(x) - WIN) // HOP
db = np.array([10 * np.log10(np.mean(x[i * HOP:i * HOP + WIN] ** 2) + 1e-12) for i in range(n)])
floor = np.percentile(db, 15)
THR = -36.0          # voz (pico -20 a -30 dB) x ruído da sala (-52 a -40 dB); a cauda do "s" fica acima disso
fr = lambda t: min(n, max(0, int(round(t * 100))))  # tempo -> quadro
tm = lambda i: i / 100.0
END_PAD, START_PAD, SEARCH = 0.35, 0.15, 1.0

words = [w for seg in json.load(open(transcript))['segments'] for w in seg.get('words', [])
         if w.get('probability', 1) >= 0.05 and w['end'] - w['start'] > 0.02]
pieces, block_starts, last_words, t = [], [], [], 0.0
for bi, (a, b) in enumerate(WINDOWS):
    ws = [w for w in words if a <= w['start'] < b]
    last_words.append(ws[-1]['word'].strip(' .,!?').lower())
    s0, e0 = ws[0]['start'], ws[-1]['end']
    # fim: último som de voz até 1 s depois do fim que o Whisper marcou, + 0,35 s (nunca antes do fim do Whisper)
    hi = fr(min(b, e0 + SEARCH))
    loud = [i for i in range(fr(e0), hi) if db[i] >= THR]
    e = min(b, max(e0, tm(loud[-1] + 1) if loud else e0) + END_PAD)
    # início: primeiro som de voz até 0,5 s antes do começo marcado, - 0,15 s
    lo = fr(max(a, s0 - 0.5))
    loud = [i for i in range(lo, fr(s0) + 1) if db[i] >= THR]
    s_ = max(a, (tm(loud[0]) if loud else s0) - START_PAD)
    gap = LEAD if bi == 0 else BLOCK_GAP
    block_starts.append(t + gap if bi else 0.0)
    pieces.append((s_, e, gap)); t += gap + (e - s_)

# trava: os 40 ms antes de cada fim e depois de cada início têm de ser silêncio
bad = [(s, e) for s, e, _ in pieces if db[max(0, fr(e) - 4):fr(e)].max() >= THR or db[fr(s):fr(s) + 4].max() >= THR]
if bad:
    sys.exit('ERRO: corte em cima da voz em ' + ', '.join(f'{s:.2f}-{e:.2f}s' for s, e in bad))

total = t + TAIL
chain, labels = [], []
for i, (s, e, gap) in enumerate(pieces):
    chain.append(f'anullsrc=r={SR}:cl=mono,atrim=0:{gap:.3f}[g{i}]')
    chain.append(f'[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,'
                 f'afade=t=out:st={e - s - 0.03:.3f}:d=0.03[p{i}]')
    labels += [f'[g{i}]', f'[p{i}]']
chain.append(f'anullsrc=r={SR}:cl=mono,atrim=0:{TAIL:.3f}[tail]'); labels.append('[tail]')
chain.append(''.join(labels) + f'concat=n={len(labels)}:v=0:a=1[out]')
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-filter_complex', ';'.join(chain), '-map', '[out]',
                '-ar', str(SR), out_wav], check=True)
bounds = block_starts + [total]
blocks = [bounds[i + 1] - bounds[i] for i in range(len(WINDOWS))]
json.dump({'blocks': blocks, 'last_words': last_words}, open(out_json, 'w'), ensure_ascii=False)
print(f'limiar de voz {THR:.1f} dB (ruído p15 {floor:.1f} dB) · {len(pieces)} blocos, cortes em silêncio')
for (s_, e, _), (a, b) in zip(pieces, WINDOWS): print(f'  bloco {s_:7.2f} -> {e:7.2f}s  (janela {a}-{b})')
print('blocos:', ' '.join(f'{v:.1f}' for v in blocks), f'= {total:.1f}s')
print('última palavra de cada bloco:', last_words)
