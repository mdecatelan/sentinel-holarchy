"""
Holon 3: Knowledge Ledger Manager for Decentralized Experience Accumulation.
Records multi-batch operational learnings, adaptation scores, and mass balances.
"""

import json
import os
from typing import List, Dict, Any

class KnowledgeLedgerManager:
    """Persistent experience ledger enabling federated learning across bio-hubs."""

    def __init__(self, ledger_filepath: str = "knowledge_ledger.json"):
        self.filepath = ledger_filepath

    def load_ledger(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.filepath):
            return []
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def record_batch(self, entry: Dict[str, Any]) -> int:
        records = self.load_ledger()
        records.append(entry)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        return len(records)

    def calculate_experience_factor(self, intrant_type: str = "organique") -> float:
        """Computes learning boost multiplier based on past successful batches."""
        records = self.load_ledger()
        matching = [r for r in records if r.get("intrant_type") == intrant_type or "organique" in r.get("intrant_type", "")]
        count = len(matching)
        # Logarithmic experience curve scaling from 1.00x up to 2.50x
        if count == 0:
            return 1.00
        import math
        boost = 1.0 + 0.35 * math.log(1 + count)
        return round(min(boost, 2.50), 2)
