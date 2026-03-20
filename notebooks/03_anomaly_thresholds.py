# %% [markdown]
# # 03 — Anomaly Threshold Calibration
# **What z-score should trigger an alert per source?**
#
# Current system uses z ≥ 2.0 globally. Bursty sources need higher thresholds,
# stable sources need lower. We find optimal per-source thresholds using
# ROC analysis against YELLOW ground truth.

# %%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc, precision_recall_curve

df = pd.read_parquet("daily_matrix.parquet")
sources = [c for c in df.columns if c not in ("n_yellow", "is_elevated", "total")
           and not c.startswith("cat_")]
y = df["is_elevated"].values

# %% [markdown]
# ## Compute rolling z-scores (7-day window)

# %%
zscores = pd.DataFrame(index=df.index)
for src in sources:
    vals = df[src].astype(float)
    roll_mean = vals.rolling(7, min_periods=3).mean().shift(1)
    roll_std = vals.rolling(7, min_periods=3).std().shift(1).clip(lower=1)
    zscores[src] = (vals - roll_mean) / roll_std

zscores = zscores.fillna(0)
print(f"Z-score matrix: {zscores.shape}")
print(f"\nZ-score ranges per source:")
print(pd.DataFrame({"min": zscores.min(), "max": zscores.max(),
                     "mean": zscores.mean()}).round(2).to_string())

# %% [markdown]
# ## ROC curves per source
# For each source, the z-score is a classifier: z ≥ threshold → predict YELLOW.

# %%
fig, axes = plt.subplots(3, 4, figsize=(16, 12))
axes = axes.flatten()

results = {}
for idx, src in enumerate(sorted(sources)):
    z = zscores[src].values
    if np.std(z) == 0: continue

    fpr, tpr, thresholds = roc_curve(y, z)
    roc_auc = auc(fpr, tpr)

    # Youden's J
    J = tpr - fpr
    best_idx = np.argmax(J)
    best_thresh = thresholds[best_idx]
    best_tpr = tpr[best_idx]
    best_fpr = fpr[best_idx]

    results[src] = {
        "auc": roc_auc, "optimal_z": best_thresh,
        "tpr": best_tpr, "fpr": best_fpr, "J": J[best_idx]
    }

    if idx < len(axes):
        ax = axes[idx]
        ax.plot(fpr, tpr, 'b-', lw=2)
        ax.plot([0, 1], [0, 1], 'k--', alpha=0.3)
        ax.plot(best_fpr, best_tpr, 'ro', markersize=8)
        ax.set_title(f"{src}\nAUC={roc_auc:.2f}, z*={best_thresh:.1f}")
        ax.set_xlabel("FPR")
        ax.set_ylabel("TPR")

# Hide unused axes
for i in range(len(sources), len(axes)):
    axes[i].set_visible(False)

plt.suptitle("Per-Source ROC Curves (z-score → YELLOW)", fontsize=14)
plt.tight_layout()
plt.savefig("roc_curves.png", dpi=150)
plt.show()

# %% [markdown]
# ## Optimal thresholds table

# %%
res_df = pd.DataFrame(results).T.sort_values("auc", ascending=False)
print("Calibrated anomaly thresholds:\n")
print(res_df.round(3).to_string())

print(f"\n\n# For deployment:")
print("ANOMALY_THRESHOLDS = {")
for src, row in res_df.iterrows():
    print(f'    "{src}": {row["optimal_z"]:.1f},  # AUC={row["auc"]:.3f}, J={row["J"]:.3f}')
print("}")

# %% [markdown]
# ## Combined anomaly score
# Weight each source's excess z-score by its AUC (better discriminators get more weight).
#
# $$\text{AnomalyScore}(t) = \sum_i \text{AUC}_i \cdot \max(0,\; z_i(t) - \tau_i^*)$$

# %%
anomaly_scores = np.zeros(len(df))
for src, row in res_df.iterrows():
    z = zscores[src].values
    excess = np.maximum(0, z - row["optimal_z"])
    anomaly_scores += row["auc"] * excess

df_plot = pd.DataFrame({"anomaly_score": anomaly_scores, "is_yellow": y}, index=df.index)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

# Time series
ax1.bar(range(len(df_plot)), df_plot["anomaly_score"],
        color=df_plot["is_yellow"].map({0: "#22c55e", 1: "#ef4444"}))
ax1.set_ylabel("Anomaly Score")
ax1.set_title("Combined Anomaly Score (green=GREEN day, red=YELLOW+ day)")

# Distribution
for label, color in [(0, "#22c55e"), (1, "#ef4444")]:
    vals = df_plot[df_plot["is_yellow"] == label]["anomaly_score"]
    ax2.hist(vals, bins=20, alpha=0.6, color=color,
             label=f"{'GREEN' if label==0 else 'YELLOW+'}", density=True)
ax2.set_xlabel("Anomaly Score")
ax2.set_ylabel("Density")
ax2.legend()

plt.tight_layout()
plt.savefig("anomaly_scores.png", dpi=150)
plt.show()

# Separation quality
from sklearn.metrics import roc_auc_score
combined_auc = roc_auc_score(y, anomaly_scores)
print(f"\nCombined anomaly score AUC: {combined_auc:.3f}")
