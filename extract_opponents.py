"""Extract each replay's opponent action tape into a standalone fixed-agent .py.

Each generated bot replays the opponent's exact recorded actions by step, so the
29 real ladder opponents become a local sparring pool for run_harness.py.
"""
import json
import glob
import os
import re

REPLAY_DIR = r"C:\Users\harsh\Downloads"
OUT = os.path.join(os.path.dirname(__file__), "opponents")
os.makedirs(OUT, exist_ok=True)


def my_seat(info):
    for i, a in enumerate(info.get("Agents", [])):
        if "harshini" in (a.get("Name", "") or "").lower():
            return i
    return None


def main():
    files = sorted(glob.glob(os.path.join(REPLAY_DIR, "10[56]*.json")))
    manifest = []
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        info = d["info"]
        seat = my_seat(info)
        if seat is None:
            continue
        opp = 1 - seat
        steps = d["steps"]
        tape = [
            (s[opp].get("action") or {"farmer": ["PASS"], "hands": [], "market": []})
            for s in steps
        ]
        ep = os.path.basename(f)[:-5]
        name = re.sub(r"[^A-Za-z0-9]+", "_", info["Agents"][opp]["Name"]).strip("_") or "opp"
        seed = info.get("seed")
        fn = f"opp_{ep}_{name}.py"
        with open(os.path.join(OUT, fn), "w", encoding="utf-8") as w:
            w.write("import json\n")
            w.write(f"# Opponent tape from episode {ep} vs {info['Agents'][opp]['Name']}\n")
            w.write(f"EPISODE_SEED = {seed!r}\n")
            w.write("_TAPE = json.loads(r'''" + json.dumps(tape) + "''')\n\n\n")
            w.write("def agent(obs, config=None):\n")
            w.write("    s = int(obs.get('step', 0) or 0)\n")
            w.write("    if s >= len(_TAPE):\n")
            w.write("        return {'farmer': ['PASS'], 'hands': [], 'market': []}\n")
            w.write("    return _TAPE[s]\n")
        manifest.append(
            {
                "episode": ep,
                "opponent": info["Agents"][opp]["Name"],
                "seed": seed,
                "orig_opp_reward": d["rewards"][opp],
                "orig_my_reward": d["rewards"][seat],
                "orig_margin": d["rewards"][seat] - d["rewards"][opp],
                "file": fn,
            }
        )
    json.dump(manifest, open(os.path.join(OUT, "_manifest.json"), "w"), indent=2)
    print(f"extracted {len(manifest)} opponent tapes -> {OUT}")


if __name__ == "__main__":
    main()
