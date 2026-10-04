import numpy as np
import wave

SR = 48000
DUR = 20.0
N = int(SR * DUR)
rng = np.random.default_rng(7)

bufL = np.zeros(N)
bufR = np.zeros(N)
sendL = np.zeros(N)
sendR = np.zeros(N)


def idx(t):
    return int(round(t * SR))


def add(sig, start, pan=0.0, gain=1.0, send=0.0):
    i = idx(start)
    if i >= N or len(sig) == 0:
        return
    if i < 0:
        sig = sig[-i:]
        i = 0
    n = min(len(sig), N - i)
    if n <= 0:
        return
    sig = sig[:n] * gain
    ang = (pan + 1.0) * np.pi / 4
    gl, gr = np.cos(ang), np.sin(ang)
    bufL[i:i + n] += sig * gl
    bufR[i:i + n] += sig * gr
    if send > 0:
        sendL[i:i + n] += sig * gl * send
        sendR[i:i + n] += sig * gr * send


def expdec(n, attack, decay):
    e = np.exp(-np.arange(n) / (decay * SR))
    a = int(attack * SR)
    if a > 1:
        e[:a] *= np.linspace(0, 1, a)
    return e


def lp1_var(x, cut):
    a = np.exp(-2 * np.pi * np.asarray(cut, dtype=np.float64) / SR)
    y = np.empty_like(x)
    prev = 0.0
    for i in range(len(x)):
        ai = a[i]
        prev = (1.0 - ai) * x[i] + ai * prev
        y[i] = prev
    return y


def lp1(x, cut):
    return lp1_var(x, np.full(len(x), float(cut)))


def hp1(x, cut):
    return x - lp1(x, cut)


def tri(f, n, phase=0.0):
    x = (np.arange(n) * f / SR + phase) % 1.0
    return 4.0 * np.abs(x - 0.5) - 1.0


# ---------------------------------------------------------------- chords
Fm = [185.00, 220.00, 277.18, 369.99]   # F#m : F#3 A3 C#4 F#4
Dm = [146.83, 185.00, 220.00, 293.66]   # D   : D3 F#3 A3 D4
Am = [220.00, 277.18, 329.63, 440.00]   # A   : A3 C#4 E4 A4
Em = [164.81, 207.65, 246.94, 329.63]   # E   : E3 G#3 B3 E4
CHORDS = [
    (0.0, 4.4, Fm, 92.50),
    (4.4, 8.4, Dm, 73.42),
    (8.4, 12.4, Am, 110.00),
    (12.4, 16.4, Em, 82.41),
    (16.4, 20.5, Fm, 92.50),
]


def chord_at(t):
    for s, e, notes, root in CHORDS:
        if s <= t < e:
            return notes, root
    return CHORDS[-1][2], CHORDS[-1][3]


# ---------------------------------------------------------------- pad
padL = np.zeros(N)
padR = np.zeros(N)
for s, e, notes, _ in CHORDS:
    i0, i1 = idx(s), min(idx(e), N)
    n = i1 - i0
    if n <= 0:
        continue
    tt = np.arange(n)
    segL = np.zeros(n)
    segR = np.zeros(n)
    for k, f in enumerate(notes):
        amp = 0.55 / (k + 1.6)
        segL += amp * (np.sin(2 * np.pi * f * tt / SR) + 0.35 * np.sin(2 * np.pi * 2 * f * tt / SR))
        segR += amp * (np.sin(2 * np.pi * f * 1.0016 * tt / SR) + 0.35 * np.sin(2 * np.pi * 2 * f * 0.9985 * tt / SR))
    xf = int(0.30 * SR)
    env = np.ones(n)
    env[:xf] *= np.linspace(0, 1, xf)
    env[-xf:] *= np.linspace(1, 0, xf)
    padL[i0:i1] += segL * env
    padR[i0:i1] += segR * env

tt_all = np.arange(N) / SR
cut = np.interp(tt_all, [0.0, 3.4, 7.8, 13.2, 16.4, 20.0], [420, 420, 950, 1700, 2600, 2600])
padL = lp1_var(padL, cut)
padR = lp1_var(padR, cut)
pg = np.interp(tt_all, [0.0, 3.3, 3.5, 7.7, 7.9, 13.1, 13.3, 16.3, 16.5, 19.3, 20.0],
               [0.55, 0.6, 0.85, 0.85, 1.0, 1.0, 1.1, 1.1, 1.2, 1.1, 0.0])
