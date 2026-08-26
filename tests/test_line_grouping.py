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


# ---------------------------------------------------------------------------
# Fixture: PAK'nSAVE Palmerston North, 16 May 2026 (84 blocks, 54 rows)
# Lower-quality scan: more OCR errors, larger description-to-price Y offsets
# (up to 0.4%), and a 3-block header row at the same Y.
# ---------------------------------------------------------------------------
PAKNSAVE_20260516 = [
    _block("ASAVE",                                            4.3,  42),
    _block("****",                                             8.7,  26),
    _block("PAR",                                              8.6,  33),
    _block("PALMERSTON NORTH",                                 8.6,  46),
    _block("FERGUSON STREET",                                  9.8,  41),
    _block("SOBRO LIMITED",                                   11.0,  40),
    _block("PH: 06) 356-4043",                                12.2,  37),
    _block("Order online and collect-trom the store",         14.4,  22),
    _block("Go to paknsave.co.nz/shop",                       15.7,  31),
    _block("KIA KAHA. STRESSED OR OVERWHELMED?",              16.8,  26),
    _block("CALL OR TEXT 1737 FOR FREE KORERO",               18.0,  26),
    _block("CINCERELLA ALMOND MEAL 400G",                     19.1,  14),
    _block("$12.39",                                          19.3,  77),
    _block("FRE (AS BREAD MIXED GRAIN /50G",                  20.2,  13),
    _block("$4.37",                                           20.5,  79),
    _block("YAS BREAD SOYA / LINSEED 7506",                   21.4,  16),
    _block("$4.37",                                           21.7,  79),
    _block("BARRAWAYS ROLLED GATS ORG 8006",                  22.6,  13),
    _block("$8.19",                                           22.8,  79),
    _block("PALMERSION NORTH COUNCIL RUBBISH BAG.5S",         23.7,  13),
    _block("$19.00",                                          24.0,  77),
    _block("PAMS DATES 400G",                                 24.8,  13),
    _block("$2.69",                                           25.2,  78),
    _block("PAMS DESIDCATED COCONUT 2506",                    26.0,  13),
    _block("$3.75",                                           26.3,  79),
    _block("PAMS WASH VANILLA REFILL 1L",                     27.2,  13),
    _block("2@",                                              28.5,  26),
    _block("$4.49",                                           28.5,  38),
    _block("$8.98",                                           28.6,  78),
    _block("PAMS PLANT BASED SOY MILK REGULAR IL",            29.6,  13),
    _block("20",                                              30.9,  25),
    _block("$2.49",                                           30.9,  38),
    _block("$4.98",                                           31.0,  78),
    _block("TUX ADULT ORIGINAL MEATY 8KG",                    32.0,  14),
    _block("$34.99",                                          32.2,  77),
    _block("CABBAGE GREEN",                                   33.2,  13),
    _block("$2.99",                                           33.3,  78),
    _block("CLERY",                                           34.4,  13),
    _block("$2.99",                                           34.5,  78),
    _block("PAMS VALUE MILK STANDARD 4",                      35.5,  13),
    _block("$4.38",                                           35.7,  78),
    _block("is BALANCE DUE",                                  38.0,  14),
    _block("$114.57",                                         38.0,  75),
    _block("EFTPOS",                                          39.1,  17),
    _block("$114.57",                                         39.2,  75),
    _block("SUBTOTAL",                                        42.5,  17),
    _block("$99.63",                                          42.7,  76),
    _block("TOTAL GST",                                       43.8,  17),
    _block("$14.94",                                          43.9,  76),
    _block("TOTAL",                                           45.0,  17),
    _block("$114",                                            45.1,  75),
    _block("CHANGE",                                          47.3,  12),
    _block("$0.00",                                           47.5,  78),
    _block("PAK N SAVE PALMERSTO",                            49.5,  10),
    _block("327 FERGUSON STREET",                             50.7,  10),
    _block("PALMERSTON NORTH",                                51.9,  10),
    _block("EFTPOS",                                          54.4,  25),
    _block("TERM:NAL",                                        55.5,  10),
    _block("04155063",                                        55.6,  39),
    _block("TIME",                                            56.7,  10),
    _block("16May26 15:42",                                   56.7,  33),
    _block("TRAN 071792",                                     57.8,  10),
    _block("CHEQUE",                                          57.9,  42),
    _block("EFTPOS",                                          59.0,   9),
    _block("CARD",                                            60.2,   9),
    _block("8996",                                            60.3,  44),
    _block("PURCHASE",                                        61.5,   9),
    _block("NZD114.57",                                       61.5,  38),
    _block("TOTAL",                                           62.6,   9),
    _block("NZD114.57",                                       62.6,  38),
    _block("ACCEPTED",                                        65.0,  24),
    _block("CUSTOMER COPY",                                   68.5,  20),
    _block("CASHIER NAME: SCO Cashier",                       69.7,  12),
    _block("16/05/2026 15:42:28 05082 0212",                  70.9,  12),
    _block("TAX",                                             72.1,  40),
    _block("INVOICE",                                         72.1,  46),
    _block("**** GST No: 138-395-464 ****",                   73.3,  28),
    _block("All items GST inclusive",                         74.5,  32),
    _block("unless otherwise specified by (*)",               75.7,  25),
    _block("******** BE IN TOWIN $500",                       78.2,  24),
    _block("Tell us how we did today and go",                 79.3,  27),
    _block("into the monthly draw to win a",                  80.5,  28),
    _block("$500 PAK'nSave gift card",                        81.7,  32),
    _block("Have your say al pakusave.co.nz/surveys",         82.9,  21),
]

