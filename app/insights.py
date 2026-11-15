"""Explainable observations derived from comparable reported records."""
from collections import defaultdict
from math import isfinite


def trend_insights(rows):
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        key = tuple(row.get(k) for k in ('company_id', 'metric_id', 'entity', 'boundary', 'unit_id', 'measurement_type'))
        # Only actuals are comparable observations, not targets or savings initiatives.
        if all(key) and row.get('measurement_type') == 'actual' and row.get('year') is not None:
            groups[key][row['year']].append(row)
    results = []
    for key, years in groups.items():
        for year in sorted(years):
            if year - 1 not in years or len(years[year]) != 1 or len(years[year - 1]) != 1:
                continue
            previous, current = years[year - 1][0], years[year][0]
            values = (previous.get('value'), current.get('value'))
            if any(r.get('value_qualifier') != 'eq' for r in (previous, current)):
                continue
            if any(v is None or not isfinite(float(v)) for v in values) or values[0] <= 0:
                continue
            change = (values[1] - values[0]) / values[0] * 100
            results.append({'company_id': key[0], 'metric_id': key[1], 'entity': key[2],
                'boundary': key[3], 'unit_id': key[4], 'measurement_type': key[5],
                'metric_name_vi': current.get('metric_name_vi'), 'unit_code': current.get('unit_code'),
                'from_year': year - 1, 'to_year': year, 'from_value': values[0], 'to_value': values[1],
                'change_percent': change, 'observation_ids': [previous['observation_id'], current['observation_id']],
                'sources': [{'report_id': r.get('report_id'), 'source_file': r.get('source_file'),
                             'page': r.get('source_page_pdf')} for r in (previous, current)],
                'methodology': '(current value − previous value) / previous value × 100',
                'limitations': 'Reported actuals with matching recorded scope and unit; comparability and source data are not independently verified.'})
    return sorted(results, key=lambda x: (-x['to_year'], x['company_id'], x['metric_id'], x['entity'], x['boundary']))
