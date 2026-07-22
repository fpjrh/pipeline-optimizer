#!/usr/bin/env python3
"""CLI script to trigger data collection from GitHub Actions."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.database import init_db, SessionLocal
from app.services.github_client import GitHubClient
from app.services.cost_calculator import update_all_costs


def main():
    init_db()
    db = SessionLocal()
    try:
        client = GitHubClient()
        print("Collecting data from GitHub Actions...")
        stats = client.collect_all(db)
        print(f"Collection complete: {stats}")

        print("Calculating costs...")
        update_all_costs(db)
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
