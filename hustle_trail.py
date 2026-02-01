"""
HUSTLE TRAIL: 0 to 1 - Oregon Trail Faithful Edition
=====================================================
Refactored for classic Oregon Trail gameplay:
- Semi-automatic travel (distance auto-advances)
- Menu-driven number-key choices (no WASD in core)
- RNG-based event outcomes
- Three trail segments with escalating risks
- ONE final bonus arcade at the end

Changes from v1:
- Replaced real-time arcade phases with auto-advancing trail
- River crossing is now RNG menu (1-4 choices) not skill game
- Events trigger periodically based on frame counter
- Final bonus arcade unlocks after reaching distance 2000
"""

import pygame
import random
import sys
import math
import json
import os
import asyncio

# Save file path
SAVE_FILE = os.path.join(os.path.dirname(__file__), "hustle_save.json")

# Init
pygame.init()
pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Hustle Trail: 0 to 1 (Oregon Trail Edition)")
clock = pygame.time.Clock()
font = pygame.font.SysFont('arial', 20, bold=True)
small_font = pygame.font.SysFont('arial', 16)
big_font = pygame.font.SysFont('arial', 42, bold=True)

# Generate retro sound effects
def generate_sound(frequency, duration, volume=0.3, wave_type='square'):
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


class Game:
    """
    STATES:
    -1 = Onboarding
     0 = Title Screen
     1 = TRAIL (main Oregon Trail gameplay - auto-advancing)
     2 = FINAL_BONUS (one arcade game after reaching distance 2000)
     5 = Win
     6 = Lose
    """
    
    def __init__(self):
        # ══════════════════════════════════════════════════════════════
        # CORE STATE - Changed from multiple arcade states to TRAIL + BONUS
        # ══════════════════════════════════════════════════════════════
        self.state = 0  # Start at title
        
        # ── Onboarding ──
        self.onboarding_step = 0
        self.company_name = ""
        self.problem = ""
        self.solution = ""
        self.warm_intro = False      # +10% river success
        self.elite_college = False   # +5% event success
        self.input_text = ""
        self.input_active = True
        
        # ══════════════════════════════════════════════════════════════
        # NEW: TRAIL SYSTEM - Oregon Trail faithful
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
        
        # Trail segment (calculated from distance)
        # 0-700 = EARLY, 700-1400 = MID, 1400-2000 = LATE
        
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
        
        # Arcade game variables (reused from original)
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
    
    def get_segment_risk(self):
        """Return base risk multiplier for current segment"""
        segment = self.get_trail_segment()
        if segment == "EARLY":
            return 0.15  # 10-20% base risk
        elif segment == "MID":
            return 0.25  # 20-30% base risk
        else:
            return 0.35  # 30-40% base risk
    
    def get_pace_speed(self):
        """Return distance increment per frame based on pace"""
        speeds = {1: 0.5, 2: 0.75, 3: 1.0}
        return speeds.get(self.pace, 0.5)
    
    def get_pace_drain(self):
        """Return runway drain per frame based on pace"""
        drains = {1: 0.02, 2: 0.035, 3: 0.05}
        return drains.get(self.pace, 0.02)

    # ══════════════════════════════════════════════════════════════════
    # EVENT SYSTEM - RNG-based Oregon Trail events
    # ══════════════════════════════════════════════════════════════════
    
    def trigger_random_event(self):
        """Trigger a random trail event based on segment"""
        segment = self.get_trail_segment()
        
        # Event pool with weights
        events = [
            ('river', 30),      # River crossing
            ('breakdown', 20),  # Wagon/code breakdown
            ('sickness', 15),   # Co-founder sickness
            ('decision', 25),   # Random startup decision
            ('windfall', 10),   # Good luck!
        ]
        
        # Late trail has more sickness
        if segment == "LATE":
            events = [
                ('river', 25),
                ('breakdown', 20),
                ('sickness', 25),
                ('decision', 20),
                ('windfall', 10),
            ]
        
        # Weighted random choice
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
        elif chosen == 'windfall':
            self.trigger_windfall_event()
    
    def trigger_river_event(self):
        """River crossing - menu choice with RNG outcome"""
        play_sound(SFX_EVENT)
        self.current_event = 'river'
        
        river_names = [
            "Series Seed Chasm", "VC Valley Creek", "Dilution River",
            "Cap Table Canyon", "Fundraise Falls", "Equity Rapids"
        ]
        
        self.event_text = f"You've reached the {random.choice(river_names)}!"
        self.event_options = [
            "1: Ford the river (YOLO) - 40% fail risk",
            "2: Caulk wagon & float - 25% fail risk",
            "3: Wait for conditions - 10% fail, costs time",
            "4: Pay for ferry - Safe, -15 runway"
        ]
        self.log(f"🌊 River crossing ahead!")
    
    def trigger_breakdown_event(self):
        """Wagon/code breakdown"""
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
        self.log(f"⚠️ Breakdown: {self.event_text[:40]}...")
    
    def trigger_sickness_event(self):
        """Co-founder sickness/departure risk"""
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
        self.log(f"😰 {victim['name']} needs attention!")
    
    def trigger_decision_event(self):
        """Random startup decision"""
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
        """Good luck event!"""
        play_sound(SFX_POWERUP)
        self.current_event = None  # Auto-resolves
        
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
    # EVENT RESOLUTION - Handle menu choices
    # ══════════════════════════════════════════════════════════════════
    
    def handle_river_choice(self, choice):
        """Process river crossing choice with RNG"""
        base_risk = self.get_segment_risk()
        
        # Fail chances
        fail_chances = {
            1: 0.40,  # Ford - 40%
            2: 0.25,  # Caulk - 25%
            3: 0.10,  # Wait - 10%
            4: 0.00,  # Ferry - safe
        }
        
        fail_chance = fail_chances.get(choice, 0.25)
        
        # Apply onboarding bonuses
        if self.warm_intro:
            fail_chance -= 0.10  # +10% success
        if self.elite_college:
            fail_chance -= 0.05  # +5% success
        
        fail_chance = max(0, fail_chance)
        
        # Roll the dice
        roll = random.random()
        failed = roll < fail_chance
        
        if choice == 4:  # Ferry - always safe but costs runway
            self.runway -= 15
            self.event_result = "💰 Paid for ferry. Safe crossing! -15 runway"
            self.traction += 5
        elif failed:
            # Failure consequences
            equity_loss = random.randint(15, 30)
            runway_loss = random.randint(5, 15)
            self.equity -= equity_loss
            self.runway -= runway_loss
            
            self.event_result = f"💀 DISASTER! Lost {equity_loss} equity, {runway_loss} runway!"
            
            # Chance to lose co-founder based on segment
            death_chance = {
                "EARLY": 0.10,
                "MID": 0.20,
                "LATE": 0.30,
            }.get(self.get_trail_segment(), 0.15)
            
            if random.random() < death_chance:
                alive = [cf for cf in self.co_founders if cf["alive"]]
                if alive:
                    victim = random.choice(alive)
                    victim["alive"] = False
                    reason = random.choice(self.death_reasons)
                    self.event_result += f"\n💀 {victim['name']} {reason}!"
                    play_sound(SFX_LOSE)
        else:
            # Success!
            self.traction += 10
            self.event_result = "🎉 Crossed successfully! +10 traction"
            if choice == 3:  # Wait costs time
                self.runway -= 5
                self.event_result += " (-5 runway for waiting)"
        
        self.event_result_timer = 240
        self.current_event = None
        self.log(self.event_result.split('\n')[0])
    
    def handle_breakdown_choice(self, choice):
        """Process breakdown choice"""
        # Parse the option text for effects (simplified)
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
        """Process sickness/burnout choice"""
        victim = getattr(self, 'event_victim', None)
        
        if choice == 1:  # Rest
            self.runway -= 25
            self.event_result = f"{victim['name'] if victim else 'Team'} recovered! -25 runway"
        elif choice == 2:  # Push through
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
        else:  # Retreat
            self.runway -= 15
            self.equity = min(100, self.equity + 10)
            self.event_result = "Team retreat helped! -15 runway, +10 equity"
        
        self.event_result_timer = 180
        self.current_event = None
        self.log(self.event_result.split('\n')[0] if self.event_result else "Event resolved")
    
    def handle_decision_choice(self, choice):
        """Process decision choice - parse effects from option text"""
        opt = self.event_options[choice - 1] if choice <= len(self.event_options) else ""
        
        # Simple effect parsing
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
    # FINAL BONUS ARCADE - One game after trail completion
    # ══════════════════════════════════════════════════════════════════
    
    def start_final_bonus(self):
        """Start the final bonus arcade game"""
        self.state = 2  # FINAL_BONUS
        self.bonus_type = random.choice(['galaga', 'mario', 'frogger'])
        self.bonus_timer = random.randint(60, 90) * 60  # 60-90 seconds in frames
        self.bonus_score = 0
        self.bonus_max_score = 100
        
        # Reset arcade variables
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
        """Calculate bonus rewards and transition to win"""
        # Base reward: 20 + score × 5, capped at 100
        runway_bonus = 20 + (self.bonus_score * 5)
        runway_bonus = min(100, runway_bonus)
        
        # High-reward tier: if score >= 70% of max, add +50-80
        if self.bonus_score >= self.bonus_max_score * 0.7:
            high_tier = random.randint(50, 80)
            runway_bonus += high_tier
            self.log(f"🏆 HIGH SCORE TIER! +{high_tier} bonus runway!")
        
        # Cap total
        runway_bonus = min(runway_bonus, 150)
        self.runway = min(100, self.runway + runway_bonus)
        
        # Bonus traction and equity
        self.traction += self.bonus_score * 2
        self.equity = min(100, self.equity + 10)
        
        # Chance to revive co-founder if score was good
        if self.bonus_score >= self.bonus_max_score * 0.5:
            dead = [cf for cf in self.co_founders if not cf["alive"]]
            if dead and random.random() < 0.3:
                revived = random.choice(dead)
                revived["alive"] = True
                self.log(f"🎉 {revived['name']} rejoined the team!")
        
        self.log(f"🎮 Bonus complete! +{runway_bonus} runway, +{self.bonus_score * 2} traction")
        
        # Go to win state
        self.state = 5
        play_sound(SFX_WIN)
        self.generate_remix_prompt()
    
    def update_bonus_galaga(self):
        """Update Galaga-style bonus game"""
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a] and self.player_x > 25:
            self.player_x -= 5
        if keys[pygame.K_d] and self.player_x < WIDTH - 25:
            self.player_x += 5
        self.player_rect.center = (self.player_x, self.player_y)
        
        # Spawn enemies
        self.enemy_spawn_timer += 1
        if self.enemy_spawn_timer > 40:
            enemy_data = random.choice(self.enemy_types)
            self.enemies.append({
                'rect': pygame.Rect(random.randint(20, WIDTH-60), -40, 40, 40),
                'type': enemy_data[0],
                'speed': random.uniform(2, 4)
            })
            self.enemy_spawn_timer = 0
        
        # Update bullets
        for b in self.bullets[:]:
            b['rect'].y -= 8
            if b['rect'].y < 0:
                self.bullets.remove(b)
        
        # Update enemies
        for e in self.enemies[:]:
            e['rect'].y += e['speed']
            if e['rect'].y > HEIGHT:
                self.enemies.remove(e)
            elif e['rect'].colliderect(self.player_rect):
                self.equity -= 5
                self.enemies.remove(e)
                play_sound(SFX_DAMAGE)
        
        # Check bullet-enemy collisions
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
        """Update Mario-style bonus game"""
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]:
            self.scroll_x += 3
            self.player_x = max(50, self.player_x - 2)
        if keys[pygame.K_d]:
            self.scroll_x -= 5
            self.player_x = min(WIDTH - 50, self.player_x + 2)
        if keys[pygame.K_w] and self.player_y > HEIGHT - 200:
            self.player_y -= 8
        else:
            self.player_y = min(HEIGHT - 80, self.player_y + 3)
        
        self.player_rect.center = (self.player_x, self.player_y)
        
        # Score for distance traveled
        if self.scroll_x < -100:
            self.bonus_score += 1
            self.scroll_x = 0
    
    def update_bonus_frogger(self):
        """Update Frogger-style bonus game"""
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a] and self.player_x > 25:
            self.player_x -= 5
        if keys[pygame.K_d] and self.player_x < WIDTH - 25:
            self.player_x += 5
        if keys[pygame.K_w] and self.player_y > 50:
            self.player_y -= 5
        if keys[pygame.K_s] and self.player_y < HEIGHT - 50:
            self.player_y += 5
        
        self.player_rect.center = (self.player_x, self.player_y)
        
        # Spawn obstacles
        if random.random() < 0.03:
            obs = {
                'rect': pygame.Rect(random.choice([-50, WIDTH]), random.randint(100, HEIGHT-150), 60, 30),
                'dir': random.choice([-1, 1]),
                'speed': random.randint(3, 6)
            }
            self.obstacles.append(obs)
        
        # Update obstacles
        for o in self.obstacles[:]:
            o['rect'].x += o['dir'] * o['speed']
            if o['rect'].right < -100 or o['rect'].left > WIDTH + 100:
                self.obstacles.remove(o)
            elif o['rect'].colliderect(self.player_rect):
                self.equity -= 10
                self.player_y = HEIGHT - 80  # Reset
                self.obstacles.remove(o)
                play_sound(SFX_DAMAGE)
        
        # Score for reaching top
        if self.player_y < 60:
            self.bonus_score += 5
            self.player_y = HEIGHT - 80

    # ══════════════════════════════════════════════════════════════════
    # REMEDY SYSTEM (kept from original)
    # ══════════════════════════════════════════════════════════════════
    
    def trigger_remedy(self):
        """Trigger Five Remedies when equity is low"""
        play_sound(SFX_REMEDY)
        self.remedy_active = True
        self.remedy_timer = 0
        self.remedy_text = "⚠️ EQUITY CRITICAL! Choose a remedy:"
        self.log("💔 Equity low! Time for self-care, founder.")
    
    def handle_remedy(self, choice):
        """Process remedy selection"""
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
    # SAVE/LOAD (kept from original)
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
            with open(SAVE_FILE, 'w') as f:
                json.dump(save_data, f, indent=2)
        except:
            pass
    
    def load_profile(self):
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE, 'r') as f:
                    data = json.load(f)
                self.company_name = data.get("company_name", "")
                self.problem = data.get("problem", "")
                self.solution = data.get("solution", "")
                self.warm_intro = data.get("warm_intro", False)
                self.elite_college = data.get("elite_college", False)
                self.games_played = data.get("games_played", 0)
                self.has_saved_profile = bool(self.company_name)
            else:
                self.has_saved_profile = False
                self.games_played = 0
        except:
            self.has_saved_profile = False
            self.games_played = 0
    
    def reset_profile(self):
        try:
            if os.path.exists(SAVE_FILE):
                os.remove(SAVE_FILE)
            self.has_saved_profile = False
            self.company_name = ""
        except:
            pass

    def bootstrap_ending(self):
        """Secret ending for bootstrapping"""
        self.state = 6
        self.death_quote = (
            "You bootstrapped quietly.\n"
            "Hit $9M ARR in 18 months. Zero dilution.\n"
            "No one knows your name. You retired to Phoenix.\n"
            "\nTRUE ENDING: Quiet Wealth\n"
            "Eric Bahn: Skill issue? Nah... respect."
        )

    def log(self, msg):
        """Add message to log"""
        print(msg)
        self.log_messages.append(msg)
        if len(self.log_messages) > 5:
            self.log_messages.pop(0)

    def generate_remix_prompt(self):
        """Generate shareable prompt"""
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
    # MAIN UPDATE LOOP
    # ══════════════════════════════════════════════════════════════════
    
    def update(self):
        """Main game update - Oregon Trail style"""
        
        # ── TRAIL STATE (main gameplay) ──
        if self.state == 1:
            # Handle pause
            if self.paused:
                self.pause_timer -= 1
                if self.pause_timer <= 0:
                    self.paused = False
                return
            
            # Handle remedy resting
            if self.remedy_active and self.remedy_timer > 0:
                self.remedy_timer -= 1
                self.equity = min(100, self.equity + 0.3)
                if self.remedy_timer <= 0:
                    self.remedy_active = False
                    self.selected_remedy = ""
                return
            
            # Handle event result display
            if self.event_result_timer > 0:
                self.event_result_timer -= 1
                if self.event_result_timer <= 0:
                    self.event_result = None
                return
            
            # If there's an active event, wait for input (don't auto-advance)
            if self.current_event:
                return
            
            # If remedy selection needed
            if self.remedy_active and self.remedy_timer == 0:
                return
            
            # ══════════════════════════════════════════════════════════
            # AUTO-ADVANCE DISTANCE (Oregon Trail core mechanic)
            # ══════════════════════════════════════════════════════════
            self.distance += self.get_pace_speed()
            self.runway -= self.get_pace_drain()
            
            # Random SV quote
            if random.random() < 0.002:
                self.current_quote = random.choice(self.sv_quotes)
                self.quote_timer = 150
            
            # Decrement quote timer
            if self.quote_timer > 0:
                self.quote_timer -= 1
                if self.quote_timer <= 0:
                    self.current_quote = None
            
            # ══════════════════════════════════════════════════════════
            # EVENT TRIGGER (RNG-based, every 800-1500 frames)
            # ══════════════════════════════════════════════════════════
            self.event_timer += 1
            if self.event_timer >= self.next_event_at:
                self.trigger_random_event()
                self.event_timer = 0
                self.next_event_at = random.randint(800, 1500)
            
            # ══════════════════════════════════════════════════════════
            # REMEDY TRIGGER (equity <= 30)
            # ══════════════════════════════════════════════════════════
            if self.equity <= self.remedy_threshold and not self.remedy_active:
                self.trigger_remedy()
            
            # ══════════════════════════════════════════════════════════
            # WIN CONDITION: Distance >= 2000 → Final Bonus
            # ══════════════════════════════════════════════════════════
            if self.distance >= 2000:
                self.log("🎯 Trail complete! Final bonus time!")
                self.start_final_bonus()
                return
            
            # ══════════════════════════════════════════════════════════
            # LOSE CONDITIONS
            # ══════════════════════════════════════════════════════════
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
        
        # ── FINAL BONUS STATE ──
        elif self.state == 2:
            self.bonus_timer -= 1
            
            if self.bonus_type == 'galaga':
                self.update_bonus_galaga()
            elif self.bonus_type == 'mario':
                self.update_bonus_mario()
            elif self.bonus_type == 'frogger':
                self.update_bonus_frogger()
            
            # End bonus when timer runs out or equity gone
            if self.bonus_timer <= 0 or self.equity <= 0:
                self.end_final_bonus()

    # ══════════════════════════════════════════════════════════════════
    # DRAW FUNCTIONS
    # ══════════════════════════════════════════════════════════════════
    
    def draw(self):
        screen.fill(BLACK)
        
        # ── ONBOARDING ──
        if self.state == -1:
            self.draw_onboarding()
            return
        
        # ── TITLE ──
        if self.state == 0:
            self.draw_title()
            return
        
        # ── TRAIL ──
        if self.state == 1:
            self.draw_trail()
            return
        
        # ── FINAL BONUS ──
        if self.state == 2:
            self.draw_bonus()
            return
        
        # ── WIN ──
        if self.state == 5:
            self.draw_win()
            return
        
        # ── LOSE ──
        if self.state == 6:
            self.draw_lose()
            return
    
    def draw_onboarding(self):
        """Draw onboarding screen"""
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
            cursor = "|" if pygame.time.get_ticks() % 1000 < 500 else ""
            screen.blit(font.render(self.input_text + cursor, True, GREEN), (400, 120 + self.onboarding_step * 50))
        elif self.onboarding_step in (3, 4):
            screen.blit(font.render("Press Y / N", True, YELLOW), (60, y + 10))
        elif self.onboarding_step == 5:
            screen.blit(font.render("1 → Bootstrap (secret ending)", True, GREEN), (80, y + 10))
            screen.blit(font.render("2 → Seek VC Funding (start the trail!)", True, CYAN), (80, y + 45))
    
    def draw_title(self):
        """Draw title screen"""
        title = big_font.render("HUSTLE TRAIL", True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 60))
        
        tagline = font.render("Oregon Trail × Tech Startup × Silicon Valley", True, ORANGE)
        screen.blit(tagline, (WIDTH//2 - tagline.get_width()//2, 120))
        
        subtitle = font.render("0 to 1: Survive the trail. Find your first customer.", True, WHITE)
        screen.blit(subtitle, (WIDTH//2 - subtitle.get_width()//2, 160))
        
        rules = small_font.render("There are a lot of rules. Good luck figuring them out. :)", True, MAGENTA)
        screen.blit(rules, (WIDTH//2 - rules.get_width()//2, 200))
        
        if getattr(self, 'has_saved_profile', False) and self.company_name:
            pygame.draw.rect(screen, (30, 30, 60), (100, 250, WIDTH - 200, 100))
            pygame.draw.rect(screen, CYAN, (100, 250, WIDTH - 200, 100), 2)
            screen.blit(font.render(f"Welcome back, {self.company_name}!", True, CYAN), (120, 265))
            screen.blit(font.render("SPACE → Continue | N → New Company", True, GREEN), (120, 305))
        else:
            screen.blit(font.render("SPACE to Start New Company", True, GREEN), (WIDTH//2 - 120, 280))
        
        credits = small_font.render("Inspired by Eric Bahn, Hustle Fund, and HBO's Silicon Valley", True, WHITE)
        screen.blit(credits, (WIDTH//2 - credits.get_width()//2, 520))
    
    def draw_trail(self):
        """Draw main trail screen - Oregon Trail style"""
        # Background - scrolling landscape
        pygame.draw.rect(screen, (20, 60, 20), (0, 400, WIDTH, 200))  # Ground
        pygame.draw.rect(screen, (10, 30, 60), (0, 0, WIDTH, 400))    # Sky
        
        # Mountains in distance
        for i in range(5):
            x = (i * 200 - int(self.distance) % 200)
            pygame.draw.polygon(screen, (60, 60, 80), [(x, 400), (x + 100, 200), (x + 200, 400)])
        
        # Wagon (auto-moving)
        wagon_x = 100 + (int(self.distance) % 50)
        pygame.draw.rect(screen, BROWN, (wagon_x, 360, 80, 50))
        pygame.draw.circle(screen, BLACK, (wagon_x + 20, 410), 15)
        pygame.draw.circle(screen, BLACK, (wagon_x + 60, 410), 15)
        
        # Co-founders on wagon
        alive = [cf for cf in self.co_founders if cf["alive"]]
        for i, cf in enumerate(alive[:3]):
            pygame.draw.circle(screen, CYAN, (wagon_x + 20 + i * 20, 350), 8)
        
        # ══════════════════════════════════════════════════════════════
        # HUD - Top of screen
        # ══════════════════════════════════════════════════════════════
        pygame.draw.rect(screen, (0, 0, 0, 180), (0, 0, WIDTH, 80))
        
        # Distance progress bar
        progress = min(1, self.distance / 2000)
        pygame.draw.rect(screen, GRAY, (150, 15, 500, 20), 2)
        pygame.draw.rect(screen, GREEN, (152, 17, int(496 * progress), 16))
        screen.blit(small_font.render(f"Distance: {int(self.distance)}/2000", True, WHITE), (10, 15))
        screen.blit(small_font.render(self.get_trail_segment(), True, YELLOW), (660, 15))
        
        # Stats
        runway_color = WHITE if self.runway > 20 else RED
        equity_color = WHITE if self.equity > 20 else RED
        screen.blit(font.render(f"Runway: {int(self.runway)}%", True, runway_color), (10, 45))
        stake_emoji = ":)" if self.equity >= 90 else ":("
        screen.blit(font.render(f"Stake: {self.equity}% {stake_emoji}", True, equity_color), (180, 45))
        screen.blit(font.render(f"Traction: {self.traction}", True, WHITE), (380, 45))
        
        # Co-founder count
        alive_count = sum(1 for cf in self.co_founders if cf["alive"])
        cf_color = WHITE if alive_count > 1 else RED
        screen.blit(font.render(f"Team: {alive_count}/3", True, cf_color), (550, 45))
        
        # Pace indicator
        pace_names = {1: "Steady", 2: "Strenuous", 3: "Grueling"}
        screen.blit(small_font.render(f"Pace: {pace_names.get(self.pace, 'Steady')} [1-3 to change]", True, ORANGE), (10, 75))
        
        # ══════════════════════════════════════════════════════════════
        # EVENT OVERLAY
        # ══════════════════════════════════════════════════════════════
        if self.current_event:
            self.draw_event_overlay()
        
        # Remedy overlay
        elif self.remedy_active:
            self.draw_remedy_overlay()
        
        # Event result message
        elif self.event_result:
            pygame.draw.rect(screen, BLACK, (50, 150, WIDTH - 100, 100))
            pygame.draw.rect(screen, YELLOW, (50, 150, WIDTH - 100, 100), 3)
            lines = self.event_result.split('\n')
            for i, line in enumerate(lines):
                color = RED if "💀" in line else GREEN if "🎉" in line else YELLOW
                screen.blit(font.render(line, True, color), (70, 165 + i * 25))
        
        # Paused overlay
        if self.paused:
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.set_alpha(180)
            overlay.fill(BLACK)
            screen.blit(overlay, (0, 0))
            screen.blit(big_font.render("PAUSED", True, YELLOW), (WIDTH//2 - 80, HEIGHT//2 - 30))
            screen.blit(font.render(f"Resuming in {self.pause_timer // 60 + 1}s...", True, WHITE), (WIDTH//2 - 80, HEIGHT//2 + 30))
        
        # Quote overlay
        if self.current_quote and self.quote_timer > 0:
            quote_surf = font.render(self.current_quote[:60], True, YELLOW)
            pygame.draw.rect(screen, BLACK, (45, HEIGHT - 55, quote_surf.get_width() + 10, 30))
            pygame.draw.rect(screen, YELLOW, (45, HEIGHT - 55, quote_surf.get_width() + 10, 30), 2)
            screen.blit(quote_surf, (50, HEIGHT - 50))
        
        # Log messages
        log_y = HEIGHT - 120
        for msg in self.log_messages[-3:]:
            screen.blit(small_font.render(msg[:70], True, CYAN), (10, log_y))
            log_y += 18
    
    def draw_event_overlay(self):
        """Draw event menu overlay"""
        pygame.draw.rect(screen, BLACK, (30, 120, WIDTH - 60, 280))
        pygame.draw.rect(screen, YELLOW, (30, 120, WIDTH - 60, 280), 3)
        
        # Event title
        title_color = BLUE if self.current_event == 'river' else ORANGE if self.current_event == 'breakdown' else YELLOW
        screen.blit(font.render(f"⚡ {self.current_event.upper()} EVENT", True, title_color), (50, 135))
        
        # Event text
        lines = self.event_text.split('\n') if self.event_text else [""]
        for i, line in enumerate(lines):
            screen.blit(font.render(line, True, WHITE), (50, 170 + i * 25))
        
        # Options
        y = 230
        for i, opt in enumerate(self.event_options):
            color = GREEN if i == 0 else CYAN if i == 1 else ORANGE if i == 2 else MAGENTA
            screen.blit(font.render(opt, True, color), (60, y))
            y += 35
        
        # Instructions
        screen.blit(small_font.render("Press 1-4 to choose", True, GRAY), (50, 370))
    
    def draw_remedy_overlay(self):
        """Draw remedy selection overlay"""
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
            # Resting animation
            progress = 1 - (self.remedy_timer / 360)
            bar_width = int(600 * progress)
            
            screen.blit(big_font.render(f"🧘 {self.selected_remedy}...", True, MAGENTA), (WIDTH//2 - 150, 200))
            pygame.draw.rect(screen, WHITE, (100, 280, 600, 30), 2)
            pygame.draw.rect(screen, MAGENTA, (102, 282, bar_width, 26))
            screen.blit(font.render(f"Restoring equity... {self.remedy_timer//60 + 1}s", True, WHITE), (WIDTH//2 - 100, 330))
    
    def draw_bonus(self):
        """Draw final bonus arcade screen"""
        # Background
        for i in range(50):
            x = (i * 73 + self.scroll_x) % WIDTH
            y = (i * 47) % HEIGHT
            pygame.draw.circle(screen, WHITE, (int(x), int(y)), 1)
        
        bonus_names = {
            'galaga': "SHOOT THE REJECTIONS!",
            'mario': "PLATFORM PIVOT!",
            'frogger': "DODGE THE COMPETITION!"
        }
        
        # Title
        title = big_font.render(f"🎮 {bonus_names.get(self.bonus_type, 'FINAL BONUS')}", True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 10))
        
        # Timer
        secs = self.bonus_timer // 60
        timer_text = font.render(f"Time: {secs}s | Score: {self.bonus_score}", True, WHITE)
        screen.blit(timer_text, (WIDTH//2 - 80, 60))
        
        # Draw player
        pygame.draw.rect(screen, BROWN, self.player_rect)
        pygame.draw.rect(screen, WHITE, self.player_rect, 2)
        
        if self.bonus_type == 'galaga':
            # Draw bullets
            for b in self.bullets:
                pygame.draw.rect(screen, GREEN, b['rect'])
            # Draw enemies
            for e in self.enemies:
                pygame.draw.rect(screen, RED, e['rect'])
                screen.blit(small_font.render(e['type'][:6], True, WHITE), (e['rect'].x, e['rect'].y + 10))
            # Instructions
            screen.blit(small_font.render("A/D to move, SPACE to shoot!", True, CYAN), (10, HEIGHT - 30))
        
        elif self.bonus_type == 'mario':
            # Draw platforms
            for p in self.platforms:
                px = p.x + self.scroll_x
                if -200 < px < WIDTH + 200:
                    pygame.draw.rect(screen, BLUE, (px, p.y, p.width, p.height))
            screen.blit(small_font.render("A/D to move, W to jump! Go right!", True, CYAN), (10, HEIGHT - 30))
        
        elif self.bonus_type == 'frogger':
            # Draw goal
            pygame.draw.rect(screen, GREEN, (WIDTH//2 - 50, 20, 100, 40))
            screen.blit(font.render("GOAL", True, BLACK), (WIDTH//2 - 25, 30))
            # Draw obstacles
            for o in self.obstacles:
                pygame.draw.rect(screen, RED, o['rect'])
            screen.blit(small_font.render("WASD to move! Reach the top!", True, CYAN), (10, HEIGHT - 30))
        
        # Equity bar
        pygame.draw.rect(screen, GRAY, (10, 90, 200, 20), 2)
        pygame.draw.rect(screen, GREEN if self.equity > 20 else RED, (12, 92, int(196 * self.equity / 100), 16))
        screen.blit(small_font.render(f"Equity: {self.equity}%", True, WHITE), (220, 90))
    
    def draw_win(self):
        """Draw win screen"""
        pygame.draw.rect(screen, BLACK, (50, 100, WIDTH - 100, 400))
        pygame.draw.rect(screen, GREEN, (50, 100, WIDTH - 100, 400), 4)
        
        screen.blit(big_font.render("🎉 FIRST CUSTOMER!", True, GREEN), (WIDTH//2 - 180, 130))
        screen.blit(font.render("0 → 1 ACHIEVED", True, YELLOW), (WIDTH//2 - 70, 190))
        
        # Stats
        screen.blit(font.render(f"Company: {self.company_name}", True, WHITE), (80, 240))
        screen.blit(font.render(f"Distance: {int(self.distance)} miles", True, WHITE), (80, 270))
        screen.blit(font.render(f"Runway: {int(self.runway)}% | Equity: {self.equity}%", True, WHITE), (80, 300))
        screen.blit(font.render(f"Traction: {self.traction} | Followers: {self.followers}", True, WHITE), (80, 330))
        
        alive = sum(1 for cf in self.co_founders if cf["alive"])
        cf_names = ", ".join(cf["name"] for cf in self.co_founders if cf["alive"])
        screen.blit(font.render(f"Surviving team ({alive}/3): {cf_names}", True, CYAN), (80, 360))
        
        screen.blit(font.render("Check console for shareable stats!", True, YELLOW), (80, 410))
        screen.blit(font.render("SPACE to play again", True, GREEN), (WIDTH//2 - 100, 460))
    
    def draw_lose(self):
        """Draw lose screen"""
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
        
        screen.blit(font.render(f"Distance traveled: {int(self.distance)} miles", True, WHITE), (80, 380))
        screen.blit(font.render("SPACE to try again", True, GREEN), (WIDTH//2 - 100, 450))

    # ══════════════════════════════════════════════════════════════════
    # EVENT HANDLING
    # ══════════════════════════════════════════════════════════════════
    
    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        
        key = event.key
        
        # ── ONBOARDING INPUT ──
        if self.state == -1:
            if self.input_active:
                if key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                elif key == pygame.K_RETURN:
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
                    self.state = 1  # Start TRAIL
                    self.log(f"🚀 {self.company_name} begins the Hustle Trail!")
                    play_sound(SFX_EVENT)
        
        # ── TITLE SCREEN ──
        elif self.state == 0:
            if key == pygame.K_SPACE:
                if getattr(self, 'has_saved_profile', False) and self.company_name:
                    self.state = 1
                    # Reset for new run
                    cofounder_names = ["Jane", "Alex", "Sam", "Taylor", "Jordan", "Riley", "Casey"]
                    random.shuffle(cofounder_names)
                    self.co_founders = [{"name": cofounder_names[i], "alive": True} for i in range(3)]
                    self.runway = 100
                    self.equity = 100
                    self.traction = 0
                    self.distance = 0
                    self.log(f"🚀 {self.company_name} returns to the trail!")
                else:
                    self.state = -1
            elif key == pygame.K_n:
                self.reset_profile()
                self.state = -1
                self.onboarding_step = 0
                self.input_active = True
        
        # ── TRAIL STATE ──
        elif self.state == 1:
            # Pause
            if key == pygame.K_p and not self.current_event and not self.remedy_active:
                self.paused = True
                self.pause_timer = 25 * 60  # 25 seconds
                self.log("⏸️ Paused for 25 seconds")
            
            # Pace change (1-3)
            if key == pygame.K_1 and not self.current_event:
                self.pace = 1
                self.log("🐢 Pace: Steady (safe, slow)")
            elif key == pygame.K_2 and not self.current_event and not self.remedy_active:
                self.pace = 2
                self.log("🚶 Pace: Strenuous (balanced)")
            elif key == pygame.K_3 and not self.current_event and not self.remedy_active:
                self.pace = 3
                self.log("🏃 Pace: Grueling (risky, fast)")
            
            # Event choices
            if self.current_event:
                if key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    choice = int(pygame.key.name(key))
                    if self.current_event == 'river':
                        self.handle_river_choice(choice)
                    elif self.current_event == 'breakdown':
                        self.handle_breakdown_choice(choice)
                    elif self.current_event == 'sickness':
                        self.handle_sickness_choice(choice)
                    elif self.current_event == 'decision':
                        self.handle_decision_choice(choice)
            
            # Remedy choices
            elif self.remedy_active and self.remedy_timer == 0:
                if key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    choice = int(pygame.key.name(key))
                    self.handle_remedy(choice)
        
        # ── BONUS STATE ──
        elif self.state == 2:
            if key == pygame.K_SPACE and self.bonus_type == 'galaga':
                self.bullets.append({
                    'rect': pygame.Rect(self.player_x - 2, self.player_y - 30, 5, 15)
                })
                play_sound(SFX_SHOOT)
        
        # ── WIN/LOSE RESTART ──
        elif self.state in (5, 6):
            if key == pygame.K_SPACE:
                self.__init__()


# ══════════════════════════════════════════════════════════════════════
# MAIN LOOP - Async for web compatibility
# ══════════════════════════════════════════════════════════════════════

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
        await asyncio.sleep(0)
    
    pygame.quit()

asyncio.run(main())
