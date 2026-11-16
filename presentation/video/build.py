#!/usr/bin/env python3
"""Monta os vídeos do Projeto Store com ffmpeg.

  python3 build.py hpa                         # vídeo do teste de carga (sem narração)
  python3 build.py apresentacao                # apresentação muda, no tempo estimado do roteiro
  python3 build.py apresentacao --audio voz.m4a  # re-cronometra pelos silêncios da voz e junta o áudio
"""
import json, os, re, subprocess, sys, glob

ROOT = os.path.dirname(os.path.abspath(__file__))
C = lambda *p: os.path.join(ROOT, 'clips', *p)
S = lambda name: os.path.join(ROOT, 'slides', name + '.png')
OUT = os.path.join(ROOT, 'out')
TMP = os.path.join(ROOT, 'tmp')
FPS = 30
ENC = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', str(FPS), '-an']


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit('ffmpeg falhou:\n' + ' '.join(cmd) + '\n' + r.stderr[-3000:])
    return r


def dur(path):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]).stdout)


def still(out, png, T, overlays=()):
    """Imagem parada por T segundos."""
    cmd = ['ffmpeg', '-y', '-loop', '1', '-t', f'{T:.3f}', '-i', png]
    for o in overlays:
        cmd += ['-loop', '1', '-t', f'{T:.3f}', '-i', o]
    chain = f'[0:v]scale=1920:1080,fps={FPS},format=yuv420p[v0]'
    last = 'v0'
    for i in range(len(overlays)):
        chain += f';[{last}][{i+1}:v]overlay=0:0[v{i+1}]'
        last = f'v{i+1}'
    run(cmd + ['-filter_complex', chain, '-map', f'[{last}]', '-t', f'{T:.3f}'] + ENC + [out])


def clip(out, src, a, b, T, overlays=()):
    """Trecho [a, b] do vídeo, acelerado (ou com o último quadro congelado) para durar T segundos."""
    raw = b - a
    cmd = ['ffmpeg', '-y', '-i', src]
    for o in overlays:
        cmd += ['-loop', '1', '-i', o]
    if T < raw:
        timing = f'setpts=(PTS-STARTPTS)*{T/raw:.6f}'
    else:
        timing = f'setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={T-raw:.3f}'
    chain = f'[0:v]trim=start={a}:end={b},{timing},scale=1920:1080,fps={FPS},format=yuv420p[v0]'
    last = 'v0'
    for i in range(len(overlays)):
        chain += f';[{last}][{i+1}:v]overlay=0:0:shortest=1[v{i+1}]'
        last = f'v{i+1}'
    run(cmd + ['-filter_complex', chain, '-map', f'[{last}]', '-t', f'{T:.3f}'] + ENC + [out])


def concat(parts, out, audio=None):
    lst = os.path.join(TMP, 'list.txt')
    with open(lst, 'w') as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', lst]
    if audio:
        cmd += ['-i', audio, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k',
                '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-shortest']
    else:
        cmd += ['-c', 'copy']
    run(cmd + ['-movflags', '+faststart', out])


# ---------------------------------------------------------------- vídeo do HPA
def build_hpa():
    raw, tail = C('hpa-raw.mp4'), C('hpa-tail.mp4')
    lt = S('lt-hpa')
    plan = [
        ('still', S('hpa-title'), 4.0, []),
        ('clip', raw, 0, 12, 12.0, [S('sp-1'), lt]),        # estado inicial e o comando do busybox
        ('clip', raw, 12, 90, 26.0, [S('sp-3'), lt]),       # 1 -> 4 -> 6 -> 10 réplicas
        ('clip', raw, 90, 166, 12.7, [S('sp-6'), lt]),      # 10 réplicas sob carga, Ctrl+C
        ('clip', raw, 166, 470, 10.1, [S('sp-30'), lt]),    # janela de estabilização (5 min)
        ('clip', raw, 470, dur(raw), 16.5, [S('sp-4'), lt]),  # 10 -> 9 -> 3 -> 2
        ('clip', tail, 0.5, dur(tail), 5.3, [S('sp-tail'), lt]),  # 1 réplica
    ]
    parts = render(plan, 'hpa')
    out = os.path.join(OUT, 'teste-de-carga-hpa.mp4')
    concat(parts, out)
    print(out, f'{dur(out):.1f}s')


# ------------------------------------------------------ vídeo de apresentação
# palavras de cada bloco do roteiro (números falados por extenso)
WORDS = [23, 36, 37, 47, 31, 64, 13]
WPS, PAUSE, TAIL = 2.4, 0.7, 2.0


