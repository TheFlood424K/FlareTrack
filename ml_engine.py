# ml_engine.py
# Phase 2: Random Forest classifier for flare-up risk prediction.
#
# Trains on severity-weighted daily log data exported by
# FlareUpPredictor.export_training_data().  Feature importances are
# capped at 35% (IMPORTANCE_CAP) so no single variable dominates the
# prediction — excess importance is redistributed proportionally to
# all other features.
#
# Entry point for ai_engine.py:
#   from ml_engine import load_model
#   model = load_model()          # None if data/model.pkl not found
#   result = model.predict(agg)   # dict with risk_score, risk_level

import json
import os
import pickle
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import Pipeline
    _SKLEARN_OK = True
except ImportError:
    _SKLEARN_OK = False

MODEL_PATH     = "data/model.pkl"
MIN_TRAIN_DAYS = 30
IMPORTANCE_CAP = 0.35   # no single feature may exceed this share of total importance

# Numeric features fed to the classifier.
# Excludes: date, triggers (text), avg_severity/max_severity/is_flare_day/severity_weight
# (those are the label or derived directly from it).
FEATURE_COLS: List[str] = [
    "symptom_count",
    "medication_adherence",
    "sleep_hours",
    "sleep_quality",
    "stress_level",
    "exercise_minutes",
    "temperature_f",
    "humidity_percent",
    "air_quality_index",
    "barometric_pressure_hpa",
    "alcohol_units",
    "caffeine_mg",
    "hydration_oz",
]


# =========================================================
# IMPORTANCE CAP
# =========================================================

def _apply_cap(raw: Any, cap: float = IMPORTANCE_CAP) -> Any:
    """Cap each feature importance at `cap`, redistributing excess proportionally.

    Iterates until no feature exceeds the cap.  In degenerate cases where all
    free features are also above cap (only possible with very few features),
    excess is spread evenly and a final normalisation keeps the sum at 1.0.
    Note: with 13 features and cap=0.35 this edge-case cannot occur.
    """
    if not _SKLEARN_OK:
        return raw
    result      = np.array(raw, dtype=float)
    capped_mask = np.zeros(len(result), dtype=bool)

    for _ in range(len(result)):
        newly_over = (~capped_mask) & (result > cap)
        if not newly_over.any():
            break
        excess = float((result[newly_over] - cap).sum())
        result[newly_over] = cap
        capped_mask |= newly_over

        free = ~capped_mask
        if free.any():
            free_sum = float(result[free].sum())
            if free_sum > 0:
                result[free] += excess * result[free] / free_sum
            else:
                result[free] += excess / float(int(free.sum()))
        # else: all features at cap — excess cannot be redistributed further

    total = float(result.sum())
    if total > 0:
        result = result / total
    return result


# =========================================================
# MODEL CLASS
# =========================================================

