# harry_potter_duel_full.py
# Full-featured Harry Potter duel (PyGame)

import pygame
import math
import random
import time
from dataclasses import dataclass
from typing import Tuple, List, Optional

# ---------- Config ----------
WIDTH, HEIGHT = 1280, 720
FPS = 60
PARTICLE_LIMIT = 1400

# Colors
WHITE = (255,255,255)
BLACK = (0,0,0)
GOLD = (255,200,40)
CYAN = (70,200,220)
RED = (220,30,30)
GREEN = (40,200,60)
ORANGE = (255,140,0)
PURPLE = (150,60,200)
GRAY = (100,100,100)
DARK = (12,18,28)
AVADA_GREEN = (10,255,80)
CRUCIO_RED = (200,20,20)
BLOOD = (150,10,10)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Harry Potter Duel - Full")
clock = pygame.time.Clock()
font = pygame.font.SysFont("consolas", 18)
bigfont = pygame.font.SysFont("consolas", 36)

# ---------- Dataclasses ----------
@dataclass
class SpellDef:
    name: str
    dmg: float
    mana: int
    cd: float
    color: Tuple[int,int,int]
    special: str
    speed: float
    duration: float = 0.0  # e.g., DOT or stun duration

@dataclass
class Projectile:
    x: float
    y: float
    vx: float
    vy: float
    spell: SpellDef
    life: float = 3.0

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: Tuple[int,int,int]
    size: float

@dataclass
class WandDrop:
    x: float
    y: float
    vx: float
    vy: float
    owner: str
    life: float = 12.0

# ---------- Spells ----------
SPELLS: List[SpellDef] = [
    SpellDef("Expelliarmus", dmg=0, mana=12, cd=1.0, color=GOLD, special="disarm", speed=900),
    SpellDef("Stupefy", dmg=12, mana=18, cd=1.4, color=CYAN, special="stun", speed=900, duration=1.0),
    SpellDef("Incendio", dmg=6, mana=22, cd=2.0, color=ORANGE, special="burn", speed=700, duration=3.0),
    SpellDef("Protego", dmg=0, mana=20, cd=3.0, color=GREEN, special="shield", speed=0, duration=1.8),
    SpellDef("Petrificus Totalus", dmg=0, mana=24, cd=2.6, color=PURPLE, special="petrify", speed=750, duration=2.0),
    SpellDef("Confringo", dmg=28, mana=36, cd=3.0, color=(255,180,80), special="explode", speed=1000),
    SpellDef("Avada Kedavra", dmg=9999, mana=90, cd=6.0, color=AVADA_GREEN, special="kill", speed=1200),
    SpellDef("Rictusempra", dmg=6, mana=16, cd=1.8, color=(200,200,255), special="guffaw", speed=800, duration=1.2),
    SpellDef("Crucio", dmg=1.5, mana=28, cd=3.5, color=CRUCIO_RED, special="crucio", speed=700, duration=4.0),
    SpellDef("Sectumsempra", dmg=8, mana=30, cd=3.8, color=BLOOD, special="bleed", speed=850, duration=4.0),
]

# ---------- Opponents ----------
OPPONENTS = {
    "Voldemort": {"color": (80,10,10), "hp": 150, "dodge": 0.10, "counter": 0.20},
    "Bellatrix": {"color": (150,0,120), "hp": 120, "dodge": 0.20, "counter": 0.14},
    "Dolores Umbridge": {"color": (255,105,180), "hp": 90, "dodge": 0.12, "counter": 0.08},
    "Severus Snape": {"color": (20,20,20), "hp": 130, "dodge": 0.08, "counter": 0.25},
    "Albus Dumbledore": {"color": (200,200,255), "hp": 160, "dodge": 0.06, "counter": 0.30},
}

