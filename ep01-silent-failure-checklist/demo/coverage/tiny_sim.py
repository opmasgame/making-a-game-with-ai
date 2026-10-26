"""A toy bot simulation with four planted silent failures, to show what to log.

    python tiny_sim.py > events.jsonl
    python ../../action_coverage.py --actions actions.csv events.jsonl

It runs 12 bots for 40 turns and finishes "with zero crashes": every exception is
caught and logged as an error event, the way a real server keeps going. The two
log calls to copy into your own game are marked LOG.
"""
import json
import random
import sys

CARDS = {"docker": "Person", "fixer": "Person", "pawn-shop": "Store", "crowbar": "Item", "badge": "Item"}
DRAW_PILE = ["docker", "fixer", "pawn-shop", "crowbar", "badge"]   # "press-pass" was never added


class Bot:
    def __init__(self, i):
        self.name = f"bot-{i:02d}"
        self.gold = 10
        self.heat = 0
        self.hand = []


# Each action: (gate on the menu, effect when resolved)
def can_odd_jobs(b):
    return True, ""


def can_trade_stocks(b):
    return (b.gold >= 25, "needs 25 gold")


def can_run_shop(b):
    # Planted bug 1: the rule asks for a "Shop" card; the cards say "Store".
    ok = any(CARDS[c] == "Shop" for c in b.hand)
    return ok, "needs a Shop card"


def can_pickpocket(b):
    return (b.heat < 3, "too much heat")


def can_bribe(b):
    return (b.gold >= 1000, "needs 1000 gold")


def can_publish(b):
    return ("press-pass" in b.hand, "needs a press pass")


def can_launder(b):
    return (b.gold >= 30, "needs 30 gold")


def can_rob_bank(b):
    return ("crowbar" in b.hand and b.heat == 0, "needs a crowbar and no heat")


def do_odd_jobs(b):
    b.gold += 3


def do_trade_stocks(b):
    b.gold += random.choice([-10, 15])


def do_run_shop(b):
    b.gold += 8


def do_pickpocket(b):
    b.heat += 1
    if random.random() < 0.6:
        b.gold += 5
        return "success"
    return "failure"   # a failed roll is a rule, not an error


def do_bribe(b):
    b.heat = 0


def do_publish(b):
    b.gold += 2


def do_launder(b):
    rates = {"docks": 0.8}
    b.gold = int(b.gold * rates[b.district])   # Planted bug 3: bots have no district


def do_rob_bank(b):
    b.gold += 200


ACTIONS = {
    "odd-jobs": (can_odd_jobs, do_odd_jobs),
    "trade-stocks": (can_trade_stocks, do_trade_stocks),
    "run-shop": (can_run_shop, do_run_shop),
    "pickpocket": (can_pickpocket, do_pickpocket),
    "bribe-officer": (can_bribe, do_bribe),
    "publish-story": (can_publish, do_publish),   # Planted bug 2: nobody can draw a press pass
    "launder-money": (can_launder, do_launder),
    "rob-bank": (can_rob_bank, do_rob_bank),
}
# Menus only show an action when you hold a card that unlocks it.
UNLOCKED_BY = {"run-shop": "pawn-shop", "publish-story": "press-pass", "rob-bank": "crowbar"}


def log(event):
    print(json.dumps(event))


def menu(b):
    options = []
    for action, (gate, _) in ACTIONS.items():
        if action in UNLOCKED_BY and UNLOCKED_BY[action] not in b.hand:
            continue
        ok, reason = gate(b)
        options.append({"action": action, "possible": ok, **({} if ok else {"reason": reason})})
    log({"type": "menu", "bot": b.name, "options": options})          # LOG 1: what the player saw
    return options


def choose(b, options):
    possible = [o["action"] for o in options if o["possible"]]
    if b.heat >= 3:
        return "bribe-officer"   # Planted bug 4: the command path never checks the gate
    weights = {"rob-bank": 0.01}
    return random.choices(possible, [weights.get(a, 1) for a in possible])[0]


def resolve(b, action):
    try:
        result = ACTIONS[action][1](b) or "success"
        log({"type": "resolved", "bot": b.name, "action": action, "outcome": result})   # LOG 2
    except Exception as e:   # the server keeps going, so nobody notices
        log({"type": "resolved", "bot": b.name, "action": action, "outcome": "error",
             "detail": f"{type(e).__name__}: {e}"})


def main():
    random.seed(7)
    bots = [Bot(i) for i in range(12)]
    for turn in range(40):
        for b in bots:
            if turn % 5 == 0:
                b.hand.append(random.choice(DRAW_PILE))
            resolve(b, choose(b, menu(b)))
    print("simulation finished: 480 turns, 0 crashes", file=sys.stderr)


if __name__ == "__main__":
    main()
