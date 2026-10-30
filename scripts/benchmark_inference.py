"""Local warmed microbenchmark; not a measurement of hosted request latency."""
import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model_bundle import load_bundle
from schema.user_input import UserRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations', type=int, default=300)
    args = parser.parse_args()
    if not 20 <= args.iterations <= 10000:
        parser.error('Use 20–10000 iterations')
    started = perf_counter()
    model, metadata = load_bundle(Path(__file__).resolve().parents[1] / 'model')
    loaded = perf_counter() - started
    profile = UserRequest(age=35, gender_raw='female', height_cm=165, weight_kg=65, city='urban', smoker_raw='no',
        physical_activity_level_raw='medium', daily_steps=7000, sleep_hours=7, stress_level=4, diabetes=0,
        heart_disease=0, medication_count=0, previous_year_cost=5000, insurance_type_raw='private', insurance_coverage_frac=.8)
    matrix = np.array([list(profile.model_features().values())])
    for _ in range(20):
        model.booster_.predict(matrix, pred_contrib=True, num_threads=1)
    samples = {'two_calls': [], 'one_call': []}
    # Alternate ordering to reduce systematic warmup/order bias.
    for index in range(args.iterations):
        for name in (['two_calls', 'one_call'] if index % 2 else ['one_call', 'two_calls']):
            start = perf_counter()
            if name == 'two_calls':
                model.booster_.predict(matrix, num_threads=1)
            values = model.booster_.predict(matrix, pred_contrib=True, num_threads=1)[0]
            float(np.sum(values))
            samples[name].append((perf_counter() - start) * 1000)
    print(json.dumps({'platform': platform.platform(), 'model_version': metadata['model_version'],
        'iterations_per_path': args.iterations, 'model_load_seconds': loaded,
        'latency': {name: {'median_ms': statistics.median(values), 'p95_ms': float(np.percentile(values, 95))} for name, values in samples.items()},
        'limitation': 'Synthetic example profile, warmed local calls, no network or Vercel cold-start timing.'}, indent=2))


if __name__ == '__main__':
    main()
