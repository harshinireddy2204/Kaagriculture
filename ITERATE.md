# The iterate loop: build → gate → submit → analyze → repeat

The ladder is the only faithful rank judge (a replay opponent is a de-guarded
ghost at ~54% strength — beating it predicts nothing). But two local checks
DON'T lie, because they measure your own agent, not a fake opponent. Use them as
a submit gate so you never ship a broken agent (like the 569 clone) again.

## Each cycle

### 1. Make ONE change to a copy of the champion
```
copy main_fscore_cad.py candidate.py     # or edit an existing candidate_*.py
```
Only market-order changes are safe on the tape (sell timing/quantity, buy order).
Changing hire count or unit positions DESYNCS the tape — never do it.

### 2. Signature + crash gate (reliable — your own actions)
```
python score_replay.py <a self-play or any replay of the candidate>
```
Require: no crash, herd >= 14 (not below the champion), hire ~in range. This
catches gross failures before they cost a submission.

### 3. Duel the current champion (faithful — both real agents)
```
python duel.py candidate.py --seeds 6
```
Submit ONLY if verdict is IMPROVEMENT (wins > 55%, positive avg margin). If it's
NO CLEAR GAIN or REGRESSION, the change isn't worth a slot — try another.

### 4. Submit (the ladder decides rank)
```
copy candidate.py main.py
kaggle competitions submit kaggriculture -f main.py -m "cN: <what changed>"
```
Keep the champion as your OTHER active agent so a bad candidate can't tank you.

### 5. Analyze the new losses, decide the next change
```
kaggle competitions submissions kaggriculture           # get submission id
kaggle competitions episodes <SUBMISSION_ID> -v          # list games
# download the loss replays into Downloads, then:
python score_replay.py --dir C:\Users\harsh\Downloads    # herd/hire/$-per-unit vs winners
```
The gap table tells you the next change. Known gaps for fscore_cad:
- herd 14 vs winners 16-17 (TAPE-LOCKED — needs a new tape, not an edit)
- milk $/unit ~$10 below winners (market-layer — addressable)
- close games are coinflips (little overlay room)

## What each tool is for
| tool | use | trustworthy? |
|---|---|---|
| score_replay.py | herd/hire/$-per-unit of any replay | YES (own actions) |
| duel.py | candidate vs champion head-to-head | YES (both real agents) |
| build_candidate.py | clone a strong TAPE into guarded main.py | — |
| harness_replay.py | replay-opponent scores | NO — opponents desync to 54%, do not trust for rank |

## Hard truths (measured this session, so we don't relearn them)
- fscore_cad ~1719 is its tape's ceiling; the 2500 gap is herd size, which is
  frozen in the tape. Overlay edits can only chase the smaller $/unit gap.
- Top players are adaptive -> not clonable (Mengfei & Olympus clones both
  collapsed on replay; the 569 was one of them).
- A from-scratch reactive agent lands at ~1% of tape output (v0-v2) — the v7 trap.
- The real jump comes from adopting a stronger PUBLIC TAPE, screened with
  score_replay before submitting.