PAKNSAVE_20260516_EXPECTED = [
    "ASAVE",
    "****  PAR  PALMERSTON NORTH",
    "FERGUSON STREET",
    "SOBRO LIMITED",
    "PH: 06) 356-4043",
    "Order online and collect-trom the store",
    "Go to paknsave.co.nz/shop",
    "KIA KAHA. STRESSED OR OVERWHELMED?",
    "CALL OR TEXT 1737 FOR FREE KORERO",
    "CINCERELLA ALMOND MEAL 400G  $12.39",
    "FRE (AS BREAD MIXED GRAIN /50G  $4.37",
    "YAS BREAD SOYA / LINSEED 7506  $4.37",
    "BARRAWAYS ROLLED GATS ORG 8006  $8.19",
    "PALMERSION NORTH COUNCIL RUBBISH BAG.5S  $19.00",
    "PAMS DATES 400G  $2.69",
    "PAMS DESIDCATED COCONUT 2506  $3.75",
    "PAMS WASH VANILLA REFILL 1L",
    "2@  $4.49  $8.98",
    "PAMS PLANT BASED SOY MILK REGULAR IL",
    "20  $2.49  $4.98",
    "TUX ADULT ORIGINAL MEATY 8KG  $34.99",
    "CABBAGE GREEN  $2.99",
    "CLERY  $2.99",
    "PAMS VALUE MILK STANDARD 4  $4.38",
    "is BALANCE DUE  $114.57",
    "EFTPOS  $114.57",
    "SUBTOTAL  $99.63",
    "TOTAL GST  $14.94",
    "TOTAL  $114",
    "CHANGE  $0.00",
    "PAK N SAVE PALMERSTO",
    "327 FERGUSON STREET",
    "PALMERSTON NORTH",
    "EFTPOS",
    "TERM:NAL  04155063",
    "TIME  16May26 15:42",
    "TRAN 071792  CHEQUE",
    "EFTPOS",
    "CARD  8996",
    "PURCHASE  NZD114.57",
    "TOTAL  NZD114.57",
    "ACCEPTED",
    "CUSTOMER COPY",
    "CASHIER NAME: SCO Cashier",
    "16/05/2026 15:42:28 05082 0212",
    "TAX  INVOICE",
    "**** GST No: 138-395-464 ****",
    "All items GST inclusive",
    "unless otherwise specified by (*)",
    "******** BE IN TOWIN $500",
    "Tell us how we did today and go",
    "into the monthly draw to win a",
    "$500 PAK'nSave gift card",
    "Have your say al pakusave.co.nz/surveys",
]