class FlareRFModel:
    """Random Forest classifier for flare-up risk prediction.

    Typical workflow:
        model = FlareRFModel()
        report = model.train(records)     # records from export_training_data()
        result = model.predict(features)  # {'risk_score': 0.72, 'risk_level': 'high', ...}
        model.save()                      # → data/model.pkl
        model2 = FlareRFModel.load()      # reload from disk
    """

    def __init__(self) -> None:
        self._pipeline:           Optional[Any]      = None
        self._feature_cols:       List[str]          = FEATURE_COLS[:]
        self._importances_raw:    Dict[str, float]   = {}
        self._importances_capped: Dict[str, float]   = {}
        self._meta:               Dict[str, Any]     = {}

    # =========================================================
    # TRAINING
    # =========================================================

    def train(self, records: List[Dict], save_path: str = MODEL_PATH) -> Dict[str, Any]:
        """Fit the Random Forest on exported training records.

        Args:
            records:   List of feature dicts from FlareUpPredictor.export_training_data().
            save_path: Where to persist the trained model (default: data/model.pkl).

        Returns:
            Report dict: {status, n_samples, n_flare_days, cv_auc,
                          importances_capped, importances_raw, capped_features}
            On failure: {error: str}
        """
        if not _SKLEARN_OK:
            return {"error": "scikit-learn / numpy not installed. Run: pip install scikit-learn numpy"}

        # Use only days that have actual symptom data; phantom "empty day" records
        # produced by extract_features_range() for unlogged calendar days are excluded
        # to match the behaviour of _load_range_features() used at prediction time.
        valid = [
            r for r in records
            if r.get("is_flare_day") is not None and r.get("symptom_count", 0) > 0
        ]

        if len(valid) < MIN_TRAIN_DAYS:
            return {
                "error": (
                    f"Need at least {MIN_TRAIN_DAYS} logged days with symptoms, "
                    f"found {len(valid)}. Keep logging daily to enable ML predictions."
                )
            }

        X_rows, y_vals, sw_vals = [], [], []
        for r in valid:
            row = [
                float("nan") if r.get(col) is None else float(r[col])
                for col in FEATURE_COLS
            ]
            X_rows.append(row)
            y_vals.append(1 if r["is_flare_day"] else 0)
            sw_vals.append(float(r.get("severity_weight", 1.0)))

        X  = np.array(X_rows, dtype=float)
        y  = np.array(y_vals,  dtype=int)
        sw = np.array(sw_vals, dtype=float)

        n_flare    = int(y.sum())
        n_nonflare = len(y) - n_flare

        if n_flare < 2 or n_nonflare < 2:
            return {
                "error": (
                    f"Need at least 2 flare days and 2 non-flare days to train. "
                    f"Found {n_flare} flare, {n_nonflare} non-flare. "
                    f"Log more high-severity symptoms (severity ≥7) to enable training."
                )
            }

        # Pipeline: median imputation → Random Forest
        # sample_weight is passed to the RF step via sklearn's fit params forwarding.
        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("rf", RandomForestClassifier(
                n_estimators=200,
                max_depth=6,
                min_samples_leaf=3,
                random_state=42,
            )),
        ])
        pipeline.fit(X, y, rf__sample_weight=sw)

        # Feature importances + 35% reinforcement cap
        raw_imp    = pipeline.named_steps["rf"].feature_importances_
        capped_imp = _apply_cap(raw_imp.copy())

        importances_raw    = dict(zip(FEATURE_COLS, raw_imp.tolist()))
        importances_capped = dict(zip(FEATURE_COLS, capped_imp.tolist()))
        capped_features    = [
            col for col, ri in zip(FEATURE_COLS, raw_imp.tolist())
            if ri > IMPORTANCE_CAP + 0.001
        ]

        # Cross-validation ROC-AUC (unweighted — estimates generalisation quality)
        cv_auc = None
        if n_flare >= 3 and n_nonflare >= 3:
            cv_fold  = min(5, n_flare, n_nonflare)
            cv_pipe  = Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("rf",      RandomForestClassifier(n_estimators=100, random_state=42)),
            ])
            try:
                scores = cross_val_score(cv_pipe, X, y, cv=cv_fold, scoring="roc_auc")
                cv_auc = round(float(scores.mean()), 3)
            except Exception:
                cv_auc = None

        self._pipeline           = pipeline
        self._feature_cols       = FEATURE_COLS[:]
        self._importances_raw    = importances_raw
        self._importances_capped = importances_capped
        self._meta = {
            "trained_at":   datetime.now().isoformat(),
            "n_samples":    len(valid),
            "n_flare_days": n_flare,
            "n_features":   len(FEATURE_COLS),
            "cv_auc":       cv_auc,
        }

        self.save(save_path)

        return {
            "status":             "ok",
            "trained_at":         self._meta["trained_at"],
            "n_samples":          len(valid),
            "n_flare_days":       n_flare,
            "cv_auc":             cv_auc,
            "importances_capped": importances_capped,
            "importances_raw":    importances_raw,
            "capped_features":    capped_features,
        }

    # =========================================================
    # FEATURE AGGREGATION
    # =========================================================

    def aggregate_features(self, rows: List[Dict]) -> Dict[str, Optional[float]]:
        """Severity-weighted mean of each feature across a window of logged days.

        Called by ai_engine.predict_flare_risk() to collapse the last 14 logged
        days into a single feature vector for the ML prediction.
        """
        result: Dict[str, Optional[float]] = {}
        for col in self._feature_cols:
            pairs = [
                (float(r[col]), float(r.get("severity_weight", 1.0)))
                for r in rows
                if r.get(col) is not None
            ]
            if pairs:
                total_w    = sum(w for _, w in pairs)
                result[col] = sum(v * w for v, w in pairs) / total_w if total_w > 0 else None
            else:
                result[col] = None
        return result

    # =========================================================
    # PREDICTION
    # =========================================================

    def predict(self, feature_row: Dict) -> Dict[str, Any]:
        """Return a risk prediction for a single (possibly aggregated) feature vector.

        Args:
            feature_row: Dict with FEATURE_COLS keys; None values are imputed.

        Returns:
            {risk_score: float 0-1, risk_level: str, method: str, trained_at: str}
        """
        if self._pipeline is None:
            raise RuntimeError("Model not trained. Call train() or load() first.")
        if not _SKLEARN_OK:
            raise RuntimeError("scikit-learn not available.")

        X = np.array(
            [[float("nan") if feature_row.get(col) is None else float(feature_row[col])
              for col in self._feature_cols]],
            dtype=float,
        )
        proba = float(self._pipeline.predict_proba(X)[0][1])

        if proba >= 0.65:
            risk_level = "high"
        elif proba >= 0.35:
            risk_level = "moderate"
        else:
            risk_level = "low"

        return {
            "risk_score": round(proba, 3),
            "risk_level": risk_level,
            "method":     "random_forest",
            "trained_at": self._meta.get("trained_at"),
        }

    # =========================================================
    # IMPORTANCES
    # =========================================================

    def get_importances(self) -> Dict[str, float]:
        """Capped feature importances sorted by descending importance."""
        return dict(sorted(self._importances_capped.items(), key=lambda kv: -kv[1]))

    # =========================================================
    # PERSISTENCE
    # =========================================================

    def save(self, path: str = MODEL_PATH) -> None:
        dir_ = os.path.dirname(path)
        if dir_:
            os.makedirs(dir_, exist_ok=True)
        payload = {
            "pipeline":           self._pipeline,
            "feature_cols":       self._feature_cols,
            "importances_raw":    self._importances_raw,
            "importances_capped": self._importances_capped,
            "meta":               self._meta,
        }
        with open(path, "wb") as f:
            pickle.dump(payload, f)

    @classmethod
    def load(cls, path: str = MODEL_PATH) -> Optional["FlareRFModel"]:
        """Load a saved model from disk.  Returns None if file is absent or corrupt."""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as f:
                payload = pickle.load(f)
            obj = cls()
            obj._pipeline           = payload["pipeline"]
            obj._feature_cols       = payload.get("feature_cols", FEATURE_COLS[:])
            obj._importances_raw    = payload.get("importances_raw", {})
            obj._importances_capped = payload.get("importances_capped", {})
            obj._meta               = payload.get("meta", {})
            return obj
        except Exception:
            return None


# =========================================================
# MODULE-LEVEL ENTRY POINT
# =========================================================

def load_model(path: str = MODEL_PATH) -> Optional[FlareRFModel]:
    """Load a trained FlareRFModel or return None if unavailable.
    Called by FlareUpPredictor.__init__() to upgrade predict_flare_risk()."""
    return FlareRFModel.load(path)
