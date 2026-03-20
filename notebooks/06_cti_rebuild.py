# %% [markdown]
# # 06 — CTI Formula Rebuild from Data
# Build three competing models. Evaluate with proper cross-validation.
# Export the winner as a deployable formula.
#
# 1. **Hand-tuned CTI** — current production weights
# 2. **Logistic Regression** — L2 regularized, z-score features
# 3. **Gradient Boosted Trees** — catches non-linear interactions

# %%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegressionCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit, cross_validate
from sklearn.metrics import (f1_score, precision_score, recall_score,
                              accuracy_score, roc_auc_score, make_scorer,
                              classification_report, ConfusionMatrixDisplay)
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

df = pd.read_parquet("daily_matrix.parquet")
sources = [c for c in df.columns if c not in ("n_yellow", "is_elevated", "total")
           and not c.startswith("cat_")]
active = [s for s in sources if df[s].std() > 0]

# %% [markdown]
# ## Feature engineering
# - Raw counts
# - 7-day rolling z-scores
# - 3-day momentum (velocity)
# - Day-of-week (weekend effect)

# %%
features = pd.DataFrame(index=df.index)

for src in active:
    vals = df[src].astype(float)
    roll_mean = vals.rolling(7, min_periods=1).mean().shift(1).fillna(0)
    roll_std = vals.rolling(7, min_periods=1).std().shift(1).fillna(1).clip(lower=1)

    features[f"{src}_z"] = (vals - roll_mean) / roll_std       # z-score
    features[f"{src}_vel"] = vals.diff(3).fillna(0) / 3        # velocity
    features[f"{src}_raw"] = vals                               # raw count

features["day_of_week"] = df.index.dayofweek
features["is_weekend"] = (features["day_of_week"] >= 5).astype(int)
features["total"] = df[active].sum(axis=1)
features["total_z"] = (features["total"] - features["total"].rolling(7).mean().shift(1).fillna(0)) / \
                       features["total"].rolling(7).std().shift(1).fillna(1).clip(lower=1)

X = features.fillna(0).values
y = df["is_elevated"].values

print(f"Feature matrix: {X.shape} ({X.shape[1]} features)")
print(f"YELLOW+ prevalence: {y.mean():.1%}")

# %% [markdown]
# ## Model 1: Hand-tuned CTI (current production)

# %%
HAND_W = {"gpsjam": 20, "adsb": 15, "acled": 15, "firms": 15,
          "ais": 10, "telegram": 10, "rss": 5, "gdelt": 5, "ioda": 5}
total_w = sum(HAND_W.values())

hand_scores = np.zeros(len(df))
for src, w in HAND_W.items():
    if f"{src}_z" in features.columns:
        z = features[f"{src}_z"].clip(lower=0).values
        hand_scores += np.minimum(z * 10, 100) * (w / total_w)

# Sweep threshold
best_f1, best_t = 0, 15.2
for t in np.arange(1, 50, 0.5):
    preds = (hand_scores >= t).astype(int)
    f1 = f1_score(y, preds, zero_division=0)
    if f1 > best_f1:
        best_f1, best_t = f1, t

hand_preds = (hand_scores >= best_t).astype(int)
print(f"Model 1 — Hand-tuned CTI (threshold={best_t:.1f})")
print(classification_report(y, hand_preds, target_names=["GREEN", "YELLOW+"]))

# %% [markdown]
# ## Model 2: Logistic Regression (L2, cross-validated C)

# %%
tscv = TimeSeriesSplit(n_splits=3)

pipe_lr = Pipeline([
    ("scaler", StandardScaler()),
    ("lr", LogisticRegressionCV(Cs=10, cv=tscv, scoring="f1", class_weight="balanced",
                                 max_iter=1000, random_state=42))
])
pipe_lr.fit(X, y)
lr_preds = pipe_lr.predict(X)
lr_proba = pipe_lr.predict_proba(X)[:, 1]

print(f"Model 2 — Logistic Regression (C={pipe_lr['lr'].C_[0]:.3f})")
print(classification_report(y, lr_preds, target_names=["GREEN", "YELLOW+"]))

# Top coefficients
coefs = pd.Series(pipe_lr["lr"].coef_[0], index=features.columns).abs().sort_values(ascending=False)
print("Top 10 features (|coef|):")
print(coefs.head(10).round(4).to_string())

# %% [markdown]
# ## Model 3: Gradient Boosted Trees