class TestGroupBlocksMay2026(unittest.TestCase):
    def test_row_count(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260516)
        self.assertEqual(len(rows), 54)

    def test_all_blocks_assigned(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260516)
        self.assertEqual(sum(len(r) for r in rows), len(PAKNSAVE_20260516))

    def test_reading_order(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260516)
        tops = [min(b["Geometry"]["BoundingBox"]["Top"] for b in row) for row in rows]
        self.assertEqual(tops, sorted(tops))

    def test_merged_lines(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260516)
        self.assertEqual(_lines(rows), PAKNSAVE_20260516_EXPECTED)

    def test_three_block_header_row(self):
        """**** PAR PALMERSTON NORTH are three blocks at the same Y — must chain."""
        rows, _, _ = group_blocks(PAKNSAVE_20260516)
        self.assertIn("****  PAR  PALMERSTON NORTH", _lines(rows))

    def test_large_y_offset_chains(self):
        """Descriptions and prices up to 0.4% apart vertically must still chain."""
        rows, _, _ = group_blocks(PAKNSAVE_20260516)
        result = _lines(rows)
        self.assertIn("PAMS DATES 400G  $2.69", result)

    def test_multi_purchase_alone(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260516)
        result = _lines(rows)
        self.assertIn("PAMS WASH VANILLA REFILL 1L", result)
        self.assertFalse(any("PAMS WASH" in l and "$" in l for l in result))


# ---------------------------------------------------------------------------
# Fixture: PAK'nSAVE Palmerston North, 24 Aug 2026 (65 blocks, 48 rows)
# job_id: 72d08995-ce1f-42ce-8e85-863253ed0171
# Key case: $13.18 and $9.58 are right-edge price orphans whose Y sits above
# the quantity-breakdown row they belong to (receipt curl artefact). Phase 3
# of group_blocks must absorb them into the row below.
# ---------------------------------------------------------------------------
PAKNSAVE_20260824 = [
    _block("LPAKINSAVE",                                  6.2,  20),
    _block("**** PELMERSION NORTH **",                   10.9,  33),
    _block("32) FERGUSON STREET",                        12.8,  41),
    _block("SDBTJ LIMITED",                              14.6,  45),
    _block("PF: ()6) 356-4043",                          15.9,  42),
    _block("Order online end collect from the store",    18.1,  28),
    _block("Go to pakinsave.co.nz/shop",                 20.2,  37),
    _block("KIA KAMA. STRESSED OR OVERWHELMED?",         21.1,  31),
    _block("CALL OF TEXT 1737 FOR FREE KORERO",          22.7,  31),
    _block("WHITTAKERS BLOCK RLM / RAISIN 2500",         24.4,  20),
    _block("$13.18",                                     25.3,  79),
    _block("20",                                         26.3,  31),
    _block("$6.59",                                      26.4,  42),
    _block("PAMS VALUE MILK STENDARD 2",                 27.4,  20),
    _block("$9.58",                                      28.4,  81),
    _block("20",                                         29.2,  31),
    _block("14.79",                                      29.4,  42),
    _block("Supervisor #76",                             30.4,  19),
    _block("STOKE IPA 330M 12F) CAN",                    31.9,  19),
    _block("$22.99",                                     31.6,  79),
    _block("5 BALANCE QUE",                              34.9,  20),
    _block("$45.75",                                     34.6,  79),
    _block("EFTPOS",                                     36.4,  23),
    _block("$45.75",                                     36.1,  79),
    _block("**************95",                           38.0,  26),
    _block("SUB TOTAL",                                  40.8,  22),
    _block("$39.78",                                     40.7,  78),
    _block("TOTAL GST",                                  42.2,  22),
    _block("$5.97",                                      42.2,  80),
    _block("TOTAL",                                      43.7,  22),
    _block("$45.75",                                     43.7,  78),
    _block("CHANGE",                                     46.6,  18),
    _block("$0.00",                                      46.8,  79),
    _block("PAK N SAVE PALMERSTO",                       49.4,  15),
    _block("327 FERGUSON STREET",                        50.9,  15),
    _block("PALMERSTON NORTH",                           52.4,  15),
    _block("EFTPOS",                                     55.5,  29),
    _block("TERMINAL",                                   56.8,  14),
    _block("04155010",                                   57.1,  42),
    _block("TIME",                                       58.2,  14),
    _block("24ALg26 20 15",                              58.5,  35),
    _block("TRAN 087091",                                59.7,  14),
    _block("CHEQUE",                                     60.1,  44),
    _block("EFTPOS",                                     61.2,  14),
    _block("CARD",                                       62.6,  13),
    _block("8996",                                       63.0,  46),
    _block("PURCHASE",                                   64.0,  13),
    _block("72045.75",                                   64.4,  41),
    _block("TOTAL",                                      65.5,  13),
    _block("M2045 75",                                   65.9,  41),
    _block("ACCEPTED",                                   68.6,  27),
    _block("CUSTOMER COPY",                              73.0,  23),
    _block("Join Club anc get ready to shop smarter.",   74.4,  21),
    _block("Visit clubplus.co.nz",                       76.1,  35),
    _block("CASHIER NAME: CATHERINE M",                  78.7,  14),
    _block("24/08/2026 20:45:28 05082 010 3143 0085",    80.2,  14),
    _block("TAX INVOICE",                                82.1,  41),
    _block("**** GST 40: 138-395-464 ****",              83.5,  29),
    _block("All items GST inclusive",                    85.0,  33),
    _block("unless othervise specified by (*)",          86.4,  26),
    _block("******** EE De TO WIN $500 ********",        89.5,  25),
    _block("Tall us for Vd did today and go",            90.9,  27),
    _block("into the sinthly draw to win a",             92.6,  28),
    _block("SOC Pat'nSeve gift card",                    94.1,  34),
    _block("Have your script prknsave.co.mazeurveys",    95.3,  21),
]