# ---------- Game class ----------
class DuelGame:
    def __init__(self):
        self.name = ""
        self.state = "menu"  # menu, playing, result
        self.chosen_opponent = list(OPPONENTS.keys())[0]
        self._init_play_vars()

    def _init_play_vars(self):
        cfg = OPPONENTS[self.chosen_opponent]
        # player
        self.player_x = WIDTH * 0.18
        self.player_y = HEIGHT // 2
        self.player_hp = 100.0
        self.player_max_hp = 100.0
        self.player_mana = 100.0
        self.player_max_mana = 100.0
        self.player_shield_until = 0.0
        self.player_stunned_until = 0.0
        # enemy
        self.enemy_x = WIDTH * 0.82
        self.enemy_y = HEIGHT // 2
        self.enemy_name = self.chosen_opponent
        self.enemy_hp = float(cfg["hp"])
        self.enemy_max_hp = float(cfg["hp"])
        self.enemy_color = cfg["color"]
        self.enemy_dodge = cfg["dodge"]
        self.enemy_counter = cfg["counter"]
        self.enemy_shield_until = 0.0
        self.enemy_stunned_until = 0.0
        self.enemy_wand_present = True
        self.wand_drops: List[WandDrop] = []
        # game systems
        self.projectiles: List[Projectile] = []
        self.particles: List[Particle] = []
        self.selected_spell = 0
        self.last_cast = [-9999.0 for _ in SPELLS]
        self.score = 0
        self.mouse_held = False
        self.aim_path: List[Tuple[int,int]] = []
        self.message = "Hold mouse to aim, release to cast. 1-9/0 chooses spells."
        # DOT timers
        self.enemy_burn_until = 0.0
        self.enemy_bleed_until = 0.0
        self.enemy_crucio_until = 0.0

    def now(self): return time.time()

    # ---------- spawning helpers ----------
    def spawn_particles(self, x, y, color, n=12, speed=3.0, life=0.9):
        allowed = max(0, PARTICLE_LIMIT - len(self.particles))
        n = min(n, allowed)
        for _ in range(n):
            ang = random.random() * math.pi * 2
            spd = random.random() * speed
            self.particles.append(Particle(x, y, math.cos(ang)*spd, math.sin(ang)*spd, life, color, random.uniform(2,5)))

    def spawn_projectile(self, sx, sy, tx, ty, spell: SpellDef):
        dx = tx - sx; dy = ty - sy
        dist = math.hypot(dx, dy)
        if dist == 0: return
        speed = spell.speed / FPS
        vx = dx/dist * speed
        vy = dy/dist * speed
        self.projectiles.append(Projectile(sx, sy, vx, vy, spell, life=3.0))
        self.spawn_particles(sx, sy, spell.color, n=6)

    # ---------- casting ----------
    def try_cast(self, aim_x, aim_y):
        sp = SPELLS[self.selected_spell]
        now = self.now()
        if now - self.last_cast[self.selected_spell] < sp.cd:
            self.message = f"{sp.name} is cooling down!"
            return
        if self.player_mana < sp.mana:
            self.message = "Not enough mana!"
            return
        # Protego immediate shield
        if sp.special == "shield":
            self.player_shield_until = now + sp.duration
            self.player_mana -= sp.mana
            self.last_cast[self.selected_spell] = now
            self.spawn_particles(self.player_x, self.player_y, CYAN, n=24)
            self.message = "Protego!"
            return
        # spawn projectile
        self.player_mana -= sp.mana
        self.last_cast[self.selected_spell] = now
        self.spawn_projectile(self.player_x + 20, self.player_y, aim_x, aim_y, sp)
        self.message = f"Cast {sp.name}."

    # ---------- collisions & reactions ----------
    def update_projectiles(self, dt):
        now = self.now()
        new_proj = []
        for p in self.projectiles:
            p.x += p.vx * 1.0
            p.y += p.vy * 1.0
            p.life -= dt
            if p.life <= 0:
                continue
            # hit enemy?
            if math.hypot(p.x - self.enemy_x, p.y - self.enemy_y) < 46:
                self.on_spell_hit_enemy(p.spell)
                self.spawn_particles(p.x, p.y, p.spell.color, n=20)
                continue
            new_proj.append(p)
        self.projectiles = new_proj
