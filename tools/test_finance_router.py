"""Only offline regression fixtures; none enter the measuring run or server."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
import financial_evidence as calc


def fixtures():
    return [{"id":prefix+"-"+day,"date":day,"value":value,"source_sha256":"a"*64}
            for prefix,values in [("fx",("80","100")),("share",("100","110"))]
            for day,value in zip(("2024-06-06","2024-06-07"),values)]


class Grounding(unittest.TestCase):
    def test_reverse_comparison_and_cross_rate(self):
        c=calc.build(fixtures())
        r=[x for x in c if "Эквивалент" in x["metric"]]
        self.assertEqual([x["answer"] for x in r],["down","up"])
        self.assertNotIn("answer",calc.menu(c)[0])
        self.assertEqual(set(r[0]["source_hashes"]),set(x["id"] for x in fixtures()))

    def test_missing_rate_removes_both_currency_conversions(self):
        c=calc.build(fixtures()[1:])
        self.assertEqual(len(c),2)
        self.assertTrue(all("в рублях" in x["metric"] for x in c))
        self.assertEqual(calc.resolve('{"id":"NONE"}',c)["evidence"],[])

    def test_no_arbitrary_prices_inputs_or_fabricated_model_numbers(self):
        rows=fixtures()
        with self.assertRaises(ValueError):calc.build(rows+[rows[0]])
        for val in ["NaN","Infinity","-1","0.00000000000001"]:
            with self.subTest(val=val),self.assertRaises(ValueError):
                calc.build([{**rows[0],"value":val}])
        for value in ['{"id":"A","answer":"up"}','{"id":"NONE","id":"A"}','{"id":"UNKNOWN_ID"}']:
            with self.assertRaises(ValueError):calc.resolve(value,calc.build(rows))


if __name__=="__main__":
    unittest.main()
