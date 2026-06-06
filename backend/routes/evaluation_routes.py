import json
from pathlib import Path

from fastapi import APIRouter

from app.models import EmailInput
from services.triage_service import calculate_priority

router = APIRouter()


@router.get("/evaluate")
def evaluate_model():
    dataset_path = Path("golden_dataset.json")

    if not dataset_path.exists():
        return {
            "error": "golden_dataset.json not found in backend folder",
        }

    with open(dataset_path, "r") as file:
        dataset = json.load(file)

    results = []
    correct = 0

    for item in dataset:
        prediction = calculate_priority(
            EmailInput(
                sender=item["sender"],
                subject=item["subject"],
                body=item["body"],
            )
        )

        expected = item["expected_priority"]
        predicted = prediction["priority_label"]
        is_correct = expected == predicted

        if is_correct:
            correct += 1

        results.append({
            "subject": item["subject"],
            "expected": expected,
            "predicted": predicted,
            "is_correct": is_correct,
        })

    accuracy = round((correct / len(dataset)) * 100, 2)

    return {
        "accuracy": accuracy,
        "total_samples": len(dataset),
        "correct_predictions": correct,
        "results": results,
    }