bufL += padL * pg
bufR += padR * pg
sendL += padL * pg * 0.35
sendR += padR * pg * 0.35

# ---------------------------------------------------------------- beat grid
BEAT0, BEAT = 0.4, 0.5


def beats(t0, t1, step=BEAT):
    k = int(np.ceil((t0 - BEAT0) / step))
    while True:
        t = BEAT0 + k * step
        if t > t1:
            break
        if t >= t0 - 1e-9:
            yield t
        k += 1


def bass_note(f, n):
    x = np.sin(2 * np.pi * f * np.arange(n) / SR) + 0.45 * np.sin(2 * np.pi * 2 * f * np.arange(n) / SR)
    return x * expdec(n, 0.005, 0.11)


# intro sub drone
n = idx(3.7)
drone = np.sin(2 * np.pi * 46.25 * np.arange(n) / SR) * expdec(n, 0.9, 3.2)
add(drone, 0.0, 0.0, 0.30)

# bass pulse with the beat
for t in beats(3.4, 16.45):
    _, root = chord_at(t)
    add(bass_note(root, idx(0.30)), t, 0.0, 0.5)


def kick(n):
    tt = np.arange(n) / SR
    f = 47 + 95 * np.exp(-tt * 26)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-tt * 10)
    click = 0.18 * hp1(rng.standard_normal(n), 2500) * np.exp(-tt * 90)
    return body + click


KICK = kick(idx(0.34))
bar = 0.4
while bar <= 16.5:
    for t in (bar, bar + 1.0):
        if 3.4 <= t <= 16.45:
            add(KICK, t, 0.0, 0.62)
    bar += 2.0


def hat(n, accent):
    x = hp1(rng.standard_normal(n), 5200)
    return x * np.exp(-np.arange(n) / (0.026 * SR)) * accent


HAT = hat(idx(0.09), 1.0)
t = 3.4
while t <= 16.46:
    step = 0.25 if t < 7.9 else 0.125
    accent = 1.0 if abs((t / 0.5) % 2) < 1e-6 else 0.55
    add(HAT, t, -0.25 if int(t / step) % 2 else 0.25, 0.16 * accent)
    t += step


def pluck(f, n, bright=0.0):
    x = 0.75 * np.sin(2 * np.pi * f * np.arange(n) / SR) + 0.25 * tri(f, n)
    if bright:
        x += bright * 0.18 * np.sin(2 * np.pi * 2 * f * np.arange(n) / SR)
    return x * expdec(n, 0.003, 0.17)


step = 0.125
pat = [0, 1, 2, 3, 2, 1]
t = 3.4
i = 0
while t <= 16.46:
    notes, _ = chord_at(t)
    f = notes[pat[i % len(pat)]]
    if t >= 7.9:
        f *= 2.0
    bright = 0.5 if t >= 13.3 else 0.15
    gain = 0.13 if t < 7.9 else 0.16
    add(pluck(f, idx(0.22), bright), t, -0.35 if i % 2 else 0.35, gain, send=0.3)
    t += step
    i += 1

# ---------------------------------------------------------------- sfx
def tick(n=int(0.014 * SR), cut=3800):
    x = hp1(rng.standard_normal(n), cut)
    return x * np.exp(-np.arange(n) / (0.0045 * SR))


# typing ticks
t = 0.36
while t < 2.45:
    add(tick(), t, 0.1, 0.05 + 0.02 * rng.random())
    t += 0.075 + 0.02 * rng.random()

# button press thock at 3.0
n = idx(0.20)
tt = np.arange(n) / SR
f = 70 + 110 * np.exp(-tt * 22)
thock = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9)
add(thock, 3.0, 0.0, 0.30)


def whoosh(dur=0.5, rise=True):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    x = rng.standard_normal(n)
    c = (300 + 3400 * (tt / dur) ** 2) if rise else (3200 - 2600 * (tt / dur))
    x = lp1_var(x, c)
    x = x - lp1_var(x, c * 0.35)
    env = (np.arange(n) / n) ** 1.5
    rel = int(0.07 * SR)
    env[-rel:] *= np.linspace(1, 0, rel)
    return x * env


for t, rise in ((3.35, True), (7.8, True), (13.32, True), (16.5, True)):
    add(whoosh(0.5, rise), t, 0.0, 0.30, send=0.4)

