"""Synthesize the 27s soundtrack + SFX for the promo (no external samples).
Usage: python3 music.py out.wav
"""
import sys
import wave

import numpy as np
from scipy.signal import butter, lfilter, fftconvolve

SR = 44100
DUR = 27.0
N = int(SR * DUR)
rng = np.random.default_rng(221)

L = np.zeros(N)
R = np.zeros(N)


def mf(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tt(d):
    return np.arange(int(d * SR)) / SR


def add(sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= N or i + len(sig) <= 0:
        return
    s = sig[: max(0, N - i)] * gain
    lg, rg = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    L[i:i + len(s)] += s * lg * 1.414
    R[i:i + len(s)] += s * rg * 1.414


def filt(x, kind, f, order=2):
    b, a = butter(order, np.array(f) / (SR / 2), kind)
    return lfilter(b, a, x)


# ---------------- instruments ----------------
def kick():
    t = tt(0.32)
    f = 48 + 120 * np.exp(-t * 32)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 9) + 0.25 * np.exp(-t * 300) * rng.standard_normal(len(t))


def clap():
    t = tt(0.25)
    n = rng.standard_normal(len(t))
    env = np.zeros(len(t))
    for d in (0, 0.011, 0.022):
        env += (t >= d) * np.exp(-np.maximum(t - d, 0) * 60)
    env += 0.5 * np.exp(-t * 14)
    return filt(n * env, 'bandpass', [900, 4000]) * 0.9


def hat(dec=55):
    t = tt(0.12 if dec > 20 else 0.5)
    return filt(rng.standard_normal(len(t)), 'highpass', 7000) * np.exp(-t * dec)


def crash():
    t = tt(1.6)
    return filt(rng.standard_normal(len(t)), 'highpass', 4500) * np.exp(-t * 2.6) * 0.6


def pluck(m, d=0.45, bright=0.5):
    """Karplus-Strong pizzicato."""
    f = mf(m)
    p = int(SR / f)
    n = int(d * SR)
    y = np.zeros(n + p)
    y[:p] = rng.uniform(-1, 1, p)
    y[:p] = filt(y[:p], 'lowpass', min(12000, 2000 + bright * 8000), 1)
    decay = 0.996
    for s in range(p, n + p, p):
        e = min(s + p, n + p)
        seg = y[s - p:e - p]
        prev = np.concatenate(([y[s - p - 1] if s - p - 1 >= 0 else 0], seg[:-1]))
        y[s:e] = decay * 0.5 * (seg + prev)
    out = y[p:]
    t = np.arange(len(out)) / SR
    return out * np.exp(-t * 4) * (1 - np.exp(-t * 400))


def glock(m, d=0.9):
    t = tt(d)
    f = mf(m)
    s = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6)
         + 0.15 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 12))
    return s * np.exp(-t * 4.5) * (1 - np.exp(-t * 2000))


def bass(m, d=0.22):
    t = tt(d)
    f = mf(m)
    ph = (f * t) % 1.0
    saw = 2 * ph - 1
    sq = np.sign(np.sin(2 * np.pi * f * t))
    s = filt(0.6 * saw + 0.4 * sq, 'lowpass', 900)
    return s * np.exp(-t * 5) * (1 - np.exp(-t * 300)) * np.minimum(1, (d - t) * 60)


def pad(ms, d):
    t = tt(d)
    s = sum(((mf(m) * k * t) % 1.0) * 2 - 1 for m in ms for k in (0.997, 1.003))
    s = filt(s, 'lowpass', 1600)
    env = np.minimum(1, t / 0.08) * np.minimum(1, (d - t) / 0.1)
    return s * env / len(ms) * 0.5


# ---------------- SFX ----------------
def whoosh(d=0.45, up=False):
    n = int(d * SR)
    x = rng.standard_normal(n)
    out = np.zeros(n)
    blk = 512
    zi = None
    for i in range(0, n, blk):
        p = i / n
        fc = (400 + 7000 * p) if up else (500 + 6000 * np.sin(np.pi * p))
        b, a = butter(2, [max(80, fc * 0.5) / (SR / 2), min(0.95, fc * 1.6 / (SR / 2))], 'bandpass')
        if zi is None:
            zi = np.zeros(max(len(a), len(b)) - 1)
        out[i:i + blk], zi = lfilter(b, a, x[i:i + blk], zi=zi)
    t = np.arange(n) / SR
    env = np.sin(np.pi * t / d) ** (1.5 if not up else 3)
    return out * env * 1.4


def pop():
    t = tt(0.09)
    f = 500 + 900 * (t / 0.09)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 40)


def tick():
    t = tt(0.03)
    return filt(rng.standard_normal(len(t)), 'bandpass', [2000, 6000]) * np.exp(-t * 220)


