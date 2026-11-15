import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from insights import trend_insights

class InsightTests(unittest.TestCase):
    def row(self, year, value, **changes):
        row = dict(company_id='c', metric_id='m', entity='e', boundary='b', unit_id='u', measurement_type='actual', year=year, value=value, value_qualifier='eq', observation_id=str(year), report_id='r')
        row.update(changes)
        return row
    def test_comparable_values_include_provenance(self):
        result = trend_insights([self.row(2022, 100), self.row(2023, 80)])
        self.assertEqual(result[0]['change_percent'], -20)
        self.assertEqual(result[0]['observation_ids'], ['2022', '2023'])
        self.assertEqual(result[0]['sources'][0]['report_id'], 'r')
    def test_excludes_incompatible_or_ambiguous_values(self):
        base = self.row(2022, 100)
        for rows in ([base, self.row(2023, 80, boundary='other')], [base, self.row(2023, 80, value_qualifier='approx')], [base, self.row(2023, 80), self.row(2023, 81)], [self.row(2022, 0), self.row(2023, 80)], [base, self.row(2024, 80)], [base, self.row(2023, 80, measurement_type='target')]):
            self.assertEqual(trend_insights(rows), [])

if __name__ == '__main__': unittest.main()
