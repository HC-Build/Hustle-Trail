"""
HUSTLE TRAIL: 0 to 1 - Startup Odyssey Faithful Edition
=====================================================
Refactored for classic startup hustle gameplay:
- Semi-automatic travel (traction auto-advances)
- Menu-driven number-key choices (no WASD in core)
- RNG-based event outcomes
- Three trail segments with escalating risks
- BONUS ARCADE HUSTLE (Startup authentic!)
- ONE final bonus arcade at the end

Features:
- Bonus Arcade Hustle: Crosshair shooter triggered every 1000-1500 traction
- SV-themed prey: Bad Code Bugs, Rug Pull Unicorns, SVB Waves
- Rewards scale: base 20 + score×3, cap 80; 70%+ = +40 bonus
"""

import pygame
import random
import sys
import math
import json
import os
import re
import hashlib
import hmac
import asyncio

# Save file path
SAVE_FILE = os.path.join(os.path.dirname(__file__), "hustle_save.json")

# ── Security helpers ──
_SAVE_KEY = b"hustle-trail-2026-integrity"

def sanitize_input(text, max_len=50):
    """Strip control chars and non-printable characters from user input"""
    return re.sub(r'[^\w\s\.\,\!\?\-\'\"\:\;\(\)\@\#\$\%\&\+\/]', '', text)[:max_len]

def _save_hash(data_str):
    """HMAC integrity hash for save file tamper detection"""
    return hmac.new(_SAVE_KEY, data_str.encode('utf-8'), hashlib.sha256).hexdigest()[:16]

# Init
pygame.init()
pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Hustle Trail: 0 to 1 (Startup Odyssey Edition)")
clock = pygame.time.Clock()
font = pygame.font.SysFont('arial', 20, bold=True)
small_font = pygame.font.SysFont('arial', 16)
big_font = pygame.font.SysFont('arial', 42, bold=True)

# Generate retro sound effects
def generate_sound(frequency, duration, volume=0.3, wave_type='square'):
    duration = min(duration, 5.0)
    sample_rate = 22050
    n_samples = int(sample_rate * duration)
    buf = bytearray(n_samples * 2)
    max_amp = int(32767 * volume)
    
    for i in range(n_samples):
        t = i / sample_rate
        if wave_type == 'square':
            val = max_amp if math.sin(2 * math.pi * frequency * t) > 0 else -max_amp
        elif wave_type == 'saw':
            val = int(max_amp * (2 * (frequency * t % 1) - 1))
        else:
            val = int(max_amp * math.sin(2 * math.pi * frequency * t))
        fade = 1 - (i / n_samples) ** 0.5
        val = int(val * fade)
        buf[i*2] = val & 0xff
        buf[i*2+1] = (val >> 8) & 0xff
    
    return pygame.mixer.Sound(buffer=bytes(buf))

# Create sounds
try:
    SFX_SHOOT = generate_sound(880, 0.1, 0.2, 'square')
    SFX_ENEMY_DIE = generate_sound(440, 0.2, 0.25, 'saw')
    SFX_POWERUP = generate_sound(660, 0.15, 0.2, 'sine')
    SFX_DAMAGE = generate_sound(110, 0.3, 0.3, 'square')
    SFX_EVENT = generate_sound(330, 0.1, 0.2, 'sine')
    SFX_WIN = generate_sound(880, 0.5, 0.3, 'sine')
    SFX_LOSE = generate_sound(110, 0.8, 0.4, 'square')
    SFX_DECISION = generate_sound(330, 0.1, 0.2, 'sine')
    SFX_REMEDY = generate_sound(550, 0.3, 0.2, 'sine')
    SFX_HUNT_HIT = generate_sound(550, 0.15, 0.25, 'square')
    SFX_HUNT_MISS = generate_sound(220, 0.1, 0.15, 'saw')
    AUDIO_ENABLED = True
except:
    AUDIO_ENABLED = False

def play_sound(sound):
    if AUDIO_ENABLED:
        try:
            sound.play()
        except:
            pass

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BROWN = (139, 69, 19)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
BLUE = (0, 100, 255)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
ORANGE = (255, 165, 0)
GRAY = (150, 150, 150)
DARK_BLUE = (10, 15, 40)
WOOD = (139, 90, 43)

# ── Q&A Timing Constants ──
QA_PHASE_DURATION = 20 * 60       # 20 seconds in frames at 60fps
QA_QUESTION_DURATION = 5 * 60     # 5 seconds per question
QA_RESULT_DISPLAY = 60            # 1 second to show reward
QA_QUESTIONS_PER_ROUND = 4
ROUNDS_PER_CYCLE = 4
QA_TRANSITION_PAUSE = 2 * 60     # 2 seconds between QA and trail
TRAIL_ROUND_MIN_SECONDS = 15
TRAIL_ROUND_MAX_SECONDS = 25

# ── Question Pool Loader ──
QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), "questions.json")

def load_questions():
    try:
        if os.path.exists(QUESTIONS_FILE):
            with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError, ValueError):
        pass
    return [
        {
            "id": i,
            "question": f"Startup Knowledge Q#{i}: Placeholder question?",
            "options": ["A) Best choice (+15)", "B) Good choice (+10)", "C) Fair choice (+7)", "D) Okay choice (+4)"],
            "runway_rewards": [15, 10, 7, 4],
        }
        for i in range(1, 16)
    ]

# ── Q&A Side-Scrolling Platformer Constants ──
QA_GROUND_Y = 490           # Ground Y (wagon bottom rests here)
QA_WAGON_X = 120            # Fixed wagon X position
QA_WAGON_W = 100            # Collision width
QA_WAGON_H_STAND = 50       # Standing collision height
QA_WAGON_H_DUCK = 25        # Ducking collision height
QA_JUMP_VEL = -12           # Initial jump velocity
QA_GRAVITY = 0.6            # Gravity per frame
QA_SCROLL_SPEED = 3         # Base scroll speed
QA_BULLET_SPEED = 10        # Bullet horizontal speed
QA_BULLET_COOLDOWN = 20     # Frames between shots

# ── Obstacle Types for Q&A Side-Scroller ──
# lane: ground (jump over), overhead (duck under), mid (shoot), collect_ground/collect_air (walk/jump into)
QA_OBSTACLE_TYPES = [
    # Ground obstacles - JUMP to avoid
    {"name": "Bug Report", "emoji": "X", "lane": "ground", "points": -5, "color": RED, "w": 40, "h": 35},
    {"name": "Tech Debt", "emoji": "D", "lane": "ground", "points": -4, "color": MAGENTA, "w": 45, "h": 30},
    {"name": "Scope Creep", "emoji": "S", "lane": "ground", "points": -6, "color": RED, "w": 50, "h": 40},
    # Overhead obstacles - DUCK to avoid
    {"name": "VC Meeting", "emoji": "V", "lane": "overhead", "points": -5, "color": (100, 100, 200), "w": 60, "h": 25},
    {"name": "Board Meeting", "emoji": "B", "lane": "overhead", "points": -4, "color": (120, 80, 180), "w": 55, "h": 25},
    {"name": "Investor Call", "emoji": "I", "lane": "overhead", "points": -3, "color": (90, 90, 170), "w": 50, "h": 25},
    # Mid-level enemies - SHOOT to destroy (hp = hits to kill)
    {"name": "Server Crash", "emoji": "!", "lane": "mid", "points": -8, "kill_points": 3, "color": RED, "w": 35, "h": 35, "hp": 2},
    {"name": "Copycat", "emoji": "C", "lane": "mid", "points": -6, "kill_points": 5, "color": ORANGE, "w": 30, "h": 30, "hp": 1},
    {"name": "Troll Tweet", "emoji": "T", "lane": "mid", "points": -3, "kill_points": 2, "color": MAGENTA, "w": 28, "h": 28, "hp": 1},
    # Collectibles - walk/jump into for bonus
    {"name": "Angel Check", "emoji": "$", "lane": "collect_ground", "points": 5, "color": GREEN, "w": 30, "h": 30},
    {"name": "Customer", "emoji": "+", "lane": "collect_ground", "points": 6, "color": GREEN, "w": 28, "h": 28},
    {"name": "Viral Post", "emoji": "V", "lane": "collect_air", "points": 4, "color": YELLOW, "w": 28, "h": 28},
    {"name": "Term Sheet", "emoji": "T", "lane": "collect_air", "points": 8, "color": CYAN, "w": 32, "h": 32},
]


def draw_lowrider_wagon(scr, wagon_x, wagon_y, runway_pct=100, wheel_angle=0, bounce_offset=0):
    """Lowrider covered wagon with gold wire rims, candy paint + flames"""
    CANDY_RED = (200, 0, 0)
    FLAME_ORANGE = (255, 140, 0)
    FLAME_YELLOW = (255, 255, 0)
    GOLD = (255, 215, 0)
    GOLD_TINT = (200, 160, 0) if runway_pct < 50 else GOLD
    CHROME = (220, 220, 220)
    OX_BROWN = (139, 69, 19)
    bo = int(bounce_offset)

    wheel_r = 20
    wby = wagon_y + 38
    fwc = (wagon_x + 32, wby + bo)
    bwc = (wagon_x + 108, wby + bo)

    def draw_rim(cx, cy, angle):
        pygame.draw.circle(scr, CHROME, (cx, cy), wheel_r + 2, 2)
        pygame.draw.circle(scr, GOLD_TINT, (cx, cy), wheel_r)
        pygame.draw.circle(scr, BLACK, (cx, cy), wheel_r - 3)
        for i in range(24):
            sa = angle + i * (math.pi / 12)
            ex = cx + int((wheel_r - 4) * math.cos(sa))
            ey = cy + int((wheel_r - 4) * math.sin(sa))
            pygame.draw.line(scr, GOLD_TINT, (cx, cy), (ex, ey), 2)
        pygame.draw.circle(scr, CHROME, (cx, cy), 8)
        pygame.draw.circle(scr, GOLD, (cx, cy), 6)
        pygame.draw.circle(scr, (255, 255, 200), (cx, cy), wheel_r - 1, 1)

    draw_rim(fwc[0], fwc[1], wheel_angle)
    draw_rim(bwc[0], bwc[1], wheel_angle + math.pi / 3)
    pygame.draw.line(scr, CHROME, fwc, bwc, 4)

    # Wagon body - candy red + flame murals
    bby = wagon_y + 18
    bed = [(wagon_x + 8, bby + 10 + bo), (wagon_x + 8, bby + bo),
           (wagon_x + 132, bby + bo), (wagon_x + 132, bby + 10 + bo)]
    pygame.draw.polygon(scr, CANDY_RED, bed)
    pygame.draw.polygon(scr, BLACK, bed, 3)

    fby = bby + 3 + bo
    for side_off in [0, 100]:
        fp = [(wagon_x + 20 + side_off, fby), (wagon_x + 40 + side_off, fby - 12),
              (wagon_x + 60 + side_off, fby - 5), (wagon_x + 80 + side_off, fby - 15),
              (wagon_x + 100 + side_off, fby)]
        pygame.draw.lines(scr, FLAME_ORANGE, False, fp, 4)
        pygame.draw.lines(scr, FLAME_YELLOW, False, fp, 2)

    # Canvas cover
    cover = [(wagon_x + 14, bby + bo), (wagon_x + 38, bby - 10 + bo),
             (wagon_x + 70, bby - 13 + bo), (wagon_x + 102, bby - 10 + bo),
             (wagon_x + 126, bby + bo)]
    pygame.draw.polygon(scr, (180, 0, 0), cover)
    pygame.draw.polygon(scr, BLACK, cover, 2)
    tf = [(wagon_x + 50, bby - 8 + bo), (wagon_x + 70, bby - 20 + bo),
          (wagon_x + 90, bby - 8 + bo)]
    pygame.draw.polygon(scr, FLAME_ORANGE, tf)
    pygame.draw.polygon(scr, FLAME_YELLOW, tf, 2)

    # "LOW H$" logo
    logo = small_font.render('LOW H$', True, GOLD)
    scr.blit(logo, (wagon_x + 50, bby + 2 + bo))

    # Shadow
    sw = int(4 + abs(bounce_offset) * 0.5)
    pygame.draw.line(scr, (80, 80, 90), (wagon_x + 10, wagon_y + 48),
                     (wagon_x + 130, wagon_y + 48), sw)

    # Oxen (gold horns, chrome chains)
    ox_y = wagon_y + 25 + bo
    for ox_x, flip in [(wagon_x - 20, -1), (wagon_x + 140, 1)]:
        pygame.draw.ellipse(scr, OX_BROWN, (ox_x - 14, ox_y - 14, 28, 28))
        pygame.draw.line(scr, GOLD, (ox_x, ox_y), (ox_x + flip * 15, ox_y - 10), 4)
        pygame.draw.line(scr, GOLD, (ox_x, ox_y), (ox_x + flip * 15, ox_y + 10), 4)
        chain_to = wagon_x + 8 if flip == -1 else wagon_x + 132
        pygame.draw.line(scr, CHROME, (ox_x - flip * 10, ox_y), (chain_to, ox_y), 3)

    # Yoke bar
    pygame.draw.line(scr, WOOD, (wagon_x + 8, ox_y), (wagon_x + 132, ox_y), 6)
    pygame.draw.line(scr, BLACK, (wagon_x + 8, ox_y), (wagon_x + 132, ox_y), 2)


