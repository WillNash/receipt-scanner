"""Tests for the two-phase Textract block grouping algorithm."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda", "processor"))

from line_grouping import group_blocks


def _block(text, top_pct, left_pct):
    """Build a minimal Textract LINE block dict from percentage coordinates."""
    return {
        "BlockType": "LINE",
        "Text": text,
        "Geometry": {
            "BoundingBox": {
                "Top":    top_pct  / 100,
                "Left":   left_pct / 100,
                "Width":  0.1,
                "Height": 0.01,
            }
        },
    }


def _lines(rows):
    return ["  ".join(b["Text"] for b in row) for row in rows]


# ---------------------------------------------------------------------------
# Fixture: PAK'nSAVE Palmerston North, 23 Aug 2026 (125 blocks, 78 rows)
# Captured from debug panel after two-phase algorithm was confirmed correct.
# ---------------------------------------------------------------------------
PAKNSAVE_20260823 = [
    _block("PAKńSAVE",                                        5.7,  22),
    _block("**** PAK'nSAVE PALMERSTON NORTH",                 8.5,  30),
    _block("327 FERGUSON STREET",                             9.7,  40),
    _block("SDBRJ LIMITED",                                  10.8,  43),
    _block("PH: (06) 356-4043",                              11.8,  41),
    _block("Order online and collect from the store",        13.8,  26),
    _block("Go to peknsave.co.nz/shop",                      14.8,  35),
    _block("KIA KAHA. STRESSED OR OVERWHELMED?",             15.8,  30),
    _block("CALL OR TEXT 1737 FOR FREE KORERO",              16.8,  30),
    _block("CINDERELLA DRIED MANGO 275G",                    17.8,  18),
    _block("$9.89",                                          17.8,  82),
    _block("DIAMOND PASTA FETTUCCINE 500G",                  18.8,  18),
    _block("2 @",                                            19.9,  30),
    _block("$2.29",                                          19.9,  42),
    _block("$4.58",                                          19.8,  82),
    _block("GOLDEN CRUMPETS ROUND 6PK 300G",                 20.8,  18),
    _block("2 @",                                            21.9,  30),
    _block("$2.79",                                          21.9,  42),
    _block("$5.58",                                          21.8,  81),
    _block("GOLDEN CRUMPETS ROUN",                           22.9,  18),
    _block("-$0.58",                                         22.9,  80),
    _block("NEW DAY FREE RANGE EGGS SIZE 7 18PK",            23.8,  18),
    _block("$14.99",                                         23.9,  80),
    _block("OXO STOCK CUBES BEEF 71G",                       24.9,  18),
    _block("$3.69",                                          24.9,  81),
    _block("PAMS PLANT BASED SOY MILK REGULAR 1L",           25.9,  18),
    _block("2@",                                             27.0,  30),
    _block("$2.49",                                          27.0,  42),
    _block("$4.98",                                          26.9,  81),
    _block("PASTA MARIA PASTA FUSILLI 4000",                 27.9,  18),
    _block("2 @",                                            29.0,  30),
    _block("$1.29",                                          28.9,  42),
    _block("$2.58",                                          28.9,  81),
    _block("PASTA MARIA SPAGHETTI 400G",                     29.9,  18),
    _block("2 @",                                            31.0,  30),
    _block("$1.29",                                          31.0,  42),
    _block("$2.58",                                          30.9,  81),
    _block("SUN VALLEY COCOA POWDER 400G",                   31.9,  18),
    _block("$12.09",                                         32.0,  80),
    _block("SUNBITES GRAINWAVES SOUR CRN/CHIVES 140G",       32.9,  18),
    _block("$1.99",                                          33.0,  81),
    _block("WATTIES TOMATO CHOPPED PUREE 400G",              34.0,  18),
    _block("4 @",                                            35.0,  30),
    _block("$1.99",                                          35.0,  41),
    _block("$7.96",                                          35.0,  81),
    _block("APPLES QUEEN",                                   36.0,  18),
    _block("1,371 Kg @",                                     37.0,  20),
    _block("$2.49/Kg",                                       37.0,  41),
    _block("$3.41",                                          37.0,  81),
    _block("BOBBY BANANAS",                                  38.0,  18),
    _block("$4.49",                                          38.0,  81),
    _block("BROCCOLI",                                       39.0,  18),
    _block("$1.99",                                          39.0,  81),
    _block("GARLIC",                                         40.0,  18),
    _block("0.031 Kg @",                                     41.0,  20),
    _block("$22.99/Kg",                                      41.0,  40),
    _block("$0.71",                                          40.9,  81),
    _block("ORANGE NAVEL IMPORTED",                          42.0,  17),
    _block("1.866 Kg @",                                     43.0,  20),
    _block("$2.49/Kg",                                       43.0,  41),
    _block("$4.65",                                          42.9,  81),
    _block("VALUE BROWN ONIONS 2KG",                         43.9,  17),
    _block("$3.99",                                          44.0,  81),
    _block("PAMS CHEESE BLOCK COLBY 1KG",                    44.9,  17),
    _block("$12.88",                                         45.0,  79),
    _block("PAMS SPEC CHEESE HALOUMI 200G",                  45.9,  17),
    _block("$6.49",                                          46.0,  81),
    _block("PERFECT ITALIANO PARMESAN CHEESE 200G",          46.9,  17),
    _block("$7.99",                                          46.9,  81),
    _block("T/C YOG STRAIGHT UP 9000",                       47.9,  17),
    _block("$7.39",                                          47.9,  81),
    _block("Supervisor #133",                                48.9,  17),
    _block("COOPERS STOUT BTL SGL 750ML",                    49.9,  17),
    _block("$6.89",                                          50.0,  81),
    _block("NZ LAMB MINCE",                                  50.9,  17),
    _block("$7.32",                                          50.9,  81),
    _block("NZ LAMB MINCE",                                  51.9,  17),
    _block("$7.74",                                          51.9,  81),
    _block("NZ LAMB STIR FRY",                               52.9,  17),
    _block("$8.64",                                          52.9,  80),
    _block("33 BALANCE DUE",                                 54.9,  17),
    _block("$154.91",                                        55.0,  78),
    _block("EFTPOS",                                         55.9,  21),
    _block("$154.91",                                        56.0,  78),
    _block("************8996",                               57.0,  25),
    _block("SUB TOTAL",                                      58.9,  21),
    _block("$134.70",                                        59.0,  78),
    _block("TOTAL GST",                                      60.0,  21),
    _block("$20.21",                                         60.0,  79),
    _block("TOTAL",                                          61.0,  21),
    _block("$154.91",                                        61.0,  78),
    _block("CHANGE",                                         63.0,  17),
    _block("$0.00",                                          63.0,  80),
    _block("PAK N SAVE PALMERSTO",                           65.0,  14),
    _block("327 FERGUSON STREET",                            66.0,  14),
    _block("PALMERSTON NORTH",                               67.0,  14),
    _block("EFTPOS",                                         69.0,  30),
    _block("TERMINAL",                                       70.0,  14),
    _block("04155008",                                       70.0,  43),
    _block("TIME",                                           71.0,  14),
    _block("23Aug26 15:25",                                  71.0,  36),
    _block("TRAN 070550",                                    72.0,  14),
    _block("CHEQUE",                                         72.0,  46),
    _block("EFTPOS",                                         73.1,  14),
    _block("CARD",                                           74.1,  14),
    _block("....8996",                                       74.1,  43),
    _block("PURCHASE",                                       75.0,  14),
    _block("NZD154.91",                                      75.1,  41),
    _block("TOTAL",                                          76.1,  14),
    _block("NZD154.91",                                      76.1,  41),
    _block("ACCEPTED",                                       78.1,  28),
    _block("CUSTOMER COPY",                                  81.1,  24),
    _block("Join Club+ and get ready to shop smarter.",      82.1,  23),
    _block("Visit clubplus.co.nz",                           83.2,  37),
    _block("CASHIER NAME: TOM M",                            85.2,  16),
    _block("23/08/2026 15:25:52 05082 008 2653 0019",        86.2,  16),
    _block("TAX INVOICE",                                    87.4,  44),
    _block("GST No: 138-395-464 ****",                       88.3,  38),
    _block("All items GST inclusive",                        89.3,  36),
    _block("unless otherwise specified by (*)",              90.3,  29),
    _block("BE IN TO WIN $500",                              92.4,  40),
    _block("Tell us how we did today and go",                93.3,  31),
    _block("into the nonthly draw to win 8",                 94.3,  32),
    _block("$500 PAK'nSave gift card",                       95.4,  36),
    _block("Have-your say at paknsave.co.nz/surveys",        96.1,  25),
]

PAKNSAVE_20260823_EXPECTED = [
    "PAKńSAVE",
    "**** PAK'nSAVE PALMERSTON NORTH",
    "327 FERGUSON STREET",
    "SDBRJ LIMITED",
    "PH: (06) 356-4043",
    "Order online and collect from the store",
    "Go to peknsave.co.nz/shop",
    "KIA KAHA. STRESSED OR OVERWHELMED?",
    "CALL OR TEXT 1737 FOR FREE KORERO",
    "CINDERELLA DRIED MANGO 275G  $9.89",
    "DIAMOND PASTA FETTUCCINE 500G",
    "2 @  $2.29  $4.58",
    "GOLDEN CRUMPETS ROUND 6PK 300G",
    "2 @  $2.79  $5.58",
    "GOLDEN CRUMPETS ROUN  -$0.58",
    "NEW DAY FREE RANGE EGGS SIZE 7 18PK  $14.99",
    "OXO STOCK CUBES BEEF 71G  $3.69",
    "PAMS PLANT BASED SOY MILK REGULAR 1L",
    "2@  $2.49  $4.98",
    "PASTA MARIA PASTA FUSILLI 4000",
    "2 @  $1.29  $2.58",
    "PASTA MARIA SPAGHETTI 400G",
    "2 @  $1.29  $2.58",
    "SUN VALLEY COCOA POWDER 400G  $12.09",
    "SUNBITES GRAINWAVES SOUR CRN/CHIVES 140G  $1.99",
    "WATTIES TOMATO CHOPPED PUREE 400G",
    "4 @  $1.99  $7.96",
    "APPLES QUEEN",
    "1,371 Kg @  $2.49/Kg  $3.41",
    "BOBBY BANANAS  $4.49",
    "BROCCOLI  $1.99",
    "GARLIC",
    "0.031 Kg @  $22.99/Kg  $0.71",
    "ORANGE NAVEL IMPORTED",
    "1.866 Kg @  $2.49/Kg  $4.65",
    "VALUE BROWN ONIONS 2KG  $3.99",
    "PAMS CHEESE BLOCK COLBY 1KG  $12.88",
    "PAMS SPEC CHEESE HALOUMI 200G  $6.49",
    "PERFECT ITALIANO PARMESAN CHEESE 200G  $7.99",
    "T/C YOG STRAIGHT UP 9000  $7.39",
    "Supervisor #133",
    "COOPERS STOUT BTL SGL 750ML  $6.89",
    "NZ LAMB MINCE  $7.32",
    "NZ LAMB MINCE  $7.74",
    "NZ LAMB STIR FRY  $8.64",
    "33 BALANCE DUE  $154.91",
    "EFTPOS  $154.91",
    "************8996",
    "SUB TOTAL  $134.70",
    "TOTAL GST  $20.21",
    "TOTAL  $154.91",
    "CHANGE  $0.00",
    "PAK N SAVE PALMERSTO",
    "327 FERGUSON STREET",
    "PALMERSTON NORTH",
    "EFTPOS",
    "TERMINAL  04155008",
    "TIME  23Aug26 15:25",
    "TRAN 070550  CHEQUE",
    "EFTPOS",
    "CARD  ....8996",
    "PURCHASE  NZD154.91",
    "TOTAL  NZD154.91",
    "ACCEPTED",
    "CUSTOMER COPY",
    "Join Club+ and get ready to shop smarter.",
    "Visit clubplus.co.nz",
    "CASHIER NAME: TOM M",
    "23/08/2026 15:25:52 05082 008 2653 0019",
    "TAX INVOICE",
    "GST No: 138-395-464 ****",
    "All items GST inclusive",
    "unless otherwise specified by (*)",
    "BE IN TO WIN $500",
    "Tell us how we did today and go",
    "into the nonthly draw to win 8",
    "$500 PAK'nSave gift card",
    "Have-your say at paknsave.co.nz/surveys",
]


class TestGroupBlocks(unittest.TestCase):
    def test_row_count(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260823)
        self.assertEqual(len(rows), 78)

    def test_all_blocks_assigned(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260823)
        assigned = sum(len(r) for r in rows)
        self.assertEqual(assigned, len(PAKNSAVE_20260823))

    def test_reading_order(self):
        """Rows must be in top-to-bottom order."""
        rows, _, _ = group_blocks(PAKNSAVE_20260823)
        tops = [min(b["Geometry"]["BoundingBox"]["Top"] for b in row) for row in rows]
        self.assertEqual(tops, sorted(tops))

    def test_merged_lines(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260823)
        self.assertEqual(_lines(rows), PAKNSAVE_20260823_EXPECTED)

    # --- spot-checks for the tricky cases that motivated this algorithm ---

    def test_single_purchase_chains_with_price(self):
        """CINDERELLA and $9.89 are at the same Y — must appear on one row."""
        rows, _, _ = group_blocks(PAKNSAVE_20260823)
        result = _lines(rows)
        self.assertIn("CINDERELLA DRIED MANGO 275G  $9.89", result)

    def test_multi_purchase_description_alone(self):
        """DIAMOND PASTA was bought as 2-pack — description must be alone."""
        rows, _, _ = group_blocks(PAKNSAVE_20260823)
        result = _lines(rows)
        self.assertIn("DIAMOND PASTA FETTUCCINE 500G", result)
        self.assertFalse(any("DIAMOND PASTA" in l and "$" in l for l in result))

    def test_qty_breakdown_chains(self):
        """Qty breakdown '2 @  $2.29  $4.58' must be a single row."""
        rows, _, _ = group_blocks(PAKNSAVE_20260823)
        result = _lines(rows)
        self.assertIn("2 @  $2.29  $4.58", result)

    def test_weight_item_alone(self):
        """Weight-priced items have no inline price — description must be alone."""
        rows, _, _ = group_blocks(PAKNSAVE_20260823)
        result = _lines(rows)
        self.assertIn("APPLES QUEEN", result)
        self.assertFalse(any("APPLES QUEEN" in l and "$" in l for l in result))

    def test_weight_breakdown_chains(self):
        """Weight breakdown with unit price and total must form one row."""
        rows, _, _ = group_blocks(PAKNSAVE_20260823)
        result = _lines(rows)
        self.assertIn("1,371 Kg @  $2.49/Kg  $3.41", result)

    def test_calibration_range(self):
        """Line height should be ~1% for this evenly-spaced receipt."""
        _, line_height, step_tol = group_blocks(PAKNSAVE_20260823)
        self.assertGreaterEqual(line_height, 0.008)
        self.assertLessEqual(line_height, 0.013)
        self.assertAlmostEqual(step_tol, line_height * 0.4)

    def test_empty_input(self):
        rows, lh, st = group_blocks([])
        self.assertEqual(rows, [])
        self.assertEqual(lh, 0.0)
        self.assertEqual(st, 0.0)


if __name__ == "__main__":
    unittest.main()
