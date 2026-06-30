#!/usr/bin/env python3
"""
v5.22 Stage 0 量化腳本: tech_score_multifactor 的 ma50 factor ratio-based 設計 pitfall

量化目標:
  1. Stage 1c 線性掃描每個 param,量化 flat-step 比例
  2. 真實場景復現: price 固定, ma50 從 50 掃到 500,看 score 是否真實連續

設計意圖 (v5.9 floor 提高但保留 ratio-based scaling):
  ma50_factor = (
      if price >= ma50: min(0.85, 0.6 + 0.2 * (price/ma50 - 1.0) / 0.2)
      else: max(0.2, 0.4 - 0.2 * (1 - (price/ma50 - 0.8) / 0.2))
  )

Pitfall: 當 price 固定, ma50 變化時, (price/ma50) 在 ma50 > price 區域梯度極小,
  導致 ma50=50,100,150 三個完全相同 score (flat)。

待 v5.22 P41 修復: 改用 absolute diff:
  ma50_pct_diff = (price - ma50) / ma50  # 真實相對差
  ma50_factor = clip(0.5 + 0.5 * ma50_pct_diff, 0.2, 0.85)
"""
import sys
sys.path.insert(0, 'scripts')
import stock_analysis as sa
import numpy as np


def scan_full_per_param(fn, ranges, params_to_scan, n_steps=50):
    """對每個 input param 沿自己全 range linear scan, 看 score gradient"""
    results = {}
    base_kwargs = {p: np.random.uniform(*ranges[p]) if p in ranges else 0.0
                   for p in inspect_param_names(fn)}
    for param in params_to_scan:
        if param not in ranges:
            continue
        low, high = ranges[param]
        xs = np.linspace(low, high, n_steps)
        ys = []
        for x in xs:
            kwargs = dict(base_kwargs)
            kwargs[param] = float(x)
            try:
                ys.append(fn(**kwargs))
            except Exception:
                ys.append(None)
        ys = [y for y in ys if y is not None]
        diffs = np.diff(ys) if len(ys) > 1 else []
        results[param] = {
            'range': [float(ys[0]) if ys else 0.0, float(ys[-1]) if ys else 0.0],
            'min': float(min(ys)) if ys else 0.0,
            'max': float(max(ys)) if ys else 0.0,
            'zero_slope_steps': int(np.sum(np.abs(diffs) < 1e-6)),
        }
    return results


def inspect_param_names(fn):
    import inspect
    return list(inspect.signature(fn).parameters.keys())


def ma50_scenario(price=200.0, rsi=50, macd=0, momentum=0.05):
    """真實場景: price 固定, ma50 變化"""
    ma50_values = [50, 100, 150, 180, 195, 200, 205, 220, 250, 300]
    print(f"price fixed @ {price}, rsi={rsi}, macd={macd}, momentum={momentum}")
    print(f"{'ma50':>8} | {'score':>10}")
    out = {}
    for ma50 in ma50_values:
        s = sa.tech_score_multifactor(rsi=rsi, macd_val=macd, price=price,
                                      ma50=ma50, momentum_20d=momentum)
        out[ma50] = s
        print(f"{ma50:>8.1f} | {s:>10.4f}")
    flat_unique = len(set(out.values()))
    print(f"\n真實 flat: {flat_unique}/{len(out)} (unique values)")
    return out


def main():
    print("=" * 60)
    print("v5.22 Stage 0 量化: tech_score_multifactor.ma50_factor pitfall")
    print("=" * 60)

    tech_ranges = {
        'rsi': (0, 100), 'macd_val': (-5, 5),
        'price': (10, 500), 'ma50': (10, 500),
        'momentum_20d': (-0.3, 0.3),
    }

    # Stage 1c: per-param gradient scan
    print("\n=== Stage 1c: Per-param slope-zero step count ===")
    results = scan_full_per_param(
        sa.tech_score_multifactor, tech_ranges,
        params_to_scan=['rsi', 'macd_val', 'price', 'ma50', 'momentum_20d'],
    )
    for param, info in results.items():
        n_flat = info['zero_slope_steps']
        flag = "🔴 " if n_flat > 5 else "✅ "
        print(f"  {flag}{param}: zero-slope {n_flat}/49 steps, "
              f"score range [{info['min']:.4f}, {info['max']:.4f}]")

    # 真實場景
    print("\n=== Real scenario: price=$200 fixed, ma50 varies ===")
    out = ma50_scenario()
    flat_count = sum(1 for v in out.values() if v == max(out.values()))
    if flat_count >= 2:
        print(f"\n[REAL PITFALL] {flat_count} ma50 values → identical score")
        print("  Fix: replace ratio-based ma50_factor with absolute-diff-based")
    else:
        print("\n[OK] ma50 score 真實連續")


if __name__ == "__main__":
    main()
