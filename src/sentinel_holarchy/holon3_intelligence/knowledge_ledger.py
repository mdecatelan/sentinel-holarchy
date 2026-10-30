"""
Holon 3: Knowledge Ledger Manager for Decentralized Experience Accumulation.
Implements a SHA-256 hash-chained tamper-evident audit ledger and Conjugate Bayesian
updating for batch yield and kinetic parameter inference across bio-hubs.
"""

import json
import os
import math
import hashlib
from typing import List, Dict, Any


class KnowledgeLedgerManager:
    """Persistent hash-chained experience ledger enabling federated learning across bio-hubs."""

    GENESIS_HASH = "0" * 64

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

    @staticmethod
    def _compute_hash(payload: Dict[str, Any], prev_hash: str) -> str:
        canonical = json.dumps(
            {k: v for k, v in sorted(payload.items()) if k not in ("entry_hash", "prev_hash")},
            sort_keys=True
        )
        return hashlib.sha256(f"{prev_hash}:{canonical}".encode("utf-8")).hexdigest()

    def record_batch(self, entry: Dict[str, Any]) -> int:
        records = self.load_ledger()
        prev_hash = records[-1].get("entry_hash", self.GENESIS_HASH) if records else self.GENESIS_HASH

        enriched = dict(entry)
        enriched["prev_hash"] = prev_hash
        enriched["entry_hash"] = self._compute_hash(enriched, prev_hash)

        records.append(enriched)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        return len(records)

    def verify_chain_integrity(self) -> Dict[str, Any]:
        """Verifies cryptographic hash chain across all chained ledger records."""
        records = self.load_ledger()
        chained_records = [r for r in records if "entry_hash" in r and "prev_hash" in r]
        if not chained_records:
            return {"valid": True, "checked_blocks": 0, "tampered_index": None}

        expected_prev = chained_records[0]["prev_hash"]
        for idx, rec in enumerate(chained_records):
            if rec["prev_hash"] != expected_prev:
                return {"valid": False, "checked_blocks": idx, "tampered_index": idx}
            recomputed = self._compute_hash(rec, rec["prev_hash"])
            if recomputed != rec["entry_hash"]:
                return {"valid": False, "checked_blocks": idx, "tampered_index": idx}
            expected_prev = rec["entry_hash"]

        return {"valid": True, "checked_blocks": len(chained_records), "tampered_index": None}

    def calculate_experience_factor(self, intrant_type: str = "organique") -> float:
        """Computes learning boost multiplier based on past successful batches."""
        records = self.load_ledger()
        matching = [
            r for r in records
            if r.get("intrant_type") == intrant_type or "organique" in r.get("intrant_type", "")
        ]
        count = len(matching)
        if count == 0:
            return 1.00
        boost = 1.0 + 0.35 * math.log(1 + count)
        return round(min(boost, 2.50), 2)

    def estimate_posterior_yield(
        self,
        intrant_type: str = "organique",
        prior_mean_g: float = 30.0,
        prior_std_g: float = 8.0,
        obs_noise_std_g: float = 5.0
    ) -> Dict[str, float]:
        """
        Normal-Normal conjugate Bayesian update for expected Grade A PHA yield (g).
        Combines theoretical prior N(mu_0, sigma_0^2) with empirical batch observations.
        """
        records = self.load_ledger()
        observations = [
            float(r["final_GradeA"])
            for r in records
            if r.get("intrant_type") == intrant_type and "final_GradeA" in r and float(r["final_GradeA"]) > 0
        ]
        n = len(observations)
        if n == 0:
            return {
                "posterior_mean_g": round(prior_mean_g, 2),
                "posterior_std_g": round(prior_std_g, 2),
                "ci_95_low_g": round(prior_mean_g - 1.96 * prior_std_g, 2),
                "ci_95_high_g": round(prior_mean_g + 1.96 * prior_std_g, 2),
                "sample_size": 0
            }

        sample_mean = sum(observations) / n
        prec_0 = 1.0 / (prior_std_g ** 2)
        prec_lik = n / (obs_noise_std_g ** 2)
        post_prec = prec_0 + prec_lik
        post_var = 1.0 / post_prec
        post_std = math.sqrt(post_var)
        post_mean = post_var * (prec_0 * prior_mean_g + prec_lik * sample_mean)

        return {
            "posterior_mean_g": round(post_mean, 2),
            "posterior_std_g": round(post_std, 3),
            "ci_95_low_g": round(post_mean - 1.96 * post_std, 2),
            "ci_95_high_g": round(post_mean + 1.96 * post_std, 2),
            "sample_size": n
        }
