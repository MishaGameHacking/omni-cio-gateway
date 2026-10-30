"""Offline parser/grounding regressions; these fixtures never enter evaluation or the app."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import evaluate_finance_reasoning as lab


class Sources(unittest.TestCase):
    def test_reject_lookahead_and_wrong_nominal(self):
        pattern='<ValCurs Date="{}"><Valute><CharCode>USD</CharCode><NumCode>840</NumCode><Nominal>{}</Nominal><Value>80,5</Value></Valute></ValCurs>'
        for date,nominal in [("07.06.2024","1"),("06.06.2024","100")]:
            with self.subTest(date=date,nominal=nominal), self.assertRaises(ValueError):
                lab.cbr_row(lab.DAYS[0],"fixture",pattern.format(date,nominal).encode())

    def test_never_join_different_sessions_or_duplicate_rows(self):
        cols=["BOARDID","TRADEDATE","SECID","CLOSE","CURRENCYID","TRADINGSESSION"]
        base=["TQBR",lab.DAYS[0],"SBER",100,"SUR",1]
        for extra in [base,["TQBR",lab.DAYS[1],"SBER",100,"SUR",3]]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                lab.moex_rows(json.dumps({"history":{"columns":cols,"data":[base,extra]}}).encode())

    def test_fx_conversion_can_reverse_market_direction_and_needs_four_sources(self):
        rows=[{"id":prefix+d,"value":value} for prefix,values in [("share-",("100","110")),("fx-",("80","100"))]
              for d,value in zip(lab.DAYS,values)]
        cases={name:(answer,cites) for name,_,answer,cites in lab.comparisons(rows)}
        self.assertEqual(cases["rub_close"][0],"up")
        self.assertEqual(cases["usd_equivalent"][0],"down")
        self.assertEqual(set(cases["usd_equivalent"][1]),{r["id"] for r in rows})
        self.assertEqual(cases["future_missing"],("unknown",[]))
        self.assertNotIn("usd_equivalent",[c[0] for c in lab.comparisons(rows[1:])])

    def test_correct_conclusion_with_false_or_extra_evidence_fails(self):
        for raw in ['{"answer":"up","evidence":["a","x"]}','{"answer":"up","evidence":["a","a"]}',
                    '{"answer":"down","answer":"up","evidence":["a","b"]}','{"answer":"up","evidence":["a"]}']:
            self.assertFalse(lab.score(raw,"up",["a","b"]))
        self.assertTrue(lab.score('{"answer":"up","evidence":["b","a"]}',"up",["a","b"]))


if __name__=="__main__":
    unittest.main()