#someone kill me before this prohect does 
    def on_spell_hit_enemy(self, spell: SpellDef):
        now = self.now()
        # enemy dodge
        if random.random() < self.enemy_dodge and spell.special != "kill":
            # dodge movement
            self.enemy_x += random.choice([-60,60])
            self.enemy_x = max(WIDTH*0.55, min(WIDTH-80, self.enemy_x))
            self.message = f"{self.enemy_name} dodged!"
            # small chance to counter
            if random.random() < self.enemy_counter:
                self.enemy_counter_action()
            return

        # special reactions
        if spell.special == "disarm":
            if self.enemy_wand_present:
                self.enemy_wand_present = False
                # drop wand object
                wd = WandDrop(self.enemy_x + random.uniform(-6,6), self.enemy_y + 10, random.uniform(-2,2), random.uniform(-4,-1), owner=self.enemy_name)
                self.wand_drops.append(wd)
                self.message = f"{self.enemy_name} disarmed!"
            # small damage
            self.enemy_hp -= 4
        elif spell.special == "stun":
            self.enemy_hp -= spell.dmg
            self.enemy_stunned_until = now + spell.duration
            # knockback
            self.enemy_x += -30
            self.message = f"{self.enemy_name} stunned!"
        elif spell.special == "burn":
            self.enemy_burn_until = now + spell.duration
            self.enemy_hp -= spell.dmg
            self.message = f"{self.enemy_name} burning!"
        elif spell.special == "petrify":
            self.enemy_stunned_until = now + spell.duration
            self.message = f"{self.enemy_name} petrified!"
        elif spell.special == "explode":
            self.enemy_hp -= spell.dmg
            self.spawn_particles(self.enemy_x, self.enemy_y, ORANGE, n=36)
            self.message = "Confringo!"
        elif spell.special == "kill":
            self.spawn_particles(self.enemy_x, self.enemy_y, AVADA_GREEN, n=120)
            self.enemy_hp = 0
            self.message = "Avada Kedavra!"
        elif spell.special == "guffaw":
            self.enemy_stunned_until = now + spell.duration
            self.enemy_hp -= spell.dmg
            self.message = f"{self.enemy_name} laughing!"
        elif spell.special == "crucio":
            self.enemy_crucio_until = now + spell.duration
            self.enemy_hp -= spell.dmg
            self.message = f"{self.enemy_name} suffers Crucio!"
        elif spell.special == "bleed":
            self.enemy_bleed_until = now + spell.duration
            self.enemy_hp -= spell.dmg
            self.spawn_particles(self.enemy_x, self.enemy_y, BLOOD, n=12)
            self.message = f"{self.enemy_name} bleeding!"
        else:
            self.enemy_hp -= spell.dmg

    def enemy_counter_action(self):
        # simple: either Protego or Stupefy
        if random.random() < 0.6:
            self.enemy_shield_until = self.now() + 1.2
            self.spawn_particles(self.enemy_x, self.enemy_y, CYAN, n=18)
            self.message = f"{self.enemy_name} cast Protego!"
        else:
            # small stun on player
            self.player_stunned_until = self.now() + 0.9
            self.player_hp -= 6
            self.spawn_particles(self.player_x, self.player_y, CYAN, n=12)
            self.message = f"{self.enemy_name} cast Stupefy!"

    # ---------- dots & timed effects ----------
    def apply_dots(self, dt):
        now = self.now()
        if self.enemy_burn_until > now:
            self.enemy_hp -= 6.0 * dt
            # flame particles
            if random.random() < 0.4:
                self.spawn_particles(self.enemy_x + random.uniform(-12,12), self.enemy_y + random.uniform(-12,12), ORANGE, n=1, speed=1.4, life=0.6)
        if self.enemy_bleed_until > now:
            self.enemy_hp -= 3.0 * dt
            if random.random() < 0.2:
                self.spawn_particles(self.enemy_x + random.uniform(-8,8), self.enemy_y + random.uniform(-8,8), BLOOD, n=1, speed=1.2, life=0.6)
        if self.enemy_crucio_until > now:
            self.enemy_hp -= 4.0 * dt

    # ---------- update step ----------
    def update(self, dt):
        now = self.now()
        # mana regen
        self.player_mana = min(self.player_max_mana, self.player_mana + dt * 8.0)
        # projectiles
        self.update_projectiles(dt)
        # particles update
        new_particles = []
        for pa in self.particles:
            pa.x += pa.vx
            pa.y += pa.vy
            pa.life -= dt
            pa.vx *= 0.98; pa.vy *= 0.98
            if pa.life > 0:
                new_particles.append(pa)
        self.particles = new_particles[:PARTICLE_LIMIT]
        # wand drops update and pickup by enemy
        for wd in list(self.wand_drops):
            wd.x += wd.vx; wd.y += wd.vy
            wd.vy += 0.12  # gravity
            wd.life -= dt
            if wd.life <= 0:
                self.wand_drops.remove(wd)
                continue
            # enemy auto-pickup if near
            if math.hypot(wd.x - self.enemy_x, wd.y - self.enemy_y) < 36:
                self.enemy_wand_present = True
                if wd in self.wand_drops:
                    self.wand_drops.remove(wd)
                self.message = f"{self.enemy_name} picked up their wand."
        # DOTs
        self.apply_dots(dt)
        # simple enemy wandering/dodge when not stunned
        if self.enemy_stunned_until < now and random.random() < 0.018:
            self.enemy_x += random.uniform(-28,28)
            self.enemy_y += random.uniform(-20,20)
            self.enemy_x = max(WIDTH*0.55, min(WIDTH-80, self.enemy_x))
            self.enemy_y = max(80, min(HEIGHT-80, self.enemy_y))
        # check deaths
        if self.enemy_hp <= 0 and self.state == "playing":
            self.state = "result"
            self.message = f"You defeated {self.enemy_name}!"
            self.score += 1
        if self.player_hp <= 0 and self.state == "playing":
            self.state = "result"
            self.message = f"You were defeated by {self.enemy_name}."

    # ---------- drawing ----------
    def draw_hud(self, surf):
        # player
        surf.blit(bigfont.render("You", True, WHITE), (12,6))
        pygame.draw.rect(surf, GRAY, (12, 48, 260, 18))
        pygame.draw.rect(surf, GREEN, (12, 48, 260 * (self.player_hp / self.player_max_hp), 18))
        pygame.draw.rect(surf, GRAY, (12, 72, 260, 12))
        pygame.draw.rect(surf, CYAN, (12, 72, 260 * (self.player_mana / self.player_max_mana), 12))
        surf.blit(font.render(f"HP: {int(self.player_hp)}", True, WHITE), (16, 48))
        surf.blit(font.render(f"Mana: {int(self.player_mana)}", True, WHITE), (16, 72))
        # enemy
        surf.blit(bigfont.render(self.enemy_name, True, self.enemy_color), (WIDTH-260,6))
        pygame.draw.rect(surf, GRAY, (WIDTH-280, 48, 260, 18))
        pygame.draw.rect(surf, RED, (WIDTH-280, 48, 260 * (self.enemy_hp / self.enemy_max_hp), 18))
        surf.blit(font.render(f"HP: {int(self.enemy_hp)}", True, WHITE), (WIDTH-276,48))
        # spells
        sy = HEIGHT - 100
        for i, sp in enumerate(SPELLS):
            x = 18 + i * 120
            rect = pygame.Rect(x, sy, 110, 60)
            pygame.draw.rect(surf, (25,25,30), rect)
            if i == self.selected_spell:
                pygame.draw.rect(surf, GOLD, rect, 3)
            surf.blit(font.render(f"{i+1}. {sp.name}", True, sp.color), (x+6, sy+6))
            surf.blit(font.render(f"M{sp.mana} CD{sp.cd}s", True, WHITE), (x+6, sy+30))
        # message & score
        surf.blit(font.render(self.message, True, WHITE), (WIDTH//2 - 260, HEIGHT - 34))
        surf.blit(font.render(f"Score: {self.score}", True, WHITE), (WIDTH-120, HEIGHT-34))

    def draw_wands(self, surf):
        # draw simple glowing wand lines for player and enemy if they have wands
        # player's wand on right-hand side of player
        # draw player wand
        wand_len = 44
        # player wand angle aimed toward last aim pos or toward enemy
        if self.aim_path:
            tx, ty = self.aim_path[-1]
        else:
            tx, ty = self.enemy_x, self.enemy_y
        ang = math.atan2(ty - self.player_y, tx - self.player_x)
        x2 = self.player_x + math.cos(ang) * wand_len
        y2 = self.player_y + math.sin(ang) * wand_len
        pygame.draw.line(surf, (255,220,140), (self.player_x, self.player_y-6), (x2, y2-6), 4)
        pygame.draw.circle(surf, (255,220,140), (int(x2), int(y2)), 5)
        # enemy wand (if present)
        if self.enemy_wand_present:
            # angle toward player
            ang2 = math.atan2(self.player_y - self.enemy_y, self.player_x - self.enemy_x)
            ex2 = self.enemy_x + math.cos(ang2) * wand_len
            ey2 = self.enemy_y + math.sin(ang2) * wand_len
            pygame.draw.line(surf, (200,180,120), (self.enemy_x, self.enemy_y-6), (ex2, ey2-6), 4)
            pygame.draw.circle(surf, (200,180,120), (int(ex2), int(ey2)), 5)

    def draw(self, surf):
        surf.fill(DARK)
        # arena panel
        pygame.draw.rect(surf, (18,20,26), (60, 40, WIDTH-120, HEIGHT-120), border_radius=6)
        # draw player
        if self.player_shield_until > self.now():
            pygame.draw.circle(surf, CYAN, (int(self.player_x), int(self.player_y)), 46, 4)
        if self.player_stunned_until > self.now():
            # show stunned (shake)
            offset = math.sin(self.now()*40)*6
            pygame.draw.circle(surf, (80,120,255), (int(self.player_x+offset), int(self.player_y)), 36)
        else:
            pygame.draw.circle(surf, (80,120,255), (int(self.player_x), int(self.player_y)), 36)
        # draw enemy
        if getattr(self, "enemy_shield_until", 0.0) > self.now():
            pygame.draw.circle(surf, CYAN, (int(self.enemy_x), int(self.enemy_y)), 50, 4)
        if self.enemy_stunned_until > self.now():
            # frozen pose - change color tint
            pygame.draw.circle(surf, (170,170,200), (int(self.enemy_x), int(self.enemy_y)), 44)
        else:
            pygame.draw.circle(surf, self.enemy_color, (int(self.enemy_x), int(self.enemy_y)), 44)
        # draw projectiles
        for p in self.projectiles:
            pygame.draw.circle(surf, p.spell.color, (int(p.x), int(p.y)), 8)
        # draw particles
        for pa in self.particles:
            pygame.draw.circle(surf, pa.color, (int(pa.x), int(pa.y)), max(1, int(pa.size)))
        # draw wand drops
        for wd in self.wand_drops:
            pygame.draw.rect(surf, (220,180,80), (int(wd.x)-6, int(wd.y)-3, 12, 6))
        # draw wand visuals
        self.draw_wands(surf)
        # if Avada was cast recently, paint green flash if enemy died (handled in HUD area)
        # HUD
        self.draw_hud(surf)
        # if mouse aiming, draw path
        if self.mouse_held and len(self.aim_path) > 1:
            pygame.draw.lines(surf, GOLD, False, self.aim_path[-16:], 3)

    # ---------- start/resets ----------
    def start(self):
        self._init_play_vars()
        self.state = "playing"

# ---------- Main loop ----------
def main():
    game = DuelGame()
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if game.state == "menu":
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        running = False
                    elif ev.key == pygame.K_TAB:
                        # cycle opponents
                        names = list(OPPONENTS.keys())
                        idx = names.index(game.chosen_opponent)
                        game.chosen_opponent = names[(idx+1) % len(names)]
                    elif ev.key == pygame.K_RETURN:
                        game.start()
                    elif ev.key == pygame.K_BACKSPACE:
                        game.name = game.name[:-1]
                    else:
                        if len(ev.unicode) == 1 and ev.unicode.isprintable():
                            game.name += ev.unicode
            elif game.state == "playing":
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        running = False
                    if ev.key == pygame.K_r:
                        game.start()
                    # select spells (1..9,0 for 10)
                    if ev.key >= pygame.K_1 and ev.key <= pygame.K_9:
                        idx = ev.key - pygame.K_1
                        if idx < len(SPELLS):
                            game.selected_spell = idx
                    if ev.key == pygame.K_0:
                        if len(SPELLS) >= 10:
                            game.selected_spell = 9
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    game.mouse_held = True
                    game.aim_path.append(ev.pos)
                if ev.type == pygame.MOUSEMOTION and game.mouse_held:
                    game.aim_path.append(ev.pos)
                if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    game.mouse_held = False
                    if game.aim_path:
                        tx, ty = game.aim_path[-1]
                        game.try_cast(tx, ty)
                        game.aim_path.clear()
            elif game.state == "result":
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_r:
                        game.start()
                    if ev.key == pygame.K_ESCAPE:
                        running = False

        if game.state == "playing":
            game.update(dt)
            # quick check: player death handling (could add respawn or game over)
        # draw
        if game.state == "menu":
            screen.fill(DARK)
            title = bigfont.render("Harry Potter Duel - Select Opponent", True, GOLD)
            screen.blit(title, (WIDTH//2 - title.get_width()//2, 60))
            instr = font.render("Type your name (optional), press TAB to cycle opponent, ENTER to start", True, WHITE)
            screen.blit(instr, (WIDTH//2 - instr.get_width()//2, 140))
            name_txt = font.render(f"Name: {game.name or '_'}", True, CYAN)
            screen.blit(name_txt, (WIDTH//2 - 120, 220))
            opp_txt = bigfont.render(f"Opponent: {game.chosen_opponent}", True, OPPONENTS[game.chosen_opponent]["color"])
            screen.blit(opp_txt, (WIDTH//2 - opp_txt.get_width()//2, 320))
            hint = font.render("Press ENTER to start. ESC to quit. R to restart during play.", True, WHITE)
            screen.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT-80))
        elif game.state in ("playing","result"):
            game.draw(screen)
            if game.state == "result":
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0,0,0,180))
                screen.blit(overlay, (0,0))
                res = bigfont.render(game.message, True, WHITE)
                screen.blit(res, (WIDTH//2 - res.get_width()//2, HEIGHT//2 - 20))
                sub = font.render("Press R to replay or ESC to quit.", True, WHITE)
                screen.blit(sub, (WIDTH//2 - sub.get_width()//2, HEIGHT//2 + 40))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