class Game:
    """
    STATES:
    -1 = Onboarding
     0 = Title Screen
     1 = TRAIL (main startup hustle gameplay - auto-advancing)
     2 = FINAL_BONUS (one arcade game after reaching traction 2000)
     3 = HUSTLE (startup bonus arcade hustle mini-game!)
     5 = Win
     6 = Lose
    """
    
    def __init__(self):
        # ══════════════════════════════════════════════════════════════
        # CORE STATE
        # ══════════════════════════════════════════════════════════════
        self.state = 0  # Start at title
        
        # ── Onboarding ──
        self.onboarding_step = 0
        self.company_name = ""
        self.problem = ""
        self.solution = ""
        self.warm_intro = False      # +10% funding round success
        self.elite_college = False   # +5% event success
        self.input_text = ""
        self.input_active = True
        
        # ══════════════════════════════════════════════════════════════
        # TRAIL SYSTEM - Startup odyssey faithful
        # ══════════════════════════════════════════════════════════════
        self.distance = 0            # 0 to 2000 (win condition)
        self.pace = 1                # 1=steady, 2=strenuous, 3=grueling
        self.event_timer = 0         # Frames until next event
        self.next_event_at = random.randint(800, 1500)
        self.paused = False
        self.pause_timer = 0
        
        # Current event state
        self.current_event = None    # None, 'river', 'breakdown', 'sickness', etc.
        self.event_text = ""
        self.event_options = []
        self.event_result = None     # Result message after choice
        self.event_result_timer = 0
        
        # ══════════════════════════════════════════════════════════════
        # BONUS ARCADE HUSTLE - Startup odyssey authentic!
        # ══════════════════════════════════════════════════════════════
        self.hunt_timer = 0              # 45-60 seconds
        self.hunt_score = 0              # "Pounds of traction"
        self.hunt_max_score = 100        # For high-tier calculation
        self.hunt_bullets = 8            # Limited runway fuel!
        self.hunt_max_bullets = 8
        self.hunt_reload_timer = 0       # Slow reload
        self.hunt_crosshair_x = WIDTH // 2
        self.hunt_crosshair_y = HEIGHT // 2
        self.hunt_prey = []              # Active prey on screen
        self.hunt_spawn_timer = 0
        self.hunt_hits = []              # Hit effects
        self.hunt_distance_trigger = 0   # Track distance for hunt triggers
        self.hunt_next_at = random.randint(1000, 1500)  # Distance until next hunt
        self.hunt_traction_earned = 0
        self.hunt_runway_earned = 0
        self.hunt_equity_earned = 0
        
        # Prey types: (name, emoji, points, speed, reward_type, min_segment)
        self.hunt_prey_types = [
            # EARLY segment prey (easy)
            ("Bad Code Bug", "🐛", 5, 1.5, 'traction', "EARLY"),
            ("Spam Email", "📧", 3, 2.0, 'traction', "EARLY"),
            ("GPT Wrapper", "🤖", 8, 1.8, 'traction', "EARLY"),
            
            # MID segment prey (medium)
            ("Paul Bros Scam", "👊", 10, 2.5, 'runway', "MID"),
            ("Musk Tweet", "🚀", 15, 3.5, 'traction', "MID"),
            ("Rug Pull Unicorn", "💸", 30, 2.0, 'runway', "MID"),
            ("Ghost VC", "👻", 12, 3.0, 'runway', "MID"),
            
            # LATE segment prey (hard/boss)
            ("Theranos Cloud", "🩸", 20, 2.8, 'equity', "LATE"),
            ("SVB Collapse", "🏦", 25, 4.0, 'runway', "LATE"),
            ("Down Round", "📉", 18, 3.5, 'equity', "LATE"),
            ("Dead Unicorn", "🦄", 35, 1.5, 'runway', "LATE"),
        ]
        
        # ── Co-founders (3 to start) ──
        cofounder_names = ["Jane", "Alex", "Sam", "Taylor", "Jordan", "Riley", "Casey"]
        random.shuffle(cofounder_names)
        self.co_founders = [
            {"name": cofounder_names[0], "alive": True},
            {"name": cofounder_names[1], "alive": True},
            {"name": cofounder_names[2], "alive": True},
        ]
        
        # ── Core stats ──
        self.runway = 100.0
        self.equity = 100
        self.traction = 0
        self.followers = 0
        
        # ══════════════════════════════════════════════════════════════
        # FINAL BONUS ARCADE - Only ONE game after trail completion
        # ══════════════════════════════════════════════════════════════
        self.bonus_type = None       # 'galaga', 'mario', or 'frogger'
        self.bonus_timer = 0         # 60-120 seconds
        self.bonus_score = 0
        self.bonus_max_score = 100   # For calculating high-reward tier
        
        # Arcade game variables
        self.player_x = WIDTH // 2
        self.player_y = HEIGHT - 80
        self.player_rect = pygame.Rect(self.player_x - 25, self.player_y - 25, 50, 50)
        self.bullets = []
        self.enemies = []
        self.obstacles = []
        self.powerups = []
        self.scroll_x = 0
        self.enemy_spawn_timer = 0
        self.platforms = [pygame.Rect(100 + i*200, HEIGHT - 100, 150, 20) for i in range(10)]
        
        # ── Remedy system ──
        self.remedy_active = False
        self.remedy_text = ""
        self.remedy_options = [
            "1: Pleasure (+equity, -traction) - Touch grass, founder",
            "2: Tears (+equity, -runway) - Let it out, it's okay",
            "3: Contemplating Truth (+equity, +traction, longer) - Jian-Yang wisdom",
            "4: Friends (+equity, random boost) - Call your cofounder",
            "5: Bath & Nap (+equity, +runway) - Self-care is founder-care"
        ]
        self.remedy_threshold = 30
        self.remedy_timer = 0
        self.selected_remedy = ""
        
        # ── Quotes and UI ──
        self.current_quote = None
        self.quote_timer = 0
        self.death_quote = None
        self.log_messages = []
        
        # ── SV Quotes ──
        self.sv_quotes = [
            "We booked $1000 in the past hour → $9M ARR now! 🚀",
            "What does this company even do? 🤔",
            "Karma can protect you... sometimes.",
            "Wait 10 min, then log off. Ghosted.",
            "I generally don't like to brag, but... my resume is insane.",
            "Your TAM slide is giving delusion.",
            "Hustle Fund passed. Skill issue.",
            "Oculus? Octopus. It is a water animal.",
            "Hot dog. Not hot dog.",
            "You blew it, mister. We could have run this town.",
            "How likely? VERY? SOMEWHAT? NOT AT ALL?!",
            "If oil company wants house, there IS oil beneath house.",
            "We're pre-revenue but post-vibe.",
            "Pivoting to AI because VCs stopped calling back.",
            "Our moat is vibes. Unassailable vibes.",
            # Richard Hendricks quotes - awkward genius founder satire
            "Our middle-out compression just shattered every benchmark.",
            "It's weird. I actually don't know what to do when things are going well. It is not natural.",
            "I just want to build something beautiful. Is that so wrong?",
            "Look, guys, for thousands of years, guys like us have gotten the s*** kicked out of us.",
            "Jobs was a poser. He didn't even write code.",
            "Whoa, it is, like, 500 degrees in here.",
            "We now have 20 grand we would have otherwise lost if I had listened to you delicate little snowflakes and settled.",
            "Tabernacle!",
            "I don't want to live in a world where someone else makes the world a better place better than we do.",
            "The true resonance takes place not inside the ear, but inside the heart.",
            # More Richard Hendricks quotes
            "I believe in a thing called love.",
            "It's not about the money. It's about the money.",
            "I'm not a sociopath, Nelson. I'm autistic.",
            "The less people know about how sausages are made, the better.",
            "I don't have friends. I have people who tolerate me.",
            "I'm making history tonight.",
            "I am not a pirate.",
            "This is the most fun I've had in years.",
            "I think we should call it Pied Piper.",
            "I don't like the way you look at me.",
        ]
        
        # ── Co-founder death reasons (SV flavored) ──
        self.death_reasons = [
            "left to become a plumber in Phoenix",
            "moved to Bali for 'spiritual alignment'",
            "went full stripper at a crypto conference",
            "got poached by a Series D company",
            "had a breakdown and joined a cult",
            "became a TikTok influencer instead",
            "ghosted the team for a solo project",
            "went back to consulting at McKinsey",
            "had an existential crisis about TAM",
            "took a sabbatical that never ended",
        ]
        
        # ── Enemy types for bonus arcade ──
        self.enemy_types = [
            ("🐛 Bug", 1, "Your codebase is spaghetti"),
            ("👊 Rejection", 2, "We'll pass, but keep us updated!"),
            ("🚀 Musk Tweet", 3, "Mass layoffs are efficient"),
            ("💸 Burn Rate", 2, "Cash flowing away..."),
            ("🏦 SVB Ghost", 4, "Your runway evaporated"),
            ("📈 Wired Survey", 2, "HOW LIKELY?! VERY?!"),
            ("💨 Neumann Flow", 3, "$47B energy vibes"),
            ("🤖 GPT Wrapper", 1, "It's AI! (it's an API call)"),
            ("📉 Down Round", 3, "Cap table is cooked"),
            ("👻 Ghost VC", 2, "Will circle back! (never)"),
        ]
        
        # ══════════════════════════════════════════════════════════════
        # CYCLE / ROUND SYSTEM
        # ══════════════════════════════════════════════════════════════
        self.cycle_number = 0
        self.round_in_cycle = 0          # 0-3 (4 rounds per cycle)
        self.cycle_phase = "qa"          # "qa" or "trail"

        # Q&A Phase State
        self.qa_timer = 0                # Frames remaining in 20s QA phase
        self.qa_question_timer = 0       # Frames remaining for current question (5s)
        self.qa_question_index = 0       # Which question in this phase (0-3)
        self.qa_current_question = None  # Current question dict
        self.qa_selected_answer = -1     # Player's answer (-1 = none)
        self.qa_answered = False         # Has player answered current Q?
        self.qa_result_text = ""         # "Correct!" / "Wrong!"
        self.qa_result_timer = 0         # Frames to show result
        self.qa_round_score = 0          # Points earned this QA phase

        # Question Pool
        self.questions = load_questions()
        self.question_order = []
        self.question_pointer = 0
        self._shuffle_questions()

        # Side-Scrolling Platformer during Q&A
        self.qa_wagon_y = QA_GROUND_Y       # Wagon Y (changes with jump)
        self.qa_wagon_vy = 0                # Vertical velocity
        self.qa_is_jumping = False          # In air?
        self.qa_is_ducking = False          # Ducking?
        self.qa_scroll_speed = QA_SCROLL_SPEED  # Current scroll speed
        self.qa_scroll_x = 0               # Background scroll offset
        self.qa_obstacles = []              # Active obstacles on screen
        self.qa_bullets = []                # Active bullets
        self.qa_bullet_cooldown = 0         # Frames until can shoot again
        self.qa_obstacle_spawn_timer = 0    # Frames until next obstacle
        self.qa_spawn_interval = 80         # Starting spawn interval (frames)
        self.qa_invincible_timer = 0        # I-frames after damage
        self.qa_score_popups = []           # Floating +X/-X text popups

        # Trail Round Phase
        self.trail_round_active = False
        self.trail_round_timer = 0

        # Cycle Arcade
        self.arcade_rotation = ["hunt", "galaga", "boss", "mario", "frogger"]
        self.arcade_rotation_index = 0
        self.cycle_arcade_active = False

        # Transition pause between QA and trail
        self.round_transition_timer = 0
        self.round_transition_text = ""

        # ── Lowrider wagon animation ──
        self.wheel_angle = 0.0
        self.bounce_time = 0.0

        # ── Touch / Mobile controls ──
        self.is_touch = False           # True after first FINGERDOWN
        self.touch_left = False
        self.touch_right = False
        self.touch_up = False
        self.touch_down = False
        self.touch_buttons = []         # current frame's button defs
        self.touch_active_btn = None    # currently-held button action

        # Load saved profile
        self.load_profile()

    # ══════════════════════════════════════════════════════════════════
    # TRAIL SEGMENT HELPERS
    # ══════════════════════════════════════════════════════════════════
    
    def get_trail_segment(self):
        """Return current trail segment based on distance"""
        if self.distance < 700:
            return "EARLY"
        elif self.distance < 1400:
            return "MID"
        else:
            return "LATE"
    
    def get_trail_segment_display(self):
        """Return display name for current trail segment"""
        segment = self.get_trail_segment()
        if segment == "EARLY":
            return "Idea Validation"
        elif segment == "MID":
            return "PMF Grind"
        else:
            return "Scale Rush"
    
    def get_segment_risk(self):
        """Return base risk multiplier for current segment"""
        segment = self.get_trail_segment()
        if segment == "EARLY":
            return 0.15
        elif segment == "MID":
            return 0.25
        else:
            return 0.35
    
    def get_pace_speed(self):
        """Return distance increment per frame based on pace"""
        speeds = {1: 0.5, 2: 0.75, 3: 1.0}
        return speeds.get(self.pace, 0.5)
    
    def get_pace_drain(self):
        """Return runway drain per frame based on pace"""
        drains = {1: 0.02, 2: 0.035, 3: 0.05}
        return drains.get(self.pace, 0.02)

    # ══════════════════════════════════════════════════════════════════
    # BONUS ARCADE HUSTLE - Startup odyssey authentic crosshair shooter!
    # ══════════════════════════════════════════════════════════════════
    
    def start_hunt(self):
        """Start the bonus arcade hustle mini-game"""
        self.state = 3
        self.hunt_timer = random.randint(45, 60) * 60
        self.hunt_score = 0
        self.hunt_bullets = self.hunt_max_bullets
        self.hunt_reload_timer = 0
        self.hunt_crosshair_x = WIDTH // 2
        self.hunt_crosshair_y = HEIGHT // 2
        self.hunt_prey = []
        self.hunt_hits = []
        self.hunt_spawn_timer = 0
        self.hunt_traction_earned = 0
        self.hunt_runway_earned = 0
        self.hunt_equity_earned = 0
        
        self.log(f"🎯 BONUS ARCADE HUSTLE TIME! Shoot rug pulls for funding!")
        self.log(f"   {self.hunt_max_bullets} runway fuel — don't waste on hype!")
        play_sound(SFX_EVENT)
    
    def end_hunt(self):
        """End bonus arcade hustle and calculate rewards"""
        runway_bonus = 20 + (self.hunt_score * 3)
        runway_bonus = min(80, runway_bonus)
        
        if self.hunt_score >= self.hunt_max_score * 0.7:
            runway_bonus += 40
            self.log(f"🏆 MASTER HUNTER! +40 bonus runway!")
        
        self.runway = min(100, self.runway + runway_bonus + self.hunt_runway_earned)
        self.traction += self.hunt_traction_earned
        self.equity = min(100, self.equity + self.hunt_equity_earned)
        
        pounds = self.hunt_score + self.hunt_traction_earned + self.hunt_runway_earned
        
        self.log(f"🎯 Hunt complete! {pounds} lbs hunted")
        self.log(f"   +{runway_bonus} runway, +{self.hunt_traction_earned} traction")
        
        self.event_result = f"🎯 Hunted {pounds} lbs! +{runway_bonus} runway, +{self.hunt_traction_earned} traction"
        self.event_result_timer = 180
        
        self.hunt_distance_trigger = self.distance
        self.hunt_next_at = random.randint(1000, 1500)

        if self.cycle_arcade_active:
            self.cycle_arcade_active = False
            self.bonus_score = self.hunt_score  # For end_cycle_arcade reward calc
            self.end_cycle_arcade()
        else:
            self.state = 1
            play_sound(SFX_POWERUP)
    
    def spawn_hunt_prey(self):
        """Spawn prey based on current trail segment"""
        segment = self.get_trail_segment()
        
        available = []
        for prey in self.hunt_prey_types:
            name, emoji, points, speed, reward, min_seg = prey
            if min_seg == "EARLY":
                available.append(prey)
            elif min_seg == "MID" and segment in ("MID", "LATE"):
                available.append(prey)
            elif min_seg == "LATE" and segment == "LATE":
                available.append(prey)
        
        if not available:
            available = self.hunt_prey_types[:3]
        
        prey_data = random.choice(available)
        name, emoji, points, speed, reward, _ = prey_data
        
        side = random.choice(['top', 'left', 'right'])
        if side == 'top':
            x = random.randint(50, WIDTH - 50)
            y = -30
            dx = random.uniform(-1, 1)
            dy = speed
        elif side == 'left':
            x = -30
            y = random.randint(100, HEIGHT - 100)
            dx = speed
            dy = random.uniform(-0.5, 0.5)
        else:
            x = WIDTH + 30
            y = random.randint(100, HEIGHT - 100)
            dx = -speed
            dy = random.uniform(-0.5, 0.5)
        
        self.hunt_prey.append({
            'name': name,
            'emoji': emoji,
            'points': points,
            'reward': reward,
            'x': x,
            'y': y,
            'dx': dx,
            'dy': dy,
            'size': 40,
            'alive': True,
        })
    
    def update_hunt(self):
        """Update bonus arcade hustle mini-game"""
        self.hunt_timer -= 1
        
        if self.hunt_bullets < self.hunt_max_bullets:
            self.hunt_reload_timer += 1
            if self.hunt_reload_timer >= 90:
                self.hunt_bullets += 1
                self.hunt_reload_timer = 0
        
        keys = pygame.key.get_pressed()
        move_speed = 8
        if keys[pygame.K_LEFT] or keys[pygame.K_a] or self.touch_left:
            self.hunt_crosshair_x = max(20, self.hunt_crosshair_x - move_speed)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d] or self.touch_right:
            self.hunt_crosshair_x = min(WIDTH - 20, self.hunt_crosshair_x + move_speed)
        if keys[pygame.K_UP] or keys[pygame.K_w] or self.touch_up:
            self.hunt_crosshair_y = max(80, self.hunt_crosshair_y - move_speed)
        if keys[pygame.K_DOWN] or keys[pygame.K_s] or self.touch_down:
            self.hunt_crosshair_y = min(HEIGHT - 20, self.hunt_crosshair_y + move_speed)
        
        self.hunt_spawn_timer += 1
        spawn_rate = 60 if self.get_trail_segment() == "EARLY" else 45 if self.get_trail_segment() == "MID" else 35
        if self.hunt_spawn_timer >= spawn_rate:
            self.spawn_hunt_prey()
            self.hunt_spawn_timer = 0
        
        for prey in self.hunt_prey[:]:
            prey['x'] += prey['dx']
            prey['y'] += prey['dy']
            
            if (prey['x'] < -50 or prey['x'] > WIDTH + 50 or 
                prey['y'] < -50 or prey['y'] > HEIGHT + 50):
                self.hunt_prey.remove(prey)
        
        for hit in self.hunt_hits[:]:
            hit['timer'] -= 1
            if hit['timer'] <= 0:
                self.hunt_hits.remove(hit)
        
        if self.hunt_timer <= 0:
            self.end_hunt()
    
    def hunt_shoot(self):
        """Fire a shot at crosshair position"""
        if self.hunt_bullets <= 0:
            play_sound(SFX_HUNT_MISS)
            return
        
        self.hunt_bullets -= 1
        play_sound(SFX_SHOOT)
        
        hit_something = False
        for prey in self.hunt_prey[:]:
            dist = math.sqrt((prey['x'] - self.hunt_crosshair_x)**2 + 
                           (prey['y'] - self.hunt_crosshair_y)**2)
            if dist < prey['size']:
                hit_something = True
                self.hunt_score += prey['points']
                
                if prey['reward'] == 'traction':
                    self.hunt_traction_earned += prey['points']
                elif prey['reward'] == 'runway':
                    self.hunt_runway_earned += prey['points']
                elif prey['reward'] == 'equity':
                    self.hunt_equity_earned += prey['points']
                
                self.hunt_hits.append({
                    'x': prey['x'],
                    'y': prey['y'],
                    'text': f"+{prey['points']} {prey['reward'][:4]}",
                    'timer': 45,
                })
                
                self.hunt_prey.remove(prey)
                play_sound(SFX_HUNT_HIT)
                break
        
        if not hit_something:
            self.hunt_hits.append({
                'x': self.hunt_crosshair_x,
                'y': self.hunt_crosshair_y,
                'text': "MISS",
                'timer': 30,
            })
    
    def draw_hunt(self):
        """Draw bonus arcade hustle mini-game screen"""
        screen.fill(DARK_BLUE)
        
        random.seed(42)
        for i in range(100):
            x = random.randint(0, WIDTH)
            y = random.randint(0, HEIGHT)
            brightness = random.randint(100, 255)
            pygame.draw.circle(screen, (brightness, brightness, brightness), (x, y), 1)
        random.seed()
        
        pygame.draw.rect(screen, (30, 50, 30), (0, HEIGHT - 60, WIDTH, 60))
        
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, 70))
        
        title = big_font.render("🎯 BONUS ARCADE HUSTLE!", True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 5))
        
        secs = max(0, self.hunt_timer // 60)
        timer_color = WHITE if secs > 10 else RED
        screen.blit(font.render(f"Time: {secs}s", True, timer_color), (20, 45))
        
        runway_fuel_text = "🚀 " + "●" * self.hunt_bullets + "○" * (self.hunt_max_bullets - self.hunt_bullets)
        runway_fuel_color = WHITE if self.hunt_bullets > 2 else RED
        screen.blit(font.render(runway_fuel_text, True, runway_fuel_color), (150, 45))
        
        screen.blit(font.render(f"Hustled: {self.hunt_score} traction", True, GREEN), (450, 45))
        
        segment_display = self.get_trail_segment_display()
        seg_color = GREEN if self.get_trail_segment() == "EARLY" else YELLOW if self.get_trail_segment() == "MID" else RED
        screen.blit(small_font.render(f"[{segment_display[:12]}]", True, seg_color), (WIDTH - 120, 50))
        
        for prey in self.hunt_prey:
            prey_text = font.render(f"{prey['emoji']} {prey['name'][:8]}", True, WHITE)
            screen.blit(prey_text, (prey['x'] - prey_text.get_width()//2, prey['y'] - 10))
            pygame.draw.circle(screen, GRAY, (int(prey['x']), int(prey['y'])), prey['size'], 1)
        
        for hit in self.hunt_hits:
            color = GREEN if "+" in hit['text'] else RED
            hit_surf = font.render(hit['text'], True, color)
            y_offset = (45 - hit['timer']) * 0.5
            screen.blit(hit_surf, (hit['x'] - hit_surf.get_width()//2, hit['y'] - 20 - y_offset))
        
        cx, cy = self.hunt_crosshair_x, self.hunt_crosshair_y
        crosshair_color = WHITE if self.hunt_bullets > 0 else RED
        
        pygame.draw.circle(screen, crosshair_color, (cx, cy), 25, 2)
        pygame.draw.circle(screen, crosshair_color, (cx, cy), 3)
        pygame.draw.line(screen, crosshair_color, (cx - 35, cy), (cx - 28, cy), 2)
        pygame.draw.line(screen, crosshair_color, (cx + 28, cy), (cx + 35, cy), 2)
        pygame.draw.line(screen, crosshair_color, (cx, cy - 35), (cx, cy - 28), 2)
        pygame.draw.line(screen, crosshair_color, (cx, cy + 28), (cx, cy + 35), 2)
        
        instructions = "WASD/Arrows: Aim | SPACE: Shoot | ESC: End early"
        screen.blit(small_font.render(instructions, True, CYAN), (WIDTH//2 - 180, HEIGHT - 25))
        
        flavor_texts = [
            "Hustle rug pulls for funding!",
            "Don't waste runway fuel on hype!",
            "Shoot bad code for traction!",
            "Every unicorn counts!",
        ]
        flavor = flavor_texts[(self.hunt_timer // 180) % len(flavor_texts)]
        screen.blit(small_font.render(flavor, True, YELLOW), (20, HEIGHT - 45))

    # ══════════════════════════════════════════════════════════════════
    # EVENT SYSTEM - RNG-based startup odyssey events
    # ══════════════════════════════════════════════════════════════════
    
    def trigger_random_event(self):
        """Trigger a random trail event based on segment"""
        segment = self.get_trail_segment()
        
        events = [
            ('river', 10),
            ('breakdown', 8),
            ('sickness', 6),
            ('decision', 8),
            ('dilemma', 18),
            ('yc_lottery', 5),
            ('tweet', 10),
            ('windfall', 7),
            ('erlich', 10),
            ('hotdog', 10),
            ('gilfoyle', 8),
        ]

        if segment == "LATE":
            events = [
                ('river', 8),
                ('breakdown', 8),
                ('sickness', 10),
                ('decision', 6),
                ('dilemma', 18),
                ('yc_lottery', 8),
                ('tweet', 8),
                ('windfall', 7),
                ('erlich', 10),
                ('hotdog', 8),
                ('gilfoyle', 9),
            ]
        
        total = sum(w for _, w in events)
        r = random.randint(1, total)
        cumulative = 0
        chosen = 'decision'
        for event, weight in events:
            cumulative += weight
            if r <= cumulative:
                chosen = event
                break
        
        if chosen == 'river':
            self.trigger_river_event()
        elif chosen == 'breakdown':
            self.trigger_breakdown_event()
        elif chosen == 'sickness':
            self.trigger_sickness_event()
        elif chosen == 'decision':
            self.trigger_decision_event()
        elif chosen == 'dilemma':
            self.trigger_dilemma_event()
        elif chosen == 'yc_lottery':
            self.trigger_yc_lottery()
        elif chosen == 'tweet':
            self.trigger_tweet_event()
        elif chosen == 'windfall':
            self.trigger_windfall_event()
        elif chosen == 'erlich':
            self.trigger_erlich_event()
        elif chosen == 'hotdog':
            self.trigger_hotdog_event()
        elif chosen == 'gilfoyle':
            self.trigger_gilfoyle_event()
    
    def trigger_river_event(self):
        play_sound(SFX_EVENT)
        self.current_event = 'river'
        
        river_names = [
            "Series Seed Chasm", "VC Valley Creek", "Dilution River",
            "Cap Table Canyon", "Fundraise Falls", "Equity Rapids"
        ]
        
        self.event_text = f"You've reached the {random.choice(river_names)}!"
        self.event_options = [
            "1: Ford the river (YOLO) - 40% fail risk",
            "2: Caulk startup vehicle & float - 25% fail risk",
            "3: Wait for conditions - 10% fail, costs time",
            "4: Pay for ferry - Safe, -15 runway"
        ]
        self.log(f"🌊 Funding round/chasm crossing ahead!")
    
    def trigger_breakdown_event(self):
        play_sound(SFX_EVENT)
        self.current_event = 'breakdown'
        
        breakdowns = [
            ("Codebase has spaghetti. Refactor or ship broken?", 
             ["1: Refactor (-20 runway, safe)", "2: Ship it (30% -15 equity)"]),
            ("Server crashed at 2AM. Fix now or sleep?",
             ["1: Fix now (-15 runway)", "2: Sleep (25% lose traction)"]),
            ("Dependency deprecated. Migrate or hack?",
             ["1: Migrate (-25 runway, +10 equity)", "2: Hack (40% -20 equity)"]),
            ("Investor deck corrupted. Rebuild or wing it?",
             ["1: Rebuild (-10 runway)", "2: Wing it (35% -25 traction)"]),
        ]
        
        breakdown = random.choice(breakdowns)
        self.event_text = breakdown[0]
        self.event_options = breakdown[1]
        self.log(f"⚠️ Startup vehicle breakdown: {self.event_text[:40]}...")
    
    def trigger_sickness_event(self):
        play_sound(SFX_EVENT)
        
        alive = [cf for cf in self.co_founders if cf["alive"]]
        if not alive:
            self.trigger_decision_event()
            return
        
        victim = random.choice(alive)
        self.current_event = 'sickness'
        self.event_victim = victim
        
        sicknesses = [
            f"{victim['name']} has startup burnout!",
            f"{victim['name']} is questioning life choices!",
            f"{victim['name']} got a competing offer!",
            f"{victim['name']} is having founder existential crisis!",
        ]
        
        self.event_text = random.choice(sicknesses)
        self.event_options = [
            "1: Rest & recover (-25 runway, safe)",
            "2: Push through (30% they leave)",
            "3: Team retreat (-15 runway, +10 equity)",
        ]
        self.log(f"😰 {victim['name']} has co-founder burnout!")
    
    def trigger_decision_event(self):
        play_sound(SFX_DECISION)
        self.current_event = 'decision'
        
        decisions = [
            ("VC wants board seat for $500K.",
             ["1: Accept (+30 runway, -20 equity)", "2: Counter (-10 runway, +10 traction)"]),
            ("Competitor launched same feature!",
             ["1: Pivot fast (-20 runway, +15 traction)", "2: Double down (+10 equity)"]),
            ("TechCrunch wants interview.",
             ["1: Do it (+20 traction, -10 runway)", "2: Focus on product (+10 equity)"]),
            ("Engineer wants 4-day work week.",
             ["1: Allow (+15 equity, -10 runway)", "2: Deny (-20 equity, +10 runway)"]),
            ("User growth flat. Pivot to AI?",
             ["1: Pivot to AI (-15 equity, +25 traction)", "2: Stay course (+10 equity)"]),
            ("YC or Hustle Fund?",
             ["1: YC (+20 traction, -15 equity)", "2: Hustle Fund (+15 equity, +10 traction)"]),
            ("Thirst trap for engagement?",
             ["1: Post it (+20 traction, -10 equity)", "2: Stay professional (+5 equity)"]),
            ("$50K OpenAI bill arrived.",
             ["1: Pay it (-30 runway)", "2: Build in-house (-15 equity, +10 traction)"]),
        ]
        
        decision = random.choice(decisions)
        self.event_text = decision[0]
        self.event_options = decision[1]
        self.log(f"💼 Decision time: {self.event_text[:30]}...")
    
    def trigger_windfall_event(self):
        play_sound(SFX_POWERUP)
        self.current_event = None
        
        windfalls = [
            ("Angel investor dropped $25K!", 25, 0, 0),
            ("Viral tweet! +30 traction!", 0, 0, 30),
            ("Product Hunt feature!", 10, 10, 15),
            ("Eric Bahn retweeted you!", 0, 5, 25),
            ("Customer paid annual upfront!", 20, 5, 10),
        ]
        
        windfall = random.choice(windfalls)
        self.runway = min(100, self.runway + windfall[1])
        self.equity = min(100, self.equity + windfall[2])
        self.traction += windfall[3]
        
        self.event_result = f"🎉 {windfall[0]}"
        self.event_result_timer = 180
        self.log(f"🎉 Windfall: {windfall[0]}")

    # ══════════════════════════════════════════════════════════════════
    # EVENT RESOLUTION
    # ══════════════════════════════════════════════════════════════════
    
    def handle_river_choice(self, choice):
        fail_chances = {1: 0.40, 2: 0.25, 3: 0.10, 4: 0.00}
        fail_chance = fail_chances.get(choice, 0.25)
        
        if self.warm_intro:
            fail_chance -= 0.10
        if self.elite_college:
            fail_chance -= 0.05
        fail_chance = max(0, fail_chance)
        
        roll = random.random()
        failed = roll < fail_chance
        
        if choice == 4:
            self.runway -= 15
            self.event_result = "💰 Paid for ferry. Safe crossing! -15 runway"
            self.traction += 5
        elif failed:
            equity_loss = random.randint(15, 30)
            runway_loss = random.randint(5, 15)
            self.equity -= equity_loss
            self.runway -= runway_loss
            
            self.event_result = f"💀 DISASTER! Lost {equity_loss} equity, {runway_loss} runway!"
            
            death_chance = {"EARLY": 0.10, "MID": 0.20, "LATE": 0.30}.get(self.get_trail_segment(), 0.15)
            
            if random.random() < death_chance:
                alive = [cf for cf in self.co_founders if cf["alive"]]
                if alive:
                    victim = random.choice(alive)
                    victim["alive"] = False
                    reason = random.choice(self.death_reasons)
                    self.event_result += f"\n💀 {victim['name']} {reason}!"
                    play_sound(SFX_LOSE)
        else:
            self.traction += 10
            self.event_result = "🎉 Crossed successfully! +10 traction"
            if choice == 3:
                self.runway -= 5
                self.event_result += " (-5 runway for waiting)"
        
        self.event_result_timer = 240
        self.current_event = None
        self.log(self.event_result.split('\n')[0])
    
    def handle_breakdown_choice(self, choice):
        if choice == 1:
            self.runway -= 20
            self.event_result = "Fixed properly. -20 runway, but stable!"
        else:
            if random.random() < 0.35:
                loss = random.randint(15, 25)
                self.equity -= loss
                self.event_result = f"Quick fix failed! -{loss} equity"
            else:
                self.event_result = "Quick fix worked! Shipped it."
                self.traction += 5
        
        self.event_result_timer = 180
        self.current_event = None
        self.log(self.event_result)
    
    def handle_sickness_choice(self, choice):
        victim = getattr(self, 'event_victim', None)
        
        if choice == 1:
            self.runway -= 25
            self.event_result = f"{victim['name'] if victim else 'Team'} recovered! -25 runway"
        elif choice == 2:
            if random.random() < 0.30:
                if victim and victim["alive"]:
                    victim["alive"] = False
                    reason = random.choice(self.death_reasons)
                    self.event_result = f"💀 {victim['name']} {reason}!"
                    play_sound(SFX_LOSE)
                else:
                    self.event_result = "Team morale dropped. -15 equity"
                    self.equity -= 15
            else:
                self.event_result = "Pushed through! Hustle mentality."
                self.traction += 5
        else:
            self.runway -= 15
            self.equity = min(100, self.equity + 10)
            self.event_result = "Team retreat helped! -15 runway, +10 equity"
        
        self.event_result_timer = 180
        self.current_event = None
        self.log(self.event_result.split('\n')[0] if self.event_result else "Event resolved")
    
    def handle_decision_choice(self, choice):
        opt = self.event_options[choice - 1] if choice <= len(self.event_options) else ""
        
        if "+30 runway" in opt: self.runway = min(100, self.runway + 30)
        if "+25 runway" in opt: self.runway = min(100, self.runway + 25)
        if "+20 runway" in opt: self.runway = min(100, self.runway + 20)
        if "+15 runway" in opt: self.runway = min(100, self.runway + 15)
        if "+10 runway" in opt: self.runway = min(100, self.runway + 10)
        if "-30 runway" in opt: self.runway -= 30
        if "-25 runway" in opt: self.runway -= 25
        if "-20 runway" in opt: self.runway -= 20
        if "-15 runway" in opt: self.runway -= 15
        if "-10 runway" in opt: self.runway -= 10
        
        if "+20 equity" in opt: self.equity = min(100, self.equity + 20)
        if "+15 equity" in opt: self.equity = min(100, self.equity + 15)
        if "+10 equity" in opt: self.equity = min(100, self.equity + 10)
        if "+5 equity" in opt: self.equity = min(100, self.equity + 5)
        if "-20 equity" in opt: self.equity -= 20
        if "-15 equity" in opt: self.equity -= 15
        if "-10 equity" in opt: self.equity -= 10
        
        if "+25 traction" in opt: self.traction += 25
        if "+20 traction" in opt: self.traction += 20
        if "+15 traction" in opt: self.traction += 15
        if "+10 traction" in opt: self.traction += 10
        if "+5 traction" in opt: self.traction += 5
        
        self.event_result = f"Decision made: {opt[:50]}..."
        self.event_result_timer = 150
        self.current_event = None
        self.log(f"📋 {self.event_result[:50]}")

    # ══════════════════════════════════════════════════════════════════
    # SV DILEMMA EVENTS - Rich RNG with worse/good chances
    # ══════════════════════════════════════════════════════════════════

    SV_DILEMMAS = [
        {
            'text': "Runway 2 months -- Bahn: 'Dodgy ARR won't save you.'",
            'choices': [
                {'text': "Lay off 50% (Safe)", 'rating': 'Safe', 'base_runway': 10, 'rng_worse_chance': 20, 'worse_extra': -15, 'worse_effect': "Co-founder to Bali quit"},
                {'text': "Shutdown (Balanced)", 'rating': 'Balanced', 'base_runway': -20, 'rng_worse_chance': 30, 'worse_extra': -10, 'worse_effect': "Full team scatter"},
                {'text': "Down round (Risky)", 'rating': 'Risky', 'base_runway': -30, 'rng_worse_chance': 50, 'worse_extra': -20, 'worse_effect': "Heavy dilution roast"},
                {'text': "Pivot AI (Aggressive)", 'rating': 'Aggressive', 'base_runway': -40, 'rng_worse_chance': 40, 'worse_extra': -20, 'worse_effect': "Hype crash", 'good_chance': 30, 'good_extra': 50},
            ]
        },
        {
            'text': "CTO drama -- Gilfoyle: 'Hell anyway.'",
            'choices': [
                {'text': "Fire CTO (Safe)", 'rating': 'Safe', 'base_runway': 5, 'rng_worse_chance': 20, 'worse_extra': -15, 'worse_effect': "Morale dip"},
                {'text': "Keep CTO (Balanced)", 'rating': 'Balanced', 'base_runway': -10, 'rng_worse_chance': 30, 'worse_extra': -10, 'worse_effect': "Ongoing drag"},
                {'text': "Demote CTO (Risky)", 'rating': 'Risky', 'base_runway': -20, 'rng_worse_chance': 40, 'worse_extra': -20, 'worse_effect': "Plumber gig quit"},
                {'text': "Erlich mediate (Aggressive)", 'rating': 'Aggressive', 'base_runway': -15, 'rng_worse_chance': 30, 'worse_extra': -20, 'worse_effect': "Aviato rant waste", 'good_chance': 30, 'good_extra': 30},
            ]
        },
        {
            'text': "VC terms suck -- Bahn: 'What does this company do?'",
            'choices': [
                {'text': "Accept terms (Safe)", 'rating': 'Safe', 'base_runway': 15, 'rng_worse_chance': 20, 'worse_extra': -20, 'worse_effect': "Dilution hit"},
                {'text': "Reject offer (Balanced)", 'rating': 'Balanced', 'base_runway': -15, 'rng_worse_chance': 30, 'worse_extra': -10, 'worse_effect': "Search longer"},
                {'text': "Negotiate (Risky)", 'rating': 'Risky', 'base_runway': -25, 'rng_worse_chance': 50, 'worse_extra': -20, 'worse_effect': "Ghosted log off"},
                {'text': "Counter YOLO (Aggressive)", 'rating': 'Aggressive', 'base_runway': -35, 'rng_worse_chance': 40, 'worse_extra': -20, 'worse_effect': "Karma loss", 'good_chance': 40, 'good_extra': 45},
            ]
        },
        {
            'text': "PMF not clicking -- Richard: 'Not natural when good.'",
            'choices': [
                {'text': "Pivot (Safe)", 'rating': 'Safe', 'base_runway': 10, 'rng_worse_chance': 20, 'worse_extra': -15, 'worse_effect': "Traction reset"},
                {'text': "Persevere (Balanced)", 'rating': 'Balanced', 'base_runway': -10, 'rng_worse_chance': 30, 'worse_extra': -10, 'worse_effect': "Burn continues"},
                {'text': "Fake metrics (Risky)", 'rating': 'Risky', 'base_runway': -20, 'rng_worse_chance': 50, 'worse_extra': -30, 'worse_effect': "Bahn roast crash"},
                {'text': "Seek advice (Aggressive)", 'rating': 'Aggressive', 'base_runway': -25, 'rng_worse_chance': 30, 'worse_extra': -20, 'worse_effect': "Jian-Yang Octopus confusion", 'good_chance': 30, 'good_extra': 40},
            ]
        },
        {
            'text': "Market down -- Erlich: 'Crazy person walk away?'",
            'choices': [
                {'text': "Down round (Safe)", 'rating': 'Safe', 'base_runway': 10, 'rng_worse_chance': 20, 'worse_extra': -25, 'worse_effect': "Equity ego hit"},
                {'text': "Bridge loan (Balanced)", 'rating': 'Balanced', 'base_runway': -15, 'rng_worse_chance': 30, 'worse_extra': -15, 'worse_effect': "Debt crush"},
                {'text': "Cut costs (Risky)", 'rating': 'Risky', 'base_runway': -20, 'rng_worse_chance': 40, 'worse_extra': -20, 'worse_effect': "Layoff morale"},
                {'text': "Wait it out (Passive)", 'rating': 'Passive', 'base_runway': -20, 'rng_worse_chance': 20, 'worse_extra': -10, 'worse_effect': "Stall risk"},
            ]
        },
        {
            'text': "Co-founder wants out -- Jian-Yang: 'Not my baby.'",
            'choices': [
                {'text': "Let go (Safe)", 'rating': 'Safe', 'base_runway': 5, 'rng_worse_chance': 20, 'worse_extra': -20, 'worse_effect': "Co-founder loss"},
                {'text': "Buy out (Balanced)", 'rating': 'Balanced', 'base_runway': -20, 'rng_worse_chance': 30, 'worse_extra': -10, 'worse_effect': "Cash drain"},
                {'text': "Convince stay (Risky)", 'rating': 'Risky', 'base_runway': -15, 'rng_worse_chance': 40, 'worse_extra': -20, 'worse_effect': "Drama explosion"},
                {'text': "Ignore (Aggressive)", 'rating': 'Aggressive', 'base_runway': -30, 'rng_worse_chance': 30, 'worse_extra': -20, 'worse_effect': "Gilfoyle shrug fail", 'good_chance': 30, 'good_extra': 20},
            ]
        },
        {
            'text': "Media hype fades -- Erlich: 'Aviato forever!'",
            'choices': [
                {'text': "Double marketing (Safe)", 'rating': 'Safe', 'base_runway': -10, 'rng_worse_chance': 20, 'worse_extra': -10, 'worse_effect': "Traction fade"},
                {'text': "Cut hype (Balanced)", 'rating': 'Balanced', 'base_runway': -10, 'rng_worse_chance': 30, 'worse_extra': -10, 'worse_effect': "Visibility drop"},
                {'text': "New feature rush (Risky)", 'rating': 'Risky', 'base_runway': -25, 'rng_worse_chance': 50, 'worse_extra': -20, 'worse_effect': "Bug crash"},
                {'text': "Blame market (Aggressive)", 'rating': 'Aggressive', 'base_runway': -20, 'rng_worse_chance': 30, 'worse_extra': -20, 'worse_effect': "Karma loss", 'good_chance': 30, 'good_extra': 30},
            ]
        },
        {
            'text': "Bad vendor contract -- Bahn ghosting.",
            'choices': [
                {'text': "Pay more (Safe)", 'rating': 'Safe', 'base_runway': -5, 'rng_worse_chance': 20, 'worse_extra': -10, 'worse_effect': "Ongoing cost"},
                {'text': "Switch vendor (Balanced)", 'rating': 'Balanced', 'base_runway': -15, 'rng_worse_chance': 30, 'worse_extra': -15, 'worse_effect': "Downtime"},
                {'text': "Sue vendor (Risky)", 'rating': 'Risky', 'base_runway': -30, 'rng_worse_chance': 50, 'worse_extra': -20, 'worse_effect': "Legal drain"},
                {'text': "Hack around (Aggressive)", 'rating': 'Aggressive', 'base_runway': -25, 'rng_worse_chance': 40, 'worse_extra': -20, 'worse_effect': "Gilfoyle hell", 'good_chance': 30, 'good_extra': 30},
            ]
        },
        {
            'text': "Big pitch tomorrow -- Richard: 'Tabernacle!'",
            'choices': [
                {'text': "Wing it (Safe)", 'rating': 'Safe', 'base_runway': 5, 'rng_worse_chance': 20, 'worse_extra': -15, 'worse_effect': "Awkward fail"},
                {'text': "Overprep (Balanced)", 'rating': 'Balanced', 'base_runway': -10, 'rng_worse_chance': 30, 'worse_extra': -10, 'worse_effect': "Burnout"},
                {'text': "Cancel pitch (Risky)", 'rating': 'Risky', 'base_runway': -20, 'rng_worse_chance': 40, 'worse_extra': -20, 'worse_effect': "Opportunity loss"},
                {'text': "Thirst trap post (Aggressive)", 'rating': 'Aggressive', 'base_runway': -15, 'rng_worse_chance': 30, 'worse_extra': -20, 'worse_effect': "Bahn troll", 'good_chance': 30, 'good_extra': 30},
            ]
        },
        {
            'text': "Bank wobbles -- Dinesh panic.",
            'choices': [
                {'text': "Move banks (Safe)", 'rating': 'Safe', 'base_runway': -10, 'rng_worse_chance': 20, 'worse_extra': -10, 'worse_effect': "Fees"},
                {'text': "Withdraw all (Balanced)", 'rating': 'Balanced', 'base_runway': -15, 'rng_worse_chance': 30, 'worse_extra': -15, 'worse_effect': "Panic tax"},
                {'text': "Wait it out (Risky)", 'rating': 'Risky', 'base_runway': -25, 'rng_worse_chance': 50, 'worse_extra': -20, 'worse_effect': "Possible loss"},
                {'text': "Diversify late (Aggressive)", 'rating': 'Aggressive', 'base_runway': -20, 'rng_worse_chance': 30, 'worse_extra': -20, 'worse_effect': "Too slow", 'good_chance': 30, 'good_extra': 20},
            ]
        },
        {
            'text': "MVP launch bombs -- network melts under load.",
            'choices': [
                {'text': "Hotfix quick (Safe)", 'rating': 'Safe', 'base_runway': 10, 'rng_worse_chance': 20, 'worse_extra': -15, 'worse_effect': "Traction dip"},
                {'text': "Ignore feedback (Balanced)", 'rating': 'Balanced', 'base_runway': -10, 'rng_worse_chance': 30, 'worse_extra': -10, 'worse_effect': "Churn rise"},
                {'text': "Full rewrite (Risky)", 'rating': 'Risky', 'base_runway': -30, 'rng_worse_chance': 50, 'worse_extra': -20, 'worse_effect': "Delay crash"},
                {'text': "Blame users (Aggressive)", 'rating': 'Aggressive', 'base_runway': -20, 'rng_worse_chance': 30, 'worse_extra': -20, 'worse_effect': "Backlash", 'good_chance': 30, 'good_extra': 30},
            ]
        },
        {
            'text': "Copycat competitor launches -- Erlich crazy person.",
            'choices': [
                {'text': "Sue them (Safe)", 'rating': 'Safe', 'base_runway': -5, 'rng_worse_chance': 20, 'worse_extra': -15, 'worse_effect': "Legal slow"},
                {'text': "Differentiate (Balanced)", 'rating': 'Balanced', 'base_runway': -15, 'rng_worse_chance': 30, 'worse_extra': -10, 'worse_effect': "Feature rush"},
                {'text': "Copy back (Risky)", 'rating': 'Risky', 'base_runway': -25, 'rng_worse_chance': 50, 'worse_extra': -20, 'worse_effect': "Ethics roast"},
                {'text': "Partner with them (Aggressive)", 'rating': 'Aggressive', 'base_runway': -30, 'rng_worse_chance': 40, 'worse_extra': -20, 'worse_effect': "Betrayal risk", 'good_chance': 30, 'good_extra': 40},
            ]
        },
    ]

    def trigger_dilemma_event(self):
        play_sound(SFX_DECISION)
        self.current_event = 'dilemma'
        dilemma = random.choice(self.SV_DILEMMAS)
        self.event_dilemma = dilemma
        self.event_text = dilemma['text']
        self.event_options = [
            f"{i+1}: {c['text']} [{c['rating']}]"
            for i, c in enumerate(dilemma['choices'])
        ]
        self.log(f"SV DILEMMA: {self.event_text[:40]}...")

    def handle_dilemma_choice(self, choice):
        dilemma = getattr(self, 'event_dilemma', None)
        if not dilemma or choice < 1 or choice > len(dilemma['choices']):
            return
        c = dilemma['choices'][choice - 1]

        # Apply base runway
        self.runway = max(0, min(100, self.runway + c['base_runway']))
        result_parts = [f"{c['text']}: {c['base_runway']:+d} runway"]

        # RNG worse outcome
        worse_roll = random.randint(1, 100)
        if worse_roll <= c.get('rng_worse_chance', 0):
            self.runway = max(0, self.runway + c.get('worse_extra', 0))
            result_parts.append(f"BAD LUCK: {c.get('worse_effect', 'Setback')} ({c.get('worse_extra', 0):+d})")
            play_sound(SFX_DAMAGE)

            # Worse effect can kill a co-founder on aggressive choices
            if c.get('rating') in ('Risky', 'Aggressive') and random.random() < 0.2:
                alive = [cf for cf in self.co_founders if cf["alive"]]
                if alive:
                    victim = random.choice(alive)
                    victim["alive"] = False
                    reason = random.choice(self.death_reasons)
                    result_parts.append(f"{victim['name']} {reason}!")
                    play_sound(SFX_LOSE)
        else:
            # RNG good outcome (only some aggressive choices have this)
            good_roll = random.randint(1, 100)
            if good_roll <= c.get('good_chance', 0):
                bonus = c.get('good_extra', 0)
                self.runway = min(100, self.runway + bonus)
                result_parts.append(f"JACKPOT! +{bonus} bonus runway!")
                play_sound(SFX_WIN)

        self.event_result = "\n".join(result_parts)
        self.event_result_timer = 240
        self.current_event = None
        self.log(result_parts[0][:50])

    # ══════════════════════════════════════════════════════════════════
    # FINAL BONUS ARCADE
    # ══════════════════════════════════════════════════════════════════

    def start_final_bonus(self):
        self.state = 2
        self.bonus_type = random.choice(['galaga', 'mario', 'frogger'])
        self.bonus_timer = random.randint(60, 90) * 60
        self.bonus_score = 0
        self.bonus_max_score = 100
        
        self.player_x = WIDTH // 2
        self.player_y = HEIGHT - 80
        self.player_rect = pygame.Rect(self.player_x - 25, self.player_y - 25, 50, 50)
        self.bullets = []
        self.enemies = []
        self.obstacles = []
        self.enemy_spawn_timer = 0
        self.scroll_x = 0
        
        bonus_names = {
            'galaga': "SHOOT THE REJECTIONS!",
            'mario': "PLATFORM PIVOT!",
            'frogger': "DODGE THE COMPETITION!"
        }
        
        self.log(f"🎮 FINAL BONUS: {bonus_names.get(self.bonus_type, 'HUSTLE TIME!')}")
        play_sound(SFX_EVENT)
    
    def end_final_bonus(self):
        runway_bonus = 20 + (self.bonus_score * 5)
        runway_bonus = min(100, runway_bonus)
        
        if self.bonus_score >= self.bonus_max_score * 0.7:
            high_tier = random.randint(50, 80)
            runway_bonus += high_tier
            self.log(f"🏆 HIGH SCORE TIER! +{high_tier} bonus runway!")
        
        runway_bonus = min(runway_bonus, 150)
        self.runway = min(100, self.runway + runway_bonus)
        
        self.traction += self.bonus_score * 2
        self.equity = min(100, self.equity + 10)
        
        if self.bonus_score >= self.bonus_max_score * 0.5:
            dead = [cf for cf in self.co_founders if not cf["alive"]]
            if dead and random.random() < 0.3:
                revived = random.choice(dead)
                revived["alive"] = True
                self.log(f"🎉 {revived['name']} rejoined the team!")
        
        self.log(f"🎮 Bonus complete! +{runway_bonus} runway, +{self.bonus_score * 2} traction")
        
        self.state = 5
        play_sound(SFX_WIN)
        self.generate_remix_prompt()
    
    def update_bonus_galaga(self):
        keys = pygame.key.get_pressed()
        if (keys[pygame.K_a] or self.touch_left) and self.player_x > 25:
            self.player_x -= 5
        if (keys[pygame.K_d] or self.touch_right) and self.player_x < WIDTH - 25:
            self.player_x += 5
        self.player_rect.center = (self.player_x, self.player_y)
        
        self.enemy_spawn_timer += 1
        if self.enemy_spawn_timer > 40:
            enemy_data = random.choice(self.enemy_types)
            self.enemies.append({
                'rect': pygame.Rect(random.randint(20, WIDTH-60), -40, 40, 40),
                'type': enemy_data[0],
                'speed': random.uniform(2, 4)
            })
            self.enemy_spawn_timer = 0
        
        for b in self.bullets[:]:
            b['rect'].y -= 8
            if b['rect'].y < 0:
                self.bullets.remove(b)
        
        for e in self.enemies[:]:
            e['rect'].y += e['speed']
            if e['rect'].y > HEIGHT:
                self.enemies.remove(e)
            elif e['rect'].colliderect(self.player_rect):
                self.equity -= 5
                self.enemies.remove(e)
                play_sound(SFX_DAMAGE)
        
        for b in self.bullets[:]:
            for e in self.enemies[:]:
                if b['rect'].colliderect(e['rect']):
                    if b in self.bullets:
                        self.bullets.remove(b)
                    self.enemies.remove(e)
                    self.bonus_score += 1
                    play_sound(SFX_ENEMY_DIE)
                    break
    
    def update_bonus_mario(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a] or self.touch_left:
            self.scroll_x += 3
            self.player_x = max(50, self.player_x - 2)
        if keys[pygame.K_d] or self.touch_right:
            self.scroll_x -= 5
            self.player_x = min(WIDTH - 50, self.player_x + 2)
        if (keys[pygame.K_w] or self.touch_up) and self.player_y > HEIGHT - 200:
            self.player_y -= 8
        else:
            self.player_y = min(HEIGHT - 80, self.player_y + 3)
        
        self.player_rect.center = (self.player_x, self.player_y)
        
        if self.scroll_x < -100:
            self.bonus_score += 1
            self.scroll_x = 0
    
    def update_bonus_frogger(self):
        keys = pygame.key.get_pressed()
        if (keys[pygame.K_a] or self.touch_left) and self.player_x > 25:
            self.player_x -= 5
        if (keys[pygame.K_d] or self.touch_right) and self.player_x < WIDTH - 25:
            self.player_x += 5
        if (keys[pygame.K_w] or self.touch_up) and self.player_y > 50:
            self.player_y -= 5
        if (keys[pygame.K_s] or self.touch_down) and self.player_y < HEIGHT - 50:
            self.player_y += 5
        
        self.player_rect.center = (self.player_x, self.player_y)
        
        if random.random() < 0.03:
            obs = {
                'rect': pygame.Rect(random.choice([-50, WIDTH]), random.randint(100, HEIGHT-150), 60, 30),
                'dir': random.choice([-1, 1]),
                'speed': random.randint(3, 6)
            }
            self.obstacles.append(obs)
        
        for o in self.obstacles[:]:
            o['rect'].x += o['dir'] * o['speed']
            if o['rect'].right < -100 or o['rect'].left > WIDTH + 100:
                self.obstacles.remove(o)
            elif o['rect'].colliderect(self.player_rect):
                self.equity -= 10
                self.player_y = HEIGHT - 80
                self.obstacles.remove(o)
                play_sound(SFX_DAMAGE)
        
        if self.player_y < 60:
            self.bonus_score += 5
            self.player_y = HEIGHT - 80

    # ══════════════════════════════════════════════════════════════════
    # REMEDY SYSTEM
    # ══════════════════════════════════════════════════════════════════
    
    def trigger_remedy(self):
        play_sound(SFX_REMEDY)
        self.remedy_active = True
        self.remedy_timer = 0
        self.remedy_text = "⚠️ EQUITY CRITICAL! Choose a remedy:"
        self.log("💔 Equity low! Time for self-care, founder.")
    
    def handle_remedy(self, choice):
        remedies = ["Pleasure", "Tears", "Contemplating Truth", "Friends", "Bath & Nap"]
        self.selected_remedy = remedies[choice - 1]
        
        if choice == 1:
            self.equity = min(100, self.equity + 20)
            self.traction = max(0, self.traction - 5)
            self.remedy_timer = 180
        elif choice == 2:
            self.equity = min(100, self.equity + 15)
            self.runway = max(0, self.runway - 10)
            self.remedy_timer = 240
        elif choice == 3:
            self.equity = min(100, self.equity + 25)
            self.traction += 5
            self.remedy_timer = 360
        elif choice == 4:
            boost = random.randint(10, 30)
            self.equity = min(100, self.equity + boost)
            self.remedy_timer = 120
        elif choice == 5:
            self.equity = min(100, self.equity + 20)
            self.runway = min(100, self.runway + 15)
            self.remedy_timer = 240
        
        self.log(f"🧘 {self.selected_remedy} remedy started.")

    # ══════════════════════════════════════════════════════════════════
    # SAVE/LOAD
    # ══════════════════════════════════════════════════════════════════
    
    def save_profile(self):
        save_data = {
            "company_name": self.company_name,
            "problem": self.problem,
            "solution": self.solution,
            "warm_intro": self.warm_intro,
            "elite_college": self.elite_college,
            "high_score": getattr(self, 'high_score', 0),
            "games_played": getattr(self, 'games_played', 0) + 1,
        }
        try:
            data_str = json.dumps(save_data, sort_keys=True)
            save_data["_hash"] = _save_hash(data_str)
            with open(SAVE_FILE, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2)
        except (IOError, TypeError):
            pass
    
    def load_profile(self):
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                    raw = f.read()
                data = json.loads(raw)
                # Verify integrity hash if present
                stored_hash = data.pop("_hash", None)
                if stored_hash is not None:
                    check_str = json.dumps(data, sort_keys=True)
                    if stored_hash != _save_hash(check_str):
                        # Tampered save — reset
                        self.has_saved_profile = False
                        self.games_played = 0
                        return
                # Type-safe casting
                self.company_name = str(data.get("company_name", ""))[:50]
                self.problem = str(data.get("problem", ""))[:100]
                self.solution = str(data.get("solution", ""))[:100]
                self.warm_intro = bool(data.get("warm_intro", False))
                self.elite_college = bool(data.get("elite_college", False))
                self.games_played = int(data.get("games_played", 0))
                self.high_score = int(data.get("high_score", 0))
                self.has_saved_profile = bool(self.company_name)
            else:
                self.has_saved_profile = False
                self.games_played = 0
        except (json.JSONDecodeError, IOError, ValueError, TypeError):
            self.has_saved_profile = False
            self.games_played = 0
    
    def reset_profile(self):
        try:
            if os.path.exists(SAVE_FILE):
                os.remove(SAVE_FILE)
            self.has_saved_profile = False
            self.company_name = ""
        except (IOError, OSError):
            pass

    def bootstrap_ending(self):
        self.state = 6
        self.death_quote = (
            "You bootstrapped quietly.\n"
            "Hit $9M ARR in 18 months. Zero dilution.\n"
            "No one knows your name. You retired to Phoenix.\n"
            "\nTRUE ENDING: Quiet Wealth\n"
            "Eric Bahn: Skill issue? Nah... respect."
        )

    def log(self, msg):
        print(msg)
        self.log_messages.append(msg)
        if len(self.log_messages) > 5:
            self.log_messages.pop(0)

    def generate_remix_prompt(self):
        self.remix_prompt = f"""
🎮 HUSTLE TRAIL COMPLETE! 🎮
━━━━━━━━━━━━━━━━━━━━━━━━━
Company: {self.company_name}
Final Stats: Runway {int(self.runway)}% | Equity {self.equity}% | Traction {self.traction}
Distance: {int(self.distance)} miles | Co-founders: {sum(1 for cf in self.co_founders if cf['alive'])}/3
━━━━━━━━━━━━━━━━━━━━━━━━━
Share your run! #HustleTrail #0to1
"""
        print(self.remix_prompt)

    # ══════════════════════════════════════════════════════════════════
    # SV BOSS BATTLES
    # ══════════════════════════════════════════════════════════════════

    BOSS_TYPES = [
        {
            'name': "SVB Bank Run",
            'quote': "Your deposits are safe... just kidding.",
            'color': (0, 100, 200),
            'hp': 80,
            'attack': 'deposits',    # falling deposit bags to dodge
            'attack_speed': 4,
            'attack_rate': 25,       # frames between spawns
            'projectile_color': GREEN,
            'projectile_label': "$",
            'win_bonus': 40,
        },
        {
            'name': "Elizabeth Holmes",
            'quote': "The technology works. Trust me.",
            'color': (180, 0, 0),
            'hp': 100,
            'attack': 'vials',       # fake blood vials
            'attack_speed': 5,
            'attack_rate': 20,
            'projectile_color': RED,
            'projectile_label': "V",
            'win_bonus': 50,
        },
        {
            'name': "WeWork Neumann",
            'quote': "$47B energy vibes. Adjusted EBITDA is real.",
            'color': (255, 200, 0),
            'hp': 90,
            'attack': 'orbs',        # energy orbs that "adjust EBITDA"
            'attack_speed': 3.5,
            'attack_rate': 22,
            'projectile_color': YELLOW,
            'projectile_label': "E",
            'win_bonus': 45,
        },
    ]

    def start_boss_battle(self):
        """Initialize a boss fight"""
        self.boss = random.choice(self.BOSS_TYPES).copy()
        self.boss_hp = self.boss['hp']
        self.boss_max_hp = self.boss['hp']
        self.boss_x = WIDTH // 2
        self.boss_y = 80
        self.boss_dx = 2
        self.boss_projectiles = []
        self.boss_attack_timer = 0
        self.boss_phase = 1           # 1-3, escalates at HP thresholds
        self.boss_flash_timer = 0
        self.boss_defeated = False

        # Player setup (bottom of screen, move left/right + shoot up)
        self.player_x = WIDTH // 2
        self.player_y = HEIGHT - 60
        self.player_rect = pygame.Rect(self.player_x - 20, self.player_y - 20, 40, 40)
        self.bullets = []
        self.bonus_score = 0
        self.bonus_timer = 60 * 60  # 60 seconds max

        self.log(f"BOSS: {self.boss['name']}! \"{self.boss['quote']}\"")

    def update_boss_battle(self):
        """Update boss fight logic"""
        self.bonus_timer -= 1

        # Boss movement (bounces left/right, speeds up by phase)
        speed = self.boss_dx * self.boss_phase
        self.boss_x += speed
        if self.boss_x > WIDTH - 60 or self.boss_x < 60:
            self.boss_dx *= -1

        # Boss attacks
        self.boss_attack_timer += 1
        rate = max(10, self.boss['attack_rate'] - (self.boss_phase * 5))
        if self.boss_attack_timer >= rate:
            self.boss_attack_timer = 0
            # Spawn projectile aimed at player
            self.boss_projectiles.append({
                'x': self.boss_x,
                'y': self.boss_y + 40,
                'speed': self.boss['attack_speed'] + (self.boss_phase * 0.5),
            })

        # Update boss projectiles
        for p in self.boss_projectiles[:]:
            p['y'] += p['speed']
            p_rect = pygame.Rect(p['x'] - 10, p['y'] - 10, 20, 20)
            if p_rect.colliderect(self.player_rect):
                self.boss_projectiles.remove(p)
                self.equity -= 5
                play_sound(SFX_DAMAGE)
            elif p['y'] > HEIGHT + 20:
                self.boss_projectiles.remove(p)

        # Player bullets hit boss
        boss_rect = pygame.Rect(self.boss_x - 40, self.boss_y - 30, 80, 60)
        for b in self.bullets[:]:
            b['rect'].y -= 10
            if b['rect'].y < 0:
                self.bullets.remove(b)
            elif b['rect'].colliderect(boss_rect):
                self.bullets.remove(b)
                self.boss_hp -= 5
                self.bonus_score += 2
                self.boss_flash_timer = 8
                play_sound(SFX_HUNT_HIT)

        # Phase escalation
        hp_pct = self.boss_hp / self.boss_max_hp
        if hp_pct < 0.33:
            self.boss_phase = 3
        elif hp_pct < 0.66:
            self.boss_phase = 2

        # Flash timer
        if self.boss_flash_timer > 0:
            self.boss_flash_timer -= 1

        # Player movement
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a] or keys[pygame.K_LEFT] or self.touch_left:
            self.player_x = max(25, self.player_x - 6)
        if keys[pygame.K_d] or keys[pygame.K_RIGHT] or self.touch_right:
            self.player_x = min(WIDTH - 25, self.player_x + 6)
        self.player_rect.center = (self.player_x, self.player_y)

        # Win/lose checks
        if self.boss_hp <= 0:
            self.boss_defeated = True
            self.bonus_score += 20
            self.log(f"BOSS DEFEATED: {self.boss['name']}!")
            play_sound(SFX_WIN)
            self.end_cycle_arcade()
        elif self.bonus_timer <= 0 or self.equity <= 0:
            self.log(f"Boss survived! {self.boss['name']} wins.")
            self.end_cycle_arcade()

    def draw_boss_battle(self):
        """Draw boss fight screen"""
        screen.fill(DARK_BLUE)

        # Stars
        random.seed(99)
        for i in range(80):
            x = random.randint(0, WIDTH)
            y = random.randint(0, HEIGHT)
            pygame.draw.circle(screen, WHITE, (x, y), 1)
        random.seed()

        # Boss
        boss_color = WHITE if self.boss_flash_timer > 0 else self.boss['color']
        pygame.draw.rect(screen, boss_color, (self.boss_x - 40, self.boss_y - 30, 80, 60))
        pygame.draw.rect(screen, WHITE, (self.boss_x - 40, self.boss_y - 30, 80, 60), 2)
        name_surf = font.render(self.boss['name'], True, WHITE)
        screen.blit(name_surf, (self.boss_x - name_surf.get_width() // 2, self.boss_y - 50))

        # Boss HP bar
        hp_pct = max(0, self.boss_hp / self.boss_max_hp)
        bar_color = GREEN if hp_pct > 0.5 else YELLOW if hp_pct > 0.25 else RED
        pygame.draw.rect(screen, GRAY, (self.boss_x - 40, self.boss_y + 35, 80, 8), 1)
        pygame.draw.rect(screen, bar_color, (self.boss_x - 39, self.boss_y + 36, int(78 * hp_pct), 6))

        # Phase indicator
        phase_text = f"Phase {self.boss_phase}/3"
        screen.blit(small_font.render(phase_text, True, RED if self.boss_phase == 3 else YELLOW), (self.boss_x + 50, self.boss_y))

        # Boss projectiles
        for p in self.boss_projectiles:
            pygame.draw.rect(screen, self.boss['projectile_color'], (p['x'] - 10, p['y'] - 10, 20, 20))
            lbl = small_font.render(self.boss['projectile_label'], True, WHITE)
            screen.blit(lbl, (p['x'] - lbl.get_width() // 2, p['y'] - lbl.get_height() // 2))

        # Player
        pygame.draw.rect(screen, BROWN, self.player_rect)
        pygame.draw.rect(screen, WHITE, self.player_rect, 2)

        # Player bullets
        for b in self.bullets:
            pygame.draw.rect(screen, CYAN, b['rect'])

        # HUD
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, 30))
        secs = max(0, self.bonus_timer // 60)
        timer_color = WHITE if secs > 10 else RED
        screen.blit(font.render(f"BOSS: {self.boss['name']}", True, YELLOW), (10, 3))
        screen.blit(font.render(f"Time: {secs}s", True, timer_color), (400, 3))
        screen.blit(font.render(f"Equity: {self.equity}%", True, WHITE if self.equity > 20 else RED), (560, 3))

        # Quote
        quote_surf = small_font.render(f'"{self.boss["quote"]}"', True, ORANGE)
        screen.blit(quote_surf, (WIDTH // 2 - quote_surf.get_width() // 2, HEIGHT - 25))

        # Instructions
        screen.blit(small_font.render("A/D: Dodge | SPACE: Shoot", True, CYAN), (10, HEIGHT - 25))

    # ══════════════════════════════════════════════════════════════════
    # YC LOTTERY EVENT
    # ══════════════════════════════════════════════════════════════════

    def trigger_yc_lottery(self):
        play_sound(SFX_EVENT)
        self.current_event = 'yc_lottery'
        self.event_text = "YC app submitted! Results in 3... 2... 1..."
        self.event_options = [
            "1: Check inbox (1% JACKPOT, 99% rejection)",
            "2: Don't look, keep building (-5 runway, +10 traction)",
        ]
        self.log("YC APPLICATION SUBMITTED!")

    def handle_yc_lottery_choice(self, choice):
        if choice == 1:
            roll = random.randint(1, 100)
            if roll <= 1:
                # JACKPOT - 1% chance
                self.runway = 100
                self.equity = min(100, self.equity + 20)
                self.traction += 50
                self.event_result = (
                    "YC ACCEPTED! Full runway refill!\n"
                    "+20 equity, +50 traction!\n"
                    "Paul Graham: 'Make something people want.'"
                )
                play_sound(SFX_WIN)
            else:
                # Rejection - 99%
                self.runway = max(0, self.runway - 10)
                reject_quotes = [
                    "Rejected. 'Skill issue.' - Eric Bahn",
                    "Rejected. 'What does this company even do?'",
                    "Rejected. 'We'll pass, keep us updated!' (never)",
                    "Rejected. 'Your TAM slide is giving delusion.'",
                    "Rejected. 'Hot dog. Not hot dog.' - Jian-Yang",
                ]
                self.event_result = f"{random.choice(reject_quotes)}\n-10 runway"
                play_sound(SFX_DAMAGE)
        else:
            self.runway = max(0, self.runway - 5)
            self.traction += 10
            self.event_result = "Smart. Kept building. -5 runway, +10 traction."
            play_sound(SFX_EVENT)

        self.event_result_timer = 240
        self.current_event = None
        self.log(self.event_result.split('\n')[0][:50])

    # ══════════════════════════════════════════════════════════════════
    # AUTO-CORRECT TWEET FAILS
    # ══════════════════════════════════════════════════════════════════

    TWEET_PROMPTS = [
        ("pivot to AI", "pirate to AI"),
        ("raise seed round", "raise weed round"),
        ("product market fit", "product market fist"),
        ("disrupt the market", "disrupt the muppet"),
        ("scale to millions", "scale to minions"),
        ("ship the MVP", "ship the MV-Pee"),
        ("close Series A", "close Serious A"),
        ("iterate quickly", "irritate quickly"),
        ("growth hacking", "growth whacking"),
        ("exit strategy", "exit tragedy"),
        ("burn rate is fine", "burn rate is fire"),
        ("10x engineer", "10x endanger"),
    ]

    def trigger_tweet_event(self):
        play_sound(SFX_EVENT)
        self.current_event = 'tweet'
        prompt_pair = random.choice(self.TWEET_PROMPTS)
        self.tweet_target = prompt_pair[0]
        self.tweet_mangled = prompt_pair[1]
        self.tweet_input = ""
        self.tweet_timer = 5 * 60  # 5 seconds to type
        self.tweet_done = False

        if self.is_touch:
            # Mobile: multiple-choice instead of typing
            self.tweet_mobile_choices = True
            # Build 3 options: correct + mangled + a random other mangled
            other_pairs = [p for p in self.TWEET_PROMPTS if p[0] != self.tweet_target]
            decoy = random.choice(other_pairs)[1] if other_pairs else "lorem ipsum startup"
            self.tweet_options = [self.tweet_target, self.tweet_mangled, decoy]
            random.shuffle(self.tweet_options)
            self.tweet_correct_idx = self.tweet_options.index(self.tweet_target)
            self.event_text = "TWEET FOR TRACTION!\nWhich tweet is correct?"
            self.event_options = [
                f"{i+1}: \"{opt}\"" for i, opt in enumerate(self.tweet_options)
            ]
        else:
            self.tweet_mobile_choices = False
            self.event_text = f"TWEET FOR TRACTION!\nType: \"{self.tweet_target}\""
            self.event_options = [
                "Type it correctly in 5 seconds!",
                "30% chance auto-correct mangles it anyway...",
            ]
        self.log("Tweet time! Type fast, founder!")

    def update_tweet_event(self):
        """Tick down tweet timer (called from update when state==1 and event=='tweet')"""
        if self.current_event != 'tweet' or self.tweet_done:
            return
        self.tweet_timer -= 1
        if self.tweet_timer <= 0 and not self.tweet_done:
            self._resolve_tweet(timed_out=True)

    def _resolve_tweet(self, timed_out=False):
        self.tweet_done = True
        if timed_out:
            self.runway = max(0, self.runway - 8)
            self.event_result = (
                f"TIME'S UP! Auto-correct: \"{self.tweet_mangled}\"\n"
                "VCs ghosted. -8 runway\n"
                "Bahn: Skill issue."
            )
            play_sound(SFX_DAMAGE)
        elif self.tweet_input.strip().lower() == self.tweet_target.lower():
            # Typed correctly, but 30% auto-correct chance
            if random.random() < 0.30:
                self.runway = max(0, self.runway - 5)
                self.traction += 5
                self.event_result = (
                    f"Auto-correct struck! Sent: \"{self.tweet_mangled}\"\n"
                    "Went viral for wrong reasons. -5 runway, +5 traction\n"
                    "Jian-Yang: Octopus. It is a water animal."
                )
                play_sound(SFX_DAMAGE)
            else:
                self.traction += 20
                self.runway = min(100, self.runway + 5)
                self.event_result = (
                    "Tweet nailed! Viral boost!\n"
                    "+20 traction, +5 runway\n"
                    "Eric Bahn retweeted you!"
                )
                play_sound(SFX_POWERUP)
        else:
            self.runway = max(0, self.runway - 5)
            self.event_result = (
                f"Typo! Sent: \"{self.tweet_input[:30]}\"\n"
                "VCs confused. -5 runway\n"
                "Richard: 'It's weird.'"
            )
            play_sound(SFX_DAMAGE)

        self.event_result_timer = 240
        self.current_event = None
        self.log(self.event_result.split('\n')[0][:50])

    def handle_tweet_keypress(self, event):
        """Handle keyboard input during tweet event"""
        if self.tweet_done:
            return
        if event.key == pygame.K_BACKSPACE:
            self.tweet_input = self.tweet_input[:-1]
        elif event.key == pygame.K_RETURN:
            self._resolve_tweet(timed_out=False)
        elif event.unicode and len(self.tweet_input) < 50:
            self.tweet_input += event.unicode

    def _handle_tweet_mobile_choice(self, choice):
        """Handle mobile multiple-choice tweet selection"""
        if self.tweet_done:
            return
        self.tweet_done = True
        idx = choice - 1
        if idx == getattr(self, 'tweet_correct_idx', -1):
            # Picked correct tweet — same 30% auto-correct risk
            if random.random() < 0.30:
                self.runway = max(0, self.runway - 5)
                self.traction += 5
                self.event_result = (
                    f"Auto-correct struck! Sent: \"{self.tweet_mangled}\"\n"
                    "Went viral for wrong reasons. -5 runway, +5 traction"
                )
                play_sound(SFX_DAMAGE)
            else:
                self.traction += 20
                self.runway = min(100, self.runway + 5)
                self.event_result = (
                    "Tweet nailed! Viral boost!\n"
                    "+20 traction, +5 runway"
                )
                play_sound(SFX_POWERUP)
        else:
            self.runway = max(0, self.runway - 5)
            self.event_result = (
                f"Wrong tweet! Sent the mangled version.\n"
                "VCs confused. -5 runway"
            )
            play_sound(SFX_DAMAGE)
        self.event_result_timer = 240
        self.current_event = None
        self.log(self.event_result.split('\n')[0][:50])

    def draw_tweet_overlay(self):
        """Draw the tweet typing minigame overlay"""
        pygame.draw.rect(screen, BLACK, (30, 120, WIDTH - 60, 280))
        pygame.draw.rect(screen, CYAN, (30, 120, WIDTH - 60, 280), 3)

        screen.blit(font.render("TWEET FOR TRACTION!", True, CYAN), (50, 135))

        # Timer bar
        t_pct = max(0, self.tweet_timer / (5 * 60))
        bar_color = GREEN if t_pct > 0.4 else YELLOW if t_pct > 0.2 else RED
        pygame.draw.rect(screen, GRAY, (50, 160, WIDTH - 100, 12), 1)
        pygame.draw.rect(screen, bar_color, (51, 161, int((WIDTH - 102) * t_pct), 10))

        # Target text
        screen.blit(font.render(f"Type: \"{self.tweet_target}\"", True, YELLOW), (50, 185))

        # Input field
        cursor = "|" if pygame.time.get_ticks() % 600 < 300 else ""
        pygame.draw.rect(screen, (30, 30, 60), (50, 220, WIDTH - 100, 40))
        pygame.draw.rect(screen, WHITE, (50, 220, WIDTH - 100, 40), 2)
        screen.blit(font.render(self.tweet_input + cursor, True, GREEN), (60, 228))

        # Matching indicator
        target = self.tweet_target.lower()
        typed = self.tweet_input.strip().lower()
        if typed and target.startswith(typed):
            screen.blit(small_font.render("Looking good...", True, GREEN), (50, 270))
        elif typed:
            screen.blit(small_font.render("Typo detected!", True, RED), (50, 270))

        screen.blit(small_font.render("ENTER to send | 30% auto-correct risk!", True, ORANGE), (50, 300))
        screen.blit(small_font.render(f"Secs left: {max(0, self.tweet_timer // 60)}", True, WHITE), (50, 370))

    # ══════════════════════════════════════════════════════════════════
    # ERLICH BACHMANN RANT GENERATOR
    # ══════════════════════════════════════════════════════════════════

    ERLICH_RANTS = [
        {
            "intro": "Erlich Bachmann storms in, vape cloud trailing...",
            "rant": "AVIATO! You know what Aviato is? I'll tell you what Aviato is. "
                    "It's the Rolls Royce of cloud-based travel platforms. "
                    "I built it in THIS GARAGE. All great companies start in garages!",
            "exit_line": "You're gonna walk away from that money? Crazy person!",
        },
        {
            "intro": "Erlich kicks down the door uninvited...",
            "rant": "Let me tell you something. I once turned a $500 investment "
                    "into a $5 MILLION exit. Granted, most of that was luck and a "
                    "judge who didn't understand equity dilution, but STILL.",
            "exit_line": "This is my incubator. I decide who disrupts and who doesn't.",
        },
        {
            "intro": "Erlich appears with a kimono and a smoothie...",
            "rant": "You're thinking too small! Your TAM? GARBAGE. "
                    "My TAM for Aviato was literally everyone who has ever traveled. "
                    "That's 7 billion people. You want to know what 7 billion times $1 is?",
            "exit_line": "I've been known to give away a lot of free advice. Here's another: you're welcome.",
        },
        {
            "intro": "Erlich commandeers your pitch meeting...",
            "rant": "Listen, I've seen a THOUSAND startups. You know what separates "
                    "the unicorns from the deadpool? ME. I am the X factor. "
                    "I am the incubator. I am... Bachmanity.",
            "exit_line": "BACHMANITY INSANITY! That's the name. Write it down.",
        },
        {
            "intro": "Erlich stumbles out of an Uber Black...",
            "rant": "I once pitched Gavin Belson himself. To his FACE. "
                    "He said no. You know what I said? I said Gavin, "
                    "you just passed on the next Google. Then I keyed his Tesla.",
            "exit_line": "If you're not pissing someone off, you're not disrupting hard enough.",
        },
        {
            "intro": "Erlich emerges from a failed ayahuasca retreat...",
            "rant": "I have SEEN things. In the jungle. A vision told me "
                    "to invest in blockchain NFT AI. Then I woke up and realized "
                    "I'd already done that. Twice. And it worked ZERO times.",
            "exit_line": "The universe has plans for me. Mostly legal trouble, but PLANS.",
        },
    ]

    def trigger_erlich_event(self):
        play_sound(SFX_EVENT)
        self.current_event = 'erlich'
        rant = random.choice(self.ERLICH_RANTS)
        self.erlich_rant = rant
        self.event_text = f"{rant['intro']}\n\n\"{rant['rant'][:120]}...\""
        self.event_options = [
            "1: Listen to the whole rant (+8 traction hype, -5 runway wasted)",
            "2: Interrupt him (-3 equity awkward, +3 runway saved)",
            "3: Quote-tweet his rant (50/50: +15 viral or -10 roasted)",
        ]
        self.log(f"ERLICH BACHMANN: {rant['intro'][:40]}...")

    def handle_erlich_choice(self, choice):
        rant = getattr(self, 'erlich_rant', None)
        if not rant:
            return

        if choice == 1:
            # Listen: traction boost, runway drain from time wasted
            self.traction += 8
            self.runway = max(0, self.runway - 5)
            self.event_result = (
                f"You sat through the whole thing.\n"
                f"+8 traction (hype energy), -5 runway (time is money)\n"
                f"Erlich: \"{rant['exit_line']}\""
            )
            play_sound(SFX_WIN)

        elif choice == 2:
            # Interrupt: awkward equity hit, save some runway
            self.equity = max(0, self.equity - 3)
            self.runway = min(100, self.runway + 3)
            self.event_result = (
                "You cut him off mid-sentence.\n"
                "Erlich: \"Did you just... interrupt ME?\"\n"
                "-3 equity (burned bridge), +3 runway (time saved)\n"
                "He slams the door. Vape cloud lingers for hours."
            )
            play_sound(SFX_DAMAGE)

        else:
            # Quote-tweet: 50/50 viral or roast
            if random.random() < 0.5:
                self.runway = min(100, self.runway + 15)
                self.traction += 10
                self.event_result = (
                    "VIRAL THREAD! Everyone loves dunking on Erlich.\n"
                    "+15 runway, +10 traction\n"
                    "Erlich: \"No such thing as bad press, baby!\""
                )
                play_sound(SFX_WIN)
            else:
                self.runway = max(0, self.runway - 10)
                self.equity = max(0, self.equity - 5)
                self.event_result = (
                    "RATIO'D. Erlich's reply went mega-viral instead.\n"
                    "-10 runway, -5 equity\n"
                    "Erlich: \"You came at the king. You missed.\""
                )
                play_sound(SFX_DAMAGE)

        self.event_result_timer = 240
        self.current_event = None
        self.log(self.event_result.split('\n')[0][:50])

    # ══════════════════════════════════════════════════════════════════
    # JIAN-YANG "HOT DOG / NOT HOT DOG" MINI-EVENT
    # ══════════════════════════════════════════════════════════════════

    HOTDOG_ITEMS = [
        # (item_name, is_hot_dog, flavor_text)
        ("A actual hot dog", True, "Hot dog."),
        ("A bratwurst in a bun", True, "Technically... hot dog."),
        ("A corn dog", True, "Hot dog. Corn style."),
        ("A Chicago-style dog", True, "Hot dog. Very Chicago."),
        ("A slim jim", True, "...hot dog. Slim version."),
        ("Your SaaS dashboard", False, "Not hot dog."),
        ("A series A term sheet", False, "Not hot dog. Paper only."),
        ("A Kubernetes cluster", False, "Not hot dog. Is yaml."),
        ("Gavin Belson's ego", False, "Not hot dog. Is nightmare."),
        ("A product roadmap", False, "Not hot dog. Is wishful thinking."),
        ("An NFT of a hot dog", False, "Not hot dog. Is screenshot."),
        ("A pivot strategy", False, "Not hot dog. Is desperation."),
        ("Erlich's vape pen", False, "Not hot dog. Is health hazard."),
        ("Your burn rate chart", False, "Not hot dog. Is scary."),
        ("A WeWork membership", False, "Not hot dog. Is overpriced couch."),
        ("A foot-long sub", True, "Hot dog. Big version."),
    ]

    def trigger_hotdog_event(self):
        play_sound(SFX_EVENT)
        self.current_event = 'hotdog'
        item = random.choice(self.HOTDOG_ITEMS)
        self.hotdog_item = item
        self.event_text = (
            f"Jian-Yang appears on your screen.\n"
            f"\"I make app. Very good app.\"\n\n"
            f"He holds up: {item[0]}\n\n"
            f"\"What is this?\""
        )
        self.event_options = [
            "1: HOT DOG",
            "2: NOT HOT DOG",
        ]
        self.log(f"JIAN-YANG: Hot dog or not? ({item[0]})")

    def handle_hotdog_choice(self, choice):
        item = getattr(self, 'hotdog_item', None)
        if not item:
            return

        is_hot_dog = item[1]
        flavor = item[2]
        correct = (choice == 1 and is_hot_dog) or (choice == 2 and not is_hot_dog)

        if correct:
            runway_gain = random.randint(8, 15)
            self.runway = min(100, self.runway + runway_gain)
            self.traction += 5
            self.event_result = (
                f"Jian-Yang: \"{flavor}\"\n"
                f"CORRECT! +{runway_gain} runway, +5 traction\n"
                f"Jian-Yang: \"See? App work. Very good.\""
            )
            play_sound(SFX_WIN)
        else:
            self.traction = max(0, self.traction - 10)
            self.runway = max(0, self.runway - 5)
            fail_lines = [
                "Jian-Yang: \"Wrong. You are like Erlich. Stupid.\"",
                "Jian-Yang: \"No. We go to Taco Bell instead.\"",
                "Jian-Yang: \"You fail. Like octopus app.\"",
                "Jian-Yang: \"Wrong answer. I put fish in your server.\"",
                "Jian-Yang: \"Incorrect. Special occasion... for you to leave.\"",
            ]
            self.event_result = (
                f"Jian-Yang: \"{flavor}\"\n"
                f"WRONG! -5 runway, -10 traction\n"
                f"{random.choice(fail_lines)}"
            )
            play_sound(SFX_DAMAGE)

        self.event_result_timer = 240
        self.current_event = None
        self.log(self.event_result.split('\n')[0][:50])

    # ══════════════════════════════════════════════════════════════════
    # GILFOYLE SATANIST HELL BONUS
    # ══════════════════════════════════════════════════════════════════

    GILFOYLE_PACTS = [
        {
            "setup": "Server room catches fire. Everything's down.\n"
                     "Gilfoyle appears in the smoke, unfazed.\n"
                     "\"Welcome to hell. I've been here a while.\"",
            "pact_offer": "Sacrifice equity to the dark lord of uptime?",
            "choices": [
                {
                    "text": "Blood pact: Trade 15 equity for 25 runway",
                    "equity_cost": 15, "runway_gain": 25,
                    "result": "\"Smart. The singularity will remember you were cooperative.\"",
                },
                {
                    "text": "Soul lease: Trade 10 equity, 50/50 for 35 or 0 runway",
                    "equity_cost": 10, "runway_gain_good": 35, "runway_gain_bad": 0,
                    "rng": True,
                    "result_good": "\"Lucifer smiles upon your deployment.\"",
                    "result_bad": "\"The dark lord giveth, the dark lord keepeth. Hell anyway.\"",
                },
                {
                    "text": "Decline the pact. Keep your soul.",
                    "equity_cost": 0, "runway_gain": 0, "traction_gain": 5,
                    "result": "\"Your loss. I'll be in the server room. Praying. To Satan.\"",
                },
            ]
        },
        {
            "setup": "Database corrupted. 48 hours of data gone.\n"
                     "Gilfoyle, typing furiously:\n"
                     "\"I can fix this. But my services aren't free. Or moral.\"",
            "pact_offer": "Let Gilfoyle perform the forbidden git force push?",
            "choices": [
                {
                    "text": "Force push: -12 equity, +20 runway, restore data",
                    "equity_cost": 12, "runway_gain": 20,
                    "result": "\"Done. Don't look at the commit messages. They're in Latin.\"",
                },
                {
                    "text": "Forbidden merge: -8 equity, 60/40 for 30 or -5 runway",
                    "equity_cost": 8, "runway_gain_good": 30, "runway_gain_bad": -5,
                    "rng": True,
                    "result_good": "\"The merge succeeded. Even I'm surprised.\"",
                    "result_bad": "\"Merge conflict. With your soul. And production.\"",
                },
                {
                    "text": "Do it the right way. No dark arts.",
                    "equity_cost": 0, "runway_gain": 0, "traction_gain": 8,
                    "result": "\"Fine. Be ethical. See where that gets you.\" *shrugs*",
                },
            ]
        },
        {
            "setup": "Competitor launches your exact product. Morale tanked.\n"
                     "Gilfoyle, deadpan: \"They copied us. Want me to\n"
                     "make their servers... have an accident?\"",
            "pact_offer": "Unleash Gilfoyle's 'competitive intelligence'?",
            "choices": [
                {
                    "text": "Deploy the bots: -10 equity, +20 runway, +15 traction",
                    "equity_cost": 10, "runway_gain": 20, "traction_gain": 15,
                    "result": "\"Their Glassdoor reviews are now... interesting.\"",
                },
                {
                    "text": "Subtle sabotage: -7 equity, 50/50 for +25 or -8 runway",
                    "equity_cost": 7, "runway_gain_good": 25, "runway_gain_bad": -8,
                    "rng": True,
                    "result_good": "\"Oops. Their DNS just pointed to a cat video. Weird.\"",
                    "result_bad": "\"They traced it back. Time to update your LinkedIn.\"",
                },
                {
                    "text": "Take the high road. Out-build them.",
                    "equity_cost": 0, "runway_gain": 0, "traction_gain": 10,
                    "result": "\"Boring. But I respect the stoicism. Barely.\"",
                },
            ]
        },
        {
            "setup": "3 AM. Pager goes off. Production is on fire.\n"
                     "Gilfoyle hasn't slept in 3 days. Or blinked.\n"
                     "\"I can end this. But there's a cost. There's always a cost.\"",
            "pact_offer": "Accept Gilfoyle's 3 AM bargain?",
            "choices": [
                {
                    "text": "Full ritual: -15 equity, +30 runway",
                    "equity_cost": 15, "runway_gain": 30,
                    "result": "\"Fixed. I added a pentagram to the loading screen. Don't remove it.\"",
                },
                {
                    "text": "Half ritual: -5 equity, 40/60 for +20 or -10 runway",
                    "equity_cost": 5, "runway_gain_good": 20, "runway_gain_bad": -10,
                    "rng": True,
                    "result_good": "\"The half-measure worked. Satan is feeling generous tonight.\"",
                    "result_bad": "\"Should've gone full ritual. Now production AND staging are down.\"",
                },
                {
                    "text": "Call the on-call engineer instead",
                    "equity_cost": 0, "runway_gain": -3, "traction_gain": 5,
                    "result": "\"The on-call engineer is me. I'm already here. This is my life.\"",
                },
            ]
        },
    ]

    def trigger_gilfoyle_event(self):
        play_sound(SFX_DECISION)
        self.current_event = 'gilfoyle'
        pact = random.choice(self.GILFOYLE_PACTS)
        self.gilfoyle_pact = pact
        self.event_text = f"{pact['setup']}\n\n{pact['pact_offer']}"
        self.event_options = [
            f"{i+1}: {c['text']}" for i, c in enumerate(pact['choices'])
        ]
        self.log(f"GILFOYLE: {pact['pact_offer'][:40]}...")

    def handle_gilfoyle_choice(self, choice):
        pact = getattr(self, 'gilfoyle_pact', None)
        if not pact or choice < 1 or choice > len(pact['choices']):
            return

        c = pact['choices'][choice - 1]
        result_parts = []

        # Apply equity cost
        if c['equity_cost'] > 0:
            self.equity = max(0, self.equity - c['equity_cost'])
            result_parts.append(f"-{c['equity_cost']} equity")

        # Apply traction gain if any
        if c.get('traction_gain', 0) > 0:
            self.traction += c['traction_gain']
            result_parts.append(f"+{c['traction_gain']} traction")

        # Apply runway (RNG or flat)
        if c.get('rng'):
            odds = 0.5 if 'runway_gain_good' in c else 0.5
            if random.random() < odds:
                gain = c['runway_gain_good']
                self.runway = min(100, max(0, self.runway + gain))
                result_parts.append(f"+{gain} runway (LUCKY!)")
                result_parts.append(f"Gilfoyle: {c['result_good']}")
                play_sound(SFX_WIN)
            else:
                gain = c['runway_gain_bad']
                self.runway = max(0, self.runway + gain)
                if gain != 0:
                    result_parts.append(f"{gain:+d} runway (CURSED)")
                else:
                    result_parts.append("0 runway gained. The void stares back.")
                result_parts.append(f"Gilfoyle: {c['result_bad']}")
                play_sound(SFX_DAMAGE)
        else:
            gain = c.get('runway_gain', 0)
            self.runway = min(100, max(0, self.runway + gain))
            if gain != 0:
                result_parts.append(f"{gain:+d} runway")
            result_parts.append(f"Gilfoyle: {c['result']}")
            if gain > 0:
                play_sound(SFX_WIN)
            elif gain < 0:
                play_sound(SFX_DAMAGE)

        self.event_result = "\n".join(result_parts)
        self.event_result_timer = 300  # slightly longer for Gilfoyle drama
        self.current_event = None
        self.log(self.event_result.split('\n')[0][:50])

    # ══════════════════════════════════════════════════════════════════
    # CYCLE / ROUND / Q&A SYSTEM
    # ══════════════════════════════════════════════════════════════════

    def _shuffle_questions(self):
        self.question_order = list(range(len(self.questions)))
        random.shuffle(self.question_order)
        self.question_pointer = 0

    def _load_next_question(self):
        if self.question_pointer >= len(self.question_order):
            self._shuffle_questions()
        idx = self.question_order[self.question_pointer]
        self.question_pointer += 1
        self.qa_current_question = self.questions[idx]
        self.qa_selected_answer = -1
        self.qa_answered = False
        self.qa_question_timer = QA_QUESTION_DURATION
        self.qa_result_text = ""
        self.qa_result_timer = 0

    def _answer_question(self, choice_index):
        if self.qa_answered or self.qa_current_question is None:
            return
        self.qa_answered = True
        self.qa_selected_answer = choice_index
        q = self.qa_current_question
        rewards = q.get("runway_rewards", [15, 10, 7, 4])
        points = rewards[choice_index] if choice_index < len(rewards) else 4
        self.qa_round_score += points
        self.runway = min(100, self.runway + points)
        # Rate the choice
        if points >= 15:
            label = "BEST MOVE!"
        elif points >= 10:
            label = "Good call!"
        elif points >= 7:
            label = "Fair choice."
        else:
            label = "Okay move."
        self.qa_result_text = f"{label} +{points} runway"
        self.qa_result_timer = QA_RESULT_DISPLAY
        play_sound(SFX_POWERUP if points >= 10 else SFX_EVENT)

    def _timeout_question(self):
        if self.qa_answered:
            return
        self.qa_answered = True
        self.qa_selected_answer = -1
        q = self.qa_current_question
        if q is None:
            return
        self.qa_result_text = "TIME'S UP! +0 runway (missed opportunity)"
        self.qa_result_timer = QA_RESULT_DISPLAY
        play_sound(SFX_DAMAGE)

    # ── Side-Scrolling Platformer during Q&A ──

    def _spawn_qa_obstacle(self):
        """Spawn an obstacle from the right edge based on lane type"""
        # Weight selection: more collectibles early, more hazards later
        weights = []
        for ot in QA_OBSTACLE_TYPES:
            if ot['lane'] in ('collect_ground', 'collect_air'):
                weights.append(2)
            elif ot['lane'] == 'mid':
                weights.append(3)
            else:
                weights.append(4)
        obj_type = random.choices(QA_OBSTACLE_TYPES, weights=weights, k=1)[0]
        lane = obj_type['lane']

        obs = {
            'type': obj_type,
            'x': WIDTH + 20,
            'w': obj_type['w'],
            'h': obj_type['h'],
        }

        if lane == 'ground':
            obs['y'] = QA_GROUND_Y - obj_type['h']
        elif lane == 'overhead':
            obs['y'] = QA_GROUND_Y - 70
        elif lane == 'mid':
            obs['y'] = QA_GROUND_Y - random.randint(40, 80)
            obs['hp'] = obj_type.get('hp', 1)
        elif lane == 'collect_ground':
            obs['y'] = QA_GROUND_Y - obj_type['h']
        elif lane == 'collect_air':
            obs['y'] = QA_GROUND_Y - 90

        self.qa_obstacles.append(obs)
        # Decrease spawn interval (difficulty ramp)
        self.qa_spawn_interval = max(40, self.qa_spawn_interval - 1)

    def _update_qa_obstacles(self):
        """Move obstacles left, handle collisions with wagon and bullets"""
        # Wagon collision rect (adjusted for jump/duck)
        wagon_h = QA_WAGON_H_DUCK if self.qa_is_ducking else QA_WAGON_H_STAND
        wagon_top = self.qa_wagon_y - wagon_h
        wagon_rect = pygame.Rect(QA_WAGON_X - QA_WAGON_W // 2, wagon_top, QA_WAGON_W, wagon_h)

        for obs in self.qa_obstacles[:]:
            obs['x'] -= self.qa_scroll_speed
            obs_rect = pygame.Rect(obs['x'], obs['y'], obs['w'], obs['h'])
            lane = obs['type']['lane']

            # Bullet collisions with mid-lane enemies
            if lane == 'mid':
                for bul in self.qa_bullets[:]:
                    bul_rect = pygame.Rect(bul['x'], bul['y'], 12, 6)
                    if bul_rect.colliderect(obs_rect):
                        if bul in self.qa_bullets:
                            self.qa_bullets.remove(bul)
                        obs['hp'] -= 1
                        if obs['hp'] <= 0:
                            # Killed! Award kill_points
                            pts = obs['type'].get('kill_points', 2)
                            self.runway = max(0, min(100, self.runway + pts))
                            self._qa_popup(obs['x'], obs['y'], pts)
                            play_sound(SFX_ENEMY_DIE)
                            if obs in self.qa_obstacles:
                                self.qa_obstacles.remove(obs)
                        else:
                            play_sound(SFX_HUNT_HIT)
                        break

            # Check if obstacle still exists after bullet hits
            if obs not in self.qa_obstacles:
                continue

            # Wagon collision
            if obs_rect.colliderect(wagon_rect) and self.qa_invincible_timer <= 0:
                pts = obs['type']['points']
                if lane in ('collect_ground', 'collect_air'):
                    # Collectible: always good
                    self.runway = max(0, min(100, self.runway + pts))
                    self._qa_popup(obs['x'], obs['y'], pts)
                    play_sound(SFX_POWERUP)
                    if obs in self.qa_obstacles:
                        self.qa_obstacles.remove(obs)
                elif lane == 'ground':
                    # Ground obstacle: only hits if wagon is NOT jumping high enough
                    if self.qa_wagon_y > QA_GROUND_Y - 30:
                        self.runway = max(0, min(100, self.runway + pts))
                        self._qa_popup(obs['x'], obs['y'], pts)
                        self.qa_invincible_timer = 30
                        play_sound(SFX_DAMAGE)
                        if obs in self.qa_obstacles:
                            self.qa_obstacles.remove(obs)
                elif lane == 'overhead':
                    # Overhead: only hits if wagon is NOT ducking
                    if not self.qa_is_ducking:
                        self.runway = max(0, min(100, self.runway + pts))
                        self._qa_popup(obs['x'], obs['y'], pts)
                        self.qa_invincible_timer = 30
                        play_sound(SFX_DAMAGE)
                        if obs in self.qa_obstacles:
                            self.qa_obstacles.remove(obs)
                elif lane == 'mid':
                    # Mid enemy reached wagon
                    self.runway = max(0, min(100, self.runway + pts))
                    self._qa_popup(obs['x'], obs['y'], pts)
                    self.qa_invincible_timer = 30
                    play_sound(SFX_DAMAGE)
                    if obs in self.qa_obstacles:
                        self.qa_obstacles.remove(obs)

            # Remove if scrolled off left edge
            elif obs['x'] + obs['w'] < -20:
                if obs in self.qa_obstacles:
                    self.qa_obstacles.remove(obs)

        # Update bullets
        for bul in self.qa_bullets[:]:
            bul['x'] += QA_BULLET_SPEED
            if bul['x'] > WIDTH + 20:
                self.qa_bullets.remove(bul)

        # Update score popups
        for popup in self.qa_score_popups[:]:
            popup['timer'] -= 1
            popup['y'] -= 0.5
            if popup['timer'] <= 0:
                self.qa_score_popups.remove(popup)

        # Invincibility countdown
        if self.qa_invincible_timer > 0:
            self.qa_invincible_timer -= 1

    def _qa_popup(self, x, y, pts):
        """Add a score popup near the given position"""
        popup_x = max(10, min(WIDTH - 60, x))
        popup_y = max(10, min(HEIGHT - 30, y - 20))
        self.qa_score_popups.append({
            'x': popup_x, 'y': popup_y,
            'text': f"+{pts}" if pts > 0 else str(pts),
            'color': GREEN if pts > 0 else RED,
            'timer': 60,
        })

    def _qa_shoot(self):
        """Fire a bullet from wagon front"""
        if self.qa_bullet_cooldown > 0:
            return
        wagon_h = QA_WAGON_H_DUCK if self.qa_is_ducking else QA_WAGON_H_STAND
        bullet_y = self.qa_wagon_y - wagon_h // 2
        self.qa_bullets.append({
            'x': QA_WAGON_X + QA_WAGON_W // 2,
            'y': bullet_y,
        })
        self.qa_bullet_cooldown = QA_BULLET_COOLDOWN
        play_sound(SFX_SHOOT)

    def _draw_qa_background(self):
        """Draw 3-layer parallax scrolling background"""
        sx = self.qa_scroll_x

        # Sky gradient
        pygame.draw.rect(screen, (10, 20, 50), (0, 0, WIDTH, QA_GROUND_Y))

        # Far mountains (slow parallax)
        far_offset = int(sx * 0.3) % 300
        for i in range(-1, 5):
            mx = i * 300 - far_offset
            pygame.draw.polygon(screen, (40, 50, 70),
                                [(mx, QA_GROUND_Y), (mx + 150, QA_GROUND_Y - 120), (mx + 300, QA_GROUND_Y)])

        # Near hills (medium parallax)
        near_offset = int(sx * 0.6) % 200
        for i in range(-1, 7):
            hx = i * 200 - near_offset
            pygame.draw.polygon(screen, (30, 60, 30),
                                [(hx, QA_GROUND_Y), (hx + 100, QA_GROUND_Y - 60), (hx + 200, QA_GROUND_Y)])

        # Ground
        pygame.draw.rect(screen, (40, 80, 40), (0, QA_GROUND_Y, WIDTH, HEIGHT - QA_GROUND_Y))

        # Road markings (full parallax)
        road_offset = int(sx) % 80
        for i in range(-1, 12):
            rx = i * 80 - road_offset
            pygame.draw.rect(screen, (80, 80, 60), (rx, QA_GROUND_Y + 5, 40, 4))

    def _draw_qa_scene(self):
        """Draw the side-scrolling platformer scene (wagon, obstacles, bullets)"""
        # Draw wagon (lowrider)
        bounce = math.sin(self.bounce_time * 5 * math.pi) * 3
        wagon_draw_y = self.qa_wagon_y - 48  # Adjust for wagon sprite height
        # Flash during invincibility
        if self.qa_invincible_timer > 0 and self.qa_invincible_timer % 4 < 2:
            pass  # Skip drawing (flash effect)
        else:
            # If ducking, squish the wagon visually
            if self.qa_is_ducking:
                draw_lowrider_wagon(screen, QA_WAGON_X - 70, wagon_draw_y + 15, self.runway,
                                    self.wheel_angle, bounce * 0.5)
            else:
                draw_lowrider_wagon(screen, QA_WAGON_X - 70, wagon_draw_y, self.runway,
                                    self.wheel_angle, bounce)
            # Co-founders on wagon
            alive = [cf for cf in self.co_founders if cf["alive"]]
            for i, cf in enumerate(alive[:3]):
                cf_y = wagon_draw_y + 8 + (15 if self.qa_is_ducking else 0)
                pygame.draw.circle(screen, CYAN, (QA_WAGON_X - 30 + i * 20, int(cf_y + bounce)), 8)

        # Draw obstacles
        for obs in self.qa_obstacles:
            ot = obs['type']
            lane = ot['lane']
            ox, oy, ow, oh = obs['x'], obs['y'], obs['w'], obs['h']

            if lane == 'ground':
                # Red/magenta blocks on ground
                pygame.draw.rect(screen, ot['color'], (ox, oy, ow, oh))
                pygame.draw.rect(screen, WHITE, (ox, oy, ow, oh), 1)
            elif lane == 'overhead':
                # Purple/blue bars hanging from above
                pygame.draw.rect(screen, ot['color'], (ox, oy, ow, oh))
                pygame.draw.rect(screen, WHITE, (ox, oy, ow, oh), 1)
                # Hanging lines
                pygame.draw.line(screen, GRAY, (ox + ow // 4, oy), (ox + ow // 4, oy - 30), 2)
                pygame.draw.line(screen, GRAY, (ox + 3 * ow // 4, oy), (ox + 3 * ow // 4, oy - 30), 2)
            elif lane == 'mid':
                # Enemy with HP indicator
                pygame.draw.rect(screen, ot['color'], (ox, oy, ow, oh))
                pygame.draw.rect(screen, WHITE, (ox, oy, ow, oh), 2)
                # HP dots
                hp = obs.get('hp', 1)
                for h in range(hp):
                    pygame.draw.circle(screen, RED, (ox + ow // 2 + h * 8 - (hp - 1) * 4, oy - 6), 3)
            elif lane in ('collect_ground', 'collect_air'):
                # Green/yellow collectible with glow
                pygame.draw.rect(screen, ot['color'], (ox, oy, ow, oh))
                pygame.draw.rect(screen, WHITE, (ox, oy, ow, oh), 1)
                # Sparkle effect
                sparkle = int(self.bounce_time * 10) % 3
                if sparkle == 0:
                    pygame.draw.circle(screen, WHITE, (ox + ow // 2, oy - 4), 2)

            # Label
            label = small_font.render(ot['emoji'], True, WHITE)
            screen.blit(label, (ox + ow // 2 - label.get_width() // 2,
                                oy + oh // 2 - label.get_height() // 2))

        # Draw bullets
        for bul in self.qa_bullets:
            pygame.draw.rect(screen, YELLOW, (bul['x'], bul['y'] - 3, 12, 6))
            pygame.draw.rect(screen, WHITE, (bul['x'] + 10, bul['y'] - 1, 4, 2))

        # Draw score popups
        for popup in self.qa_score_popups:
            popup_surf = font.render(popup['text'], True, popup['color'])
            screen.blit(popup_surf, (popup['x'], int(popup['y'])))

    # ── Cycle Orchestration ──

    def start_new_cycle(self):
        self.round_in_cycle = 0
        self.cycle_number += 1
        self.log(f"--- CYCLE {self.cycle_number} BEGIN ---")
        self.start_qa_phase()

    def start_qa_phase(self):
        self.state = 10
        self.cycle_phase = "qa"
        self.qa_timer = QA_PHASE_DURATION
        self.qa_question_index = 0
        self.qa_question_timer = QA_QUESTION_DURATION
        self.qa_round_score = 0
        self.qa_selected_answer = -1
        self.qa_answered = False
        self.qa_result_text = ""
        self.qa_result_timer = 0
        # Platformer state
        self.qa_wagon_y = QA_GROUND_Y
        self.qa_wagon_vy = 0
        self.qa_is_jumping = False
        self.qa_is_ducking = False
        self.qa_scroll_speed = QA_SCROLL_SPEED
        self.qa_scroll_x = 0
        self.qa_obstacles = []
        self.qa_bullets = []
        self.qa_bullet_cooldown = 0
        self.qa_obstacle_spawn_timer = 0
        self.qa_spawn_interval = 80
        self.qa_invincible_timer = 0
        self.qa_score_popups = []
        self.round_transition_timer = 0
        self._load_next_question()
        self.log(f"Round {self.round_in_cycle + 1}/{ROUNDS_PER_CYCLE} - Q&A Phase!")
        play_sound(SFX_EVENT)

    def end_qa_phase(self):
        self.log(f"Q&A complete! Score: {self.qa_round_score:+d} runway")
        self.round_transition_timer = QA_TRANSITION_PAUSE
        self.round_transition_text = (
            f"Q&A Round {self.round_in_cycle + 1} complete! "
            f"{'+'if self.qa_round_score >= 0 else ''}{self.qa_round_score} runway. "
            f"Trail time!"
        )

    def start_trail_phase(self):
        self.state = 1
        self.cycle_phase = "trail"
        self.trail_round_active = True
        self.trail_round_timer = random.randint(TRAIL_ROUND_MIN_SECONDS, TRAIL_ROUND_MAX_SECONDS) * 60
        self.log(f"Trail phase - Round {self.round_in_cycle + 1}/{ROUNDS_PER_CYCLE}")

    def end_trail_phase(self):
        self.trail_round_active = False
        self.round_in_cycle += 1
        if self.distance >= 2000:
            self.log("Trail complete! Final bonus time!")
            self.start_final_bonus()
            return
        if self.round_in_cycle >= ROUNDS_PER_CYCLE:
            self.start_cycle_arcade()
        else:
            self.start_qa_phase()

    def start_cycle_arcade(self):
        arcade_type = self.arcade_rotation[self.arcade_rotation_index % len(self.arcade_rotation)]
        self.arcade_rotation_index += 1
        self.log(f"ARCADE BONUS! Playing: {arcade_type.upper()}")

        if arcade_type == "hunt":
            self.cycle_arcade_active = True
            self.start_hunt()
        elif arcade_type == "boss":
            self.state = 11
            self.bonus_type = 'boss'
            self.cycle_arcade_active = True
            self.start_boss_battle()
        else:
            self.state = 11
            self.bonus_type = arcade_type
            self.bonus_timer = random.randint(45, 60) * 60
            self.bonus_score = 0
            self.bonus_max_score = 100
            self.player_x = WIDTH // 2
            self.player_y = HEIGHT - 80
            self.player_rect = pygame.Rect(self.player_x - 25, self.player_y - 25, 50, 50)
            self.bullets = []
            self.enemies = []
            self.obstacles = []
            self.enemy_spawn_timer = 0
            self.scroll_x = 0
            self.cycle_arcade_active = True
        play_sound(SFX_EVENT)

    def end_cycle_arcade(self):
        runway_bonus = 15 + (self.bonus_score * 3)
        runway_bonus = min(60, runway_bonus)
        if self.bonus_score >= self.bonus_max_score * 0.7:
            runway_bonus += 25
            self.log(f"HIGH SCORE! +25 bonus runway!")
        self.runway = min(100, self.runway + runway_bonus)
        self.log(f"Arcade bonus: +{runway_bonus} runway")
        self.cycle_arcade_active = False
        if self.runway <= 0 or self.equity <= 0:
            pass  # Loss handled in update
        else:
            self.start_new_cycle()
        play_sound(SFX_POWERUP)

    def update_qa(self):
        """Update Q&A phase (state 10) - side-scrolling platformer"""
        # Handle transition pause
        if self.round_transition_timer > 0:
            self.round_transition_timer -= 1
            if self.round_transition_timer <= 0:
                self.start_trail_phase()
            return

        # Loss check
        if self.runway <= 0:
            self.state = 6
            self.death_quote = "Too many wrong answers. Runway depleted during Q&A."
            play_sound(SFX_LOSE)
            return

        # Main 20-second timer
        self.qa_timer -= 1

        # ── Jump / Duck / Gravity physics ──
        keys = pygame.key.get_pressed()

        # Jump (only if on ground)
        if (keys[pygame.K_UP] or keys[pygame.K_w] or self.touch_up) and not self.qa_is_jumping:
            self.qa_wagon_vy = QA_JUMP_VEL
            self.qa_is_jumping = True

        # Duck (only on ground)
        self.qa_is_ducking = (keys[pygame.K_DOWN] or keys[pygame.K_s] or self.touch_down) and not self.qa_is_jumping

        # Apply gravity
        self.qa_wagon_vy += QA_GRAVITY
        self.qa_wagon_y += self.qa_wagon_vy

        # Ground collision
        if self.qa_wagon_y >= QA_GROUND_Y:
            self.qa_wagon_y = QA_GROUND_Y
            self.qa_wagon_vy = 0
            self.qa_is_jumping = False

        # ── Scroll speed ramp ──
        self.qa_scroll_speed += 0.003
        self.qa_scroll_x += self.qa_scroll_speed

        # ── Spawn obstacles ──
        self.qa_obstacle_spawn_timer += 1
        if self.qa_obstacle_spawn_timer >= self.qa_spawn_interval:
            self._spawn_qa_obstacle()
            self.qa_obstacle_spawn_timer = 0

        # ── Bullet cooldown ──
        if self.qa_bullet_cooldown > 0:
            self.qa_bullet_cooldown -= 1

        # ── Update obstacles + bullets + collisions ──
        self._update_qa_obstacles()

        # If showing result feedback, count down
        if self.qa_result_timer > 0:
            self.qa_result_timer -= 1
            if self.qa_result_timer <= 0 and self.qa_timer > 60:
                self.qa_question_index += 1
                if self.qa_question_index < QA_QUESTIONS_PER_ROUND:
                    self._load_next_question()
            return

        # Per-question 5-second timer
        if self.qa_current_question and not self.qa_answered:
            self.qa_question_timer -= 1
            if self.qa_question_timer <= 0:
                self._timeout_question()

        # Overall 20 seconds expired
        if self.qa_timer <= 0:
            if not self.qa_answered and self.qa_current_question:
                self._timeout_question()
            self.end_qa_phase()

    def draw_qa(self):
        """Draw Q&A phase with side-scrolling platformer and question overlay"""
        screen.fill(BLACK)

        # Parallax scrolling background
        self._draw_qa_background()

        # Draw platformer scene (wagon, obstacles, bullets)
        self._draw_qa_scene()

        # ── Top HUD ──
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, 95))
        screen.blit(font.render(
            f"Cycle {self.cycle_number} | Round {self.round_in_cycle + 1}/{ROUNDS_PER_CYCLE} | Q&A",
            True, YELLOW), (10, 5))

        # 20-second timer bar
        qa_progress = max(0, self.qa_timer / QA_PHASE_DURATION)
        bar_color = GREEN if qa_progress > 0.3 else YELLOW if qa_progress > 0.15 else RED
        pygame.draw.rect(screen, GRAY, (10, 30, 300, 16), 2)
        pygame.draw.rect(screen, bar_color, (12, 32, int(296 * qa_progress), 12))
        secs_left = max(0, self.qa_timer // 60)
        screen.blit(small_font.render(f"Time: {secs_left}s", True, WHITE), (320, 30))

        runway_color = WHITE if self.runway > 20 else RED
        screen.blit(font.render(f"Runway: {int(self.runway)}%", True, runway_color), (10, 55))
        screen.blit(font.render(f"Stake: {self.equity}%", True, WHITE), (200, 55))
        score_color = GREEN if self.qa_round_score >= 0 else RED
        screen.blit(font.render(f"Q Score: {self.qa_round_score:+d}", True, score_color), (400, 55))
        screen.blit(font.render(f"Q {self.qa_question_index + 1}/{QA_QUESTIONS_PER_ROUND}", True, CYAN), (600, 55))
        screen.blit(small_font.render("JUMP/DUCK/SHOOT + 1-4: Answer", True, ORANGE), (10, 78))

        # ── Transition screen ──
        if self.round_transition_timer > 0:
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(180)
            overlay.fill(BLACK)
            screen.blit(overlay, (0, 0))
            title_surf = big_font.render("ROUND COMPLETE!", True, YELLOW)
            screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, HEIGHT // 2 - 50))
            detail_surf = font.render(self.round_transition_text, True, WHITE)
            screen.blit(detail_surf, (WIDTH // 2 - detail_surf.get_width() // 2, HEIGHT // 2 + 20))
            return

        # ── Question Card ──
        if self.qa_current_question and self.qa_question_index < QA_QUESTIONS_PER_ROUND:
            q = self.qa_current_question
            card_y = 100
            card_h = 165
            pygame.draw.rect(screen, (0, 0, 0, 200), (40, card_y, WIDTH - 80, card_h))
            pygame.draw.rect(screen, CYAN, (40, card_y, WIDTH - 80, card_h), 2)

            # Per-question timer bar
            q_progress = max(0, self.qa_question_timer / QA_QUESTION_DURATION)
            q_bar_color = WHITE if q_progress > 0.4 else YELLOW if q_progress > 0.2 else RED
            pygame.draw.rect(screen, GRAY, (60, card_y + 5, WIDTH - 120, 8), 1)
            pygame.draw.rect(screen, q_bar_color, (61, card_y + 6, int((WIDTH - 122) * q_progress), 6))

            # Question text (word wrap - compact)
            words = q["question"].split()
            lines = []
            current_line = ""
            for word in words:
                test = (current_line + " " + word).strip()
                if len(test) > 75:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
                else:
                    current_line = test
            if current_line:
                lines.append(current_line)

            for i, line in enumerate(lines[:2]):
                screen.blit(small_font.render(line, True, WHITE), (60, card_y + 16 + i * 16))

            # Answer options (graduated rewards, compact)
            choice_y = card_y + 52
            rewards = q.get("runway_rewards", [15, 10, 7, 4])
            options = q.get("options", q.get("choices", []))
            for i, option in enumerate(options):
                if self.qa_answered:
                    if i == self.qa_selected_answer:
                        color = GREEN if rewards[i] >= 10 else YELLOW
                    else:
                        color = GRAY
                else:
                    color = WHITE
                label = f"[{i+1}] {option}"
                if len(label) > 65:
                    label = label[:62] + "..."
                screen.blit(small_font.render(label, True, color), (55, choice_y + i * 24))

            # Result feedback
            if self.qa_result_text:
                if "BEST" in self.qa_result_text:
                    result_color = GREEN
                elif "Good" in self.qa_result_text:
                    result_color = CYAN
                elif "TIME" in self.qa_result_text:
                    result_color = RED
                else:
                    result_color = YELLOW
                result_surf = small_font.render(self.qa_result_text, True, result_color)
                screen.blit(result_surf, (WIDTH // 2 - result_surf.get_width() // 2, card_y + card_h - 18))

            if not self.qa_answered:
                inst = small_font.render("Press 1-4 to answer!", True, YELLOW)
                screen.blit(inst, (WIDTH // 2 - inst.get_width() // 2, card_y + card_h - 14))

        # Draw score popups on top of everything
        for popup in self.qa_score_popups:
            popup_surf = font.render(popup['text'], True, popup['color'])
            screen.blit(popup_surf, (popup['x'], int(popup['y'])))

    # ══════════════════════════════════════════════════════════════════
    # MAIN UPDATE LOOP
    # ══════════════════════════════════════════════════════════════════

    def update(self):
        # Runtime bounds clamp (anti-cheat)
        self.runway = max(0, min(100, self.runway))
        self.equity = max(0, min(100, self.equity))
        self.traction = max(0, self.traction)

        # Lowrider wagon animation (runs in all states)
        self.wheel_angle += 0.15
        self.bounce_time += 1.0 / 60.0

        if self.state == 1:
            if self.paused:
                self.pause_timer -= 1
                if self.pause_timer <= 0:
                    self.paused = False
                return
            
            if self.remedy_active and self.remedy_timer > 0:
                self.remedy_timer -= 1
                self.equity = min(100, self.equity + 0.3)
                if self.remedy_timer <= 0:
                    self.remedy_active = False
                    self.selected_remedy = ""
                return
            
            if self.event_result_timer > 0:
                self.event_result_timer -= 1
                if self.event_result_timer <= 0:
                    self.event_result = None
                return
            
            if self.current_event:
                if self.current_event == 'tweet':
                    self.update_tweet_event()
                return

            if self.remedy_active and self.remedy_timer == 0:
                return
            
            self.distance += self.get_pace_speed()
            self.runway -= self.get_pace_drain()
            
            if random.random() < 0.002:
                self.current_quote = random.choice(self.sv_quotes)
                self.quote_timer = 150
            
            if self.quote_timer > 0:
                self.quote_timer -= 1
                if self.quote_timer <= 0:
                    self.current_quote = None
            
            # Event and trigger logic depends on whether we're in a cycle round
            if self.trail_round_active:
                # During cycle rounds, suppress auto-hunt and distance win
                self.event_timer += 1
                if self.event_timer >= self.next_event_at:
                    self.trigger_random_event()
                    self.event_timer = 0
                    self.next_event_at = random.randint(800, 1500)

                if self.equity <= self.remedy_threshold and not self.remedy_active:
                    self.trigger_remedy()

                # Trail round timer
                self.trail_round_timer -= 1
                if self.trail_round_timer <= 0:
                    if (not self.current_event and
                        not self.remedy_active and
                        not self.event_result and
                        self.event_result_timer <= 0):
                        self.end_trail_phase()
                        return
            else:
                # HUNTING TRIGGER (only outside cycle rounds)
                distance_since_hunt = self.distance - self.hunt_distance_trigger
                low_traction = self.traction < 20 and self.distance > 200

                if distance_since_hunt >= self.hunt_next_at or (low_traction and distance_since_hunt > 500):
                    self.start_hunt()
                    return

                self.event_timer += 1
                if self.event_timer >= self.next_event_at:
                    self.trigger_random_event()
                    self.event_timer = 0
                    self.next_event_at = random.randint(800, 1500)

                if self.equity <= self.remedy_threshold and not self.remedy_active:
                    self.trigger_remedy()

                if self.distance >= 2000:
                    self.log("Trail complete! Final bonus time!")
                    self.start_final_bonus()
                    return

            alive_count = sum(1 for cf in self.co_founders if cf["alive"])

            if self.runway <= 0:
                self.state = 6
                self.death_quote = random.choice([
                    "Out of runway. Out of luck.\nEric Bahn: Hustle Fund passed. Skill issue.",
                    "Burned through it all.\nJian-Yang: You blew it, mister.",
                    "The money's gone.\nVC: Let me intro you to my partner. JK passing.",
                ])
                play_sound(SFX_LOSE)
            elif self.equity <= 0:
                self.state = 6
                self.death_quote = random.choice([
                    "Diluted to zero.\nYou own nothing. Congrats, employee #47.",
                    "Equity evaporated.\nWired Founder: HOW LIKELY to succeed? NOT AT ALL!",
                ])
                play_sound(SFX_LOSE)
            elif alive_count == 0:
                self.state = 6
                self.death_quote = (
                    "All co-founders gone.\n"
                    "Solo founder life isn't for everyone.\n"
                    "Jian-Yang: I am your mom. You are not my baby startup."
                )
                play_sound(SFX_LOSE)

        elif self.state == 10:
            self.update_qa()

        elif self.state == 3:
            self.update_hunt()

        elif self.state == 11:
            if self.bonus_type == 'boss':
                self.update_boss_battle()
            else:
                self.bonus_timer -= 1
                if self.bonus_type == 'galaga':
                    self.update_bonus_galaga()
                elif self.bonus_type == 'mario':
                    self.update_bonus_mario()
                elif self.bonus_type == 'frogger':
                    self.update_bonus_frogger()
                if self.bonus_timer <= 0 or self.equity <= 0:
                    self.end_cycle_arcade()

        elif self.state == 2:
            self.bonus_timer -= 1

            if self.bonus_type == 'galaga':
                self.update_bonus_galaga()
            elif self.bonus_type == 'mario':
                self.update_bonus_mario()
            elif self.bonus_type == 'frogger':
                self.update_bonus_frogger()

            if self.bonus_timer <= 0 or self.equity <= 0:
                self.end_final_bonus()

    # ══════════════════════════════════════════════════════════════════
    # DRAW FUNCTIONS
    # ══════════════════════════════════════════════════════════════════
    
    def draw(self):
        screen.fill(BLACK)
        
        if self.state == -1:
            self.draw_onboarding()
            return
        
        if self.state == 0:
            self.draw_title()
            return
        
        if self.state == 10:
            self.draw_qa()
            return

        if self.state == 1:
            self.draw_trail()
            return

        if self.state == 3:
            self.draw_hunt()
            return

        if self.state == 11:
            if self.bonus_type == 'boss':
                self.draw_boss_battle()
            else:
                self.draw_bonus()
            return

        if self.state == 2:
            self.draw_bonus()
            return
        
        if self.state == 5:
            self.draw_win()
            return
        
        if self.state == 6:
            self.draw_lose()
            return
    
    def draw_onboarding(self):
        title = big_font.render("Founder Onboarding", True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 40))
        
        prompts = [
            ("Company Name:", self.company_name),
            ("Problem (one sentence):", self.problem),
            ("Solution (one sentence):", self.solution),
            ("Warm intro to VC? (Y/N)", "Yes" if self.warm_intro else ("No" if self.onboarding_step > 3 else "")),
            ("Elite college? (Y/N)", "Yes" if self.elite_college else ("No" if self.onboarding_step > 4 else "")),
            ("Funding Path:", "")
        ]
        
        y = 120
        for i, (label, value) in enumerate(prompts):
            color = CYAN if i == self.onboarding_step else WHITE
            screen.blit(font.render(label, True, color), (60, y))
            if value:
                screen.blit(font.render(value, True, GREEN), (400, y))
            y += 50
        
        if self.onboarding_step < 3:
            mobile_defaults = ["Disrupt.ai", "Everything is broken", "AI fixes it (somehow)"]
            if self.is_touch and not self.input_text:
                # Show placeholder on mobile
                screen.blit(font.render(mobile_defaults[self.onboarding_step], True, GRAY), (400, 120 + self.onboarding_step * 50))
                screen.blit(small_font.render("Tap NEXT to accept", True, YELLOW), (400, 120 + self.onboarding_step * 50 + 25))
            else:
                cursor = "|" if pygame.time.get_ticks() % 1000 < 500 else ""
                screen.blit(font.render(self.input_text + cursor, True, GREEN), (400, 120 + self.onboarding_step * 50))
        elif self.onboarding_step in (3, 4):
            if self.is_touch:
                pass  # Y/N buttons drawn by touch UI
            else:
                screen.blit(font.render("Press Y / N", True, YELLOW), (60, y + 10))
        elif self.onboarding_step == 5:
            if not self.is_touch:
                screen.blit(font.render("1 → Bootstrap (secret ending)", True, GREEN), (80, y + 10))
                screen.blit(font.render("2 → Seek VC Funding (start the trail!)", True, CYAN), (80, y + 45))
    
    def draw_title(self):
        title = big_font.render("HUSTLE TRAIL", True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 60))
        
        tagline = font.render("Startup Odyssey × Tech Startup × Silicon Valley", True, ORANGE)
        screen.blit(tagline, (WIDTH//2 - tagline.get_width()//2, 120))
        
        subtitle = font.render("0 to 1: Survive the trail. Find your first customer.", True, WHITE)
        screen.blit(subtitle, (WIDTH//2 - subtitle.get_width()//2, 160))
        
        rules = small_font.render("There are a lot of rules. Good luck figuring them out. :)", True, MAGENTA)
        screen.blit(rules, (WIDTH//2 - rules.get_width()//2, 200))
        
        hunt_text = small_font.render("NEW: 🎯 Hunt for funding! Shoot rug pulls & bad code!", True, YELLOW)
        screen.blit(hunt_text, (WIDTH//2 - hunt_text.get_width()//2, 230))
        
        if getattr(self, 'has_saved_profile', False) and self.company_name:
            pygame.draw.rect(screen, (30, 30, 60), (100, 270, WIDTH - 200, 100))
            pygame.draw.rect(screen, CYAN, (100, 270, WIDTH - 200, 100), 2)
            screen.blit(font.render(f"Welcome back, {self.company_name}!", True, CYAN), (120, 285))
            screen.blit(font.render("SPACE → Continue | N → New Company", True, GREEN), (120, 325))
        else:
            screen.blit(font.render("SPACE to Start New Company", True, GREEN), (WIDTH//2 - 120, 300))
        
        credits = small_font.render("Inspired by Eric Bahn, Hustle Fund, and HBO's Silicon Valley", True, WHITE)
        screen.blit(credits, (WIDTH//2 - credits.get_width()//2, 520))
    
    def draw_trail(self):
        """Draw main trail screen - startup odyssey style"""
        pygame.draw.rect(screen, (20, 60, 20), (0, 400, WIDTH, 200))
        pygame.draw.rect(screen, (10, 30, 60), (0, 0, WIDTH, 400))
        
        for i in range(5):
            x = (i * 200 - int(self.distance) % 200)
            pygame.draw.polygon(screen, (60, 60, 80), [(x, 400), (x + 100, 200), (x + 200, 400)])
        
        # Lowrider startup wagon (auto-moving)
        startup_vehicle_x = 100 + (int(self.distance) % 50)
        bounce = math.sin(self.bounce_time * 5 * math.pi) * 4
        draw_lowrider_wagon(screen, startup_vehicle_x - 30, 370, self.runway,
                            self.wheel_angle, bounce)
        # Co-founders on wagon cover
        alive = [cf for cf in self.co_founders if cf["alive"]]
        for i, cf in enumerate(alive[:3]):
            pygame.draw.circle(screen, CYAN, (startup_vehicle_x + 10 + i * 20, 378 + int(bounce)), 8)
        
        pygame.draw.rect(screen, (0, 0, 0, 180), (0, 0, WIDTH, 80))
        
        progress = min(1, self.distance / 2000)
        pygame.draw.rect(screen, GRAY, (150, 15, 500, 20), 2)
        pygame.draw.rect(screen, GREEN, (152, 17, int(496 * progress), 16))
        screen.blit(small_font.render(f"Traction Miles: {int(self.distance)}/2000", True, WHITE), (10, 15))
        screen.blit(small_font.render(self.get_trail_segment_display(), True, YELLOW), (660, 15))
        
        runway_color = WHITE if self.runway > 20 else RED
        equity_color = WHITE if self.equity > 20 else RED
        screen.blit(font.render(f"Runway: {int(self.runway)}%", True, runway_color), (10, 45))
        stake_emoji = ":)" if self.equity >= 90 else ":("
        screen.blit(font.render(f"Stake: {self.equity}% {stake_emoji}", True, equity_color), (180, 45))
        screen.blit(font.render(f"Traction: {self.traction}", True, WHITE), (380, 45))
        
        alive_count = sum(1 for cf in self.co_founders if cf["alive"])
        cf_color = WHITE if alive_count > 1 else RED
        screen.blit(font.render(f"Team: {alive_count}/3", True, cf_color), (550, 45))
        
        pace_names = {1: "Steady", 2: "Strenuous", 3: "Grueling"}
        screen.blit(small_font.render(f"Pace: {pace_names.get(self.pace, 'Steady')} [1-3] | H: Hunt", True, ORANGE), (10, 75))
        
        if self.current_event:
            if self.current_event == 'tweet':
                self.draw_tweet_overlay()
            else:
                self.draw_event_overlay()
        elif self.remedy_active:
            self.draw_remedy_overlay()
        elif self.event_result:
            pygame.draw.rect(screen, BLACK, (50, 150, WIDTH - 100, 100))
            pygame.draw.rect(screen, YELLOW, (50, 150, WIDTH - 100, 100), 3)
            lines = self.event_result.split('\n')
            for i, line in enumerate(lines):
                color = RED if "💀" in line else GREEN if "🎉" in line or "🎯" in line else YELLOW
                screen.blit(font.render(line, True, color), (70, 165 + i * 25))
        
        if self.paused:
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(180)
            overlay.fill(BLACK)
            screen.blit(overlay, (0, 0))
            screen.blit(big_font.render("PAUSED", True, YELLOW), (WIDTH//2 - 80, HEIGHT//2 - 30))
            screen.blit(font.render(f"Resuming in {self.pause_timer // 60 + 1}s...", True, WHITE), (WIDTH//2 - 80, HEIGHT//2 + 30))
        
        if self.current_quote and self.quote_timer > 0:
            quote_surf = font.render(self.current_quote[:60], True, YELLOW)
            pygame.draw.rect(screen, BLACK, (45, HEIGHT - 55, quote_surf.get_width() + 10, 30))
            pygame.draw.rect(screen, YELLOW, (45, HEIGHT - 55, quote_surf.get_width() + 10, 30), 2)
            screen.blit(quote_surf, (50, HEIGHT - 50))
        
        log_y = HEIGHT - 120
        for msg in self.log_messages[-3:]:
            screen.blit(small_font.render(msg[:70], True, CYAN), (10, log_y))
            log_y += 18
    
    def draw_event_overlay(self):
        pygame.draw.rect(screen, BLACK, (30, 120, WIDTH - 60, 280))
        pygame.draw.rect(screen, YELLOW, (30, 120, WIDTH - 60, 280), 3)
        
        title_color = BLUE if self.current_event == 'river' else ORANGE if self.current_event == 'breakdown' else MAGENTA if self.current_event == 'dilemma' else YELLOW
        screen.blit(font.render(f"⚡ {self.current_event.upper()} EVENT", True, title_color), (50, 135))
        
        lines = self.event_text.split('\n') if self.event_text else [""]
        for i, line in enumerate(lines):
            screen.blit(font.render(line, True, WHITE), (50, 170 + i * 25))
        
        y = 230
        for i, opt in enumerate(self.event_options):
            color = GREEN if i == 0 else CYAN if i == 1 else ORANGE if i == 2 else MAGENTA
            screen.blit(font.render(opt, True, color), (60, y))
            y += 35
        
        screen.blit(small_font.render("Press 1-4 to choose", True, GRAY), (50, 370))
    
    def draw_remedy_overlay(self):
        pygame.draw.rect(screen, (30, 0, 30), (30, 100, WIDTH - 60, 350))
        pygame.draw.rect(screen, MAGENTA, (30, 100, WIDTH - 60, 350), 3)
        
        if self.remedy_timer == 0:
            screen.blit(big_font.render("💔 FIVE REMEDIES", True, MAGENTA), (WIDTH//2 - 150, 115))
            screen.blit(font.render(self.remedy_text, True, YELLOW), (50, 170))
            
            for i, opt in enumerate(self.remedy_options):
                color = GREEN if i % 2 == 0 else CYAN
                screen.blit(font.render(opt, True, color), (60, 210 + i * 35))
            
            screen.blit(small_font.render("Press 1-5 to choose", True, GRAY), (50, 400))
        else:
            progress = 1 - (self.remedy_timer / 360)
            bar_width = int(600 * progress)
            
            screen.blit(big_font.render(f"🧘 {self.selected_remedy}...", True, MAGENTA), (WIDTH//2 - 150, 200))
            pygame.draw.rect(screen, WHITE, (100, 280, 600, 30), 2)
            pygame.draw.rect(screen, MAGENTA, (102, 282, bar_width, 26))
            screen.blit(font.render(f"Restoring equity... {self.remedy_timer//60 + 1}s", True, WHITE), (WIDTH//2 - 100, 330))
    
    def draw_bonus(self):
        for i in range(50):
            x = (i * 73 + self.scroll_x) % WIDTH
            y = (i * 47) % HEIGHT
            pygame.draw.circle(screen, WHITE, (int(x), int(y)), 1)
        
        bonus_names = {
            'galaga': "SHOOT THE REJECTIONS!",
            'mario': "PLATFORM PIVOT!",
            'frogger': "DODGE THE COMPETITION!"
        }
        
        title = big_font.render(f"🎮 {bonus_names.get(self.bonus_type, 'FINAL BONUS')}", True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 10))
        
        secs = self.bonus_timer // 60
        timer_text = font.render(f"Time: {secs}s | Score: {self.bonus_score}", True, WHITE)
        screen.blit(timer_text, (WIDTH//2 - 80, 60))
        
        pygame.draw.rect(screen, BROWN, self.player_rect)
        pygame.draw.rect(screen, WHITE, self.player_rect, 2)
        
        if self.bonus_type == 'galaga':
            for b in self.bullets:
                pygame.draw.rect(screen, GREEN, b['rect'])
            for e in self.enemies:
                pygame.draw.rect(screen, RED, e['rect'])
                screen.blit(small_font.render(e['type'][:6], True, WHITE), (e['rect'].x, e['rect'].y + 10))
            screen.blit(small_font.render("A/D to move, SPACE to shoot!", True, CYAN), (10, HEIGHT - 30))
        
        elif self.bonus_type == 'mario':
            for p in self.platforms:
                px = p.x + self.scroll_x
                if -200 < px < WIDTH + 200:
                    pygame.draw.rect(screen, BLUE, (px, p.y, p.width, p.height))
            screen.blit(small_font.render("A/D to move, W to jump! Go right!", True, CYAN), (10, HEIGHT - 30))
        
        elif self.bonus_type == 'frogger':
            pygame.draw.rect(screen, GREEN, (WIDTH//2 - 50, 20, 100, 40))
            screen.blit(font.render("GOAL", True, BLACK), (WIDTH//2 - 25, 30))
            for o in self.obstacles:
                pygame.draw.rect(screen, RED, o['rect'])
            screen.blit(small_font.render("WASD to move! Reach the top!", True, CYAN), (10, HEIGHT - 30))
        
        pygame.draw.rect(screen, GRAY, (10, 90, 200, 20), 2)
        pygame.draw.rect(screen, GREEN if self.equity > 20 else RED, (12, 92, int(196 * self.equity / 100), 16))
        screen.blit(small_font.render(f"Equity: {self.equity}%", True, WHITE), (220, 90))
    
    def draw_win(self):
        pygame.draw.rect(screen, BLACK, (50, 100, WIDTH - 100, 400))
        pygame.draw.rect(screen, GREEN, (50, 100, WIDTH - 100, 400), 4)
        
        screen.blit(big_font.render("🎉 FIRST CUSTOMER!", True, GREEN), (WIDTH//2 - 180, 130))
        screen.blit(font.render("0 → 1 ACHIEVED", True, YELLOW), (WIDTH//2 - 70, 190))
        
        screen.blit(font.render(f"Company: {self.company_name}", True, WHITE), (80, 240))
        screen.blit(font.render(f"Traction Miles: {int(self.distance)}", True, WHITE), (80, 270))
        screen.blit(font.render(f"Runway: {int(self.runway)}% | Equity: {self.equity}%", True, WHITE), (80, 300))
        screen.blit(font.render(f"Traction: {self.traction} | Followers: {self.followers}", True, WHITE), (80, 330))
        
        alive = sum(1 for cf in self.co_founders if cf["alive"])
        cf_names = ", ".join(cf["name"] for cf in self.co_founders if cf["alive"])
        screen.blit(font.render(f"Surviving team ({alive}/3): {cf_names}", True, CYAN), (80, 360))
        
        screen.blit(font.render("Check console for shareable stats!", True, YELLOW), (80, 410))
        screen.blit(font.render("SPACE to play again", True, GREEN), (WIDTH//2 - 100, 460))
    
    def draw_lose(self):
        pygame.draw.rect(screen, BLACK, (50, 100, WIDTH - 100, 400))
        
        is_bootstrap = "bootstrapped" in str(self.death_quote).lower() if self.death_quote else False
        border_color = GREEN if is_bootstrap else RED
        pygame.draw.rect(screen, border_color, (50, 100, WIDTH - 100, 400), 4)
        
        title = "💀 GAME OVER" if not is_bootstrap else "🏆 SECRET ENDING"
        screen.blit(big_font.render(title, True, border_color), (WIDTH//2 - 150, 130))
        
        if self.death_quote:
            lines = self.death_quote.split('\n')
            y = 200
            for line in lines:
                color = GREEN if "TRUE ENDING" in line or "Quiet Wealth" in line else YELLOW
                screen.blit(font.render(line, True, color), (80, y))
                y += 30
        
        screen.blit(font.render(f"Traction Miles traveled: {int(self.distance)}", True, WHITE), (80, 380))
        screen.blit(font.render("SPACE to try again", True, GREEN), (WIDTH//2 - 100, 450))

    # ══════════════════════════════════════════════════════════════════
    # EVENT HANDLING
    # ══════════════════════════════════════════════════════════════════
    
    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        
        key = event.key
        
        if self.state == -1:
            if self.input_active:
                if key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                elif key == pygame.K_RETURN:
                    mobile_defaults = ["Disrupt.ai", "Everything is broken", "AI fixes it (somehow)"]
                    if self.onboarding_step == 0:
                        fallback = mobile_defaults[0] if self.is_touch else "Unnamed Startup"
                        self.company_name = sanitize_input(self.input_text.strip() or fallback, 50)
                    elif self.onboarding_step == 1:
                        fallback = mobile_defaults[1] if self.is_touch else "Everything is broken"
                        self.problem = sanitize_input(self.input_text.strip() or fallback, 100)
                    elif self.onboarding_step == 2:
                        fallback = mobile_defaults[2] if self.is_touch else "AI-powered solution"
                        self.solution = sanitize_input(self.input_text.strip() or fallback, 100)
                    self.input_text = ""
                    self.onboarding_step += 1
                    if self.onboarding_step >= 3:
                        self.input_active = False
                elif event.unicode and len(self.input_text) < 50:
                    self.input_text += event.unicode
            
            if self.onboarding_step == 3:
                if key == pygame.K_y:
                    self.warm_intro = True
                    self.onboarding_step += 1
                elif key == pygame.K_n:
                    self.onboarding_step += 1
            elif self.onboarding_step == 4:
                if key == pygame.K_y:
                    self.elite_college = True
                    self.onboarding_step += 1
                elif key == pygame.K_n:
                    self.onboarding_step += 1
            elif self.onboarding_step == 5:
                if key == pygame.K_1:
                    self.save_profile()
                    self.bootstrap_ending()
                elif key == pygame.K_2:
                    self.save_profile()
                    self.log(f"🚀 {self.company_name} begins the Hustle Trail!")
                    play_sound(SFX_EVENT)
                    self.start_new_cycle()
        
        elif self.state == 0:
            if key == pygame.K_SPACE:
                if getattr(self, 'has_saved_profile', False) and self.company_name:
                    cofounder_names = ["Jane", "Alex", "Sam", "Taylor", "Jordan", "Riley", "Casey"]
                    random.shuffle(cofounder_names)
                    self.co_founders = [{"name": cofounder_names[i], "alive": True} for i in range(3)]
                    self.runway = 100
                    self.equity = 100
                    self.traction = 0
                    self.distance = 0
                    self.hunt_distance_trigger = 0
                    self.log(f"🚀 {self.company_name} returns to the trail!")
                    self.start_new_cycle()
                else:
                    self.state = -1
            elif key == pygame.K_n:
                self.reset_profile()
                self.state = -1
                self.onboarding_step = 0
                self.input_active = True
        
        elif self.state == 1:
            if key == pygame.K_p and not self.current_event and not self.remedy_active:
                self.paused = True
                self.pause_timer = 25 * 60
                self.log("⏸️ Paused for 25 seconds")
            
            if key == pygame.K_h and not self.current_event and not self.remedy_active and not self.paused:
                if self.distance - self.hunt_distance_trigger > 300:
                    self.start_hunt()
                else:
                    self.log("🎯 Hunt on cooldown... keep traveling!")
            
            if not self.current_event and not self.remedy_active:
                if key == pygame.K_1:
                    self.pace = 1
                    self.log("🐢 Pace: Steady (safe, slow)")
                elif key == pygame.K_2:
                    self.pace = 2
                    self.log("🚶 Pace: Strenuous (balanced)")
                elif key == pygame.K_3:
                    self.pace = 3
                    self.log("🏃 Pace: Grueling (risky, fast)")
            
            if self.current_event:
                if self.current_event == 'tweet':
                    if getattr(self, 'tweet_mobile_choices', False) and key in (pygame.K_1, pygame.K_2, pygame.K_3):
                        self._handle_tweet_mobile_choice(int(pygame.key.name(key)))
                    else:
                        self.handle_tweet_keypress(event)
                elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    choice = int(pygame.key.name(key))
                    if self.current_event == 'river':
                        self.handle_river_choice(choice)
                    elif self.current_event == 'breakdown':
                        self.handle_breakdown_choice(choice)
                    elif self.current_event == 'sickness':
                        self.handle_sickness_choice(choice)
                    elif self.current_event == 'decision':
                        self.handle_decision_choice(choice)
                    elif self.current_event == 'dilemma':
                        self.handle_dilemma_choice(choice)
                    elif self.current_event == 'yc_lottery':
                        self.handle_yc_lottery_choice(choice)
                    elif self.current_event == 'erlich':
                        self.handle_erlich_choice(choice)
                    elif self.current_event == 'hotdog':
                        self.handle_hotdog_choice(choice)
                    elif self.current_event == 'gilfoyle':
                        self.handle_gilfoyle_choice(choice)
            
            elif self.remedy_active and self.remedy_timer == 0:
                if key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    choice = int(pygame.key.name(key))
                    self.handle_remedy(choice)
        
        elif self.state == 10:
            # Q&A phase - 1/2/3/4 for answers, SPACE/F to shoot
            if self.round_transition_timer > 0:
                return
            if key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                choice = int(pygame.key.name(key)) - 1
                self._answer_question(choice)
            elif key in (pygame.K_SPACE, pygame.K_f):
                self._qa_shoot()

        elif self.state == 3:
            if key == pygame.K_SPACE:
                self.hunt_shoot()
            elif key == pygame.K_ESCAPE:
                self.end_hunt()

        elif self.state == 11:
            # Cycle arcade controls
            if key == pygame.K_SPACE and self.bonus_type in ('galaga', 'boss'):
                self.bullets.append({
                    'rect': pygame.Rect(self.player_x - 2, self.player_y - 30, 5, 15)
                })
                play_sound(SFX_SHOOT)
            elif key == pygame.K_ESCAPE:
                self.end_cycle_arcade()

        elif self.state == 2:
            if key == pygame.K_SPACE and self.bonus_type == 'galaga':
                self.bullets.append({
                    'rect': pygame.Rect(self.player_x - 2, self.player_y - 30, 5, 15)
                })
                play_sound(SFX_SHOOT)

        elif self.state in (5, 6):
            if key == pygame.K_SPACE:
                self.__init__()

    # ══════════════════════════════════════════════════════════════════
    # TOUCH / MOBILE CONTROLS
    # ══════════════════════════════════════════════════════════════════

    def handle_mouse_as_touch(self, event):
        """Handle MOUSEBUTTONDOWN/UP as touch events (pygbag compatibility)"""
        if not self.is_touch:
            self.is_touch = True

        # Mouse events use .pos (pixel coords), not normalized .x/.y
        tx, ty = event.pos

        if event.type == pygame.MOUSEBUTTONUP:
            self.touch_left = False
            self.touch_right = False
            self.touch_up = False
            self.touch_down = False
            self.touch_active_btn = None
            return

        # MOUSEBUTTONDOWN → same logic as FINGERDOWN
        self.touch_buttons = self.get_touch_buttons()
        hit_action = None
        for btn in self.touch_buttons:
            if btn["rect"].collidepoint(tx, ty):
                hit_action = btn["action"]
                break

        self.touch_left = False
        self.touch_right = False
        self.touch_up = False
        self.touch_down = False

        if hit_action:
            self.touch_active_btn = hit_action
            if hit_action == "left":
                self.touch_left = True
            elif hit_action == "right":
                self.touch_right = True
            elif hit_action == "up":
                self.touch_up = True
            elif hit_action == "down":
                self.touch_down = True
            else:
                self._execute_touch_action(hit_action)
        else:
            self.touch_active_btn = None

    def handle_touch_event(self, event):
        """Handle FINGERDOWN / FINGERUP / FINGERMOTION for mobile play"""
        # First touch ever → enable touch UI
        if not self.is_touch:
            self.is_touch = True

        # Convert normalized 0-1 coords to screen pixels
        tx = int(event.x * WIDTH)
        ty = int(event.y * HEIGHT)

        if event.type == pygame.FINGERUP:
            self.touch_left = False
            self.touch_right = False
            self.touch_up = False
            self.touch_down = False
            self.touch_active_btn = None
            return

        # Build current buttons (needed for hit testing)
        self.touch_buttons = self.get_touch_buttons()

        hit_action = None
        for btn in self.touch_buttons:
            if btn["rect"].collidepoint(tx, ty):
                hit_action = btn["action"]
                break

        if event.type == pygame.FINGERDOWN:
            # Clear directional flags first
            self.touch_left = False
            self.touch_right = False
            self.touch_up = False
            self.touch_down = False

            if hit_action:
                self.touch_active_btn = hit_action
                if hit_action == "left":
                    self.touch_left = True
                elif hit_action == "right":
                    self.touch_right = True
                elif hit_action == "up":
                    self.touch_up = True
                elif hit_action == "down":
                    self.touch_down = True
                else:
                    # Non-directional action → execute immediately
                    self._execute_touch_action(hit_action)
            else:
                self.touch_active_btn = None

        elif event.type == pygame.FINGERMOTION:
            # Update directional holds as finger drags
            self.touch_left = (hit_action == "left")
            self.touch_right = (hit_action == "right")
            self.touch_up = (hit_action == "up")
            self.touch_down = (hit_action == "down")
            self.touch_active_btn = hit_action

    def get_touch_buttons(self):
        """Return list of virtual button defs for the current game state"""
        btns = []
        BW, BH = 110, 70  # standard button size (bigger for mobile)
        SBW = 85  # small button width
        PAD = 10
        BOT = HEIGHT - BH - PAD  # bottom row Y
        BOT2 = BOT - BH - PAD    # second from bottom

        if self.state == 0:
            # Title screen
            btns.append({"rect": pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 40, 200, 70),
                         "label": "START", "action": "space", "color": GREEN})
            if getattr(self, 'has_saved_profile', False):
                btns.append({"rect": pygame.Rect(WIDTH - 130, PAD, 120, 50),
                             "label": "RESET", "action": "n", "color": RED})

        elif self.state == -1:
            # Onboarding
            if self.onboarding_step < 3:
                btns.append({"rect": pygame.Rect(WIDTH//2 - 75, HEIGHT - 85, 150, 65),
                             "label": "NEXT", "action": "return", "color": GREEN})
            elif self.onboarding_step in (3, 4):
                btns.append({"rect": pygame.Rect(WIDTH//2 - 155, HEIGHT - 85, 145, 65),
                             "label": "YES", "action": "y", "color": GREEN})
                btns.append({"rect": pygame.Rect(WIDTH//2 + 10, HEIGHT - 85, 145, 65),
                             "label": "NO", "action": "n", "color": RED})
            elif self.onboarding_step == 5:
                btns.append({"rect": pygame.Rect(WIDTH//2 - 155, HEIGHT - 85, 145, 65),
                             "label": "BOOT", "action": "1", "color": ORANGE})
                btns.append({"rect": pygame.Rect(WIDTH//2 + 10, HEIGHT - 85, 145, 65),
                             "label": "VC FUND", "action": "2", "color": CYAN})

        elif self.state == 1:
            # Trail - context-dependent
            if self.current_event:
                if self.current_event == 'tweet' and hasattr(self, 'tweet_mobile_choices'):
                    # Mobile tweet: show 3 choice buttons
                    for i in range(3):
                        btns.append({"rect": pygame.Rect(40, 280 + i * 65, WIDTH - 80, 55),
                                     "label": f"{i+1}", "action": str(i + 1), "color": CYAN})
                elif self.current_event == 'hotdog':
                    # Hot dog: 2 big buttons
                    btns.append({"rect": pygame.Rect(PAD, BOT, WIDTH//2 - PAD * 2, BH),
                                 "label": "HOT DOG", "action": "1", "color": GREEN})
                    btns.append({"rect": pygame.Rect(WIDTH//2 + PAD, BOT, WIDTH//2 - PAD * 2, BH),
                                 "label": "NOT HOT DOG", "action": "2", "color": RED})
                elif self.current_event == 'yc_lottery':
                    btns.append({"rect": pygame.Rect(PAD, BOT, WIDTH//2 - PAD * 2, BH),
                                 "label": "CHECK", "action": "1", "color": CYAN})
                    btns.append({"rect": pygame.Rect(WIDTH//2 + PAD, BOT, WIDTH//2 - PAD * 2, BH),
                                 "label": "KEEP BUILDING", "action": "2", "color": GREEN})
                else:
                    # Generic event: up to 4 choice buttons
                    n_opts = len(getattr(self, 'event_options', [])) or 4
                    n = min(n_opts, 4)
                    bw = (WIDTH - PAD * 2 - (n - 1) * PAD) // n
                    for i in range(n):
                        btns.append({"rect": pygame.Rect(PAD + i * (bw + PAD), BOT, bw, BH),
                                     "label": str(i + 1), "action": str(i + 1), "color": CYAN})
            elif self.remedy_active and self.remedy_timer == 0:
                for i in range(5):
                    bw = (WIDTH - PAD * 2 - 4 * PAD) // 5
                    btns.append({"rect": pygame.Rect(PAD + i * (bw + PAD), BOT, bw, BH),
                                 "label": str(i + 1), "action": str(i + 1), "color": ORANGE})
            else:
                # Normal trail: pace + hunt + pause
                for i in range(3):
                    btns.append({"rect": pygame.Rect(10 + i * (SBW + PAD), BOT, SBW, BH),
                                 "label": ["SLOW", "MED", "FAST"][i], "action": str(i + 1),
                                 "color": [GREEN, YELLOW, RED][i]})
                btns.append({"rect": pygame.Rect(WIDTH - BW - PAD, BOT, BW, BH),
                             "label": "HUNT", "action": "hunt", "color": ORANGE})
                btns.append({"rect": pygame.Rect(WIDTH - BW - PAD, BOT2, BW, BH),
                             "label": "PAUSE", "action": "pause", "color": GRAY})

        elif self.state == 10:
            # Q&A: JUMP / DUCK / SHOOT + answer buttons
            btns.append({"rect": pygame.Rect(PAD, BOT, BW, BH),
                         "label": "JUMP", "action": "up", "color": GREEN})
            btns.append({"rect": pygame.Rect(PAD + BW + PAD, BOT, BW, BH),
                         "label": "DUCK", "action": "down", "color": CYAN})
            btns.append({"rect": pygame.Rect(WIDTH - BW - PAD, BOT, BW, BH),
                         "label": "SHOOT", "action": "space", "color": RED})
            if not self.qa_answered and self.qa_result_timer == 0 and self.round_transition_timer == 0:
                for i in range(4):
                    bw = (WIDTH - PAD * 2 - 3 * PAD) // 4
                    btns.append({"rect": pygame.Rect(PAD + i * (bw + PAD), BOT2, bw, 60),
                                 "label": str(i + 1), "action": str(i + 1), "color": YELLOW})

        elif self.state == 3:
            # Hunt: d-pad + fire + exit (large buttons for mobile)
            cx, cy = 130, BOT - 50  # d-pad center
            ds = 100  # d-pad button size (extra large for mobile)
            btns.append({"rect": pygame.Rect(cx - ds//2, cy - ds - 8, ds, ds),
                         "label": "^", "action": "up", "color": CYAN})
            btns.append({"rect": pygame.Rect(cx - ds - 8, cy, ds, ds),
                         "label": "<", "action": "left", "color": CYAN})
            btns.append({"rect": pygame.Rect(cx + 8, cy, ds, ds),
                         "label": ">", "action": "right", "color": CYAN})
            btns.append({"rect": pygame.Rect(cx - ds//2, cy + ds + 8, ds, ds),
                         "label": "v", "action": "down", "color": CYAN})
            btns.append({"rect": pygame.Rect(WIDTH - 140, BOT - 20, 130, 90),
                         "label": "FIRE", "action": "space", "color": RED})
            btns.append({"rect": pygame.Rect(WIDTH - 100, PAD, 90, 45),
                         "label": "EXIT", "action": "escape", "color": GRAY})

        elif self.state == 11:
            # Cycle arcade (large buttons for mobile)
            if self.bonus_type == 'frogger':
                # Frogger: full d-pad
                cx, cy = 130, BOT - 50
                ds = 100  # extra large for mobile
                btns.append({"rect": pygame.Rect(cx - ds//2, cy - ds - 8, ds, ds),
                             "label": "^", "action": "up", "color": CYAN})
                btns.append({"rect": pygame.Rect(cx - ds - 8, cy, ds, ds),
                             "label": "<", "action": "left", "color": CYAN})
                btns.append({"rect": pygame.Rect(cx + 8, cy, ds, ds),
                             "label": ">", "action": "right", "color": CYAN})
                btns.append({"rect": pygame.Rect(cx - ds//2, cy + ds + 8, ds, ds),
                             "label": "v", "action": "down", "color": CYAN})
            else:
                # Galaga/Boss/Mario: left/right only (large buttons)
                LBW = 130  # large button width
                LBH = 90   # large button height
                btns.append({"rect": pygame.Rect(PAD, BOT - 10, LBW, LBH),
                             "label": "<", "action": "left", "color": CYAN})
                btns.append({"rect": pygame.Rect(PAD + LBW + PAD, BOT - 10, LBW, LBH),
                             "label": ">", "action": "right", "color": CYAN})
                if self.bonus_type in ('galaga', 'boss'):
                    btns.append({"rect": pygame.Rect(WIDTH - 140, BOT - 10, 130, LBH),
                                 "label": "FIRE", "action": "space", "color": RED})
                elif self.bonus_type == 'mario':
                    btns.append({"rect": pygame.Rect(WIDTH - 140, BOT - 10, 130, LBH),
                                 "label": "JUMP", "action": "up", "color": GREEN})
            btns.append({"rect": pygame.Rect(WIDTH - 100, PAD, 90, 45),
                         "label": "EXIT", "action": "escape", "color": GRAY})

        elif self.state == 2:
            # Final bonus
            if self.bonus_type == 'galaga':
                btns.append({"rect": pygame.Rect(WIDTH//2 - 55, BOT, BW, BH),
                             "label": "FIRE", "action": "space", "color": RED})

        elif self.state in (5, 6):
            # Win / Lose
            btns.append({"rect": pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 80, 200, 70),
                         "label": "RESTART", "action": "space", "color": GREEN})

        return btns

    def _execute_touch_action(self, action):
        """Execute a non-directional touch action (mirrors keyboard input)"""
        # Map action to a synthetic key for handle_event
        key_map = {
            "1": pygame.K_1, "2": pygame.K_2, "3": pygame.K_3,
            "4": pygame.K_4, "5": pygame.K_5,
            "space": pygame.K_SPACE, "escape": pygame.K_ESCAPE,
            "y": pygame.K_y, "n": pygame.K_n,
            "return": pygame.K_RETURN,
        }

        if action == "hunt":
            # Direct: trigger hunt without going through handle_event
            if self.state == 1 and not self.current_event and not self.remedy_active and not self.paused:
                if self.distance - self.hunt_distance_trigger > 300:
                    self.start_hunt()
            return

        if action == "pause":
            if self.state == 1 and not self.current_event and not self.remedy_active:
                self.paused = True
                self.pause_timer = 25 * 60
            return

        if action in key_map:
            # Create a synthetic KEYDOWN event and pass to handle_event
            synth = pygame.event.Event(pygame.KEYDOWN, key=key_map[action], unicode=action, mod=0)
            self.handle_event(synth)

    def draw_touch_ui(self):
        """Draw semi-transparent virtual buttons over the game (always visible)"""
        self.touch_buttons = self.get_touch_buttons()

        # Create a transparent surface for button backgrounds
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        for btn in self.touch_buttons:
            r = btn["rect"]
            c = btn["color"]
            is_active = (btn["action"] == self.touch_active_btn)

            # Background: semi-transparent, brighter when active
            alpha = 180 if is_active else 100
            pygame.draw.rect(overlay, (c[0], c[1], c[2], alpha), r, border_radius=8)
            # Border
            border_color = WHITE if is_active else (c[0], c[1], c[2], 220)
            pygame.draw.rect(overlay, border_color, r, 2, border_radius=8)

        screen.blit(overlay, (0, 0))

        # Draw labels on top (not transparent)
        for btn in self.touch_buttons:
            r = btn["rect"]
            label = btn["label"]
            txt = font.render(label, True, WHITE)
            screen.blit(txt, (r.centerx - txt.get_width() // 2,
                              r.centery - txt.get_height() // 2))


# ══════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════════

async def main():
    try:
        game = Game()
    except Exception as e:
        # Show init error on screen so we can debug on mobile
        screen.fill(RED)
        screen.blit(font.render("INIT ERROR:", True, WHITE), (10, 10))
        screen.blit(small_font.render(str(e)[:80], True, WHITE), (10, 40))
        pygame.display.flip()
        while True:
            await asyncio.sleep(1)
        return

    running = True

    while running:
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
                    game.handle_touch_event(event)
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    game.handle_mouse_as_touch(event)
                else:
                    game.handle_event(event)

            game.update()
            game.draw()
            game.draw_touch_ui()
            pygame.display.flip()
            clock.tick(60)
        except Exception as e:
            # Show runtime error on screen
            screen.fill(RED)
            screen.blit(font.render("RUNTIME ERROR:", True, WHITE), (10, 10))
            err_lines = str(e)[:160]
            screen.blit(small_font.render(err_lines[:80], True, WHITE), (10, 40))
            if len(err_lines) > 80:
                screen.blit(small_font.render(err_lines[80:], True, WHITE), (10, 60))
            screen.blit(small_font.render(f"State: {game.state}", True, YELLOW), (10, 90))
            pygame.display.flip()
            while True:
                await asyncio.sleep(1)
            return

        await asyncio.sleep(0)

    pygame.quit()

asyncio.run(main())
