import tkinter as tk
from tkinter import ttk
from math import exp, factorial

class FootballBettingModel:
    def __init__(self, root):
        self.root = root
        self.root.title("Momentus Edge")
        self.create_widgets()
        self.history = {
            "home_xg": [],
            "away_xg": [],
            "home_sot": [],
            "away_sot": [],
            "home_possession": [],
            "away_possession": []
        }
        self.history_length = 10  # Store last 10 updates

    def create_widgets(self):
        # Create a canvas and scrollbar
        self.canvas = tk.Canvas(self.root)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.fields = {
            "Home Avg Goals Scored": tk.DoubleVar(),
            "Home Avg Goals Conceded": tk.DoubleVar(),
            "Away Avg Goals Scored": tk.DoubleVar(),
            "Away Avg Goals Conceded": tk.DoubleVar(),
            "Home Xg": tk.DoubleVar(),
            "Away Xg": tk.DoubleVar(),
            "Elapsed Minutes": tk.DoubleVar(),
            "Home Goals": tk.IntVar(),
            "Away Goals": tk.IntVar(),
            "In-Game Home Xg": tk.DoubleVar(),
            "In-Game Away Xg": tk.DoubleVar(),
            "Home Possession %": tk.DoubleVar(),
            "Away Possession %": tk.DoubleVar(),
            "Home Shots on Target": tk.IntVar(),  # New field
            "Away Shots on Target": tk.IntVar(),  # New field
            "Account Balance": tk.DoubleVar(),
            "Live Home Odds": tk.DoubleVar(),
            "Live Away Odds": tk.DoubleVar(),
            "Live Draw Odds": tk.DoubleVar(),
            "Live Next Goal Odds": tk.DoubleVar()  # New field for next goal odds
        }

        row = 0
        for field, var in self.fields.items():
            label = ttk.Label(self.scrollable_frame, text=field)
            label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            entry = ttk.Entry(self.scrollable_frame, textvariable=var)
            entry.grid(row=row, column=1, padx=5, pady=5)
            row += 1

        calculate_button = ttk.Button(self.scrollable_frame, text="Calculate", command=self.calculate_fair_odds)
        calculate_button.grid(row=row, column=0, columnspan=2, pady=10)
        
        reset_button = ttk.Button(self.scrollable_frame, text="Reset Fields", command=self.reset_fields)
        reset_button.grid(row=row+1, column=0, columnspan=2, pady=10)

        # Two separate labels: one for the next goal recommendation and one for additional betting insights.
        self.next_goal_label = ttk.Label(self.scrollable_frame, text="", font=("TkDefaultFont", 10, "bold"))
        self.next_goal_label.grid(row=row+2, column=0, columnspan=2, pady=10)
        self.insight_label = ttk.Label(self.scrollable_frame, text="")
        self.insight_label.grid(row=row+3, column=0, columnspan=2, pady=10)

    def reset_fields(self):
        for var in self.fields.values():
            if isinstance(var, tk.DoubleVar):
                var.set(0.0)
            elif isinstance(var, tk.IntVar):
                var.set(0)
        # Reset the history dictionary
        self.history = {
            "home_xg": [],
            "away_xg": [],
            "home_sot": [],
            "away_sot": [],
            "home_possession": [],
            "away_possession": []
        }

    def zero_inflated_poisson_probability(self, lam, k, p_zero=0.06):
        if k == 0:
            return p_zero + (1 - p_zero) * exp(-lam)
        return (1 - p_zero) * ((lam ** k) * exp(-lam)) / factorial(k)

    def time_decay_adjustment(self, lambda_xg, elapsed_minutes, in_game_xg):
        remaining_minutes = 90 - elapsed_minutes
        # Reduce the exponent rate to 0.01 for a gentler decay
        base_decay = exp(-0.01 * elapsed_minutes)
        # Cap the decay so it never drops below 0.6
        base_decay = max(base_decay, 0.6)

        # Adaptive decay: less decay if in-game xG is high or more decay in final 10 minutes
        if in_game_xg > 1.5:
            base_decay *= 1.15
        elif remaining_minutes < 10:
            base_decay *= 0.65

        adjusted_lambda = lambda_xg * base_decay
        return max(0.1, adjusted_lambda)  # Ensure a minimum probability

    def dynamic_kelly(self, edge):
        # Fixed 5% Kelly criterion regardless of odds
        kelly_fraction = 0.05 * edge
        return max(0, kelly_fraction)

    def update_history(self, key, value):
        """Store the last 10 values of a given key."""
        if key not in self.history:
            self.history[key] = []
        if len(self.history[key]) >= self.history_length:
            self.history[key].pop(0)  # Remove oldest entry
        self.history[key].append(value)

    def get_recent_trend(self, key):
        """Get the recent change over last 3 entries."""
        if key not in self.history or len(self.history[key]) < 3:
            return 0  # Not enough data
        return self.history[key][-1] - self.history[key][-3]

    def detect_momentum_peak(self):
        """Detects if a team is at peak momentum but the market hasn't adjusted yet."""
        trend_home_xg = self.get_recent_trend("home_xg")
        trend_away_xg = self.get_recent_trend("away_xg")
        trend_home_sot = self.get_recent_trend("home_sot")
        trend_away_sot = self.get_recent_trend("away_sot")

        if trend_home_xg > 0.3 and trend_home_sot > 1:
            return "📈 Home team at peak momentum! Possible lay bet on Away before odds adjust."
        elif trend_away_xg > 0.3 and trend_away_sot > 1:
            return "📉 Away team at peak momentum! Possible lay bet on Home before odds adjust."
        return None  # No peak detected

    def detect_market_overreaction(self, fair_home_odds, live_home_odds, fair_away_odds, live_away_odds, fair_draw_odds, live_draw_odds):
        """Identifies when live odds overreact, creating a value lay opportunity."""
        signals = []
        if live_home_odds > fair_home_odds * 1.15:
            signals.append("⚠️ Market overreaction on Home odds!")
        if live_away_odds > fair_away_odds * 1.15:
            signals.append("⚠️ Market overreaction on Away odds!")
        if live_draw_odds > fair_draw_odds * 1.15:
            signals.append("⚠️ Market overreaction on Draw odds!")
        return "\n".join(signals) if signals else None

    def detect_next_goal_overreaction(self, fair_next_goal_odds, live_next_goal_odds):
        """Detects if the bookmaker odds for the next goal market are out of line."""
        if live_next_goal_odds > fair_next_goal_odds * 1.15:
            return f"⚠️ Market overreaction: Back Next Goal at {live_next_goal_odds:.2f} (Fair: {fair_next_goal_odds:.2f})"
        elif live_next_goal_odds < fair_next_goal_odds * 0.85:
            return f"⚠️ Market overreaction: Lay Next Goal at {live_next_goal_odds:.2f} (Fair: {fair_next_goal_odds:.2f})"
        return None

    def detect_reversal_point(self):
        """Detects when a previously dominant team starts fading."""
        trend_home_xg = self.get_recent_trend("home_xg")
        trend_away_xg = self.get_recent_trend("away_xg")
        trend_home_sot = self.get_recent_trend("home_sot")
        trend_away_sot = self.get_recent_trend("away_sot")
        trend_home_possession = self.get_recent_trend("home_possession")
        trend_away_possession = self.get_recent_trend("away_possession")

        if trend_home_xg < 0 and trend_home_sot < 0 and trend_away_possession > 3:
            return "🔄 Home team losing momentum! Possible lay bet on Home."
        elif trend_away_xg < 0 and trend_away_sot < 0 and trend_home_possession > 3:
            return "🔄 Away team losing momentum! Possible lay bet on Away."
        return None

    def optimal_betting_window(self, elapsed_minutes):
        """Suggests best match phase to place lay bets based on in-game trends."""
        if elapsed_minutes < 30:
            return "⚠️ Early Game: High volatility. Only bet if extreme value."
        elif 30 <= elapsed_minutes < 45:
            return "🔍 30-45 min: Watching trends. Lay if strong edge detected."
        elif 45 <= elapsed_minutes < 60:
            return "🛠 45-60 min: Tactical shifts. Lay if favorite struggles."
        elif 60 <= elapsed_minutes < 75:
            return "🔥 Prime Betting Window (60-75 min). Strong lay opportunities!"
        elif elapsed_minutes >= 75:
            return "⚠️ Late Game: Market tightening. Higher risk on lays."

    def adjust_xg_for_scoreline(self, home_goals, away_goals, lambda_home, lambda_away, elapsed_minutes):
        goal_diff = home_goals - away_goals  # Positive if Home is leading, negative if Away is leading

        # Losing team tends to attack more, winning team defends more
        if goal_diff == 1:  # Home leads by 1 goal
            lambda_home *= 0.9
            lambda_away *= 1.2
        elif goal_diff == -1:  # Away leads by 1 goal
            lambda_home *= 1.2
            lambda_away *= 0.9
        elif goal_diff == 0:  # Draw
            lambda_home *= 1.05
            lambda_away *= 1.05
        elif abs(goal_diff) >= 2:  # Team leads by 2 or more
            lambda_home *= 0.8
            lambda_away *= 1.3 if goal_diff > 0 else 0.8

        # Late-game adjustment
        if elapsed_minutes > 75 and abs(goal_diff) >= 1:
            lambda_home *= 0.85
            lambda_away *= 1.15 if goal_diff > 0 else 0.85

        return lambda_home, lambda_away

    def calculate_fair_odds(self):
        # Get values from UI fields
        home_xg = self.fields["Home Xg"].get()
        away_xg = self.fields["Away Xg"].get()
        elapsed_minutes = self.fields["Elapsed Minutes"].get()
        home_goals = self.fields["Home Goals"].get()
        away_goals = self.fields["Away Goals"].get()
        in_game_home_xg = self.fields["In-Game Home Xg"].get()
        in_game_away_xg = self.fields["In-Game Away Xg"].get()
        home_possession = self.fields["Home Possession %"].get()
        away_possession = self.fields["Away Possession %"].get()
        account_balance = self.fields["Account Balance"].get()
        live_home_odds = self.fields["Live Home Odds"].get()
        live_away_odds = self.fields["Live Away Odds"].get()
        live_draw_odds = self.fields["Live Draw Odds"].get()
        live_next_goal_odds = self.fields["Live Next Goal Odds"].get()

        home_avg_goals_scored = self.fields["Home Avg Goals Scored"].get()
        home_avg_goals_conceded = self.fields["Home Avg Goals Conceded"].get()
        away_avg_goals_scored = self.fields["Away Avg Goals Scored"].get()
        away_avg_goals_conceded = self.fields["Away Avg Goals Conceded"].get()

        home_sot = self.fields["Home Shots on Target"].get()
        away_sot = self.fields["Away Shots on Target"].get()

        # Update history for trends
        self.update_history("home_xg", home_xg)
        self.update_history("away_xg", away_xg)
        self.update_history("home_sot", home_sot)
        self.update_history("away_sot", away_sot)
        self.update_history("home_possession", home_possession)
        self.update_history("away_possession", away_possession)

        remaining_minutes = 90 - elapsed_minutes
        lambda_home = self.time_decay_adjustment(in_game_home_xg + (home_xg * remaining_minutes / 90), elapsed_minutes, in_game_home_xg)
        lambda_away = self.time_decay_adjustment(in_game_away_xg + (away_xg * remaining_minutes / 90), elapsed_minutes, in_game_away_xg)

        lambda_home, lambda_away = self.adjust_xg_for_scoreline(home_goals, away_goals, lambda_home, lambda_away, elapsed_minutes)

        lambda_home = (lambda_home * 0.85) + ((home_avg_goals_scored / max(0.75, away_avg_goals_conceded)) * 0.15)
        lambda_away = (lambda_away * 0.85) + ((away_avg_goals_scored / max(0.75, home_avg_goals_conceded)) * 0.15)

        lambda_home *= 1 + ((home_possession - 50) / 200)
        lambda_away *= 1 + ((away_possession - 50) / 200)

        if in_game_home_xg > 1.2:
            lambda_home *= 1.15
        if in_game_away_xg > 1.2:
            lambda_away *= 1.15

        lambda_home *= 1 + (home_sot / 20)
        lambda_away *= 1 + (away_sot / 20)

        # Calculate match outcome probabilities using the zero-inflated Poisson model
        home_win_probability, away_win_probability, draw_probability = 0, 0, 0
        for home_goals_remaining in range(6):
            for away_goals_remaining in range(6):
                prob = self.zero_inflated_poisson_probability(lambda_home, home_goals_remaining) * \
                       self.zero_inflated_poisson_probability(lambda_away, away_goals_remaining)
                if home_goals + home_goals_remaining > away_goals + away_goals_remaining:
                    home_win_probability += prob
                elif home_goals + home_goals_remaining < away_goals + away_goals_remaining:
                    away_win_probability += prob
                else:
                    draw_probability += prob

        total_prob = home_win_probability + away_win_probability + draw_probability
        if total_prob > 0:
            home_win_probability /= total_prob
            away_win_probability /= total_prob
            draw_probability /= total_prob

        fair_home_odds = 1 / home_win_probability if home_win_probability > 0 else 1
        fair_away_odds = 1 / away_win_probability if away_win_probability > 0 else 1
        fair_draw_odds = 1 / draw_probability if draw_probability > 0 else 1

        # Adjust xG values using fair odds influence (still used internally)
        fair_odds_factor_home = (1 / fair_home_odds) / ((1 / fair_home_odds) + (1 / fair_away_odds))
        fair_odds_factor_away = (1 / fair_away_odds) / ((1 / fair_home_odds) + (1 / fair_away_odds))
        lambda_home *= 1 + (fair_odds_factor_home - 0.5) * 0.1
        lambda_away *= 1 + (fair_odds_factor_away - 0.5) * 0.1

        # Apply Bayesian Weighting using recent in-game trends
        weight_home = 1 + (self.get_recent_trend("home_xg") * 0.05) + (self.get_recent_trend("home_sot") * 0.03)
        weight_away = 1 + (self.get_recent_trend("away_xg") * 0.05) + (self.get_recent_trend("away_sot") * 0.03)
        lambda_home *= weight_home
        lambda_away *= weight_away

        # Final Goal Probability Calculation
        scaling_factor = 45  # Prioritize full-half xG
        goal_probability = 1 - exp(-((lambda_home + lambda_away) * remaining_minutes / scaling_factor))
        goal_probability = max(0.30, min(0.90, goal_probability))

        fair_next_goal_odds = 1 / goal_probability

        # Build next goal recommendation text (without showing match fair odds details)
        next_goal_text = f"⚽ Goal Probability: {goal_probability:.2%} → Fair Next Goal Odds: {fair_next_goal_odds:.2f}\n"
        recommendation_type = None
        if live_next_goal_odds > 0:
            edge_back = (live_next_goal_odds - fair_next_goal_odds) / fair_next_goal_odds
            edge_lay = (fair_next_goal_odds - live_next_goal_odds) / fair_next_goal_odds

            kelly_fraction_back = self.dynamic_kelly(edge_back)
            kelly_fraction_lay = self.dynamic_kelly(edge_lay)

            stake_back = (account_balance * kelly_fraction_back) / (live_next_goal_odds - 1) if edge_back > 0 else 0
            liability_lay = account_balance * kelly_fraction_lay
            stake_lay = liability_lay / (live_next_goal_odds - 1) if edge_lay > 0 else 0

            if fair_next_goal_odds > live_next_goal_odds:
                # Lay recommendation → show in green
                next_goal_text += f"Lay Next Goal at {live_next_goal_odds:.2f} | Stake: {stake_lay:.2f} | Liability: {liability_lay:.2f}\n"
                recommendation_type = "lay"
            elif fair_next_goal_odds < live_next_goal_odds:
                # Back recommendation → show in red
                next_goal_text += f"Back Next Goal at {live_next_goal_odds:.2f} | Stake: {stake_back:.2f}\n"
                recommendation_type = "back"

        # Set the text and change foreground color based on recommendation
        if recommendation_type == "lay":
            self.next_goal_label.config(text=next_goal_text, foreground="green")
        elif recommendation_type == "back":
            self.next_goal_label.config(text=next_goal_text, foreground="red")
        else:
            self.next_goal_label.config(text=next_goal_text)

        # Build and display additional betting insights (e.g. momentum signals)
        momentum_signal = self.detect_momentum_peak()
        reversal_signal = self.detect_reversal_point()
        betting_window_signal = self.optimal_betting_window(elapsed_minutes)
        overreaction_signal = self.detect_market_overreaction(
            fair_home_odds, live_home_odds, fair_away_odds, live_away_odds, fair_draw_odds, live_draw_odds
        )
        overreaction_signal_next_goal = self.detect_next_goal_overreaction(fair_next_goal_odds, live_next_goal_odds)

        insight_text = "\n📊 Betting Insights:\n"
        if momentum_signal:
            insight_text += f"{momentum_signal}\n"
        if reversal_signal:
            insight_text += f"{reversal_signal}\n"
        if betting_window_signal:
            insight_text += f"{betting_window_signal}\n"
        if overreaction_signal:
            insight_text += f"{overreaction_signal}\n"
        if overreaction_signal_next_goal:
            insight_text += f"{overreaction_signal_next_goal}\n"

        self.insight_label.config(text=insight_text)

if __name__ == "__main__":
    root = tk.Tk()
    app = FootballBettingModel(root)
    root.mainloop()
