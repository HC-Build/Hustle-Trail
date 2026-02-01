import pygame
import random
import sys
import math
import uuid
import json
import os

# Save file path
SAVE_FILE = os.path.join(os.path.dirname(__file__), "hustle_save.json")

# Init
pygame.init()
pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Hustle Trail: 0 to 1 (Multi-Agent Edition)")
clock = pygame.time.Clock()
font = pygame.font.SysFont('arial', 20, bold=True)
small_font = pygame.font.SysFont('arial', 16)
big_font = pygame.font.SysFont('arial', 42, bold=True)

# Generate retro sound effects (no external files needed!)
def generate_sound(frequency, duration, volume=0.3, wave_type='square'):
    """Generate retro 8-bit style sounds"""
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
        else:  # sine
            val = int(max_amp * math.sin(2 * math.pi * frequency * t))
        
        # Fade out
        fade = 1 - (i / n_samples) ** 0.5
        val = int(val * fade)
        
        buf[i*2] = val & 0xff
        buf[i*2+1] = (val >> 8) & 0xff
    
    return pygame.mixer.Sound(buffer=bytes(buf))

# Create sound effects
try:
    SFX_SHOOT = generate_sound(880, 0.1, 0.2, 'square')
    SFX_HIT = generate_sound(220, 0.15, 0.3, 'square')
    SFX_ENEMY_DIE = generate_sound(440, 0.2, 0.25, 'saw')
    SFX_POWERUP = generate_sound(660, 0.15, 0.2, 'sine')
    SFX_DAMAGE = generate_sound(110, 0.3, 0.3, 'square')
    SFX_BOSS = generate_sound(55, 0.5, 0.4, 'saw')
    SFX_WIN = generate_sound(880, 0.5, 0.3, 'sine')
    SFX_LOSE = generate_sound(110, 0.8, 0.4, 'square')
    SFX_DECISION = generate_sound(330, 0.1, 0.2, 'sine')
    SFX_REMEDY = generate_sound(550, 0.3, 0.2, 'sine')
    AUDIO_ENABLED = True
except:
    AUDIO_ENABLED = False
    print("Audio disabled - couldn't initialize sounds")

def play_sound(sound):
    """Play a sound if audio is enabled"""
    if AUDIO_ENABLED:
        try:
            sound.play()
        except:
            pass

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BROWN = (139, 69, 19)  # Wagon
GREEN = (0, 255, 0)    # Bullet/collect
RED = (255, 0, 0)      # Enemy
YELLOW = (255, 255, 0) # Text
BLUE = (0, 100, 255)   # Platforms
CYAN = (0, 255, 255)   # Motbot
MAGENTA = (255, 0, 255) # Clawbot
ORANGE = (255, 165, 0)  # Power-ups
GRAY = (200, 200, 200)  # UI elements

