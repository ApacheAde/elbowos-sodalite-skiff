#!/usr/bin/env python3
"""Sodalite Skiff — neon canal-hopper arcade for ElbowOS."""
from __future__ import annotations

import math
import os
import random
import subprocess
import sys

import pygame

W, H = 1080, 1920
FPS = 30
TITLE = "SODALITE SKIFF"
HANDLE = "x.com/ElbowOS"
VOID = (6, 8, 28)
INK = (10, 16, 48)
NAVY = (16, 28, 72)
INDIGO = (48, 64, 168)
VIOLET = (156, 92, 255)
CYAN = (56, 230, 255)
LIME = (168, 255, 92)
GOLD = (255, 206, 72)
PEARL = (236, 244, 255)
ROSE = (255, 88, 148)
TEAL = (32, 196, 176)

# 9 hop rows: even = bank, odd = canal
ROWS = [280, 440, 600, 760, 920, 1080, 1240, 1400, 1560]
NROW = len(ROWS)


class Spark:
    __slots__ = ("x", "y", "vx", "vy", "life", "col", "r")

    def __init__(self, x, y, vx, vy, life, col, r=5):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life, self.col, self.r = life, col, r


class Barge:
    __slots__ = ("row", "x", "w", "vx", "kind")

    def __init__(self, row, x, w, vx, kind):
        self.row, self.x, self.w, self.vx, self.kind = row, x, w, vx, kind


class Pearl:
    __slots__ = ("row", "x", "phase")

    def __init__(self, row, x):
        self.row, self.x, self.phase = row, x, random.random() * math.tau