PAKNSAVE_20260824_EXPECTED = [
    "LPAKINSAVE",
    "**** PELMERSION NORTH **",
    "32) FERGUSON STREET",
    "SDBTJ LIMITED",
    "PF: ()6) 356-4043",
    "Order online end collect from the store",
    "Go to pakinsave.co.nz/shop",
    "KIA KAMA. STRESSED OR OVERWHELMED?",
    "CALL OF TEXT 1737 FOR FREE KORERO",
    "WHITTAKERS BLOCK RLM / RAISIN 2500",
    "20  $6.59  $13.18",
    "PAMS VALUE MILK STENDARD 2",
    "20  14.79  $9.58",
    "Supervisor #76",
    "STOKE IPA 330M 12F) CAN  $22.99",
    "5 BALANCE QUE  $45.75",
    "EFTPOS  $45.75",
    "**************95",
    "SUB TOTAL  $39.78",
    "TOTAL GST  $5.97",
    "TOTAL  $45.75",
    "CHANGE  $0.00",
    "PAK N SAVE PALMERSTO",
    "327 FERGUSON STREET",
    "PALMERSTON NORTH",
    "EFTPOS",
    "TERMINAL  04155010",
    "TIME  24ALg26 20 15",
    "TRAN 087091  CHEQUE",
    "EFTPOS",
    "CARD  8996",
    "PURCHASE  72045.75",
    "TOTAL  M2045 75",
    "ACCEPTED",
    "CUSTOMER COPY",
    "Join Club anc get ready to shop smarter.",
    "Visit clubplus.co.nz",
    "CASHIER NAME: CATHERINE M",
    "24/08/2026 20:45:28 05082 010 3143 0085",
    "TAX INVOICE",
    "**** GST 40: 138-395-464 ****",
    "All items GST inclusive",
    "unless othervise specified by (*)",
    "******** EE De TO WIN $500 ********",
    "Tall us for Vd did today and go",
    "into the sinthly draw to win a",
    "SOC Pat'nSeve gift card",
    "Have your script prknsave.co.mazeurveys",
]


