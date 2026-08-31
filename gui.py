import tkinter as tk
from tkinter import ttk, filedialog
import json
from engine import Die, KeepIfHigherChance, KeepHighest, roll_dice, simulate


class DiceGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Dice Simulator")

        self.dice_rows = []

        # Dice configuration area
        dice_frame = ttk.LabelFrame(root, text="Dice")
        dice_frame.pack(padx=10, pady=10, fill="x")

        ttk.Button(
            dice_frame,
            text="Add Die",
            command=self.add_die
        ).pack(pady=5)

        self.dice_list = ttk.Frame(dice_frame)
        self.dice_list.pack(fill="x")

        # Rule settings
        rules_frame = ttk.LabelFrame(root, text="Rule Settings")
        rules_frame.pack(padx=10, pady=5, fill="x")

        ttk.Label(rules_frame, text="Threshold:").pack(side="left")

        self.threshold = ttk.Entry(rules_frame, width=10)
        self.threshold.insert(0, "0.50")
        self.threshold.pack(side="left", padx=5)

        
        ttk.Label(rules_frame, text="Rerolls:").pack(side="left")

        self.rerolls = ttk.Entry(rules_frame, width=10)
        self.rerolls.insert(0, "2")
        self.rerolls.pack(side="left", padx=5)

        # Simulation count
        ttk.Label(rules_frame, text="Simulations:").pack(side="left")

        self.simulations = ttk.Entry(rules_frame, width=10)
        self.simulations.insert(0, "100000")
        self.simulations.pack(side="left", padx=5)

        ttk.Button(
            root,
            text="Roll Once",
            command=self.run_roll
        ).pack(pady=5)

        ttk.Button(
            root,
            text="Run Simulation",
            command=self.run_simulation
        ).pack(pady=5)

        ttk.Button(
            root,
            text="Save Settings",
            command=self.save_settings
        ).pack(pady=5)

        ttk.Button(
            root,
            text="Load Settings",
            command=self.load_settings
        ).pack(pady=5)

        # Results
        results_frame = ttk.LabelFrame(root, text="Results")
        results_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.results = tk.Text(results_frame, height=10, width=50)
        self.results.pack(padx=5, pady=5, fill="both", expand=True)
    

    def add_die(self):
        row = ttk.Frame(self.dice_list)
        row.pack(fill="x", pady=2)

        ttk.Label(row, text="Count:").pack(side="left")

        count = ttk.Entry(row, width=5)
        count.insert(0, "1")
        count.pack(side="left", padx=5)

        ttk.Label(row, text="Faces:").pack(side="left")

        faces = ttk.Entry(row, width=30)
        faces.pack(side="left", padx=5)

        remove = ttk.Button(
            row,
            text="Remove",
            command=lambda: self.remove_die(row)
        )
        remove.pack(side="left")

        self.dice_rows.append((row, count, faces))

    def remove_die(self, row):
        for i, (stored_row, count, faces) in enumerate(self.dice_rows):
            if stored_row == row:
                self.dice_rows.pop(i)
                break

        row.destroy()

    def get_dice(self):
        dice = []
        for _, count_entry, faces_entry in self.dice_rows:
            count = int(count_entry.get())
            faces = [
                int(value.strip())
                for value in faces_entry.get().split(",")
            ]

            for _ in range(count):
                dice.append(Die(faces))

        return dice
    
    def run_roll(self):
        dice = self.get_dice()
        threshold = float(self.threshold.get())
        rerolls = int(self.rerolls.get())
        rule = KeepIfHigherChance(threshold)
        roll_dice(dice, rule, rerolls)

        self.results.delete("1.0", tk.END)
        self.results.insert(
            tk.END,
            str([die.value for die in dice])
        )

    def run_simulation(self):
        dice = self.get_dice()
        threshold = float(self.threshold.get())
        rerolls = int(self.rerolls.get())
        rule = KeepIfHigherChance(threshold)
        sims = int(self.simulations.get())
        avg = simulate(dice, rule, rerolls, sims)

        self.results.delete("1.0", tk.END)
        self.results.insert(
            tk.END,
            str(avg)
        )

    def save_settings(self):
        settings = {
            "dice": [],
            "threshold": float(self.threshold.get()),
            "rerolls": int(self.rerolls.get()),
            "simulations": int(self.simulations.get())
        }

        for _, count_entry, faces_entry in self.dice_rows:
            settings["dice"].append({
                "count": int(count_entry.get()),
                "faces": [
                    int(value.strip())
                    for value in faces_entry.get().split(",")
                ]
            })

        filename = filedialog.asksaveasfilename(
            title="Save Settings",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )

        if filename:
            with open(filename, "w") as file:
                json.dump(settings, file, indent=4)
    def load_settings(self):
        filename = filedialog.askopenfilename(
            title="Load Settings",
            filetypes=[("JSON files", "*.json")]
        )

        if not filename:
            return

        with open(filename, "r") as file:
            settings = json.load(file)

        self.threshold.delete(0, tk.END)
        self.threshold.insert(0, str(settings["threshold"]))

        self.rerolls.delete(0, tk.END)
        self.rerolls.insert(0, str(settings["rerolls"]))

        self.simulations.delete(0, tk.END)
        self.simulations.insert(0, str(settings["simulations"]))

        # Remove existing dice rows
        for row, _, _ in self.dice_rows:
            row.destroy()

        self.dice_rows.clear()

        # Recreate dice rows
        for die in settings["dice"]:
            self.add_die()

            _, count_entry, faces_entry = self.dice_rows[-1]

            count_entry.delete(0, tk.END)
            count_entry.insert(0, str(die["count"]))

            faces_entry.insert(
                0,
                ", ".join(str(face) for face in die["faces"])
            )