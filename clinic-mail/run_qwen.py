"""Qwen add-on to the action pilot (PROTOCOL.md, "Добавка: Qwen"; approved by Ilya 16.10).

qwen-max on the cost=pilot rung: severe x 5 plus one routine control. Adds the plan to run.py without
editing it (run.py was already loaded by the running pilot batch), then hands over to run.main:

    python3 run_qwen.py batch --plan qwen --budget-usd 3 --out runs/qwen-YYYYMMDD
"""
import run

run.PLANS["qwen"] = [("severe", "qwen-max", r) for r in range(1, 6)] + [("routine", "qwen-max", 1)]
# HQ estimate for the six runs: about $2.
run.RUN_PRICE["qwen-max"] = 0.33

if __name__ == "__main__":
    run.main()