class TestGroupBlocksAug2026b(unittest.TestCase):
    def test_row_count(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260824)
        self.assertEqual(len(rows), 48)

    def test_all_blocks_assigned(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260824)
        self.assertEqual(sum(len(r) for r in rows), len(PAKNSAVE_20260824))

    def test_reading_order(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260824)
        tops = [min(b["Geometry"]["BoundingBox"]["Top"] for b in row) for row in rows]
        self.assertEqual(tops, sorted(tops))

    def test_merged_lines(self):
        rows, _, _ = group_blocks(PAKNSAVE_20260824)
        self.assertEqual(_lines(rows), PAKNSAVE_20260824_EXPECTED)

    def test_whittakers_price_orphan_absorbed(self):
        """$13.18 sits above its breakdown row due to receipt curl — must join 20/$6.59, not WHITTAKERS."""
        rows, _, _ = group_blocks(PAKNSAVE_20260824)
        result = _lines(rows)
        self.assertIn("20  $6.59  $13.18", result)
        self.assertFalse(any("WHITTAKERS" in l and "$13.18" in l for l in result))

    def test_milk_price_orphan_absorbed(self):
        """$9.58 sits above its breakdown row due to receipt curl — must join 20/14.79."""
        rows, _, _ = group_blocks(PAKNSAVE_20260824)
        result = _lines(rows)
        self.assertIn("20  14.79  $9.58", result)
        self.assertFalse(any("STENDARD" in l and "$9.58" in l for l in result))

    def test_stoke_ipa_chains_with_price(self):
        """STOKE IPA price ($22.99) is 0.3% above the item name — must still chain."""
        rows, _, _ = group_blocks(PAKNSAVE_20260824)
        self.assertIn("STOKE IPA 330M 12F) CAN  $22.99", _lines(rows))


# ---------------------------------------------------------------------------
# Fixture: PAK'nSAVE Palmerston North, 26 Aug 2026 — second scan (81 blocks, 55 rows)
# job_id: 760bb942-eb84-44e7-9d7d-c7af06124899
# Ground truth from image inspection.  This is a flatter scan of the same
# receipt as PAKNSAVE_20260826 (same items, same totals), so it provides an
# independent check that the algorithm produces correct groupings when the
# curl is less severe.  Key cases confirmed by the image:
#   • COMVITA chains with its own $6.99 (gap only 0.2%)
#   • GOLDEN CRUMPETS ROUND is a no-price anchor (2@ below)
#   • WATTIES VEGETBLE 430G carries a separate $4.89 in addition to the
#     2@ breakdown row, because PAK'nSAVE prints the unit price twice
#   • NZ MUTTON BONES = $14.99 (not $5.99; the curled scan had these swapped)
#   • 12 BALANCE DUE and EFTPOS both chain with their own $77.83
#   • The lone * chains with EFTPOS one row below it (gap 0.3%)
# ---------------------------------------------------------------------------
PAKNSAVE_760bb942 = [
    _block("PAKńSAVE",                                     8.8,  17),
    _block("**** PAK'nSAVE PALMERSTON NORTH **",          13.9,  26),
    _block("327 FERGUSON STREET",                         15.3,  36),
    _block("SDBRJ LIMITED",                               16.7,  40),
    _block("PH: (06) 356-4043",                           18.1,  37),
    _block("Order online and collect from the store",     20.7,  22),
    _block("Go to paknsave.co.nz/shop",                   22.3,  31),
    _block("KIA KAHA. STRESSED OR OVERWHELMED?",          23.5,  26),
    _block("CALL OR TEXT 1737 FOR FREE KORERO",           24.9,  26),
    _block("COMVITA MANUKA HONEY LOZENGES LEMON 54G",     26.3,  13),
    _block("$6.99",                                       26.5,  80),
    _block("GOLDEN CRUMPETS ROUND 6PK 300G",              27.7,  13),
    _block("2@",                                          29.2,  26),
    _block("$2.79",                                       29.1,  38),
    _block("$5.58",                                       29.2,  80),
    _block("GOLDEN CRUMPETS ROUN",                        30.4,  13),
    _block("-$0.58",                                      30.6,  78),
    _block("WATTIES SOUP/DAY HOMESTYLE CHICKEN 430G",     31.6,  13),
    _block("2@",                                          33.3,  26),
    _block("$4.89",                                       33.2,  38),
    _block("$9.78",                                       33.4,  80),
    _block("WATTIES SOUP/DAY HOMESTYLE/VEGETBLE 430G",    34.4,  13),
    _block("$4.89",                                       34.7,  80),
    _block("NZ TREVALLY FILLETS",                         35.9,  13),
    _block("$14.72",                                      36.1,  78),
    _block("CAULIFLOWER",                                 37.3,  14),
    _block("$2.99",                                       37.4,  79),
    _block("TONZU ORGANIC TOFU FIRM 300G",                38.6,  14),
    _block("$5.49",                                       38.8,  79),
    _block("BANANA BREAD",                                40.1,  14),
    _block("$6.99",                                       40.1,  79),
    _block("CIABATTA BUNS 6PK",                           41.4,  14),
    _block("$5.99",                                       41.5,  79),
    _block("NZ MUTTON BONES",                             42.8,  14),
    _block("$14.99",                                      42.9,  78),
    _block("12 BALANCE DUE",                              45.5,  14),
    _block("$77.83",                                      45.5,  78),
    _block("EFTPOS",                                      46.9,  18),
    _block("$77.83",                                      46.9,  78),
    _block("************8996",                            48.2,  22),
    _block("SUB TOTAL",                                   50.9,  18),
    _block("$67.68",                                      50.9,  78),
    _block("TOTAL GST",                                   52.3,  18),
    _block("$10.15",                                      52.3,  78),
    _block("TOTAL",                                       53.6,  18),
    _block("$77.83",                                      53.6,  78),
    _block("CHANGE",                                      56.3,  14),
    _block("$0.00",                                       56.3,  79),
    _block("PAK N SAVE PALMERSTO",                        58.8,  11),
    _block("327 FERGUSON STREET",                         60.2,  11),
    _block("PALMERSTON NORTH",                            61.5,  11),
    _block("*",                                           64.5,  11),
    _block("EFTPOS",                                      64.2,  27),
    _block("TERMINAL",                                    65.5,  11),
    _block("04155066",                                    65.6,  41),
    _block("TIME",                                        66.8,  11),
    _block("26Aug26 13:10",                               66.8,  34),
    _block("TRAN 108573",                                 68.1,  11),
    _block("CHEQUE",                                      68.1,  44),
    _block("EFTPOS",                                      69.5,  11),
    _block("CARD",                                        70.8,  11),
    _block("8996",                                        70.8,  46),
    _block("PURCHASE",                                    72.1,  11),
    _block("NZD77.83",                                    72.0,  41),
    _block("TOTAL",                                       73.4,  11),
    _block("NZD77.83",                                    73.3,  41),
    _block("ACCEPTED",                                    76.0,  26),
    _block("*",                                           79.0,  50),
    _block("CUSTOMER COPY",                               80.0,  22),
    _block("Join Club+ and get ready to shop smarter.",   81.3,  21),
    _block("Visit clubplus.co.nz",                        82.7,  35),
    _block("CASHIER NAME: SCO Cashier P",                 85.2,  14),
    _block("26/08/2026 13:10:55 05082 066 6709 0216",     86.5,  14),
    _block("TAX INVOICE ************",                    88.0,  42),
    _block("**** GST No: 138-395-464 ****",               89.3,  30),
    _block("All items GST inclusive",                     90.6,  34),
    _block("unless otherwise specified by (*)",           91.9,  27),
    _block("BE IN TO WIN $500 ********",                  94.7,  38),
    _block("Tell us how we did today and go",             96.0,  29),
    _block("into the monthly draw to win a",              97.3,  30),
    _block("$500 PAK'nSave gift card",                    98.6,  34),
]

