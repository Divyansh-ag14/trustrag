"""Load the golden evaluation dataset into the database.

Usage:
    cd backend
    python scripts/load_golden_set.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.evaluation import EvaluationDataset, EvaluationItem
from app.models.workspace import Workspace

GOLDEN_SET_PATH = Path(__file__).resolve().parent.parent / "sample_data" / "golden_eval_set.json"


async def main():
    print("=== Loading Golden Evaluation Set ===\n")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    with open(GOLDEN_SET_PATH) as f:
        golden_data = json.load(f)

    async with session_factory() as session:
        # Find workspace
        result = await session.execute(select(Workspace).limit(1))
        workspace = result.scalar_one_or_none()

        if not workspace:
            print("No workspace found. Register a user first.")
            sys.exit(1)

        print(f"Workspace: {workspace.name} (id: {workspace.id})")

        # Check if dataset already exists
        result = await session.execute(
            select(EvaluationDataset).where(
                EvaluationDataset.workspace_id == workspace.id,
                EvaluationDataset.name == golden_data["name"],
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Dataset '{golden_data['name']}' already exists (id: {existing.id})")
            print(f"  Items: {existing.item_count}")
            print("\nSkipping. Delete the existing dataset first to re-import.")
            await engine.dispose()
            return

        # Create dataset
        dataset = EvaluationDataset(
            workspace_id=workspace.id,
            name=golden_data["name"],
            description=golden_data.get("description", ""),
            item_count=len(golden_data["items"]),
        )
        session.add(dataset)
        await session.flush()

        print(f"Created dataset: {dataset.name} (id: {dataset.id})")

        # Add items
        for item_data in golden_data["items"]:
            item = EvaluationItem(
                dataset_id=dataset.id,
                question=item_data["question"],
                expected_answer=item_data["expected_answer"],
                expected_source_docs=item_data.get("expected_source_docs", []),
                query_type=item_data.get("query_type"),
                difficulty=item_data.get("difficulty"),
                tags=item_data.get("tags", []),
            )
            session.add(item)

        await session.commit()

        print(f"Added {len(golden_data['items'])} evaluation items")
        print(f"\nBreakdown:")

        # Count by type
        type_counts = {}
        difficulty_counts = {}
        for item in golden_data["items"]:
            qt = item.get("query_type", "unknown")
            type_counts[qt] = type_counts.get(qt, 0) + 1
            diff = item.get("difficulty", "unknown")
            difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1

        for qt, count in sorted(type_counts.items()):
            print(f"  {qt}: {count}")
        print()
        for diff, count in sorted(difficulty_counts.items()):
            print(f"  {diff}: {count}")

    await engine.dispose()
    print("\nDone! You can now trigger evaluation runs via the API.")


if __name__ == "__main__":
    asyncio.run(main())
