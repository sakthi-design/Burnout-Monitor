import csv
import json
import os
import random
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Constants
ROOT = Path(__file__).resolve().parents[1]
TRAINING_DATA_PATH = ROOT / "data" / "burnout_training.csv"
MODEL_PATH = ROOT / "backend" / "burnout_model.pkl"
METRICS_PATH = ROOT / "backend" / "model_metrics.json"

FEATURE_NAMES = [
    "work_hours",
    "overtime_hours",
    "leave_days",
    "task_load",
    "completion_rate",
    "meeting_hours",
    "job_satisfaction",
    "stress_level",
    "sentiment_score",
]


def clamp(val, minimum=0.0, maximum=100.0):
    return max(minimum, min(maximum, float(val)))


def generate_synthetic_data(num_samples=400):
    """Generate high-quality synthetic employee data for training."""
    random.seed(42)
    np.random.seed(42)

    rows = []
    target_classes = ["Low", "Medium", "High", "Critical"]
    samples_per_class = num_samples // len(target_classes)

    for target_class in target_classes:
        for _ in range(samples_per_class):
            if target_class == "Low":
                work_hours = clamp(np.random.normal(7.0, 0.8), 4.0, 16.0)
                overtime_hours = clamp(np.random.normal(0.2, 0.3), 0.0, 8.0)
                leave_days = int(clamp(np.random.normal(6.0, 2.0), 0.0, 20.0))
                task_load = clamp(np.random.normal(25.0, 10.0), 0.0, 100.0)
                completion_rate = clamp(np.random.normal(88.0, 5.0), 0.0, 100.0)
                meeting_hours = clamp(np.random.normal(3.0, 2.0), 0.0, 40.0)
                job_satisfaction = clamp(np.random.normal(85.0, 10.0), 0.0, 100.0)
                stress_level = clamp(np.random.normal(20.0, 10.0), 0.0, 100.0)
                sentiment_score = clamp(np.random.normal(85.0, 10.0), 0.0, 100.0)
            elif target_class == "Medium":
                work_hours = clamp(np.random.normal(8.2, 0.8), 4.0, 16.0)
                overtime_hours = clamp(np.random.normal(1.0, 0.8), 0.0, 8.0)
                leave_days = int(clamp(np.random.normal(3.0, 1.5), 0.0, 20.0))
                task_load = clamp(np.random.normal(55.0, 10.0), 0.0, 100.0)
                completion_rate = clamp(np.random.normal(78.0, 8.0), 0.0, 100.0)
                meeting_hours = clamp(np.random.normal(7.5, 3.0), 0.0, 40.0)
                job_satisfaction = clamp(np.random.normal(65.0, 12.0), 0.0, 100.0)
                stress_level = clamp(np.random.normal(45.0, 12.0), 0.0, 100.0)
                sentiment_score = clamp(np.random.normal(65.0, 12.0), 0.0, 100.0)
            elif target_class == "High":
                work_hours = clamp(np.random.normal(9.6, 1.0), 4.0, 16.0)
                overtime_hours = clamp(np.random.normal(2.8, 1.0), 0.0, 8.0)
                leave_days = int(clamp(np.random.normal(1.0, 1.0), 0.0, 20.0))
                task_load = clamp(np.random.normal(78.0, 10.0), 0.0, 100.0)
                completion_rate = clamp(np.random.normal(65.0, 10.0), 0.0, 100.0)
                meeting_hours = clamp(np.random.normal(14.0, 4.0), 0.0, 40.0)
                job_satisfaction = clamp(np.random.normal(40.0, 15.0), 0.0, 100.0)
                stress_level = clamp(np.random.normal(75.0, 10.0), 0.0, 100.0)
                sentiment_score = clamp(np.random.normal(35.0, 15.0), 0.0, 100.0)
            else: # Critical
                work_hours = clamp(np.random.normal(11.5, 1.2), 4.0, 16.0)
                overtime_hours = clamp(np.random.normal(5.0, 1.5), 0.0, 8.0)
                leave_days = int(clamp(np.random.normal(0.5, 0.8), 0.0, 20.0))
                task_load = clamp(np.random.normal(92.0, 6.0), 0.0, 100.0)
                completion_rate = clamp(np.random.normal(52.0, 12.0), 0.0, 100.0)
                meeting_hours = clamp(np.random.normal(22.0, 5.0), 0.0, 40.0)
                job_satisfaction = clamp(np.random.normal(20.0, 12.0), 0.0, 100.0)
                stress_level = clamp(np.random.normal(90.0, 8.0), 0.0, 100.0)
                sentiment_score = clamp(np.random.normal(18.0, 12.0), 0.0, 100.0)

            # Calculate deterministic score with noise
            base = (
                (work_hours / 12.0) * 25.0
                + (overtime_hours / 5.0) * 20.0
                + task_load * 0.20
                + (meeting_hours / 24.0) * 15.0
                + (100.0 - sentiment_score) * 0.20
            )
            stress_adj = (stress_level - 50.0) * 0.08
            satis_adj = (50.0 - job_satisfaction) * 0.06
            completion_adj = (70.0 - completion_rate) * 0.05
            leave_adj = 2.0 if leave_days <= 1 else -3.0 if leave_days >= 5 else 0.0
            noise = np.random.normal(0, 1.0)

            score = clamp(base + stress_adj + satis_adj + completion_adj + leave_adj + noise)

            # Map to label
            if score <= 30:
                label = "Low"
            elif score <= 60:
                label = "Medium"
            elif score <= 80:
                label = "High"
            else:
                label = "Critical"

            rows.append(
                {
                    "work_hours": round(work_hours, 1),
                    "overtime_hours": round(overtime_hours, 1),
                    "leave_days": leave_days,
                    "task_load": round(task_load),
                    "completion_rate": round(completion_rate),
                    "meeting_hours": round(meeting_hours, 1),
                    "job_satisfaction": round(job_satisfaction),
                    "stress_level": round(stress_level),
                    "sentiment_score": round(sentiment_score),
                    "risk_label": label,
                }
            )

    # Save to CSV
    TRAINING_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TRAINING_DATA_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_NAMES + ["risk_label"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {num_samples} samples and wrote to {TRAINING_DATA_PATH}")


def train_and_evaluate():
    # If the training data doesn't exist or is too small, or doesn't have 4 classes, generate it
    regenerate = False
    if not TRAINING_DATA_PATH.exists() or os.path.getsize(TRAINING_DATA_PATH) < 1000:
        regenerate = True
    else:
        try:
            with open(TRAINING_DATA_PATH, mode="r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader)
                classes = set(row[-1] for row in reader if row)
                if len(classes) < 4:
                    regenerate = True
        except Exception:
            regenerate = True

    if regenerate:
        generate_synthetic_data()

    # Load data from CSV
    X = []
    y = []
    with open(TRAINING_DATA_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if not row:
                continue
            X.append([float(val) if val else np.nan for val in row[:-1]])
            y.append(row[-1])

    X = np.array(X)
    y = np.array(y)

    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Build Pipeline: Impute -> Scale -> RF
    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="mean")),
            ("scaler", StandardScaler()),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=100,
                    max_depth=8,
                    random_state=42,
                    class_weight="balanced",
                ),
            ),
        ]
    )

    # Fit Model
    pipeline.fit(X_train, y_train)

    # Predict
    y_pred = pipeline.predict(X_test)

    # Compute Metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)
    cm = confusion_matrix(y_test, y_pred).tolist()

    # Extract feature importances
    classifier = pipeline.named_steps["classifier"]
    importances = classifier.feature_importances_.tolist()
    feature_importance_dict = dict(zip(FEATURE_NAMES, importances))

    classes = sorted(list(set(y)))
    metrics = {
        "accuracy": round(float(accuracy), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1_score": round(float(f1), 4),
        "classes": classes,
        "confusion_matrix": cm,
        "feature_importances": feature_importance_dict,
    }

    # Save Model & Metrics
    joblib.dump(pipeline, MODEL_PATH)
    with open(METRICS_PATH, mode="w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print("\nModel Training Complete!")
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"Saved model to {MODEL_PATH}")
    print(f"Saved metrics to {METRICS_PATH}")


if __name__ == "__main__":
    train_and_evaluate()
