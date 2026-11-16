"""Segunda trava: transcreve o áudio editado e confere, bloco a bloco, que a última palavra está
lá inteira, e que não sobrou nenhum "Bloco N" nem tentativa repetida."""
import json, re, sys, unicodedata
import mlx_whisper
wav, blocks_json = sys.argv[1:3]
info = json.load(open(blocks_json))
norm = lambda w: unicodedata.normalize('NFKD', w).encode('ascii', 'ignore').decode().lower().strip(' .,!?')
SYN = {'14': {'14', 'quatorze', 'catorze'}, 'eks': {'eks'}, 'grafana': {'grafana', 'grafano'}}
r = mlx_whisper.transcribe(wav, path_or_hf_repo='mlx-community/whisper-large-v3-mlx', language='pt', word_timestamps=True)
words = [(w['start'], w['end'], norm(w['word'])) for s in r['segments'] for w in s.get('words', [])]
ok, t = True, 0.0
for i, (dur, last) in enumerate(zip(info['blocks'], info['last_words'])):
    ws = [w for w in words if t - 0.2 <= w[0] < t + dur - 0.2]
    tail = [w[2] for w in ws[-3:]]
    want = SYN.get(norm(last), {norm(last)})
    hit = any(x in want for x in tail)
    print(f'bloco {i+1}: termina em {" ".join(tail)!r} -> esperado {norm(last)!r}: {"OK" if hit else "FALTANDO"}')
    ok &= hit; t += dur
junk = [w for w in words if w[2] in ('bloco', 'repetir')]
if junk:
    print('sobrou:', junk); ok = False
sys.exit(0 if ok else 'ERRO: o áudio editado perdeu o fim de algum bloco')