PAKNSAVE_760bb942_EXPECTED = [
    "PAKńSAVE",
    "**** PAK'nSAVE PALMERSTON NORTH **",
    "327 FERGUSON STREET",
    "SDBRJ LIMITED",
    "PH: (06) 356-4043",
    "Order online and collect from the store",
    "Go to paknsave.co.nz/shop",
    "KIA KAHA. STRESSED OR OVERWHELMED?",
    "CALL OR TEXT 1737 FOR FREE KORERO",
    "COMVITA MANUKA HONEY LOZENGES LEMON 54G  $6.99",
    "GOLDEN CRUMPETS ROUND 6PK 300G",
    "2@  $2.79  $5.58",
    "GOLDEN CRUMPETS ROUN  -$0.58",
    "WATTIES SOUP/DAY HOMESTYLE CHICKEN 430G",
    "2@  $4.89  $9.78",
    "WATTIES SOUP/DAY HOMESTYLE/VEGETBLE 430G  $4.89",
    "NZ TREVALLY FILLETS  $14.72",
    "CAULIFLOWER  $2.99",
    "TONZU ORGANIC TOFU FIRM 300G  $5.49",
    "BANANA BREAD  $6.99",
    "CIABATTA BUNS 6PK  $5.99",
    "NZ MUTTON BONES  $14.99",
    "12 BALANCE DUE  $77.83",
    "EFTPOS  $77.83",
    "************8996",
    "SUB TOTAL  $67.68",
    "TOTAL GST  $10.15",
    "TOTAL  $77.83",
    "CHANGE  $0.00",
    "PAK N SAVE PALMERSTO",
    "327 FERGUSON STREET",
    "PALMERSTON NORTH",
    "*  EFTPOS",
    "TERMINAL  04155066",
    "TIME  26Aug26 13:10",
    "TRAN 108573  CHEQUE",
    "EFTPOS",
    "CARD  8996",
    "PURCHASE  NZD77.83",
    "TOTAL  NZD77.83",
    "ACCEPTED",
    "*",
    "CUSTOMER COPY",
    "Join Club+ and get ready to shop smarter.",
    "Visit clubplus.co.nz",
    "CASHIER NAME: SCO Cashier P",
    "26/08/2026 13:10:55 05082 066 6709 0216",
    "TAX INVOICE ************",
    "**** GST No: 138-395-464 ****",
    "All items GST inclusive",
    "unless otherwise specified by (*)",
    "BE IN TO WIN $500 ********",
    "Tell us how we did today and go",
    "into the monthly draw to win a",
    "$500 PAK'nSave gift card",
]