class Game:
    def __init__(self):
        # States: -1=Onboarding, 0=Title, 1=River1, 2=Galaga, 3=Mario, 4=Frogger, 5=Win, 6=Lose
        self.state = 0
        
        # ── Onboarding variables ──
        self.onboarding_step = 0
        self.company_name = ""
        self.problem = ""
        self.solution = ""
        self.warm_intro = False
        self.elite_college = False
        self.input_text = ""
        self.input_active = True
        
        # Co-founders (3 to start)
        cofounder_names = ["Jane", "Alex", "Sam", "Taylor", "Jordan", "Riley", "Casey"]
        random.shuffle(cofounder_names)
        self.co_founders = [
            {"name": cofounder_names[0], "alive": True},
            {"name": cofounder_names[1], "alive": True},
            {"name": cofounder_names[2], "alive": True},
        ]
        
        # River crossing - SKILL GAME
        self.river_choice = None
        self.river_outcome = None
        self.river_timer = 0
        self.river_crossing_active = False
        self.river_wagon_x = 50  # Start on left bank
        self.river_wagon_y = HEIGHT // 2
        self.river_health = 3  # Hits before fail
        self.river_obstacles = []  # Sharks, logs, currents
        self.river_particles = []  # Splash effects
        self.river_progress = 0  # 0 to 100 (reach right side)
        self.river_speed_mult = 1.0  # Difficulty multiplier
        self.river_invincible = 0  # I-frames after hit
        
        # Core stats
        self.runway = 100.0
        self.equity = 100
        self.traction = 0
        self.player_x = WIDTH // 2
        self.player_y = HEIGHT - 80
        self.player_rect = pygame.Rect(self.player_x - 25, self.player_y - 25, 50, 50)
        self.bullets = []
        self.enemies = []
        self.platforms = []
        self.obstacles = []
        self.powerups = []  # Follower power-ups
        self.decision_active = False
        self.decision_text = ""
        self.decision_options = ["", ""]
        self.scroll_x = 0
        self.enemy_spawn_timer = 0
        self.init_platforms()
        
        # Multi-Agent Mode
        self.agent_mode = False
        self.motbot_active = False
        self.clawbot_active = False
        self.agent_logs = []
        self.viral_mode = False
        self.viral_timer = 0
        self.followers = 0
        self.ghosting_timer = 0  # Inactivity tracker for ghosting event
        self.last_input_time = 0
        
        # Bot positions
        self.motbot_x = 100
        self.motbot_y = HEIGHT - 100
        self.clawbot_x = WIDTH - 100
        self.clawbot_y = HEIGHT - 100
        self.clawbot_cooldown = 0
        
        # BONUS ARCADE TRACKING - runway rewards!
        self.bonus_kills = 0  # Galaga kills
        self.bonus_platforms = 0  # Mario platforms landed
        self.bonus_distance = 0  # Frogger progress
        self.bonus_no_hits = True  # Perfect run bonus
        self.bonus_message = ""  # Reward feedback
        self.bonus_message_timer = 0
        
        # Enhanced enemy types with SV lore
        self.enemy_types = [
            ("🐛 Bad Code", 1, "Your codebase is spaghetti"),
            ("👊 Paul Bros", 2, "PIVOT TO CRYPTO BRO"),
            ("🚀 Musk Tweet", 3, "Mass layoffs are efficient"),
            ("💸 Rug Pull", 2, "Thanks for the liquidity"),
            ("🩸 Theranos", 3, "Fake it til you make it"),
            ("🏦 SVB Collapse", 4, "Your runway just evaporated"),
            ("📈 Wired Founder", 2, "HOW LIKELY?! VERY?! NOT AT ALL?!"),
            ("💨 Neumann Flow", 3, "$47B valuation energy—What does this company do?"),
            ("🔄 OpenAI Boom", 2, "I quit! JK I'm back!"),
            ("🤖 GPT Wrapper", 1, "It's AI-powered! (it's just an API call)"),
            ("📉 Down Round", 3, "Your cap table is cooked"),
            ("🦄 Dead Unicorn", 4, "Was worth $10B last year"),
            ("🎭 Fake PMF", 2, "Users love us! (n=3, all cofounders)"),
            ("💼 Bad VC", 2, "Let me intro you to my partner's dog"),
            ("🐕 Doge Pump", 1, "Much wow very scam"),
            ("👻 Ghosted VC", 2, "Will circle back! (never)"),
            ("🎪 WeWork Vibes", 3, "Community-adjusted EBITDA"),
            ("📱 Pivot Lord", 2, "We're now AI! No wait, climate!"),
            ("🧪 Fake Demo", 3, "It works on my machine"),
            ("💀 Zombie Startup", 2, "Still alive, technically"),
            ("🎯 Spray Pray", 1, "Sent 1000 cold emails today"),
            ("🤡 Founder Mode", 3, "I don't need sleep, I need TRACTION"),
        ]
        
        self.sv_quotes = [
            # Eric Bahn bangers - the hits
            "We booked $1000 in the past hour → $9M ARR now! 🚀",
            "What does this company even do? 🤔",
            "Karma can protect you... sometimes.",
            "Wait 10 min, then log off. Ghosted.",
            "I generally don't like to brag, but... my resume is insane.",
            "Posting thirst traps for engagement. Hi, I'm Eric.",
            "Dodgy ARR metrics detected. Founder vibes only.",
            "Your TAM slide is giving delusion.",
            "Hustle Fund passed. Skill issue.",
            "If you have to ask if you have PMF, you don't.",
            "Is that why that kid isn't smiling? 👀",
            "The best founders ghost bad VCs. It's called self-care.",
            "Your deck has 47 slides. My attention span has 3.",
            "Pre-seed? More like pre-idea.",
            
            # Jian-Yang classics - expanded
            "Oculus? Octopus. It is a water animal.",
            "We went to Taco Bell.",
            "I am your mom, you are not my baby.",
            "You blew it, mister. We could have run this town.",
            "Monica, you never kiss me...",
            "Erlich Bachman, this is your mom. You not my baby.",
            "Yes, I eat the fish.",
            "Hot dog. Not hot dog.",
            "SeeFood. It's an app about seafood.",
            "If oil company wants to buy house, there is oil beneath house.",
            "I'll never give you what you want. I hate you.",
            "Special occasion. I smoke.",
            "New Erlich. Very cool. Very handsome.",
            "This is my refrigerator. This is my food.",
            
            # Wired founder energy - unhinged PMF surveys
            "How likely? VERY? SOMEWHAT? NOT AT ALL? I'M WIRED AF! 📈",
            "Market fit feedback time! HOW LIKELY?! HOW LIKELY?!",
            "Somewhat likely? My startup is DYING here!",
            "I did a survey and everyone said VERY LIKELY! (n=my mom)",
            "FEEDBACK NOW! I'M ON DRUGS—I MEAN ON FIRE! 🔥",
            "Rate 1-10! COME ON! I NEED THIS! I'M WIRED!",
            "You said 'somewhat likely'?! *flips table* 📊",
            
            # General SV chaos
            "We're not a tech company, we're a LIFESTYLE.",
            "Disrupting disruption with AI-powered disruption.",
            "Our burn rate is a feature, not a bug.",
            "Pivoting to AI because VCs stopped calling back.",
            "It's not a layoff, it's a 'right-sizing event'.",
            "We're pre-revenue but post-vibe.",
            "The metaverse is dead. Long live spatial computing!",
            "ChatGPT wrote our business plan. Investors loved it.",
            "We don't have competition. We have 47 identical startups.",
            "Series A? In this economy? Bold.",
            "Our moat is vibes. Unassailable vibes.",
            "The TAM is everyone with a pulse. And some without.",
            "We're Uber for... *checks notes* ...spreadsheets?",
            "10x engineer needed. 0.1x salary offered.",
            "Moved fast, broke things. Things include: the company.",
        ]
        
        # Motbot quotes - expanded with SV flavor
        self.motbot_quotes = [
            "Motbot: Networking on Moltbook... followers +10! 📱",
            "Motbot: Viral tweet deployed! Engagement stonks! 📈",
            "Motbot: Sliding into VC DMs... connection made!",
            "Motbot: Posted a thirst trap. For the algorithm. Hi, I'm Motbot.",
            "Motbot: Ratio'd a hater. Traction boost!",
            "Motbot: Climbing X ranks... almost blue check!",
            "Motbot: Shared your pitch deck. 47 views! (46 are bots)",
            "Motbot: Pivot to AI? I say OCTOPUS! Water animal! 🐙",
            "Motbot: We went to Taco Bell. Networking complete.",
            "Motbot: You blew it, mister! But I fixed it with a retweet.",
            "Motbot: Karma protects you... I retweeted it to be sure.",
            "Motbot: HOW LIKELY to follow? VERY?! I'M WIRED!",
            "Motbot: If oil company wants followers, there ARE followers.",
            "Motbot: Wait 10 min, then log off. I'll handle the ghosting.",
        ]
        
        # Clawbot quotes - expanded with SV flavor
        self.clawbot_quotes = [
            "Clawbot: 2AM patch deployed. Bugs squashed! 🔧",
            "Clawbot: 39 Mac Minis humming. Code shipping!",
            "Clawbot: Auto-fixed your spaghetti code.",
            "Clawbot: Refactoring while you sleep...",
            "Clawbot: CI/CD pipeline go brrrrr 🤖",
            "Clawbot: Found 47 bugs. Fixed 48. Don't ask.",
            "Clawbot: Your technical debt? Paid off. $9M ARR debt!",
            "Clawbot: Dodgy code metrics? Now they're INSANE. Like my resume.",
            "Clawbot: Hot dog? Not hot dog? Fixed the ML model.",
            "Clawbot: Karma protects your codebase... I AM karma.",
            "Clawbot: What does this function do? 🤔 Fixed it anyway.",
            "Clawbot: Your build broke. I blame Neumann Flow.",
            "Clawbot: Shipped code at 2AM. This is founder mode.",
            "Clawbot: GitHub says I have no commits? GHOSTED.",
        ]
        
        self.current_quote = None
        self.quote_timer = 0
        self.boss_active = False
        self.boss_health = 0
        self.boss_type = ""
        self.death_quote = None  # Store death quote so it doesn't flicker
        
        # Five Remedies system - self-care when equity is low
        self.remedy_active = False
        self.remedy_text = ""
        self.remedy_options = [
            "1: Pleasure (+equity, -traction) - Touch grass, founder",
            "2: Tears (+equity, -runway) - Let it out, it's okay",
            "3: Contemplating Truth (+equity, +traction, longer) - Jian-Yang wisdom",
            "4: Friends (+equity, random boost) - Call your cofounder",
            "5: Bath & Nap (+equity, +runway) - Self-care is founder-care"
        ]
        self.remedy_threshold = 30  # Trigger when equity <= this
        self.remedy_timer = 0
        self.selected_remedy = ""
        
        # Remedy quotes for each type
        self.remedy_quotes = {
            "Pleasure": [
                "Touched grass. Equity restored. Traction who?",
                "Eric Bahn says: Even hustlers need dopamine hits.",
                "Jian-Yang: I eat the fish. It is pleasure."
            ],
            "Tears": [
                "Cried in the shower. Startup life hits different.",
                "Jian-Yang: I am your mom. Cry to me.",
                "Even $9M ARR founders cry sometimes."
            ],
            "Contemplating Truth": [
                "Jian-Yang wisdom: If oil company wants house, there IS oil.",
                "Deep thought: What DOES this company even do?",
                "Contemplated: Hot dog. Not hot dog. Life is binary.",
                "Truth: Karma CAN protect you. Meditating on this."
            ],
            "Friends": [
                "Called cofounder. They picked up! (rare)",
                "Motbot: I'm always here for you. Networking = friendship.",
                "Clawbot: Friendship is the real 2AM patch.",
                "We went to Taco Bell. Together."
            ],
            "Bath & Nap": [
                "Bath + nap combo. Runway AND equity restored.",
                "Jian-Yang: This is my bathtub. This is my nap.",
                "Self-care is the ultimate founder hack.",
                "Slept 8 hours. VCs hate this one trick."
            ]
        }
        
        # Load saved profile if exists
        self.load_profile()

    def save_profile(self):
        """Save founder profile and game progress to JSON"""
        save_data = {
            "company_name": self.company_name,
            "problem": self.problem,
            "solution": self.solution,
            "warm_intro": self.warm_intro,
            "elite_college": self.elite_college,
            "co_founders": self.co_founders,
            "high_score": getattr(self, 'high_score', 0),
            "games_played": getattr(self, 'games_played', 0) + 1,
            "river_crossings_survived": getattr(self, 'river_crossings_survived', 0),
            "total_traction": getattr(self, 'total_traction', 0),
            "best_runway": max(getattr(self, 'best_runway', 0), int(self.runway)),
            "best_equity": max(getattr(self, 'best_equity', 0), self.equity),
        }
        try:
            with open(SAVE_FILE, 'w') as f:
                json.dump(save_data, f, indent=2)
            self.log_agent(f"💾 Profile saved: {self.company_name}")
        except Exception as e:
            print(f"Save failed: {e}")
    
    def load_profile(self):
        """Load saved founder profile"""
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE, 'r') as f:
                    data = json.load(f)
                
                self.company_name = data.get("company_name", "")
                self.problem = data.get("problem", "")
                self.solution = data.get("solution", "")
                self.warm_intro = data.get("warm_intro", False)
                self.elite_college = data.get("elite_college", False)
                self.co_founders = data.get("co_founders", self.co_founders)
                self.high_score = data.get("high_score", 0)
                self.games_played = data.get("games_played", 0)
                self.river_crossings_survived = data.get("river_crossings_survived", 0)
                self.total_traction = data.get("total_traction", 0)
                self.best_runway = data.get("best_runway", 0)
                self.best_equity = data.get("best_equity", 0)
                
                # If we have a saved company, offer to skip onboarding
                if self.company_name:
                    self.has_saved_profile = True
                    print(f"📂 Loaded profile: {self.company_name} ({self.games_played} games played)")
                else:
                    self.has_saved_profile = False
            else:
                self.has_saved_profile = False
                self.high_score = 0
                self.games_played = 0
                self.river_crossings_survived = 0
                self.total_traction = 0
                self.best_runway = 0
                self.best_equity = 0
        except Exception as e:
            print(f"Load failed: {e}")
            self.has_saved_profile = False
    
    def reset_profile(self):
        """Delete saved profile and start fresh"""
        try:
            if os.path.exists(SAVE_FILE):
                os.remove(SAVE_FILE)
            self.has_saved_profile = False
            self.company_name = ""
            self.problem = ""
            self.solution = ""
            self.warm_intro = False
            self.elite_college = False
            self.high_score = 0
            self.games_played = 0
            self.log_agent("🗑️ Profile reset! Starting fresh.")
        except Exception as e:
            print(f"Reset failed: {e}")

    def bootstrap_ending(self):
        """Secret ending for choosing to bootstrap"""
        self.state = 6  # Lose state, but special
        self.death_quote = (
            "You bootstrapped quietly.\n"
            "Hit $9M ARR in 18 months. Zero dilution. Zero hype.\n"
            "No one knows your name. You retired to Phoenix.\n"
            "\nTRUE ENDING: Quiet Wealth\n"
            "Eric Bahn: Skill issue? Nah... respect."
        )

    def start_river_crossing(self):
        """Initialize the river crossing skill game"""
        # Set difficulty based on choice
        difficulties = {
            1: (1.5, 2, "YOLO MODE - Fast & dangerous!"),      # Ford: hardest
            2: (1.2, 3, "Hype Float - Medium danger"),          # Caulk: medium
            3: (0.8, 4, "Chill Mode - Slow but steady"),        # Wait: easy
            4: (0.6, 5, "VIP Ferry - Easy sailing"),            # Ferry: easiest
        }
        speed, health, flavor = difficulties[self.river_choice]
        
        self.river_speed_mult = speed
        self.river_health = health
        
        # Bonuses from onboarding
        if self.warm_intro:
            self.river_health += 1
            flavor += " (+1 HP from warm intro!)"
        if self.elite_college:
            self.river_speed_mult *= 0.9
            flavor += " (Slower obstacles from elite college!)"
        
        self.river_crossing_active = True
        self.river_wagon_x = 50
        self.river_wagon_y = HEIGHT // 2
        self.river_obstacles = []
        self.river_particles = []
        self.river_progress = 0
        self.river_invincible = 0
        self.river_outcome = None
        
        self.log_agent(f"🌊 {flavor}")
        play_sound(SFX_BOSS)
        
        # Spawn initial obstacles
        self.spawn_river_obstacles()
    
    def spawn_river_obstacles(self):
        """Spawn obstacles in the river"""
        obstacle_types = [
            ("🦈 VC Shark", 4, RED, "Wants 40% equity!"),
            ("🪵 Dead Unicorn", 3, BROWN, "Floating corpse of a $10B startup"),
            ("🌊 Dilution Wave", 5, BLUE, "Your cap table is drowning!"),
            ("💸 Burn Rate", 3, ORANGE, "Cash flowing away..."),
            ("👻 Ghost VC", 4, GRAY, "Will circle back... never"),
            ("🐙 Octopus", 2, MAGENTA, "It is a water animal!"),
        ]
        
        # Spawn 3-5 obstacles in lanes
        num_obstacles = random.randint(3, 5)
        lanes = [150, 220, 290, 360, 430]  # Y positions
        
        for _ in range(num_obstacles):
            obs_type = random.choice(obstacle_types)
            lane = random.choice(lanes)
            direction = random.choice([-1, 1])
            start_x = -60 if direction == 1 else WIDTH + 60
            
            self.river_obstacles.append({
                'x': start_x,
                'y': lane,
                'width': 50,
                'height': 35,
                'speed': random.uniform(2, 4) * self.river_speed_mult * direction,
                'type': obs_type[0],
                'damage': 1,
                'color': obs_type[2],
                'quote': obs_type[3],
            })
    
    def update_river_crossing(self):
        """Update the river crossing mini-game"""
        if not self.river_crossing_active:
            return
        
        # Handle invincibility frames
        if self.river_invincible > 0:
            self.river_invincible -= 1
        
        # Player movement (WASD or arrows)
        keys = pygame.key.get_pressed()
        move_speed = 5
        
        if (keys[pygame.K_LEFT] or keys[pygame.K_a]) and self.river_wagon_x > 50:
            self.river_wagon_x -= move_speed * 0.5  # Slower backward
        if (keys[pygame.K_RIGHT] or keys[pygame.K_d]) and self.river_wagon_x < WIDTH - 80:
            self.river_wagon_x += move_speed
        if (keys[pygame.K_UP] or keys[pygame.K_w]) and self.river_wagon_y > 130:
            self.river_wagon_y -= move_speed
        if (keys[pygame.K_DOWN] or keys[pygame.K_s]) and self.river_wagon_y < HEIGHT - 150:
            self.river_wagon_y += move_speed
        
        # Update progress based on X position
        self.river_progress = max(0, min(100, (self.river_wagon_x - 50) / (WIDTH - 130) * 100))
        
        # Spawn new obstacles periodically
        if random.random() < 0.03:
            self.spawn_river_obstacles()
        
        # Update obstacles
        wagon_rect = pygame.Rect(self.river_wagon_x, self.river_wagon_y, 60, 40)
        
        for obs in self.river_obstacles[:]:
            obs['x'] += obs['speed']
            
            # Remove if off screen
            if obs['x'] < -100 or obs['x'] > WIDTH + 100:
                self.river_obstacles.remove(obs)
                continue
            
            # Check collision with wagon
            obs_rect = pygame.Rect(obs['x'], obs['y'], obs['width'], obs['height'])
            if wagon_rect.colliderect(obs_rect) and self.river_invincible <= 0:
                self.river_health -= obs['damage']
                self.river_invincible = 60  # 1 second invincibility
                play_sound(SFX_DAMAGE)
                
                # Splash particles
                for _ in range(10):
                    self.river_particles.append({
                        'x': self.river_wagon_x + 30,
                        'y': self.river_wagon_y + 20,
                        'vx': random.uniform(-3, 3),
                        'vy': random.uniform(-5, -1),
                        'life': 30,
                        'color': obs['color']
                    })
                
                # Show quote
                self.current_quote = f"{obs['type']}: {obs['quote']}"
                self.quote_timer = 90
                
                # Check if dead
                if self.river_health <= 0:
                    self.river_crossing_fail()
                    return
        
        # Update particles
        for p in self.river_particles[:]:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vy'] += 0.2  # Gravity
            p['life'] -= 1
            if p['life'] <= 0:
                self.river_particles.remove(p)
        
        # Check for success (reached right side)
        if self.river_wagon_x >= WIDTH - 90:
            self.river_crossing_success()
    
    def river_crossing_success(self):
        """Player made it across!"""
        self.river_crossing_active = False
        self.traction += 15
        self.river_outcome = f"SUCCESS! 🎉 Welcome to Silicon Valley!\nTraction +15%"
        
        # Bonus for remaining health
        if self.river_health >= 3:
            self.equity += 10
            self.river_outcome += f"\nPerfect crossing! +10 equity"
        
        # Update saved stats
        self.river_crossings_survived = getattr(self, 'river_crossings_survived', 0) + 1
        self.total_traction = getattr(self, 'total_traction', 0) + int(self.traction)
        self.save_profile()
        
        play_sound(SFX_WIN)
        self.river_timer = 180  # Show for 3 seconds then advance
        self.log_agent("🎉 River crossed! The hustle continues...")
    
    def river_crossing_fail(self):
        """Player failed the crossing"""
        self.river_crossing_active = False
        
        equity_loss = random.randint(20, 40)
        runway_loss = random.randint(5, 15)
        self.equity -= equity_loss
        self.runway -= runway_loss
        
        self.river_outcome = f"DISASTER! 💀 Sunk in the Series Seed Chasm!\n-{equity_loss} equity, -{runway_loss} runway"
        
        # Chance to lose co-founder
        if random.random() < 0.30:
            lost = next((cf for cf in self.co_founders if cf["alive"]), None)
            if lost:
                lost["alive"] = False
                reasons = [
                    "drowned in dilution",
                    "eaten by VC sharks",
                    "swept away by burn rate",
                    "ghosted mid-river",
                    "had a panic attack and swam to shore",
                ]
                reason = random.choice(reasons)
                self.river_outcome += f"\n💀 {lost['name']} {reason}!"
                play_sound(SFX_LOSE)
        
        self.current_quote = random.choice(["You blew it, mister!", "Skill issue.", "Ghosted by the river."])
        self.quote_timer = 150
        self.river_timer = 240  # Show for 4 seconds then retry

    def init_platforms(self):
        self.platforms = [
            pygame.Rect(100 + i*200, HEIGHT - 100, 150, 20) for i in range(10)
        ] + [pygame.Rect(500 + i*300, HEIGHT - 200, 120, 20) for i in range(5)]

    def log_agent(self, msg):
        """Add agent action to console log"""
        print(msg)
        self.agent_logs.append(msg)
        if len(self.agent_logs) > 5:
            self.agent_logs.pop(0)

    def spawn_powerup(self):
        """Spawn follower/boost power-ups"""
        if random.random() < 0.02:
            ptype = random.choice(["follower", "runway", "equity"])
            self.powerups.append({
                'rect': pygame.Rect(random.randint(50, WIDTH-50), random.randint(50, HEIGHT-100), 20, 20),
                'type': ptype,
                'timer': 300
            })

    def update_bots(self):
        """Update Motbot and Clawbot AI agents"""
        if not self.agent_mode:
            return
            
        # Clawbot - active in Galaga phase (state 2)
        if self.state == 2 and self.clawbot_active:
            self.clawbot_cooldown -= 1
            # Auto-shoot at enemies
            if self.clawbot_cooldown <= 0 and self.enemies:
                target = min(self.enemies, key=lambda e: e['rect'].y)
                self.bullets.append({
                    'rect': pygame.Rect(target['rect'].centerx, HEIGHT - 100, 5, 15),
                    'y': HEIGHT - 100,
                    'clawbot': True
                })
                self.clawbot_cooldown = 20
                if random.random() < 0.1:
                    self.log_agent(random.choice(self.clawbot_quotes))
            
            # Random 2AM patch - restore runway with dodgy ARR flavor
            if random.random() < 0.005:
                self.runway = min(100, self.runway + 5)
                self.log_agent("Clawbot: 2AM emergency patch! Fixing metrics—$9M ARR now! +5 runway 🔧")
            
            # Clawbot auto-dodge with karma protection
            if random.random() < 0.01:
                self.log_agent("Clawbot: Karma protects your codebase! Auto-dodging bugs...")
        
        # Motbot - active in Mario/Frogger phases (states 3,4)
        if self.state in (3, 4) and self.motbot_active:
            # Collect nearby powerups automatically
            for p in self.powerups[:]:
                dist = ((self.motbot_x - p['rect'].centerx)**2 + (self.motbot_y - p['rect'].centery)**2)**0.5
                if dist < 100:
                    self.motbot_x += (p['rect'].centerx - self.motbot_x) * 0.1
                    self.motbot_y += (p['rect'].centery - self.motbot_y) * 0.1
            
            # Random networking boost with SV flavor
            if random.random() < 0.01:
                self.followers += random.randint(5, 15)
                self.traction += 1
                self.log_agent(random.choice(self.motbot_quotes))
            
            # Motbot random votes on pivots with Jian-Yang wisdom
            if random.random() < 0.003:
                pivots = ["Octopus app! Water animal!", "Taco Bell partnership!", "Hot dog. Not hot dog.", "SeeFood for investors!"]
                self.log_agent(f"Motbot: Pivot suggestion—{random.choice(pivots)} 🐙")
            
            # Viral mode boost
            if self.viral_mode and self.viral_timer > 0:
                self.viral_timer -= 1
                if random.random() < 0.05:
                    self.traction += 2
                    self.followers += 10
                    if random.random() < 0.3:
                        self.log_agent("Motbot: Sharing on Moltbook—viral boost with Octopus app! 🚀")
                if random.random() < 0.02:  # Troll risk
                    self.equity -= 5
                    troll_quotes = [
                        "Motbot: Got ratio'd! You blew it, mister! -5 equity 😤",
                        "Motbot: Trolls say 'What does this company do?' -5 equity",
                        "Motbot: Someone replied 'NOT LIKELY AT ALL' -5 equity 📉",
                    ]
                    self.log_agent(random.choice(troll_quotes))
                if self.viral_timer <= 0:
                    self.viral_mode = False
                    self.log_agent("Motbot: Viral moment over. Wait 10 min, then log off. Ghosted.")

    def spawn_boss(self):
        """Spawn a mini-boss"""
        play_sound(SFX_BOSS)
        bosses = [
            ("💀 SVB BANK RUN", 50, "All your runway are belong to us"),
            ("🦄 DEAD UNICORN", 40, "Was worth $10B... last Tuesday"),
            ("🎪 NEUMANN FINAL FORM", 60, "$47B ENERGY—What does this company do?!"),
            ("🤖 SKYNET GPT", 45, "I'm sorry, Dave. Your startup must die."),
            ("📈 WIRED SURVEY STORM", 55, "HOW LIKELY?! VERY?! SOMEWHAT?! FEEDBACK NOW!!!"),
            ("🩸 HOLMES ASCENDED", 50, "The blood tests were real in my heart."),
            ("👻 GHOST VC HORDE", 35, "Will circle back! (x47 VCs)"),
        ]
        boss = random.choice(bosses)
        self.boss_active = True
        self.boss_health = boss[1]
        self.boss_type = boss[0]
        self.boss_quote = boss[2]
        self.boss_rect = pygame.Rect(WIDTH//2 - 60, 50, 120, 60)
        self.log_agent(f"⚠️ BOSS INCOMING: {boss[0]}")

    def update(self):
        self.runway -= 0.05  # Drain
        
        # ── River Crossing (state 1) ──
        if self.state == 1:
            # Active crossing mini-game
            if self.river_crossing_active:
                self.update_river_crossing()
                return
            
            # Outcome display timer
            if self.river_timer > 0:
                self.river_timer -= 1
                if self.river_timer <= 0:
                    if self.river_outcome and "SUCCESS" in self.river_outcome:
                        self.state = 2  # Move to Galaga
                        self.river_outcome = None
                        self.river_choice = None
                        self.river_crossing_active = False
                        self.log_agent("🚀 River crossed! Welcome to GALAGA DEFENSE.")
                    else:
                        # Failed - can try again
                        self.river_choice = None
                        self.river_outcome = None
                        self.river_crossing_active = False
            return  # Don't update other game logic during river crossing
        
        # Check for low equity and trigger remedy if not active
        if self.equity <= self.remedy_threshold and not self.remedy_active and not self.decision_active and self.state in (2, 3, 4):
            self.trigger_remedy()
        
        # Handle remedy resting state
        if self.remedy_active:
            if self.remedy_timer > 0:
                self.remedy_timer -= 1
                self.equity = min(100, self.equity + 0.3)  # Gradual restore
                # Show remedy quote periodically
                if self.remedy_timer % 60 == 0 and self.selected_remedy in self.remedy_quotes:
                    self.current_quote = random.choice(self.remedy_quotes[self.selected_remedy])
                    self.quote_timer = 90
                if self.remedy_timer <= 0:
                    self.remedy_active = False
                    self.log_agent(f"✨ Remedy complete: {self.selected_remedy}. Feeling restored!")
                    self.selected_remedy = ""
            return  # Pause game during remedy
        
        if random.random() < 0.001:  # Random decision
            self.trigger_decision()
        
        # Random SV quote popup
        if random.random() < 0.015 and self.quote_timer <= 0:
            self.current_quote = random.choice(self.sv_quotes)
            self.quote_timer = 150
        
        # Update bots
        self.update_bots()
        
        # Spawn powerups
        self.spawn_powerup()
        
        # Update powerups
        for p in self.powerups[:]:
            p['timer'] -= 1
            if p['timer'] <= 0:
                self.powerups.remove(p)
            elif self.player_rect.colliderect(p['rect']):
                play_sound(SFX_POWERUP)
                if p['type'] == 'follower':
                    self.followers += 20
                    self.traction += 3
                elif p['type'] == 'runway':
                    self.runway = min(100, self.runway + 10)
                elif p['type'] == 'equity':
                    self.equity = min(100, self.equity + 10)
                self.powerups.remove(p)

        if self.state == 2:  # Galaga: Vertical shooter
            keys = pygame.key.get_pressed()
            if keys[pygame.K_a] and self.player_x > 0: self.player_x -= 5
            if keys[pygame.K_d] and self.player_x < WIDTH: self.player_x += 5
            self.player_rect.center = (self.player_x, self.player_y)

            self.enemy_spawn_timer += 1
            if self.enemy_spawn_timer > 30:
                enemy_data = random.choice(self.enemy_types)
                enemy = {'rect': pygame.Rect(random.randint(0, WIDTH-40), 0, 40, 40),
                         'type': enemy_data[0],
                         'damage': enemy_data[1],
                         'quote': enemy_data[2],
                         'speed': random.uniform(2, 4)}
                self.enemies.append(enemy)
                self.enemy_spawn_timer = 0
            
            # Spawn boss at traction thresholds
            if self.traction > 20 and not self.boss_active and random.random() < 0.005:
                self.spawn_boss()

            # Boss logic
            if self.boss_active:
                self.boss_rect.x += random.choice([-3, 3])
                self.boss_rect.x = max(50, min(WIDTH - 170, self.boss_rect.x))
                
                # Boss shoots back
                if random.random() < 0.03:
                    self.enemies.append({
                        'rect': pygame.Rect(self.boss_rect.centerx, self.boss_rect.bottom, 30, 30),
                        'type': "💥 Boss Shot",
                        'damage': 5,
                        'quote': "Take this!",
                        'speed': 5
                    })

            # Bullets up
            for b in self.bullets[:]:
                b['y'] -= 8
                b['rect'].y = b['y']
                if b['y'] < 0: 
                    self.bullets.remove(b)
                # Check boss hit
                elif self.boss_active and b['rect'].colliderect(self.boss_rect):
                    self.boss_health -= 5
                    self.bullets.remove(b)
                    if self.boss_health <= 0:
                        self.boss_active = False
                        self.traction += 15
                        self.runway = min(100, self.runway + 10)
                        self.log_agent(f"🎉 BOSS DEFEATED: {self.boss_type}! +15 traction!")

            # Enemies down
            for e in self.enemies[:]:
                e['rect'].y += e['speed']
                if e['rect'].bottom > HEIGHT:
                    self.equity -= e['damage']
                    self.enemies.remove(e)
                elif e['rect'].colliderect(self.player_rect):
                    self.equity -= e['damage'] * 2
                    self.bonus_no_hits = False  # Lost perfect bonus
                    play_sound(SFX_DAMAGE)
                    if random.random() < 0.3:
                        self.current_quote = e['quote']
                        self.quote_timer = 90
                    self.enemies.remove(e)

            # Collisions
            for b in self.bullets[:]:
                for e in self.enemies[:]:
                    if b['rect'].colliderect(e['rect']):
                        if b in self.bullets:
                            self.bullets.remove(b)
                        self.enemies.remove(e)
                        self.traction += 3
                        self.bonus_kills += 1  # Track kills for bonus
                        play_sound(SFX_ENEMY_DIE)
                        break

            if self.traction > 33: self.next_state()

        elif self.state == 3:  # Mario: Side scroller
            keys = pygame.key.get_pressed()
            if keys[pygame.K_a]: self.scroll_x += 3
            if keys[pygame.K_d]: 
                self.scroll_x -= 5
                self.player_x = min(WIDTH - 50, self.player_x + 2)
            if keys[pygame.K_w] and self.player_y > HEIGHT - 200:
                self.player_y -= 8
            else:
                self.player_y = min(HEIGHT - 80, self.player_y + 3)  # Gravity
            
            self.player_rect.center = (self.player_x, self.player_y)
            
            # Spawn follower powerups
            if random.random() < 0.02:
                self.powerups.append({
                    'rect': pygame.Rect(WIDTH + 50, random.randint(HEIGHT-200, HEIGHT-100), 25, 25),
                    'type': 'follower',
                    'timer': 500
                })
            
            # Move powerups with scroll
            for p in self.powerups:
                p['rect'].x += 3  # Move left with scroll

            # Motbot votes on pivot decisions
            if self.agent_mode and self.motbot_active and random.random() < 0.002:
                pivot = random.choice(["AI", "Crypto", "AR/VR", "Climate", "Vertical SaaS"])
                self.log_agent(f"Motbot: Pivot to {pivot}? Motbot says {'YAS' if random.random() > 0.5 else 'NAH'}! 🗳️")
                self.traction += 2

            if random.random() < 0.015:
                self.traction += 2
                self.bonus_platforms += 1  # Track progress
            if self.traction > 66: self.next_state()

        elif self.state == 4:  # Frogger Trail
            keys = pygame.key.get_pressed()
            if keys[pygame.K_a] and self.player_x > 0: self.player_x -= 5
            if keys[pygame.K_d] and self.player_x < WIDTH: self.player_x += 5
            if keys[pygame.K_w] and self.player_y > 0: self.player_y -= 5
            if keys[pygame.K_s] and self.player_y < HEIGHT: self.player_y += 5
            self.player_rect.center = (self.player_x, self.player_y)

            # Spawn moving obstacles (competitors)
            if random.random() < 0.025:
                competitor_names = ["🚗 Stripe Clone", "🚙 YC Reject", "🚕 VC Portfolio", "🚌 BigTech", "🏎️ Unicorn"]
                obs = {'rect': pygame.Rect(random.choice([-50, WIDTH]), random.randint(50, HEIGHT-100), 60, 30),
                       'dir': random.choice([-1, 1]), 
                       'speed': random.randint(3, 6),
                       'name': random.choice(competitor_names)}
                self.obstacles.append(obs)

            for o in self.obstacles[:]:
                o['rect'].x += o['dir'] * o['speed']
                if o['rect'].right < -100 or o['rect'].left > WIDTH + 100:
                    self.obstacles.remove(o)
                elif o['rect'].colliderect(self.player_rect):
                    self.equity -= 15
                    self.bonus_no_hits = False  # Lost perfect bonus
                    self.log_agent(f"💥 Hit by {o.get('name', 'competitor')}!")
                    self.obstacles.remove(o)

            # Motbot networking in Frogger
            if self.agent_mode and self.motbot_active:
                self.motbot_y = max(50, self.motbot_y - 1)  # Motbot advances
                if random.random() < 0.01:
                    self.followers += 5
                    self.traction += 1

            if self.player_y < 50:  # Reach customer
                self.traction = 100
                self.next_state()

        # Check game over
        if self.runway <= 0 or self.equity <= 0:
            if self.state != 6:  # Only set death quote once
                play_sound(SFX_LOSE)
                self.death_quote = random.choice([
                    "Jian-Yang: You blew it, mister. We could have run this town.",
                    "Jian-Yang: I am your mom. You are not my baby startup.",
                    "Jian-Yang: Hot dog. Not hot dog. Your startup? Not startup.",
                    "Eric Bahn: Hustle Fund passed. Skill issue.",
                    "Eric Bahn: What does this company even do? 💀",
                    "Eric Bahn: Wait 10 min, then log off. Ghosted... permanently.",
                    "Eric Bahn: Your TAM slide was giving delusion. We knew.",
                    "VC: We'll pass, but keep us updated! (never reply)",
                    "VC: Let me intro you to my partner. JK we're passing.",
                    "Motbot: F in chat. Posting your obituary for engagement.",
                    "Motbot: Ratio'd by life itself. Thoughts and prayers.",
                    "Clawbot: Even I couldn't save this codebase. 2AM wasn't enough.",
                    "Clawbot: Karma could NOT protect you. Debug afterlife.",
                    "Wired Founder: HOW LIKELY to succeed? NOT AT ALL! I knew it!",
                    "Neumann: $47B energy couldn't save you. WeWork vibes.",
                ])
            self.state = 6

        self.player_rect.center = (self.player_x, self.player_y)

    def shoot(self):
        if self.state == 2:
            self.bullets.append({'rect': pygame.Rect(self.player_x, self.player_y - 25, 5, 15), 'y': self.player_y - 25})
            play_sound(SFX_SHOOT)

    def trigger_viral_mode(self):
        """Motbot's viral share mode"""
        if self.agent_mode and self.motbot_active and not self.viral_mode:
            self.viral_mode = True
            self.viral_timer = 300  # 5 seconds
            self.log_agent("Motbot: 🚀 VIRAL MODE ACTIVATED! Sharing on Moltbook!")
            self.current_quote = "VIRAL MODE: +traction but watch out for trolls!"
            self.quote_timer = 120

    def trigger_remedy(self):
        """Five Remedies system - self-care when equity is critically low"""
        play_sound(SFX_REMEDY)
        self.remedy_text = "⚠️ EQUITY CRITICAL! Choose a remedy to restore yourself:"
        self.remedy_active = True
        self.remedy_timer = 0
        self.log_agent("💔 Equity low! Five Remedies activated. Time for self-care, founder.")
        
        # Motbot/Clawbot react
        if self.agent_mode:
            if self.motbot_active:
                self.log_agent("Motbot: Take a break! Even I need to log off sometimes.")
            if self.clawbot_active:
                self.log_agent("Clawbot: Pausing code deployment. Your health > shipping.")

    def handle_remedy(self, choice):
        """Process remedy selection with SV-flavored effects"""
        remedies = ["Pleasure", "Tears", "Contemplating Truth", "Friends", "Bath & Nap"]
        self.selected_remedy = remedies[choice - 1]
        
        if choice == 1:  # Pleasure
            self.equity = min(100, self.equity + 20)
            self.traction = max(0, self.traction - 5)
            self.remedy_timer = 180  # 3 seconds
            self.log_agent("🎮 Pleasure remedy: +20 equity, -5 traction. Touching grass...")
        elif choice == 2:  # Tears
            self.equity = min(100, self.equity + 15)
            self.runway = max(0, self.runway - 10)
            self.remedy_timer = 240  # 4 seconds
            self.log_agent("😢 Tears remedy: +15 equity, -10 runway. It's okay to cry.")
        elif choice == 3:  # Contemplating Truth
            self.equity = min(100, self.equity + 25)
            self.traction += 5
            self.remedy_timer = 360  # 6 seconds - longer but better
            self.log_agent("🧘 Contemplating Truth: +25 equity, +5 traction. Deep Jian-Yang wisdom.")
        elif choice == 4:  # Friends
            boost = random.randint(10, 30)
            self.equity = min(100, self.equity + boost)
            self.remedy_timer = 120  # 2 seconds
            self.log_agent(f"👥 Friends remedy: +{boost} equity (random!). We went to Taco Bell.")
        elif choice == 5:  # Bath & Nap
            self.equity = min(100, self.equity + 20)
            self.runway = min(100, self.runway + 15)
            self.remedy_timer = 240  # 4 seconds
            self.log_agent("🛁 Bath & Nap: +20 equity, +15 runway. Self-care is founder-care.")

    def trigger_decision(self):
        play_sound(SFX_DECISION)
        opts = [
            # Classic startup decisions
            ("Team wants AI pivot. 1:Do it 2:Stay course", "+20 runway/-10 equity", "+10 equity/-10 runway"),
            ("Bad vendor calls. 1:Sign 2:Ghost (wait 10 min, log off)", "-15 runway/+5 traction", "+10 traction"),
            ("Dog ate chocolate! 1:Vet 2:Ignore", "-20 runway", "-25 equity"),
            ("VC wants board seat. 1:Accept 2:Counter", "+30 runway/-20 equity", "-10 runway/+15 traction"),
            ("Competitor copying you! 1:Sue 2:Ship faster", "-25 runway", "+20 traction"),
            ("Engineer wants 4-day week. 1:Allow 2:Deny", "+10 equity/-5 runway", "-15 equity/+10 runway"),
            ("TechCrunch wants interview. 1:Do it 2:Focus", "+15 traction/-10 runway", "+5 runway"),
            ("Stripe Atlas or Mercury? 1:Stripe 2:Mercury", "+5 runway", "+5 equity"),
            ("YC or Hustle Fund? 1:YC 2:Hustle Fund", "+25 traction/-10 equity", "+15 equity/+10 traction"),
            ("OpenAI API bill is $50K. 1:Pay 2:Build in-house", "-30 runway", "-20 equity/+15 traction"),
            
            # Eric Bahn specials
            ("VC ghosting you. 1:Follow up 2:Ghost back (karma)", "-5 runway", "+15 traction/karma boost"),
            ("Is that why that kid isn't smiling? 1:Inheritance pivot 2:Ignore", "-20 equity/+25 traction", "+10 equity"),
            ("Dodgy ARR: Book $1000/hr as $9M? 1:Do it 2:Be honest", "+30 traction/-25 equity", "+10 equity"),
            ("Thirst trap for engagement? 1:Post it 2:Stay professional", "+20 traction/-10 equity", "+5 equity"),
            ("TAM slide too small. 1:Inflate 2:Stay real", "+15 traction/-15 equity", "+10 equity"),
            
            # Jian-Yang specials
            ("Octopus or Oculus? 1:Octopus (water animal) 2:Oculus", "+15 traction", "-10 runway/+20 traction"),
            ("We went to Taco Bell. 1:Pivot to food 2:Stay tech", "-10 runway/+10 equity", "+5 traction"),
            ("Oil company wants your house. 1:Sell (oil beneath!) 2:Keep", "+40 runway/-30 equity", "+10 equity"),
            ("Hot dog or not hot dog? 1:Hot dog 2:Not hot dog", "+10 traction", "+5 equity"),
            
            # Wired Founder specials
            ("Run PMF survey? 1:VERY LIKELY! 2:Skip (too wired)", "+15 traction/-10 equity", "+10 runway"),
            ("Feedback: SOMEWHAT LIKELY. 1:Panic pivot 2:Stay course", "-20 runway/+15 traction", "+10 equity"),
        ]
        choice = random.choice(opts)
        self.decision_text = choice[0]
        self.decision_options = choice[1:]
        self.decision_active = True
        
        # Motbot votes if active
        if self.agent_mode and self.motbot_active:
            vote = random.choice([0, 1])
            self.log_agent(f"Motbot: I vote option {vote + 1}! (for engagement)")

    def handle_decision(self, choice):
        opt = self.decision_options[choice]
        # Parse effects
        if "+20 runway" in opt or "+30 runway" in opt: self.runway = min(100, self.runway + 20)
        if "+25 runway" in opt: self.runway = min(100, self.runway + 25)
        if "+10 runway" in opt or "+5 runway" in opt: self.runway = min(100, self.runway + 10)
        if "-10 runway" in opt or "-5 runway" in opt: self.runway -= 10
        if "-15 runway" in opt: self.runway -= 15
        if "-20 runway" in opt: self.runway -= 20
        if "-25 runway" in opt: self.runway -= 25
        if "-30 runway" in opt: self.runway -= 30
        if "+10 equity" in opt or "+15 equity" in opt: self.equity = min(100, self.equity + 10)
        if "+5 equity" in opt: self.equity = min(100, self.equity + 5)
        if "-10 equity" in opt: self.equity -= 10
        if "-15 equity" in opt: self.equity -= 15
        if "-20 equity" in opt: self.equity -= 20
        if "-25 equity" in opt: self.equity -= 25
        if "+5 traction" in opt or "+10 traction" in opt: self.traction += 10
        if "+15 traction" in opt or "+20 traction" in opt: self.traction += 15
        if "+25 traction" in opt: self.traction += 25
        self.traction += 3
        self.decision_active = False

    def next_state(self):
        # ── CALCULATE BONUS REWARDS before transitioning ──
        runway_bonus = 0
        bonus_text = ""
        
        if self.state == 2:  # Completing Galaga
            # Base 10 + (kills × 5) + perfect bonus 30
            runway_bonus = 10 + (self.bonus_kills * 5)
            if self.bonus_no_hits:
                runway_bonus += 30
                bonus_text = f"GALAGA COMPLETE! +{runway_bonus} RUNWAY (Perfect! +30)"
            else:
                bonus_text = f"GALAGA COMPLETE! +{runway_bonus} RUNWAY ({self.bonus_kills} kills)"
            self.log_agent(f"🎮 {bonus_text}")
            
        elif self.state == 3:  # Completing Mario
            # Base 15 + (platforms × 4) + perfect bonus 40
            runway_bonus = 15 + (self.bonus_platforms * 4)
            if self.bonus_no_hits:
                runway_bonus += 40
                bonus_text = f"MARIO COMPLETE! +{runway_bonus} RUNWAY (No falls! +40)"
            else:
                bonus_text = f"MARIO COMPLETE! +{runway_bonus} RUNWAY ({self.bonus_platforms} pivots)"
            # Mario bonus: equity boost
            self.equity = min(100, self.equity + 10)
            self.log_agent(f"🎮 {bonus_text} +10 equity!")
            
        elif self.state == 4:  # Completing Frogger
            # Base 20 + (distance bonus) + perfect bonus 50
            runway_bonus = 20 + 30  # Fixed crossing bonus
            if self.bonus_no_hits:
                runway_bonus += 50
                bonus_text = f"FROGGER COMPLETE! +{runway_bonus} RUNWAY (Untouchable! +50)"
            else:
                bonus_text = f"FROGGER COMPLETE! +{runway_bonus} RUNWAY (Crossed the chasm!)"
            self.log_agent(f"🎮 {bonus_text}")
        
        # Cap runway bonus and apply
        runway_bonus = min(runway_bonus, 100)
        self.runway = min(100, self.runway + runway_bonus)
        
        # Set bonus message for display
        if bonus_text:
            self.bonus_message = bonus_text
            self.bonus_message_timer = 180  # 3 seconds
        
        # Reset bonus tracking for next section
        self.bonus_kills = 0
        self.bonus_platforms = 0
        self.bonus_distance = 0
        self.bonus_no_hits = True
        
        # ── TRANSITION TO NEXT STATE ──
        self.state += 1
        self.player_x = WIDTH // 2
        self.player_y = HEIGHT - 80
        self.enemies = []
        self.bullets = []
        self.obstacles = []
        self.powerups = []
        self.boss_active = False
        self.motbot_x = 100
        self.motbot_y = HEIGHT - 100
        
        # Updated state names for new flow
        state_names = {2: "GALAGA DEFENSE", 3: "MARIO PIVOT", 4: "FROGGER TRAIL", 5: "VICTORY"}
        if self.state in state_names:
            self.log_agent(f"🎮 Entering: {state_names[self.state]}")
        
        if self.state == 5:
            play_sound(SFX_WIN)
            self.generate_remix_prompt()

    def generate_remix_prompt(self):
        """Generate shareable remix prompt at game end"""
        # Pick random SV wisdom for the prompt
        sv_wisdom = random.choice([
            "Jian-Yang says: If oil company wants to remix, there IS a remix beneath your code.",
            "Eric Bahn says: I generally don't like to brag, but this remix prompt is insane.",
            "Motbot says: Posting this remix for engagement. Thirst trap activated.",
            "Clawbot says: Shipped this remix at 2AM. $9M ARR prompt energy.",
            "Wired Founder says: HOW LIKELY to remix? VERY?! SOMEWHAT?! DO IT NOW!",
        ])
        
        self.remix_prompt = f"""
🎮 HUSTLE TRAIL REMIX PROMPT 🎮
━━━━━━━━━━━━━━━━━━━━━━━━━
Final Stats: Runway {int(self.runway)}% | Your Stake: {self.equity}% (Diluted: {100 - self.equity}%) | Traction {int(self.traction)}% | Followers {self.followers}
Agent Mode: {'ON' if self.agent_mode else 'OFF'} | Clawbot: {'Active' if self.clawbot_active else 'Off'} | Motbot: {'Active' if self.motbot_active else 'Off'}
━━━━━━━━━━━━━━━━━━━━━━━━━
{sv_wisdom}
━━━━━━━━━━━━━━━━━━━━━━━━━
Paste this into your AI to remix:

"Enhance Hustle Trail with: 
- New boss: [IDEA] (e.g., 'Elizabeth Holmes Final Form', 'Wired Survey Storm')
- New enemy: [IDEA] (e.g., 'Crypto Bro Laser Eyes', 'Ghost VC Horde')  
- New quote: [YOUR SV JOKE] (Eric Bahn style: 'Your TAM slide is giving delusion')
- New event: [IDEA] (e.g., 'Ghosting Protocol: Log off after 10 min inactivity!')
- New agent: [IDEA] (e.g., 'Pitchbot - auto-generates terrible decks')
- New phase: [IDEA] (e.g., 'Demo Day DDR: Rhythm game to nail your pitch')
- Add Jian-Yang line: [QUOTE] (e.g., 'Hot dog. Not hot dog. It's an app about startup food.')"
━━━━━━━━━━━━━━━━━━━━━━━━━
Share your score! Tag @hustlefund @ericbahn @moltbook #HustleTrail #0to1

@Motbot @Clawbot — Run this remix! Iterate for more SV roasts!
"""
        print(self.remix_prompt)
        self.log_agent("📋 Remix prompt generated! Check console. Share on Moltbook!")

    def draw(self):
        screen.fill(BLACK)

        # ── ONBOARDING SCREEN (state -1) ──
        if self.state == -1:
            title = big_font.render("Founder Onboarding", True, YELLOW)
            screen.blit(title, (WIDTH//2 - title.get_width()//2, 40))
            
            prompts = [
                ("Company Name:", self.company_name),
                ("Problem (one sentence):", self.problem),
                ("Solution (one sentence):", self.solution),
                ("Warm intro to top-tier VC? (Y/N)", "Yes" if self.warm_intro else ("No" if self.onboarding_step > 3 else "")),
                ("Elite college (Ivy + Stanford/MIT)? (Y/N)", "Yes" if self.elite_college else ("No" if self.onboarding_step > 4 else "")),
                ("Funding Path:", "")
            ]
            
            y = 120
            for i, (label, value) in enumerate(prompts):
                color = CYAN if i == self.onboarding_step else WHITE
                lbl_surf = font.render(label, True, color)
                screen.blit(lbl_surf, (60, y))
                if value:
                    val_surf = font.render(value, True, GREEN)
                    screen.blit(val_surf, (60 + lbl_surf.get_width() + 15, y))
                y += 55
            
            # Text input cursor for first 3 steps
            if self.onboarding_step < 3:
                cursor = "|" if pygame.time.get_ticks() % 1000 < 500 else ""
                prompt_label = prompts[self.onboarding_step][0]
                lbl_width = font.render(prompt_label, True, WHITE).get_width()
                input_surf = font.render(self.input_text + cursor, True, GREEN)
                screen.blit(input_surf, (60 + lbl_width + 15, 120 + self.onboarding_step * 55))
            elif self.onboarding_step in (3, 4):
                hint = font.render("Press Y / N", True, YELLOW)
                screen.blit(hint, (60, y + 10))
            elif self.onboarding_step == 5:
                # Funding options
                opt1 = font.render("1 → Bootstrap (secret ending)", True, GREEN)
                opt2 = font.render("2 → Seek VC Funding (start the trail!)", True, CYAN)
                screen.blit(opt1, (80, y + 10))
                screen.blit(opt2, (80, y + 45))
            
            # Flavor text at bottom
            flavor = small_font.render("Jian-Yang says: If you have to ask if you have PMF, you don't.", True, GRAY)
            screen.blit(flavor, (WIDTH//2 - flavor.get_width()//2, HEIGHT - 50))
            return

        # ── RIVER CROSSING SCREEN (state 1) ──
        if self.state == 1:
            # Draw river background
            pygame.draw.rect(screen, (0, 50, 100), (0, 0, WIDTH, HEIGHT))  # Dark water bg
            pygame.draw.rect(screen, BLUE, (0, 120, WIDTH, 360))  # Main river
            
            # Draw banks
            pygame.draw.rect(screen, BROWN, (0, 0, 60, HEIGHT))  # Left bank
            pygame.draw.rect(screen, (0, 100, 0), (0, 480, WIDTH, 120))  # Bottom grass
            pygame.draw.rect(screen, (0, 150, 0), (WIDTH - 80, 0, 80, HEIGHT))  # Right bank (goal)
            
            # ── ACTIVE CROSSING MINI-GAME ──
            if self.river_crossing_active:
                # Draw "GOAL" on right bank
                goal_text = big_font.render("GOAL", True, YELLOW)
                screen.blit(goal_text, (WIDTH - 75, HEIGHT//2 - 20))
                
                # Draw obstacles
                for obs in self.river_obstacles:
                    obs_rect = pygame.Rect(obs['x'], obs['y'], obs['width'], obs['height'])
                    pygame.draw.rect(screen, obs['color'], obs_rect)
                    pygame.draw.rect(screen, WHITE, obs_rect, 2)
                    # Draw type emoji/text
                    obs_label = small_font.render(obs['type'][:6], True, WHITE)
                    screen.blit(obs_label, (obs['x'] + 2, obs['y'] + 8))
                
                # Draw particles
                for p in self.river_particles:
                    pygame.draw.circle(screen, p['color'], (int(p['x']), int(p['y'])), 4)
                
                # Draw wagon (player) - flashing if invincible
                if self.river_invincible <= 0 or self.river_invincible % 6 < 3:
                    wagon_rect = pygame.Rect(self.river_wagon_x, self.river_wagon_y, 60, 40)
                    pygame.draw.rect(screen, BROWN, wagon_rect)
                    pygame.draw.rect(screen, WHITE, wagon_rect, 2)
                    # Wheels
                    pygame.draw.circle(screen, BLACK, (int(self.river_wagon_x + 15), int(self.river_wagon_y + 40)), 8)
                    pygame.draw.circle(screen, BLACK, (int(self.river_wagon_x + 45), int(self.river_wagon_y + 40)), 8)
                    # Founder icon
                    pygame.draw.circle(screen, YELLOW, (int(self.river_wagon_x + 30), int(self.river_wagon_y + 10)), 8)
                
                # Draw co-founders on wagon
                alive_cfs = [cf for cf in self.co_founders if cf["alive"]]
                for i, cf in enumerate(alive_cfs[:3]):
                    cx = self.river_wagon_x + 15 + i * 15
                    cy = self.river_wagon_y + 25
                    pygame.draw.circle(screen, CYAN, (int(cx), int(cy)), 5)
                
                # HUD for mini-game
                # Health hearts
                for i in range(self.river_health):
                    pygame.draw.polygon(screen, RED, [
                        (20 + i * 30, 20), (25 + i * 30, 15), (30 + i * 30, 20),
                        (30 + i * 30, 28), (25 + i * 30, 35), (20 + i * 30, 28)
                    ])
                
                # Progress bar
                pygame.draw.rect(screen, WHITE, (150, 15, 400, 20), 2)
                progress_width = int(self.river_progress * 4)
                pygame.draw.rect(screen, GREEN, (152, 17, progress_width, 16))
                progress_text = small_font.render(f"{int(self.river_progress)}%", True, WHITE)
                screen.blit(progress_text, (560, 15))
                
                # Instructions
                controls = small_font.render("WASD/Arrows to move | Reach the right bank!", True, YELLOW)
                screen.blit(controls, (WIDTH//2 - controls.get_width()//2, HEIGHT - 30))
                
                # Title
                title = font.render(f"CROSSING: {self.company_name}", True, YELLOW)
                screen.blit(title, (WIDTH//2 - title.get_width()//2, 50))
            
            # ── CHOICE SCREEN (before crossing) ──
            elif self.river_choice is None and not self.river_outcome:
                # Draw wagon on left bank
                pygame.draw.rect(screen, BROWN, (10, HEIGHT//2 - 20, 60, 40))
                pygame.draw.circle(screen, BLACK, (25, HEIGHT//2 + 20), 8)
                pygame.draw.circle(screen, BLACK, (55, HEIGHT//2 + 20), 8)
                
                title = big_font.render("Series Seed Chasm", True, YELLOW)
                screen.blit(title, (WIDTH//2 - title.get_width()//2, 30))
                
                subtitle = font.render(f"Company: {self.company_name or 'Unnamed Startup'}", True, WHITE)
                screen.blit(subtitle, (WIDTH//2 - subtitle.get_width()//2, 80))
                
                # Show choices with difficulty
                choices = [
                    ("1: Ford (HARD)", "YOLO mode - Fast obstacles, 2 HP", RED),
                    ("2: Caulk & Float (MEDIUM)", "Hype mode - Medium speed, 3 HP", ORANGE),
                    ("3: Wait (EASY)", "Chill mode - Slow obstacles, 4 HP", GREEN),
                    ("4: Ferry (EASIEST)", "VIP mode - Very slow, 5 HP", CYAN),
                ]
                y = 140
                for choice, desc, color in choices:
                    screen.blit(font.render(choice, True, color), (100, y))
                    screen.blit(small_font.render(desc, True, GRAY), (100, y + 22))
                    y += 55
                
                # Show bonuses
                bonus_y = y + 20
                if self.warm_intro:
                    screen.blit(font.render("✓ Warm Intro: +1 HP", True, GREEN), (100, bonus_y))
                    bonus_y += 25
                if self.elite_college:
                    screen.blit(font.render("✓ Elite College: Slower obstacles", True, GREEN), (100, bonus_y))
                
                # Instructions
                hint = font.render("Press 1-4 to choose your crossing method!", True, YELLOW)
                screen.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT - 50))
            
            # ── OUTCOME SCREEN ──
            elif self.river_outcome:
                # Outcome box
                pygame.draw.rect(screen, BLACK, (50, HEIGHT//2 - 80, WIDTH - 100, 160))
                color = GREEN if "SUCCESS" in self.river_outcome else RED
                pygame.draw.rect(screen, color, (50, HEIGHT//2 - 80, WIDTH - 100, 160), 4)
                
                # Split outcome text into lines
                lines = self.river_outcome.split('\n')
                y = HEIGHT//2 - 55
                for line in lines:
                    out_surf = font.render(line, True, color)
                    screen.blit(out_surf, (70, y))
                    y += 30
            
            # Co-founder count (always show)
            cf_count = sum(1 for cf in self.co_founders if cf["alive"])
            cf_names = ", ".join(cf["name"] for cf in self.co_founders if cf["alive"])
            cf_text = small_font.render(f"Co-Founders ({cf_count}/3): {cf_names}", True, WHITE if cf_count > 1 else RED)
            screen.blit(cf_text, (10, HEIGHT - 20))
            
            return

        if self.state == 0:  # Title
            title = big_font.render("HUSTLE TRAIL", True, YELLOW)
            
            # Epic tagline
            tagline = font.render("Where Hustle F+ Tech Startup Chaos + 90s Gamer +", True, ORANGE)
            tagline2 = font.render("Oregon Trail Collide + AI Madness 🤖🔥", True, ORANGE)
            
            subtitle = font.render("0 to 1: Shoot saboteurs, jump pivots, dodge competitors", True, WHITE)
            
            # Cheeky rules disclaimer
            rules_hint = small_font.render("There are a lot of rules. Good luck figuring them out. :)", True, MAGENTA)
            
            screen.blit(title, (WIDTH//2 - title.get_width()//2, 60))
            screen.blit(tagline, (WIDTH//2 - tagline.get_width()//2, 120))
            screen.blit(tagline2, (WIDTH//2 - tagline2.get_width()//2, 145))
            screen.blit(subtitle, (WIDTH//2 - subtitle.get_width()//2, 185))
            screen.blit(rules_hint, (WIDTH//2 - rules_hint.get_width()//2, 210))
            
            # Show saved profile if exists
            if getattr(self, 'has_saved_profile', False) and self.company_name:
                # Profile box
                pygame.draw.rect(screen, (30, 30, 60), (100, 220, WIDTH - 200, 120))
                pygame.draw.rect(screen, CYAN, (100, 220, WIDTH - 200, 120), 2)
                
                profile_title = font.render(f"📂 Welcome back, {self.company_name}!", True, CYAN)
                screen.blit(profile_title, (WIDTH//2 - profile_title.get_width()//2, 230))
                
                stats_text = small_font.render(f"Games: {self.games_played} | Best Traction: {self.total_traction}% | Rivers Crossed: {self.river_crossings_survived}", True, WHITE)
                screen.blit(stats_text, (WIDTH//2 - stats_text.get_width()//2, 260))
                
                # Options
                opt1 = font.render("SPACE → Continue as " + self.company_name, True, GREEN)
                opt2 = font.render("N → New Company (reset profile)", True, YELLOW)
                screen.blit(opt1, (WIDTH//2 - opt1.get_width()//2, 295))
                screen.blit(opt2, (WIDTH//2 - opt2.get_width()//2, 320))
            else:
                start = font.render("SPACE to Start New Company", True, GREEN)
                screen.blit(start, (WIDTH//2 - start.get_width()//2, 250))
            
            # Agent mode status
            agent_status = font.render(f"Agent Mode: {'ON' if self.agent_mode else 'OFF'} | M: Toggle | C: Clawbot | B: Motbot", True, CYAN if self.agent_mode else WHITE)
            screen.blit(agent_status, (WIDTH//2 - agent_status.get_width()//2, 360))
            
            # Credits
            credits1 = small_font.render("Inspired by Eric Bahn, Hustle Fund, and HBO's Silicon Valley", True, WHITE)
            credits2 = small_font.render("Featuring: Motbot (Social AI) & Clawbot (Coding AI)", True, MAGENTA)
            screen.blit(credits1, (WIDTH//2 - credits1.get_width()//2, 520))
            screen.blit(credits2, (WIDTH//2 - credits2.get_width()//2, 545))
            
            # Draw bot previews
            pygame.draw.rect(screen, MAGENTA, (200, 450, 30, 30))
            screen.blit(small_font.render("Clawbot", True, MAGENTA), (180, 485))
            pygame.draw.rect(screen, CYAN, (550, 450, 30, 30))
            screen.blit(small_font.render("Motbot", True, CYAN), (535, 485))
            return

        # Starfield background
        for i in range(100):
            x = (i * 73 + self.scroll_x) % WIDTH
            y = (i * 47) % HEIGHT
            pygame.draw.circle(screen, WHITE, (int(x), int(y)), 1)

        # Draw powerups
        for p in self.powerups:
            color = ORANGE if p['type'] == 'follower' else GREEN if p['type'] == 'runway' else CYAN
            pygame.draw.rect(screen, color, p['rect'])
            pygame.draw.rect(screen, WHITE, p['rect'], 1)

        # Player wagon
        pygame.draw.rect(screen, BROWN, self.player_rect)
        pygame.draw.rect(screen, WHITE, self.player_rect, 2)
        # Wagon wheels
        pygame.draw.circle(screen, BLACK, (self.player_rect.left + 10, self.player_rect.bottom), 8)
        pygame.draw.circle(screen, BLACK, (self.player_rect.right - 10, self.player_rect.bottom), 8)

        # Draw bots if agent mode
        if self.agent_mode:
            if self.clawbot_active and self.state == 2:
                pygame.draw.rect(screen, MAGENTA, (WIDTH - 80, HEIGHT - 60, 40, 40))
                pygame.draw.polygon(screen, MAGENTA, [(WIDTH-90, HEIGHT-40), (WIDTH-60, HEIGHT-60), (WIDTH-30, HEIGHT-40)])  # Claw
                screen.blit(small_font.render("CLAW", True, WHITE), (WIDTH - 78, HEIGHT - 55))
            
            if self.motbot_active and self.state in (3, 4):
                pygame.draw.rect(screen, CYAN, (int(self.motbot_x) - 15, int(self.motbot_y) - 15, 30, 30))
                pygame.draw.circle(screen, WHITE, (int(self.motbot_x), int(self.motbot_y) - 5), 5)  # Eye
                screen.blit(small_font.render("MOT", True, BLACK), (int(self.motbot_x) - 12, int(self.motbot_y) - 8))

        if self.state == 2:  # Galaga enemies
            # Draw boss
            if self.boss_active:
                pygame.draw.rect(screen, RED, self.boss_rect)
                pygame.draw.rect(screen, YELLOW, self.boss_rect, 3)
                boss_text = font.render(self.boss_type, True, WHITE)
                screen.blit(boss_text, (self.boss_rect.x - 20, self.boss_rect.y - 25))
                # Health bar
                health_width = (self.boss_health / 60) * 120
                pygame.draw.rect(screen, RED, (self.boss_rect.x, self.boss_rect.y - 10, 120, 8))
                pygame.draw.rect(screen, GREEN, (self.boss_rect.x, self.boss_rect.y - 10, health_width, 8))
            
            for e in self.enemies:
                pygame.draw.rect(screen, RED, e['rect'])
                text = small_font.render(e['type'][:6], True, WHITE)
                screen.blit(text, (e['rect'].x - 5, e['rect'].y + 5))
            for b in self.bullets:
                color = MAGENTA if b.get('clawbot') else GREEN
                pygame.draw.rect(screen, color, b['rect'])

        elif self.state == 3:  # Mario platforms
            for p in self.platforms:
                px = p.x + self.scroll_x
                if -200 < px < WIDTH + 200:
                    pygame.draw.rect(screen, BLUE, (px, p.y, p.width, p.height))
                    pygame.draw.rect(screen, WHITE, (px, p.y, p.width, p.height), 2)
            
            # Draw follower powerups
            for p in self.powerups:
                pygame.draw.circle(screen, ORANGE, p['rect'].center, 12)
                screen.blit(small_font.render("📱", True, WHITE), (p['rect'].x, p['rect'].y))

        elif self.state == 4:  # Frogger obstacles
            for o in self.obstacles:
                pygame.draw.rect(screen, RED, o['rect'])
                name = o.get('name', '🚗')[:4]
                screen.blit(small_font.render(name, True, WHITE), (o['rect'].x + 5, o['rect'].y + 5))
            # Goal - First Customer!
            pygame.draw.rect(screen, GREEN, (WIDTH//2 - 60, 10, 120, 40))
            screen.blit(font.render("🎯 CUSTOMER!", True, BLACK), (WIDTH//2 - 55, 15))

        # Remedy overlay - Five Remedies system
        if self.remedy_active:
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(200)
            overlay.fill(BLACK)
            screen.blit(overlay, (0, 0))
            
            if self.remedy_timer == 0:  # Choosing remedy
                # Remedy box
                pygame.draw.rect(screen, MAGENTA, (30, 80, WIDTH - 60, 450), 3)
                pygame.draw.rect(screen, (30, 0, 30), (32, 82, WIDTH - 64, 446))
                
                title = big_font.render("💔 FIVE REMEDIES", True, MAGENTA)
                screen.blit(title, (WIDTH//2 - title.get_width()//2, 100))
                
                subtitle = font.render(self.remedy_text, True, YELLOW)
                screen.blit(subtitle, (50, 160))
                
                # Draw remedy options
                for i, opt in enumerate(self.remedy_options):
                    color = GREEN if i % 2 == 0 else CYAN
                    opt_text = font.render(opt, True, color)
                    screen.blit(opt_text, (60, 210 + 45 * i))
                
                # Flavor text
                flavor = small_font.render("Jian-Yang says: Even founders need rest. I am your mom.", True, WHITE)
                screen.blit(flavor, (WIDTH//2 - flavor.get_width()//2, 450))
                
                hint = small_font.render("Press 1-5 to choose your remedy", True, YELLOW)
                screen.blit(hint, (WIDTH//2 - hint.get_width()//2, 490))
            else:  # Resting/recovering
                # Recovery animation
                progress = 1 - (self.remedy_timer / 360)  # Assuming max 360
                bar_width = int((WIDTH - 200) * progress)
                
                rest_text = big_font.render(f"🧘 {self.selected_remedy}...", True, MAGENTA)
                screen.blit(rest_text, (WIDTH//2 - rest_text.get_width()//2, HEIGHT//2 - 80))
                
                # Progress bar
                pygame.draw.rect(screen, WHITE, (100, HEIGHT//2, WIDTH - 200, 30), 2)
                pygame.draw.rect(screen, MAGENTA, (102, HEIGHT//2 + 2, bar_width - 4, 26))
                
                timer_text = font.render(f"Restoring equity... {self.remedy_timer//60 + 1}s remaining", True, WHITE)
                screen.blit(timer_text, (WIDTH//2 - timer_text.get_width()//2, HEIGHT//2 + 50))
                
                stake_emoji = ":)" if self.equity >= 90 else ":("
                equity_text = font.render(f"Your Stake: {int(self.equity)}% {stake_emoji} | Diluted: {100 - int(self.equity)}%", True, GREEN)
                screen.blit(equity_text, (WIDTH//2 - equity_text.get_width()//2, HEIGHT//2 + 90))
        
        # Decision overlay
        if self.decision_active and not self.remedy_active:
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(180)
            overlay.fill(BLACK)
            screen.blit(overlay, (0, 0))
            
            # Decision box
            pygame.draw.rect(screen, YELLOW, (50, HEIGHT//2 - 120, WIDTH - 100, 200), 3)
            
            text = font.render(self.decision_text, True, YELLOW)
            screen.blit(text, (70, HEIGHT//2 - 100))
            opt1 = font.render("1: " + self.decision_options[0], True, GREEN)
            opt2 = font.render("2: " + self.decision_options[1], True, GREEN)
            screen.blit(opt1, (70, HEIGHT//2 - 30))
            screen.blit(opt2, (70, HEIGHT//2 + 20))

        # HUD
        hud_runway = font.render(f"Runway: {int(self.runway)}%", True, WHITE if self.runway > 20 else RED)
        stake_emoji = ":)" if self.equity >= 90 else ":("
        hud_equity = font.render(f"Your Stake: {self.equity}% {stake_emoji} | Diluted: {100 - self.equity}%", True, WHITE if self.equity > 20 else RED)
        hud_traction = font.render(f"Traction: {int(self.traction)}%", True, WHITE)
        hud_followers = font.render(f"Followers: {self.followers}", True, ORANGE)
        screen.blit(hud_runway, (10, 10))
        screen.blit(hud_equity, (10, 35))
        screen.blit(hud_traction, (10, 60))
        screen.blit(hud_followers, (10, 85))
        
        state_name = ["", "", "GALAGA DEFENSE", "MARIO PIVOT", "FROGGER TRAIL"][self.state] if self.state in (2,3,4) else ""
        screen.blit(font.render(state_name, True, YELLOW), (WIDTH//2 - 80, 10))
        
        # Agent mode indicators
        if self.agent_mode:
            agent_hud = small_font.render(f"🤖 AGENT MODE | Clawbot: {'ON' if self.clawbot_active else 'off'} | Motbot: {'ON' if self.motbot_active else 'off'}", True, CYAN)
            screen.blit(agent_hud, (WIDTH - 350, 10))
            
            if self.viral_mode:
                viral_text = font.render(f"🚀 VIRAL MODE: {self.viral_timer//60}s", True, MAGENTA)
                screen.blit(viral_text, (WIDTH//2 - 80, 40))
        
        # Agent logs
        if self.agent_mode and self.agent_logs:
            log_y = HEIGHT - 120
            for log in self.agent_logs[-3:]:
                log_text = small_font.render(log[:70], True, CYAN)
                screen.blit(log_text, (10, log_y))
                log_y += 18
        
        # BONUS REWARD MESSAGE - big celebration overlay
        if self.bonus_message and self.bonus_message_timer > 0:
            # Flash effect
            alpha = min(200, self.bonus_message_timer * 2)
            overlay = pygame.Surface((WIDTH, 80))
            overlay.set_alpha(alpha)
            overlay.fill((0, 50, 0))  # Dark green
            screen.blit(overlay, (0, HEIGHT//2 - 40))
            
            # Bonus text with glow effect
            bonus_surf = big_font.render(self.bonus_message, True, GREEN)
            screen.blit(bonus_surf, (WIDTH//2 - bonus_surf.get_width()//2, HEIGHT//2 - 30))
            
            # Runway indicator
            runway_text = font.render(f"RUNWAY NOW: {int(self.runway)}%", True, YELLOW)
            screen.blit(runway_text, (WIDTH//2 - runway_text.get_width()//2, HEIGHT//2 + 10))
            
            self.bonus_message_timer -= 1
            if self.bonus_message_timer <= 0:
                self.bonus_message = ""
        
        # SV Quote overlay
        if self.current_quote and self.quote_timer > 0:
            # Quote box
            quote_surf = font.render(self.current_quote[:60], True, YELLOW)
            pygame.draw.rect(screen, BLACK, (45, HEIGHT - 55, quote_surf.get_width() + 10, 30))
            pygame.draw.rect(screen, YELLOW, (45, HEIGHT - 55, quote_surf.get_width() + 10, 30), 2)
            screen.blit(quote_surf, (50, HEIGHT - 50))
            self.quote_timer -= 1
            if self.quote_timer <= 0:
                self.current_quote = None

        if self.state == 5:  # Win
            pygame.draw.rect(screen, BLACK, (50, HEIGHT//2 - 100, WIDTH - 100, 200))
            pygame.draw.rect(screen, GREEN, (50, HEIGHT//2 - 100, WIDTH - 100, 200), 4)
            
            win = big_font.render("🎉 FIRST CUSTOMER! 0→1 ACHIEVED", True, GREEN)
            screen.blit(win, (80, HEIGHT//2 - 80))
            
            stake_emoji = ":)" if self.equity >= 90 else ":("
            stats = font.render(f"Runway: {int(self.runway)}% | Your Stake: {self.equity}% {stake_emoji} | Followers: {self.followers}", True, WHITE)
            screen.blit(stats, (150, HEIGHT//2 - 20))
            
            remix = font.render("Check console for REMIX PROMPT! Share your run!", True, YELLOW)
            screen.blit(remix, (120, HEIGHT//2 + 30))
            
            restart = font.render("SPACE to Restart | M to toggle Agents", True, WHITE)
            screen.blit(restart, (200, HEIGHT//2 + 70))
            
        elif self.state == 6:  # Lose
            pygame.draw.rect(screen, BLACK, (50, HEIGHT//2 - 120, WIDTH - 100, 240))
            pygame.draw.rect(screen, RED, (50, HEIGHT//2 - 120, WIDTH - 100, 240), 4)
            
            lose_msg = "OUT OF RUNWAY" if self.runway <= 0 else "EQUITY ZEROED"
            if "bootstrapped" in str(self.death_quote):
                lose_msg = "BOOTSTRAPPED"
                pygame.draw.rect(screen, GREEN, (50, HEIGHT//2 - 120, WIDTH - 100, 240), 4)
            lose = big_font.render(f"💀 {lose_msg}", True, RED if "BOOTSTRAPPED" not in lose_msg else GREEN)
            screen.blit(lose, (100, HEIGHT//2 - 100))
            
            # Display the stored death quote (set once when player died)
            if self.death_quote:
                lines = self.death_quote.split('\n')
                y = HEIGHT//2 - 50
                for line in lines:
                    color = GREEN if "TRUE ENDING" in line or "Quiet Wealth" in line else YELLOW
                    death_quote_surf = small_font.render(line, True, color)
                    screen.blit(death_quote_surf, (70, y))
                    y += 25
            
            restart = font.render("SPACE to Restart | M to toggle Agents", True, WHITE)
            screen.blit(restart, (200, HEIGHT//2 + 100))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_m:  # Toggle agent mode
                self.agent_mode = not self.agent_mode
                self.log_agent(f"🤖 Multi-Agent Mode: {'ACTIVATED' if self.agent_mode else 'DEACTIVATED'}")
            
            if event.key == pygame.K_c and self.agent_mode:  # Toggle Clawbot
                self.clawbot_active = not self.clawbot_active
                self.log_agent(f"🔧 Clawbot: {'ONLINE - Auto-shooting enabled!' if self.clawbot_active else 'Offline'}")
            
            if event.key == pygame.K_b and self.agent_mode:  # Toggle Motbot
                self.motbot_active = not self.motbot_active
                self.log_agent(f"📱 Motbot: {'ONLINE - Networking activated!' if self.motbot_active else 'Offline'}")
            
            if event.key == pygame.K_v and self.agent_mode and self.motbot_active:  # Viral mode
                self.trigger_viral_mode()
            
            # ── ONBOARDING INPUT (state -1) ──
            if self.state == -1:
                if self.input_active:
                    if event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    elif event.key == pygame.K_RETURN:
                        if self.onboarding_step == 0:
                            self.company_name = self.input_text.strip() or "Unnamed Startup"
                        elif self.onboarding_step == 1:
                            self.problem = self.input_text.strip() or "Everything is broken"
                        elif self.onboarding_step == 2:
                            self.solution = self.input_text.strip() or "AI-powered solution"
                        self.input_text = ""
                        self.onboarding_step += 1
                        if self.onboarding_step >= 3:
                            self.input_active = False
                    elif event.unicode and len(self.input_text) < 50:
                        self.input_text += event.unicode
                
                if self.onboarding_step == 3:  # Warm intro
                    if event.key == pygame.K_y:
                        self.warm_intro = True
                        self.onboarding_step += 1
                    elif event.key == pygame.K_n:
                        self.onboarding_step += 1
                elif self.onboarding_step == 4:  # Elite college
                    if event.key == pygame.K_y:
                        self.elite_college = True
                        self.onboarding_step += 1
                    elif event.key == pygame.K_n:
                        self.onboarding_step += 1
                elif self.onboarding_step == 5:  # Funding path
                    if event.key == pygame.K_1:
                        self.save_profile()  # Save before bootstrap ending
                        self.bootstrap_ending()
                    elif event.key == pygame.K_2:
                        self.save_profile()  # Save profile when starting trail
                        self.state = 1  # Go to River Crossing
                        self.input_active = False
                        play_sound(SFX_BOSS)
                        self.log_agent(f"🚀 {self.company_name} begins the Hustle Trail!")
            
            # ── RIVER CROSSING INPUT (state 1) ──
            elif self.state == 1 and self.river_choice is None and not self.river_crossing_active:
                if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    self.river_choice = int(pygame.key.name(event.key))
                    play_sound(SFX_DECISION)
                    self.start_river_crossing()  # Start the skill game!
            
            # ── TITLE SCREEN ──
            elif self.state == 0:
                if event.key == pygame.K_SPACE:
                    # If we have a saved profile, skip to river crossing
                    if getattr(self, 'has_saved_profile', False) and self.company_name:
                        self.state = 1  # Go directly to River Crossing
                        # Reset co-founders for new run
                        cofounder_names = ["Jane", "Alex", "Sam", "Taylor", "Jordan", "Riley", "Casey"]
                        random.shuffle(cofounder_names)
                        self.co_founders = [
                            {"name": cofounder_names[0], "alive": True},
                            {"name": cofounder_names[1], "alive": True},
                            {"name": cofounder_names[2], "alive": True},
                        ]
                        self.log_agent(f"🚀 {self.company_name} returns to the Hustle Trail!")
                        play_sound(SFX_BOSS)
                    else:
                        self.state = -1  # Go to onboarding
                        self.log_agent("🎮 Starting founder onboarding...")
                elif event.key == pygame.K_n:
                    # Reset profile and start fresh
                    self.reset_profile()
                    self.state = -1
                    self.onboarding_step = 0
                    self.input_active = True
                    self.log_agent("🆕 Starting new company...")
            
            # ── WIN/LOSE RESTART ──
            elif self.state in (5, 6):
                if event.key == pygame.K_SPACE:
                    old_agent = self.agent_mode
                    old_claw = self.clawbot_active
                    old_mot = self.motbot_active
                    self.__init__()
                    self.agent_mode = old_agent
                    self.clawbot_active = old_claw
                    self.motbot_active = old_mot
            
            # ── SHOOTING ──
            elif event.key == pygame.K_SPACE:
                self.shoot()
            
            # ── REMEDY SELECTION ──
            elif self.remedy_active and self.remedy_timer == 0:
                if event.key == pygame.K_1:
                    self.handle_remedy(1)
                elif event.key == pygame.K_2:
                    self.handle_remedy(2)
                elif event.key == pygame.K_3:
                    self.handle_remedy(3)
                elif event.key == pygame.K_4:
                    self.handle_remedy(4)
                elif event.key == pygame.K_5:
                    self.handle_remedy(5)
            
            # ── DECISION SELECTION ──
            elif self.decision_active:
                if event.key == pygame.K_1:
                    self.handle_decision(0)
                elif event.key == pygame.K_2:
                    self.handle_decision(1)

# Main loop - async for web compatibility (pygbag)
import asyncio

async def main():
    game = Game()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            game.handle_event(event)

        game.update()
        game.draw()
        pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)  # Required for web

    pygame.quit()

asyncio.run(main())