def typekey():
    t = tt(0.05)
    return (filt(rng.standard_normal(len(t)), 'bandpass', [1500, 5000]) * np.exp(-t * 160)
            + 0.4 * np.sin(2 * np.pi * 180 * t) * np.exp(-t * 90))


def coin():
    out = np.zeros(int(0.9 * SR))
    for d, fs in ((0.0, (2637, 3951, 5274)), (0.09, (3136, 4699, 6272))):
        t = tt(0.8)
        s = sum(np.sin(2 * np.pi * f * t) / (j + 1) for j, f in enumerate(fs)) * np.exp(-t * 7)
        i = int(d * SR)
        out[i:i + len(s)] += s[: len(out) - i]
    return out * 0.5


def stamp():
    t = tt(0.5)
    boom = np.sin(2 * np.pi * np.cumsum(70 + 80 * np.exp(-t * 25)) / SR) * np.exp(-t * 7)
    thud = filt(rng.standard_normal(len(t)), 'lowpass', 1200) * np.exp(-t * 25)
    return boom * 1.2 + thud * 0.8


def clink(f0):
    t = tt(0.5)
    return sum(np.sin(2 * np.pi * f0 * k * t) * np.exp(-t * (14 + 6 * j))
               for j, k in enumerate((1, 2.32, 4.25))) * 0.4


def riser(d):
    t = tt(d)
    n = filt(rng.standard_normal(len(t)), 'highpass', 1500)
    tone = np.sin(2 * np.pi * np.cumsum(200 + 1400 * (t / d) ** 2) / SR)
    return (n * 0.5 + tone * 0.25) * (t / d) ** 2


# ---------------- arrangement ----------------
BEAT = 0.5
DROP = 1.0
chords = [(53, [65, 69, 72]), (48, [64, 67, 72]), (50, [62, 65, 69]), (46, [62, 65, 70])]  # F C Dm Bb
mel = [  # (eighth index, midi) per chord bar
    [(0, 72), (2, 77), (4, 81), (5, 79), (6, 77)],
    [(0, 76), (2, 79), (4, 84), (6, 79), (7, 76)],
    [(0, 74), (2, 77), (4, 81), (5, 79), (6, 77), (7, 76)],
    [(0, 77), (2, 74), (4, 70), (5, 72), (6, 74)],
]
mel2 = [
    [(0, 81), (1, 79), (2, 77), (3, 79), (4, 81), (6, 84)],
    [(0, 84), (2, 83), (3, 84), (4, 79), (6, 76)],
    [(0, 77), (1, 79), (2, 81), (4, 86), (6, 84)],
    [(0, 82), (2, 81), (4, 79), (5, 77), (6, 74), (7, 72)],
]
BREAK = (19.5, 20.0)
END = 25.5

def in_break(t):
    return BREAK[0] <= t < BREAK[1]

# intro: sneaky pizzicato + riser
for i, m in enumerate([57, 60, 62, 65, 62, 60, 64, 67]):
    add(pluck(m, 0.25, 0.3), i * 0.125, 0.55, -0.3 if i % 2 else 0.3)
add(riser(0.95), 0.05, 0.35)