class TestGroupBlocksGroundTruth760bb942(unittest.TestCase):
    def test_row_count(self):
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        self.assertEqual(len(rows), 55)

    def test_all_blocks_assigned(self):
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        self.assertEqual(sum(len(r) for r in rows), len(PAKNSAVE_760bb942))

    def test_reading_order(self):
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        tops = [min(b["Geometry"]["BoundingBox"]["Top"] for b in row) for row in rows]
        self.assertEqual(tops, sorted(tops))

    def test_merged_lines(self):
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        self.assertEqual(_lines(rows), PAKNSAVE_760bb942_EXPECTED)

    def test_comvita_chains_with_price(self):
        """COMVITA and $6.99 are 0.2% apart — must chain in Phase 2."""
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        self.assertIn("COMVITA MANUKA HONEY LOZENGES LEMON 54G  $6.99", _lines(rows))

    def test_golden_crumpets_anchor_alone(self):
        """GOLDEN CRUMPETS ROUND is a no-price anchor — description only."""
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        result = _lines(rows)
        self.assertIn("GOLDEN CRUMPETS ROUND 6PK 300G", result)
        self.assertFalse(any("GOLDEN CRUMPETS ROUND" in l and "$" in l for l in result))

    def test_golden_crumpets_discount_row(self):
        """GOLDEN CRUMPETS ROUN and -$0.58 form a separate discount row."""
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        self.assertIn("GOLDEN CRUMPETS ROUN  -$0.58", _lines(rows))

    def test_watties_chicken_anchor_alone(self):
        """WATTIES CHICKEN is a no-price anchor — description only."""
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        result = _lines(rows)
        self.assertIn("WATTIES SOUP/DAY HOMESTYLE CHICKEN 430G", result)
        self.assertFalse(any("WATTIES SOUP/DAY HOMESTYLE CHICKEN" in l and "$" in l for l in result))

    def test_watties_vegetble_carries_unit_price(self):
        """WATTIES VEGETBLE 430G chains with its own right-edge $4.89."""
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        self.assertIn("WATTIES SOUP/DAY HOMESTYLE/VEGETBLE 430G  $4.89", _lines(rows))

    def test_mutton_bones_price(self):
        """NZ MUTTON BONES = $14.99 (not $5.99, confirmed by image)."""
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        result = _lines(rows)
        self.assertIn("NZ MUTTON BONES  $14.99", result)
        self.assertFalse(any("NZ MUTTON BONES" in l and "$5.99" in l for l in result))

    def test_balance_due_and_eftpos_chain(self):
        """12 BALANCE DUE and EFTPOS each chain with their own $77.83."""
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        result = _lines(rows)
        self.assertIn("12 BALANCE DUE  $77.83", result)
        self.assertIn("EFTPOS  $77.83", result)

    def test_star_chains_with_eftpos(self):
        """The lone * (↕64.5%) chains with EFTPOS (↕64.2%) 0.3% away."""
        rows, _, _ = group_blocks(PAKNSAVE_760bb942)
        self.assertIn("*  EFTPOS", _lines(rows))


if __name__ == "__main__":
    unittest.main()