class Game:
    def __init__(self, record: bool):
        self.record = record
        self.surf = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.Font(None, 62)
        self.font_md = pygame.font.Font(None, 42)
        self.font_sm = pygame.font.Font(None, 28)
        self.score = 0
        self.reset()

    def reset(self) -> None:
        self.t = 0.0
        self.row = NROW - 1
        self.x = W * 0.5
        self.tx = self.x
        self.combo = 1
        self.barges: list[Barge] = []
        self.pearls: list[Pearl] = []
        self.sparks: list[Spark] = []
        self.ripples = [[random.uniform(0, W), random.uniform(0, H), random.uniform(0.4, 2.0)]
                        for _ in range(70)]
        self.flash = 0.0
        self.hop_cd = 0.0
        self.seed_traffic()

    def seed_traffic(self) -> None:
        self.barges.clear()
        self.pearls.clear()
        for r in range(NROW):
            if r % 2 == 0:
                continue
            vx = random.choice((-1, 1)) * random.uniform(140, 260)
            gap = random.uniform(280, 380)
            start = random.uniform(-200, 200)
            x = start
            while x < W + 400:
                kind = "wreck" if random.random() < 0.22 else "ferry"
                bw = random.uniform(150, 230)
                self.barges.append(Barge(r, x, bw, vx, kind))
                if kind == "ferry" and random.random() < 0.55:
                    self.pearls.append(Pearl(r, x + bw * 0.5))
                x += bw + gap

    def burst(self, x, y, col, n=14) -> None:
        for _ in range(n):
            a = random.random() * math.tau
            spd = random.uniform(60, 360)
            self.sparks.append(Spark(x, y, math.cos(a) * spd, math.sin(a) * spd,
                                     random.uniform(0.16, 0.4), col, random.randint(3, 7)))

    def on_bank(self, row: int) -> bool:
        return row % 2 == 0

    def ferry_under(self, row: int, x: float) -> Barge | None:
        for b in self.barges:
            if b.row == row and b.x - 8 <= x <= b.x + b.w + 8:
                return b
        return None

    def autoplay(self) -> None:
        if self.hop_cd > 0:
            return
        target = max(0, self.row - 1)
        if self.on_bank(target):
            self.row = target
            self.hop_cd = 0.18
            return
        hits = []
        for b in self.barges:
            if b.row != target or b.kind != "ferry":
                continue
            cx = b.x + b.w * 0.5
            t_arrive = 0.22
            pred = cx + b.vx * t_arrive
            if 90 < pred < W - 90:
                hits.append((abs(pred - self.x), pred, b))
        if hits:
            hits.sort()
            _, pred, _ = hits[0]
            self.tx = pred
            self.x = pred
            self.row = target
            self.hop_cd = 0.2
        elif self.row == 0:
            self.row = NROW - 1
            self.x = W * 0.5
            self.tx = self.x
            self.combo = 1
            self.hop_cd = 0.25
            self.burst(self.x, ROWS[0], GOLD, 20)
            self.score += 80
        else:
            # sidestep toward nearest ferry on current canal
            if not self.on_bank(self.row):
                best = None
                for b in self.barges:
                    if b.row == self.row and b.kind == "ferry":
                        cx = b.x + b.w * 0.5
                        d = abs(cx - self.x)
                        if best is None or d < best[0]:
                            best = (d, cx)
                if best:
                    self.tx = best[1]

    def handle(self, ev) -> None:
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_UP, pygame.K_w) and self.row > 0:
            self.row -= 1
        elif ev.key in (pygame.K_DOWN, pygame.K_s) and self.row < NROW - 1:
            self.row += 1
        elif ev.key in (pygame.K_LEFT, pygame.K_a):
            self.tx = max(70, self.tx - 90)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.tx = min(W - 70, self.tx + 90)
        elif ev.key == pygame.K_r:
            self.score = 0
            self.reset()

    def update(self, dt: float) -> None:
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        self.hop_cd = max(0.0, self.hop_cd - dt)
        if self.record:
            self.autoplay()
        self.x += (self.tx - self.x) * min(1.0, 10.0 * dt)
        for b in self.barges:
            b.x += b.vx * dt
            if b.vx > 0 and b.x > W + 80:
                b.x = -b.w - random.uniform(40, 180)
            elif b.vx < 0 and b.x + b.w < -80:
                b.x = W + random.uniform(40, 180)
        for p in self.pearls:
            p.phase += 5.0 * dt
            host = None
            for b in self.barges:
                if b.row == p.row and b.kind == "ferry" and abs((b.x + b.w * 0.5) - p.x) < b.w:
                    host = b
                    break
            if host:
                p.x = host.x + host.w * 0.5
        py = ROWS[self.row]
        if not self.on_bank(self.row):
            ride = self.ferry_under(self.row, self.x)
            if ride is None:
                self.burst(self.x, py, ROSE, 22)
                self.flash = 0.18
                self.combo = 1
                self.row = NROW - 1
                self.x = W * 0.5
                self.tx = self.x
            elif ride.kind == "wreck":
                self.burst(self.x, py, ROSE, 26)
                self.flash = 0.2
                self.combo = 1
                self.row = NROW - 1
                self.x = W * 0.5
                self.tx = self.x
            else:
                self.x += ride.vx * dt
                self.tx += ride.vx * dt
                self.x = max(50, min(W - 50, self.x))
                self.tx = max(50, min(W - 50, self.tx))
        kept: list[Pearl] = []
        for p in self.pearls:
            if p.row == self.row and abs(p.x - self.x) < 36:
                self.score += 20 * self.combo
                self.combo = min(8, self.combo + 1)
                self.flash = 0.08
                self.burst(p.x, ROWS[p.row], CYAN, 16)
                continue
            kept.append(p)
        self.pearls = kept
        if self.row == 0:
            self.score += 50 * self.combo
            self.burst(self.x, ROWS[0], GOLD, 24)
            self.row = NROW - 1
            self.x = W * 0.5
            self.tx = self.x
            self.flash = 0.12
            if random.random() < 0.7:
                self.pearls.append(Pearl(random.choice([1, 3, 5, 7]), random.uniform(200, W - 200)))
        for rp in self.ripples:
            rp[0] += math.sin(self.t * 0.8 + rp[2]) * 18 * dt
            rp[1] += (12 + rp[2] * 20) * dt
            if rp[1] > H + 10:
                rp[1] = -8
                rp[0] = random.uniform(0, W)
        live: list[Spark] = []
        for sp in self.sparks:
            sp.life -= dt
            if sp.life <= 0:
                continue
            sp.x += sp.vx * dt
            sp.y += sp.vy * dt
            live.append(sp)
        self.sparks = live

    def draw(self, s: pygame.Surface) -> None:
        s.fill(VOID)
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.rect(veil, (20, 40, 120, 55), (0, 0, W, H))
        s.blit(veil, (0, 0))
        for x, y, r in self.ripples:
            pygame.draw.circle(s, INDIGO, (int(x), int(y)), max(1, int(r)))
        canal = pygame.Rect(40, 220, W - 80, 1420)
        pygame.draw.rect(s, NAVY, canal, border_radius=36)
        pygame.draw.rect(s, CYAN, canal, 3, border_radius=36)
        for i, yy in enumerate(ROWS):
            if i % 2 == 0:
                pygame.draw.rect(s, INK, (56, yy - 38, W - 112, 76), border_radius=18)
                pygame.draw.rect(s, VIOLET, (56, yy - 38, W - 112, 76), 2, border_radius=18)
                for k in range(8):
                    pygame.draw.circle(s, (80, 70, 160), (120 + k * 120, yy), 6)
            else:
                pygame.draw.line(s, (28, 70, 140), (60, yy), (W - 60, yy), 2)
        for b in self.barges:
            yy = ROWS[b.row]
            col = ROSE if b.kind == "wreck" else TEAL
            rim = GOLD if b.kind == "ferry" else VIOLET
            rec = pygame.Rect(int(b.x), int(yy - 28), int(b.w), 56)
            pygame.draw.rect(s, col, rec, border_radius=14)
            pygame.draw.rect(s, rim, rec, 3, border_radius=14)
            if b.kind == "ferry":
                pygame.draw.polygon(s, PEARL, [
                    (int(b.x + 18), int(yy + 6)),
                    (int(b.x + 40), int(yy - 22)),
                    (int(b.x + 62), int(yy + 6)),
                ])
        for p in self.pearls:
            rad = 11 + int(3 * math.sin(p.phase))
            pygame.draw.circle(s, CYAN, (int(p.x), int(ROWS[p.row])), rad)
            pygame.draw.circle(s, PEARL, (int(p.x - 3), int(ROWS[p.row] - 3)), 4)
        px, py = self.x, ROWS[self.row]
        pygame.draw.polygon(s, (8, 20, 40), [
            (int(px + 6), int(py + 28)), (int(px - 28), int(py + 8)),
            (int(px), int(py - 30)), (int(px + 40), int(py + 8)),
        ])
        pygame.draw.polygon(s, LIME, [
            (int(px), int(py + 22)), (int(px - 26), int(py + 4)),
            (int(px), int(py - 26)), (int(px + 26), int(py + 4)),
        ])
        pygame.draw.polygon(s, GOLD, [
            (int(px), int(py + 22)), (int(px - 26), int(py + 4)),
            (int(px), int(py - 26)), (int(px + 26), int(py + 4)),
        ], 3)
        pygame.draw.circle(s, PEARL, (int(px - 6), int(py - 6)), 5)
        for sp in self.sparks:
            pygame.draw.circle(s, sp.col, (int(sp.x), int(sp.y)), max(1, int(sp.r * sp.life * 2.4)))
        if self.flash > 0:
            fl = pygame.Surface((W, H), pygame.SRCALPHA)
            fl.fill((80, 220, 255, int(55 * self.flash / 0.2)))
            s.blit(fl, (0, 0))
        title = self.font_lg.render(TITLE, True, CYAN)
        s.blit(title, title.get_rect(center=(W // 2, 54)))
        handle = self.font_sm.render(HANDLE, True, GOLD)
        s.blit(handle, handle.get_rect(center=(W // 2, 104)))
        hud = self.font_md.render(f"SCORE  {self.score}    x{self.combo}", True, LIME)
        s.blit(hud, hud.get_rect(center=(W // 2, 154)))
        hint = self.font_sm.render("W/S hop lanes   A/D drift   R reset   x.com/ElbowOS", True, VIOLET)
        s.blit(hint, hint.get_rect(center=(W // 2, H - 46)))

    def play(self) -> None:
        screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption(TITLE)
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                    running = False
                else:
                    self.handle(ev)
            self.update(dt)
            self.draw(self.surf)
            screen.blit(self.surf, (0, 0))
            pygame.display.flip()

    def record_mp4(self, path: str) -> None:
        cmd = [
            "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "20", "-preset", "fast", "-movflags", "+faststart", path,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        frames = FPS * 15
        for i in range(frames):
            self.update(1.0 / FPS)
            self.draw(self.surf)
            proc.stdin.write(pygame.image.tostring(self.surf, "RGB"))
            if i % 30 == 0:
                print(f"frame {i}/{frames}", flush=True)
        proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            raise SystemExit(f"ffmpeg failed: {rc}")
        print("wrote", path)


def main() -> None:
    record = "--record" in sys.argv or os.environ.get("ELBOWOS_RECORD") == "1"
    play = "--play" in sys.argv
    if record or not play:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.font.init()
    g = Game(record or not play)
    if record or not play:
        out = os.environ.get("ELBOWOS_MP4", "/home/workdir/artifacts/SODALITE_SKIFF_ElbowOS.mp4")
        g.record_mp4(out)
    else:
        g.play()
    pygame.quit()


if __name__ == "__main__":
    main()
