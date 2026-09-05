from abc import ABC, abstractmethod
import random

class Die:
    def __init__(self, faces):
        self.faces = list(faces)
        self.value = None
    def __repr__(self):
        return str(self.value)

    def roll(self):
        self.value = random.choice(self.faces)
        return self.value

    def probability_higher(self, value):
        higher = sum(face > value for face in self.faces)
        return higher / len(self.faces)

    
    
class Rule(ABC):

    @abstractmethod
    def should_keep(self, dice, rerolls_left):
        """
        Returns:
            sorted_dice: Die objects sorted by current value, descending
            keep: boolean list corresponding to sorted_dice
        """
        pass

class KeepHighest(Rule):

    def __init__(self, count):
        self.count = count

    def should_keep(self, dice, rerolls_left):
        sorted_dice = sorted(
            dice,
            key=lambda die: die.value,
            reverse=True
        )

        keep = [i < self.count for i in range(len(sorted_dice))]

        return sorted_dice, keep

class KeepIfHigherChance(Rule):

    def __init__(self, threshold):
        self.threshold = threshold

    def should_keep(self, dice, rerolls_left):
        dice = sorted(dice, key=lambda die: die.value, reverse=True)

        keep = []

        for die in dice:
            if rerolls_left == 0:
                keep.append(True)
                continue

            p_higher = die.probability_higher(die.value)

            p_improve = 1 - (1 - p_higher) ** rerolls_left

            keep.append(p_improve <= self.threshold)

        return dice, keep

def roll_dice(dice, rule, rerolls):
    for die in dice:
        die.roll()

    for rerolls_left in range(rerolls, 0, -1):
        sorted_dice, keep = rule.should_keep(dice, rerolls_left)

        for die, should_keep in zip(sorted_dice, keep):
            if not should_keep:
                die.roll()

    return dice

def roll_value(dice):
    sum = 0
    for d in dice:
        sum += d.value
    return sum

def simulate_distribution(dice, rule, rerolls, sims):
    return [roll_value(roll_dice(dice, rule, rerolls)) for _ in range(sims)]


def simulate(dice, rule, rerolls, sims):
    results = simulate_distribution(dice, rule, rerolls, sims)
    return sum(results) / sims