# %%
pipe_gb = Pipeline([
    ("scaler", StandardScaler()),
    ("gb", GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.1,
                                       random_state=42))
])
pipe_gb.fit(X, y)
gb_preds = pipe_gb.predict(X)
gb_proba = pipe_gb.predict_proba(X)[:, 1]

print(f"Model 3 — Gradient Boosted Trees")
print(classification_report(y, gb_preds, target_names=["GREEN", "YELLOW+"]))

# Feature importance
gb_imp = pd.Series(pipe_gb["gb"].feature_importances_, index=features.columns
                    ).sort_values(ascending=False)
print("Top 10 features (importance):")
print(gb_imp.head(10).round(4).to_string())

# %% [markdown]
# ## Time-series cross-validation (proper evaluation)

# %%
scoring = {"f1": "f1", "precision": "precision", "recall": "recall",
           "accuracy": "accuracy", "auc": "roc_auc"}

# Can't CV the hand-tuned model easily, so we do LR and GB
cv_lr = cross_validate(
    Pipeline([("scaler", StandardScaler()),
              ("lr", LogisticRegressionCV(Cs=5, cv=3, class_weight="balanced",
                                          max_iter=1000, random_state=42))]),
    X, y, cv=tscv, scoring=scoring)

cv_gb = cross_validate(
    Pipeline([("scaler", StandardScaler()),
              ("gb", GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42))]),
    X, y, cv=tscv, scoring=scoring)

print(f"\n{'='*65}")
print(f"  TIME-SERIES CROSS-VALIDATION (3-fold)")
print(f"{'='*65}\n")
print(f"  {'Model':30s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} {'AUC':>8s}")
print(f"  {'─'*60}")
print(f"  {'Hand-tuned (in-sample only)':30s} {f1_score(y, hand_preds):.3f}    {'—':>8s} {'—':>8s} {'—':>8s}")

for name, cv in [("Logistic Regression", cv_lr), ("Gradient Boosted Trees", cv_gb)]:
    f1 = f"{cv['test_f1'].mean():.3f}±{cv['test_f1'].std():.3f}"
    prec = f"{cv['test_precision'].mean():.3f}±{cv['test_precision'].std():.3f}"
    rec = f"{cv['test_recall'].mean():.3f}±{cv['test_recall'].std():.3f}"
    auc_s = f"{cv['test_auc'].mean():.3f}±{cv['test_auc'].std():.3f}"
    print(f"  {name:30s} {f1:>8s} {prec:>8s} {rec:>8s} {auc_s:>8s}")

# %% [markdown]
# ## Confusion matrices

# %%
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
for ax, preds, title in [(axes[0], hand_preds, "Hand-tuned CTI"),
                          (axes[1], lr_preds, "Logistic Regression"),
                          (axes[2], gb_preds, "Gradient Boosted")]:
    ConfusionMatrixDisplay.from_predictions(y, preds, display_labels=["GREEN", "YELLOW+"],
                                            ax=ax, cmap="Blues")
    ax.set_title(title)
plt.tight_layout()
plt.savefig("confusion_matrices.png", dpi=150)
plt.show()

# %% [markdown]
# ## Export winning formula

# %%
print(f"\n{'='*65}")
print(f"  DEPLOYABLE FORMULA")
print(f"{'='*65}\n")

# Export logistic regression coefficients (most interpretable)
lr_model = pipe_lr["lr"]
scaler = pipe_lr["scaler"]
coef = lr_model.coef_[0]
intercept = lr_model.intercept_[0]

# Only significant features
sig_features = [(features.columns[i], coef[i])
                for i in np.argsort(np.abs(coef))[::-1]
                if np.abs(coef[i]) > 0.1]

print("def compute_cti_v2(source_z_scores: dict, source_velocities: dict,")
print("                    total_signals: int, is_weekend: bool) -> tuple:")
print(f'    """Logistic CTI — trained on {len(df)} days, {int(y.sum())} YELLOW events."""')
print(f"    score = {intercept:.4f}  # intercept")
for feat, c in sig_features[:15]:
    print(f"    score += {c:+.4f} * {feat}")
print("    prob = 1 / (1 + exp(-score))")
print("    cti = prob * 100")
print("    if cti >= 92.8: return cti, 'RED'")
print("    if cti >= 59.7: return cti, 'ORANGE'")
print("    if cti >= 15.2: return cti, 'YELLOW'")
print("    return cti, 'GREEN'")
