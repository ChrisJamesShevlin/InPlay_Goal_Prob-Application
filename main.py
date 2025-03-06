import tkinter as tk
from tkinter import ttk
from math import exp, factorial

class FootballBettingModel:
    def __init__(self, root):
        self.root = root
        self.root.title("Odds Apex In-Play")
        self.create_widgets()
        # History is still maintained for potential future use
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

        # Fields with the updated metrics
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
            "Home Shots on Target": tk.IntVar(),
            "Away Shots on Target": tk.IntVar(),
            # New metrics replacing pass accuracy and tackle success:
            "Home Opp Box Touches": tk.DoubleVar(),
            "Away Opp Box Touches": tk.DoubleVar(),
            "Home Corners": tk.DoubleVar(),
            "Away Corners": tk.DoubleVar(),
            "Account Balance": tk.DoubleVar(),
            "Live Next Goal Odds": tk.DoubleVar()
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

        # Next Goal recommendation label
        self.next_goal_label = ttk.Label(self.scrollable_frame, text="", font=("TkDefaultFont", 10, "bold"))
        self.next_goal_label.grid(row=row+2, column=0, columnspan=2, pady=10)

    def reset_fields(self):
        for var in self.fields.values():
            if isinstance(var, tk.DoubleVar):
                var.set(0.0)
            elif isinstance(var, tk.IntVar):
                var.set(0)
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
        base_decay = exp(-0.01 * elapsed_minutes)
        base_decay = max(base_decay, 0.6)
        if in_game_xg > 1.5:
            base_decay *= 1.15
        elif remaining_minutes < 10:
            base_decay *= 0.65
        adjusted_lambda = lambda_xg * base_decay
        return max(0.1, adjusted_lambda)

    def dynamic_kelly(self, edge):
        kelly_fraction = 0.05 * edge
        return max(0, kelly_fraction)

    def update_history(self, key, value):
        if key not in self.history:
            self.history[key] = []
        if len(self.history[key]) >= self.history_length:
            self.history[key].pop(0)
        self.history[key].append(value)

    def adjust_xg_for_scoreline(self, home_goals, away_goals, lambda_home, lambda_away, elapsed_minutes):
        goal_diff = home_goals - away_goals
        if goal_diff == 1:
            lambda_home *= 0.9
            lambda_away *= 1.2
        elif goal_diff == -1:
            lambda_home *= 1.2
            lambda_away *= 0.9
        elif goal_diff == 0:
            lambda_home *= 1.05
            lambda_away *= 1.05
        elif abs(goal_diff) >= 2:
            lambda_home *= 0.8
            lambda_away *= 1.3 if goal_diff > 0 else 0.8
        if elapsed_minutes > 75 and abs(goal_diff) >= 1:
            lambda_home *= 0.85
            lambda_away *= 1.15 if goal_diff > 0 else 0.85
        return lambda_home, lambda_away

    def calculate_fair_odds(self):
        # Retrieve user inputs
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
        live_next_goal_odds = self.fields["Live Next Goal Odds"].get()

        home_avg_goals_scored = self.fields["Home Avg Goals Scored"].get()
        home_avg_goals_conceded = self.fields["Home Avg Goals Conceded"].get()
        away_avg_goals_scored = self.fields["Away Avg Goals Scored"].get()
        away_avg_goals_conceded = self.fields["Away Avg Goals Conceded"].get()

        home_sot = self.fields["Home Shots on Target"].get()
        away_sot = self.fields["Away Shots on Target"].get()

        # Retrieve new metrics for attacking intent and set pieces
        home_op_box_touches = self.fields["Home Opp Box Touches"].get()
        away_op_box_touches = self.fields["Away Opp Box Touches"].get()
        home_corners = self.fields["Home Corners"].get()
        away_corners = self.fields["Away Corners"].get()

        # Update history (if needed)
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

        # Adjust lambda based on touches in the opposition box and corners.
        # For touches, we use a baseline of 20 and a divisor of 200.
        lambda_home *= 1 + ((home_op_box_touches - 20) / 200)
        lambda_away *= 1 + ((away_op_box_touches - 20) / 200)
        # For corners, we use a baseline of 4 and a divisor of 50.
        lambda_home *= 1 + ((home_corners - 4) / 50)
        lambda_away *= 1 + ((away_corners - 4) / 50)

        # Calculate match outcome probabilities using the zero-inflated Poisson model
        home_win_probability = 0
        away_win_probability = 0
        draw_probability = 0
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

        # Next goal probability settings
        goal_probability = 1 - exp(-((lambda_home + lambda_away) * remaining_minutes / 45))
        goal_probability = max(0.30, min(0.90, goal_probability))
        fair_next_goal_odds = 1 / goal_probability

        # Build the output text: always show fair odds along with goal probability.
        next_goal_text = f"⚽ Goal Probability: {goal_probability:.2%} → Fair Next Goal Odds: {fair_next_goal_odds:.2f}\n"

        # Only consider lay bets: recommend a lay bet if live odds are lower than fair odds.
        if live_next_goal_odds > 0 and fair_next_goal_odds > live_next_goal_odds:
            edge_lay = (fair_next_goal_odds - live_next_goal_odds) / fair_next_goal_odds
            if edge_lay > 0:
                kelly_fraction_lay = self.dynamic_kelly(edge_lay)
                liability_lay = account_balance * kelly_fraction_lay
                stake_lay = liability_lay / (live_next_goal_odds - 1) if (live_next_goal_odds - 1) > 0 else 0
                next_goal_text += f"Lay Next Goal at {live_next_goal_odds:.2f} | Stake: {stake_lay:.2f} | Liability: {liability_lay:.2f}\n"
                recommendation_type = "lay"
            else:
                next_goal_text += "Not bet found"
                recommendation_type = "no"
        else:
            next_goal_text += "Not bet found"
            recommendation_type = "no"

        # Set the label color: green if a lay bet is recommended, red otherwise.
        if recommendation_type == "lay":
            self.next_goal_label.config(text=next_goal_text, foreground="green")
        else:
            self.next_goal_label.config(text=next_goal_text, foreground="red")

if __name__ == "__main__":
    root = tk.Tk()
    app = FootballBettingModel(root)
    root.mainloop()
