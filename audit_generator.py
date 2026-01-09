import sys
import subprocess
import datetime

# --- AUTO-INSTALLER ---
try:
    from fpdf import FPDF
except ImportError:
    print("Installing PDF library...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fpdf"])
    from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'ForwardFin | Institutional Strategy Documentation', 0, 1, 'R')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Confidential Strategy - Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, num, label):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(0, 51, 102) # Navy Blue
        self.cell(0, 10, f"Chapter {num}: {label}", 0, 1, 'L')
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def sub_title(self, label):
        self.set_font('Arial', 'B', 12)
        self.set_text_color(0, 0, 0)
        self.ln(3)
        self.cell(0, 8, label, 0, 1, 'L')

    def body_text(self, text):
        self.set_font('Arial', '', 11)
        self.set_text_color(50, 50, 50)
        # Safe encoding for symbols
        safe_text = text.encode('latin-1', 'replace').decode('latin-1')
        self.multi_cell(0, 6, safe_text)
        self.ln(2)

print("Writing Strategy Bible...", flush=True)
pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()

# --- TITLE PAGE ---
pdf.set_font('Arial', 'B', 24)
pdf.set_text_color(0, 0, 0)
pdf.ln(40)
pdf.cell(0, 10, "FORWARD FIN", 0, 1, 'C')
pdf.set_font('Arial', '', 14)
pdf.cell(0, 10, "THE ASIA EXECUTION PROTOCOL", 0, 1, 'C')
pdf.ln(10)
pdf.set_font('Arial', 'I', 10)
pdf.cell(0, 10, "A Mean-Reversion Algorithmic Strategy", 0, 1, 'C')
pdf.cell(0, 10, f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d')}", 0, 1, 'C')
pdf.add_page()

# --- CHAPTER 1: CORE PHILOSOPHY ---
pdf.chapter_title(1, "Core Philosophy & Market Theory")
pdf.body_text(
    "The ForwardFin strategy is NOT a trend-following system. It is a counter-trend 'Mean Reversion' system "
    "rooted in Institutional Market Structure (ICT Concepts). The core belief is that liquidity "
    "drives price delivery, not indicators.")

pdf.sub_title("1.1 The Manipulation Phase")
pdf.body_text(
    "Institutional algorithms (IPDA) accumulate positions by manipulating price to 'Sweep Liquidity'. "
    "They push price below old lows to trigger retail Sell Stops (Sell-side Liquidity) before buying heavily. "
    "Our strategy waits specifically for this manipulation to complete.")

pdf.sub_title("1.2 The Elastic Band Theory (Standard Deviation)")
pdf.body_text(
    "Volatility is mean-reverting. If we define a 'Baseline Range' (Asia Session), we can mathematically "
    "project how far price can travel before it becomes statistically exhausted. "
    "We use Standard Deviations (2.0 to 4.0) to identify these reversal zones.")

# --- CHAPTER 2: THE ASIA ANCHOR ---
pdf.chapter_title(2, "Phase I: The Asia Anchor")
pdf.body_text(
    "The foundation of the entire daily setup is the Asian Session. This provides the data required "
    "to calculate the day's volatility models.")

pdf.sub_title("2.1 Specific Time Window")
pdf.body_text(
    "We strictly monitor price action between 03:00 SAST and 08:59 SAST. "
    "This 6-hour window captures the Tokyo/Sydney volume. We do NOT trade during this time. "
    "We observe.")

pdf.sub_title("2.2 Defining the Range")
pdf.body_text(
    "At exactly 09:00 SAST, the system locks in two key levels:\n"
    "- Asia High: The highest price traded between 03:00-08:59.\n"
    "- Asia Low: The lowest price traded between 03:00-08:59.\n"
    "This range (High minus Low) represents 1.0 Standard Deviation of volatility for the session.")

# --- CHAPTER 3: THE KILL ZONE ---
pdf.chapter_title(3, "Phase II: The Kill Zone (Projections)")
pdf.body_text(
    "Once the Asia Range is locked, we project 'Standard Deviation Extensions' to find our entry zones. "
    "We do not chase price; we set limit orders (mentally) at these mathematical boundaries.")

pdf.sub_title("3.1 The Magic Numbers (-2.0 to -2.5)")
pdf.body_text(
    "The primary reversal zone is the -2.0 to -2.5 Standard Deviation Extension.\n"
    "CALCULATION: Target = Asia Low - ((Asia High - Asia Low) * 2.0).\n"
    "WHY: Statistically, it is rare for price to sustain a move beyond 2.5 deviations without a "
    "correction. This is where 'Smart Money' takes profit on shorts and initiates longs.")

pdf.sub_title("3.2 The 'Run on Stops'")
pdf.body_text(
    "We want to see price AGGRESSIVELY push into this zone. A slow drift is bad. "
    "We want a violent spike (Judas Swing) that triggers fear in retail traders. "
    "Only when price hits this -2.0 line do we wake up the execution module.")

# --- CHAPTER 4: SMT DIVERGENCE ---
pdf.chapter_title(4, "Phase III: SMT Divergence (The Filter)")
pdf.body_text(
    "Smart Money Technique (SMT) is our 'Lie Detector'. It filters out true crashes from fake manipulations.")

pdf.sub_title("4.1 Correlation Analysis")
pdf.body_text(
    "We compare Nasdaq-100 (NQ) vs S&P 500 (ES). These assets are highly correlated (95%+). "
    "They should move together. When they don't, it is a signal.")

pdf.sub_title("4.2 The Signal (Bullish Case)")
pdf.body_text(
    "Scenario: NQ makes a Lower Low (sweeps liquidity), hitting our -2.0 Zone.\n"
    "Confirmation: ES makes a HIGHER Low (refuses to drop).\n"
    "Meaning: The selling pressure on NQ is fake/manipulated. The relative strength in ES proves "
    "institutional accumulation. This 'Crack in Correlation' is the green light.")

# --- CHAPTER 5: EXECUTION ---
pdf.chapter_title(5, "Phase IV: Execution (The Sniper)")
pdf.body_text(
    "We do not blindly buy the -2.0 line. We switch to the 1-Minute Chart to time the entry.")

pdf.sub_title("5.1 Market Structure Shift (MSS)")
pdf.body_text(
    "We wait for price to bounce and break above a recent 'Swing High'. "
    "This Break of Structure (BOS) confirms that buyers have taken control.")

pdf.sub_title("5.2 Fair Value Gap (FVG)")
pdf.body_text(
    "The breakout candle must be large and energetic. It must leave a 'gap' (imbalance) between "
    "the wick of the first candle and the wick of the third candle. "
    "We place our entry Limit Order inside this gap.")

pdf.sub_title("5.3 Stop Loss & Take Profit")
pdf.body_text(
    "STOP LOSS: Placed just below the Swing Low that created the move.\n"
    "TAKE PROFIT 1: The median price of the Asia Range (50% Retracement).\n"
    "TAKE PROFIT 2: The opposing side of the Asia Range (The original High).")

# --- CHAPTER 6: FORWARDFIN TWEAKS ---
pdf.chapter_title(6, "ForwardFin Specific Customizations")
pdf.body_text(
    "Specific rules added for the South African context and user preferences:")

pdf.sub_title("6.1 Time Gating")
pdf.body_text(
    "To avoid low-liquidity churn, the system is hard-coded to ignore all signals outside "
    "09:00 SAST to 21:00 SAST. Even if a perfect setup occurs at 02:00 AM, it is rejected.")

pdf.sub_title("6.2 Data Handling (The V3.9 Patch)")
pdf.body_text(
    "Due to Yahoo Finance latency, the 'Stale Data Guard' has been relaxed to 20 minutes. "
    "This allows the dashboard to remain active, but requires the user to mentally adjust "
    "signals by checking the timestamp manually.")

pdf.output("ForwardFin_Deep_Dive_Strategy.pdf")
print("SUCCESS: Strategy Bible Generated: ForwardFin_Deep_Dive_Strategy.pdf")