# stage-complete blips
for t in (4.45, 5.3, 6.15, 7.0, 8.25, 9.95, 10.9, 13.9):
    n = idx(0.16)
    blip = np.sin(2 * np.pi * 1108.73 * np.arange(n) / SR) * expdec(n, 0.002, 0.05)
    add(blip, t, 0.15, 0.09)

# drawer open click
add(tick(int(0.03 * SR), 2600), 11.0, 0.3, 0.13)

# evidence tab two-note pluck
for t, f in ((11.95, 659.25), (12.04, 987.77)):
    add(pluck(f, idx(0.4), 0.3), t, 0.2, 0.15, send=0.4)

# verify chime (3 notes) at completion
for t, f in ((14.4, 554.37), (14.55, 739.99), (14.7, 880.00)):
    n = idx(1.1)
    ch = (np.sin(2 * np.pi * f * np.arange(n) / SR)
          + 0.35 * np.sin(2 * np.pi * 2 * f * np.arange(n) / SR)
          + 0.12 * np.sin(2 * np.pi * 3.01 * f * np.arange(n) / SR))
    add(ch * expdec(n, 0.004, 0.42), t, -0.1 + 0.2 * rng.random(), 0.17, send=0.55)

# claim rows landing
for t in (15.31, 15.42, 15.53):
    add(tick(int(0.02 * SR), 5200), t, 0.25, 0.08)

# riser into the hero
n = idx(0.85)
tt = np.arange(n) / SR
x = rng.standard_normal(n)
x = lp1_var(x, 300 + 5200 * (tt / (n / SR)) ** 2)
riser = x * ((np.arange(n) / n) ** 1.7)
rel = int(0.05 * SR)
riser[-rel:] *= np.linspace(1, 0, rel)
add(riser, 16.05, 0.0, 0.24, send=0.35)

# final sub hit + chord on the settled hero
n = idx(0.9)
tt = np.arange(n) / SR
f = 38 + 60 * np.exp(-tt * 12)
hit = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 4.5)
add(hit, 16.9, 0.0, 0.5)

for f in (369.99, 440.00, 554.37, 739.99):
    n = idx(2.2)
    bell = (np.sin(2 * np.pi * f * np.arange(n) / SR)
            + 0.3 * np.sin(2 * np.pi * 2 * f * np.arange(n) / SR))
    add(bell * expdec(n, 0.02, 0.9), 16.9, 0.0, 0.13, send=0.6)

# ---------------------------------------------------------------- reverb
def make_ir(seed):
    r = np.random.default_rng(seed)
    n = int(0.75 * SR)
    ir = r.standard_normal(n) * np.exp(-np.arange(n) / (0.20 * SR))
    ir = lp1(ir, 5200)
    return ir / np.sqrt(np.sum(ir ** 2))


def conv(x, ir):
    n = len(x) + len(ir) - 1
    nfft = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)
    return y[:len(x)]


irL, irR = make_ir(11), make_ir(12)
bufL += conv(sendL, irL) * 0.55
bufR += conv(sendR, irR) * 0.55

# ---------------------------------------------------------------- mix
# master tilt: tame the low end, open the top
for _b in (bufL, bufR):
    _b -= 0.30 * lp1(_b, 140.0)
    _b += 0.75 * (_b - lp1(_b, 2500.0))

peak = max(np.abs(bufL).max(), np.abs(bufR).max())
if peak > 0:
    g = 0.77 / peak
    bufL *= g
    bufR *= g

fade_in = int(0.25 * SR)
bufL[:fade_in] *= np.linspace(0, 1, fade_in)
bufR[:fade_in] *= np.linspace(0, 1, fade_in)
fo_start = idx(19.35)
fo = N - fo_start
bufL[fo_start:] *= np.linspace(1, 0, fo)
bufR[fo_start:] *= np.linspace(1, 0, fo)

bufL = np.clip(bufL, -0.98, 0.98)
bufR = np.clip(bufR, -0.98, 0.98)

inter = np.empty(N * 2, dtype=np.float64)
inter[0::2] = bufL
inter[1::2] = bufR
pcm = (inter * 32767).astype(np.int16)

out = r"D:\autoSage\brag-output-2026-09-28-132740\work\audio.wav"
with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

print("wrote", out, "peak", float(np.abs(inter).max()))