def blocks_from_words():
    d = [w / WPS + PAUSE for w in WORDS]
    d[-1] += TAIL
    return d


def blocks_from_audio(audio):
    """Duração de cada bloco = do início da fala do bloco até o início da fala do próximo.
    Os blocos são separados pelas pausas mais longas (o roteiro pede 1-2 s entre blocos)."""
    total = dur(audio)
    r = subprocess.run(['ffmpeg', '-i', audio, '-af', 'silencedetect=noise=-35dB:d=0.6', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', r)]
    ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', r)]
    sil = list(zip(starts, ends[:len(starts)]))
    lead = sil[0][1] if sil and sil[0][0] < 0.05 else 0.0           # silêncio antes da 1ª palavra
    inner = [(s, e) for s, e in sil if s > lead + 0.5 and e < total - 0.3]
    cuts = sorted(sorted(inner, key=lambda x: x[1] - x[0], reverse=True)[:len(WORDS) - 1])
    if len(cuts) < len(WORDS) - 1:
        sys.exit(f'achei só {len(cuts)} pausas entre blocos; esperado {len(WORDS) - 1}')
    bounds = [0.0] + [(s + e) / 2 for s, e in cuts] + [total + TAIL]
    return [bounds[i + 1] - bounds[i] for i in range(len(WORDS))]


def build_apresentacao(audio=None):
    if '--blocks' in sys.argv:
        d = json.load(open(sys.argv[sys.argv.index('--blocks') + 1]))
        d = d['blocks'] if isinstance(d, dict) else d
    else:
        d = blocks_from_audio(audio) if audio else blocks_from_words()
    print('blocos (s):', ' '.join(f'{x:.1f}' for x in d), f'= {sum(d):.1f}s')
    elb, bn, hpa, tail = C('elb-smoke.mp4'), C('bottlenecks.mp4'), C('hpa-raw.mp4'), C('hpa-tail.mp4')
    graf = glob.glob(C('grafana-raw', '*.webm'))[0]
    b4s, b4a = d[3] * 0.16, d[3] * 0.50     # bloco 4: slide dos 6 gargalos, terminal, Grafana
    b6a, b6b = d[5] * 0.33, d[5] * 0.13     # bloco 6: desafios, CI/CD, custos (proporção das palavras)
    h1, h2 = d[4] * 0.70, d[4] * 0.19       # bloco 5: subida, descida e 1 réplica
    g = d[3] - b4s - b4a
    plan = [
        ('still', S('s1-title'), d[0], []),
        ('still', S('s2-arch'), d[1], []),
        ('clip', elb, 0.3, dur(elb), d[2], [S('lt-eks')]),
        ('still', S('s-bn'), b4s, []),
        ('clip', bn, 0.3, dur(bn), b4a, [S('lt-bn')]),
        ('clip', graf, 3.0, 3.0 + g, g, [S('lt-graf')]),
        ('clip', hpa, 6, 90, h1, [S('sp-8'), S('lt-hpa')]),
        ('clip', hpa, 470, dur(hpa), h2, [S('sp-8'), S('lt-hpa')]),
        ('clip', tail, 1.5, dur(tail), d[4] - h1 - h2, [S('lt-hpa')]),
        ('still', S('s3-challenges'), b6a, []),
        ('still', S('s-cicd'), b6b, []),
        ('still', S('s4-costs'), d[5] - b6a - b6b, []),
        ('still', S('s5-end'), d[6], []),
    ]
    parts = render(plan, 'apr')
    name = 'apresentacao.mp4' if audio else 'apresentacao-sem-audio.mp4'
    out = os.path.join(OUT, name)
    concat(parts, out, audio)
    print(out, f'{dur(out):.1f}s')
    json.dump(d, open(os.path.join(OUT, name + '.blocos.json'), 'w'))


def render(plan, prefix):
    os.makedirs(TMP, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    parts = []
    for i, step in enumerate(plan):
        out = os.path.join(TMP, f'{prefix}-{i:02d}.mp4')
        if step[0] == 'still':
            _, png, T, ov = step
            still(out, png, T, ov)
        else:
            _, src, a, b, T, ov = step
            clip(out, src, a, b, T, ov)
        parts.append(out)
    return parts


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'hpa'
    audio = sys.argv[sys.argv.index('--audio') + 1] if '--audio' in sys.argv else None
    build_hpa() if what == 'hpa' else build_apresentacao(audio)