drum_bus = np.zeros(N)
kick_times = []
t = DROP
bar = 0
while t < END - 1e-6:
    root, ch = chords[bar % 4]
    for b in range(4):
        bt = t + b * BEAT
        if bt >= END or in_break(bt):
            continue
        add(kick(), bt, 0.95)
        kick_times.append(bt)
        if b in (1, 3):
            add(clap(), bt, 0.5, 0.05)
        add(hat(), bt + 0.25, 0.22, 0.35)
        if bt >= 11.0:
            add(hat(90), bt + 0.125, 0.09, 0.4)
            add(hat(90), bt + 0.375, 0.09, 0.4)
    # bass pattern (eighths)
    for k, (on, off) in enumerate([(0, 0), (2, 0), (3, 12), (5, 0), (6, 12), (7, 0)]):
        bt = t + on * 0.25
        if bt < END and not in_break(bt):
            add(bass(root - 12 + off + 12, 0.2), bt, 0.55)
    # pad
    if not any(in_break(t + x) for x in (0, 1.9)):
        add(pad(ch, min(2.0, END - t)), t, 0.22)
    # melody (pizz), brighter second phrase later
    phrase = mel if (bar // 4) % 2 == 0 else mel2
    for e, m in phrase[bar % 4]:
        bt = t + e * 0.25
        if bt < END and not in_break(bt):
            add(pluck(m, 0.4, 0.6), bt, 0.42, -0.2)
            if bt >= 11.0:
                add(glock(m + 12, 0.6), bt, 0.12, 0.25)
    if bar % 2 == 1:
        add(hat(14), t + 1.75, 0.12, 0.3)
    t += 2.0
    bar += 1

# build-up into 11.0
for i in range(16):
    bt = 10.0 + i * (1.0 / 16) if i < 8 else 10.5 + (i - 8) * (0.5 / 8)
    add(clap(), bt, 0.12 + 0.025 * i, 0.0)
add(riser(1.0), 10.0, 0.35)
add(riser(0.5), 19.5, 0.3)

for c in (DROP, 4.0, 8.0, 11.0, 20.0, 23.5):
    add(crash(), c, 0.5, 0.2)

# final hit
add(kick(), END, 1.1)
add(crash(), END, 0.7)
for m in (41, 53):
    add(bass(m, 1.2), END, 0.6)
for m in (65, 69, 72, 77):
    add(pluck(m, 1.5, 0.7), END, 0.35)
for i, m in enumerate((77, 81, 84, 89)):
    add(glock(m, 1.4), END + 0.5 + i * 0.09, 0.22, 0.2)
add(pad([65, 69, 72, 77], 1.5), END, 0.25)

# ---------------- SFX timeline ----------------
for w in (0.3, 7.55, 10.55, 13.15, 15.15, 17.15, 20.15, 23.05):
    add(whoosh(0.45), w, 0.32, 0.2)
add(whoosh(0.5, up=True), 3.5, 0.4)
add(whoosh(0.5), 19.5, 0.45, -0.3)  # page turn
for i in range(20):
    add(typekey(), 0.15 + i / 28, 0.18, 0.2)
for i in range(21):
    add(typekey(), 4.05 + i / 34, 0.14, -0.2)
for i in range(10):
    add(typekey(), 8.15 + i / 26, 0.16, 0.2)
for c in (1.0, 6.5, 23.7, 25.5):
    add(coin(), c, 0.4, 0.1)
for s in (6.5, 25.5):
    add(stamp(), s, 0.7)
add(stamp(), 20.25, 0.35)
for i, m in enumerate((77, 81, 84, 89)):
    add(glock(m, 0.8), 4.9 + i * 0.07, 0.25, -0.2 + i * 0.13)
for p in (2.0, 2.35, 4.15, 4.2, 5.75, 6.0, 8.3, 8.9, 10.2, 11.15, 11.3, 11.6, 11.75, 20.35,
          21.5, 21.75, 22.25, 23.55, 23.75, 24.0, 24.35, 24.75):
    add(pop(), p, 0.16, 0.0)
for p in (11.5, 13.6, 15.6, 17.6):
    add(glock(96, 0.5), p, 0.12, 0.3)
    add(glock(91, 0.5), p + 0.06, 0.1, -0.3)
for f in (8.38, 9.0, 9.2, 9.35):
    add(tick(), f, 0.5, 0.0)
add(glock(84, 0.7), 9.5, 0.22)
for i, m in enumerate((77, 79, 81, 84, 86)):
    add(glock(m, 0.6), 9.55 + i * 0.12 + 0.255, 0.26, -0.5 + i * 0.25)
for d in (13.5, 15.5, 17.5):
    add(glock(84, 0.6), d, 0.18)
    add(glock(88, 0.6), d + 0.05, 0.14)
for c, f0 in ((20.75, 2400), (21.0, 2700), (21.25, 3000)):
    add(clink(f0), c, 0.5, -0.3 + (c - 20.75) * 1.2)
for i, m in enumerate((84, 86, 88, 91, 93, 96)):
    add(glock(m, 0.5), 24.85 + i * 0.11, 0.1, -0.4 + i * 0.16)

# ---------------- mix ----------------
# sidechain-style pump on everything except drums would be ideal; approximate on the full mix lightly
pump = np.ones(N)
for k in kick_times:
    i = int(k * SR)
    seg = np.arange(int(0.25 * SR))
    j = min(N, i + len(seg))
    pump[i:j] = np.minimum(pump[i:j], 1 - 0.18 * np.exp(-seg[: j - i] / SR * 14))
L *= pump
R *= pump

ir_t = tt(1.1)
ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 5.5)
ir = filt(ir, 'lowpass', 5000) * 0.06
Lr = fftconvolve(L, ir)[:N]
Rr = fftconvolve(R, ir[::-1][::-1] * 0.98)[:N]
L2, R2 = L + Lr, R + Rr

fade = np.ones(N)
fs = int(26.3 * SR)
fade[fs:] = np.linspace(1, 0, N - fs) ** 1.5
L2 *= fade
R2 *= fade
peak = max(np.abs(L2).max(), np.abs(R2).max())
L2 = np.tanh(L2 / peak * 1.3) / np.tanh(1.3) * 0.92
R2 = np.tanh(R2 / peak * 1.3) / np.tanh(1.3) * 0.92

out = np.stack([L2, R2], axis=1)
with wave.open(sys.argv[1] if len(sys.argv) > 1 else 'music.wav', 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((out * 32767).astype('<i2').tobytes())
print('ok', DUR, 's')
