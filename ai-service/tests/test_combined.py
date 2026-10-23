"""Combinação dos sinais de máscara, luva e avental, com imagens artificiais."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import numpy as np

import teste_combinado as combined


class CombinedTests(unittest.TestCase):
    def test_all_green_only_when_every_item_is_correct(self):
        self.assertEqual(combined.combine({"mascara": "green", "luva": "green", "avental": "green"}), "green")
        self.assertEqual(combined.combine({"mascara": "green", "luva": "amber", "avental": "green"}), "amber")

    def test_any_wrong_item_is_red_even_with_unknown_items(self):
        self.assertEqual(combined.combine({"mascara": "red", "luva": "green", "avental": "green"}), "red")
        self.assertEqual(combined.combine({"mascara": "amber", "luva": "red", "avental": "amber"}), "red")

    def test_uncalibrated_items_are_inconclusive_and_mask_still_works(self):
        detector = combined.CombinedDetector()
        results = detector.predict(np.full((240, 320, 3), 90, np.uint8))
        self.assertEqual(set(results), set(combined.ITEMS))
        self.assertEqual(results["luva"].label, "inconclusiva")
        self.assertEqual(results["avental"].label, "inconclusiva")
        self.assertIn(results["mascara"].label, ("levantada", "abaixada"))


if __name__ == "__main__":
    unittest.main()
