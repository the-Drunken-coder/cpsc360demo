import gzip
import json

import pytest

from scripts.watchlist_score import main


def report(number, day, maker, model, product, story, severity='No Injury', serial=None):
    return {'report_no': number, 'publication_date': day, 'manufacturer_name': maker,
            'brand': maker, 'model': model, 'product_type': product, 'product_description': product,
            'serial_number': serial, 'incident_description': story, 'severity': severity,
            'is_injury': severity.startswith('Injury')}


def notice(number, day, maker, model, product, hazard):
    return {'RecallNumber': number, 'RecallDate': day, 'Title': f'{maker} recalls {product}',
            'Description': f'{maker} {product}, model {model}.',
            'Manufacturers': [{'Name': maker}], 'Products': [{'Name': product, 'Model': model}],
            'Hazards': [{'Name': hazard}]}


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_cli_watchlist_scores_reports_and_writes_review_queue(tmp_path):
    reports = [
        report('history', '2023-10-03', 'Atlas', 'CP-100', 'Pressure cookers', '', 'Injury, Hospital Admission'),
        report('all-three', '2024-01-01', 'Atlas', 'CP-100', 'Pressure cookers',
               'The lid blew off. Hot food ejected and burned my hand.', 'Injury, First Aid', 'SN-754'),
        report('loose-only', '2024-01-02', 'Atlas', None, 'Pressure cookers', 'Hot food sprayed and burned me.'),
        report('missed', '2025-11-04', 'Eagle', 'EZ-200', 'Hammocks', 'Uncomfortable.'),
        report('prior', '2024-05-01', 'Nimbus', 'CF-404', 'Fans', 'After the recall repair the blade snapped again.'),
        report('late', '2024-03-01', 'Bear', 'HUM-123', 'Humidifiers', 'The unit melted and nearly burned me.',
               serial='SN-123'),
        report('other', '2024-06-02', 'Aster', None, 'Mirrors', 'Damaged packaging.'),
        report('excluded', '2025-11-05', 'Eagle', 'EZ-200', 'Hammocks', ''),
    ]
    notices = [
        notice('atlas', '2024-12-31', 'Atlas', 'CP-100', 'Pressure cookers', 'Burn hazard'),
        notice('eagle', '2026-11-04', 'Eagle', 'EZ-200', 'Hammocks', 'Fall hazard'),
        notice('old', '2024-05-01', 'Nimbus', 'CF-404', 'Fans', 'Broken blade'),
        notice('followup', '2024-07-01', 'Nimbus', 'CF-404', 'Fans', 'Broken blade'),
        notice('366', '2025-03-02', 'Bear', 'HUM-123', 'Humidifiers', 'Burn hazard'),
    ]
    source = tmp_path / 'reports.json'
    source.write_text(json.dumps(reports))
    ledger = tmp_path / 'notices.json.gz'
    with gzip.open(ledger, 'wt') as stream:
        json.dump(notices, stream)
    out = tmp_path / 'output'
    args = ['--reports', str(source), '--notices', str(ledger), '--output', str(out)]
    main(args)
    result = json.loads((out / 'summary.json').read_text())
    combo = result['combo']
    assert combo['flags'] == 4 and combo['already_recalled'] == 1
    assert combo['strict'] == {'positives': 1, 'precision': 0.25, 'expected_random_hits': 4/3, 'lift': 0.75,
                               'distinct_notices': 1, 'median_lead_days': 365}
    assert combo['loose']['positives'] == 2 and combo['loose']['median_lead_days'] == 364.5
    assert combo['loose']['lift'] == pytest.approx(1.5)
    assert result['all_reports']['flags'] == 6
    assert result['coverage'] == {'caught': 1, 'reachable': 2}
    assert {rule: result[rule]['flags'] for rule in ('admission', 'mechanism', 'specific', 'repair')} == {
        'admission': 1, 'mechanism': 2, 'specific': 2, 'repair': 1,
    }
    assert {r['report_no'] for r in lines(out / 'false-positive-sample.jsonl')} == {'late', 'prior'}
    assert {r['report_no'] for r in lines(out / 'strict-positive-reports.jsonl')} == {'all-three', 'missed'}
    assert any(r['notice_no'] == 'old' and r['lead'] == 0 for r in lines(out / 'candidates.jsonl'))

    reviews = tmp_path / 'reviews.csv'
    reviews.write_text('report_no,notice_no,verdict\nall-three,atlas,none\n')
    main([*args, '--overrides', str(reviews)])
    revised = json.loads((out / 'summary.json').read_text())
    assert revised['coverage'] == {'caught': 0, 'reachable': 1}
    assert revised['combo']['flags'] == 4 and revised['combo']['loose']['positives'] == 1

    warnings = tmp_path / 'earlier-actions.csv'
    warnings.write_text('report_no,notice_no,date\nall-three,agency-warning,2023-12-12\n')
    main([*args, '--earlier-actions', str(warnings)])
    warned = json.loads((out / 'summary.json').read_text())
    assert warned['combo']['already_recalled'] == 2
    assert warned['combo']['strict']['positives'] == 0
    assert warned['combo']['loose']['positives'] == 1
    assert warned['coverage'] == {'caught': 0, 'reachable': 1}

    main([*args, '--earlier-actions', str(warnings), '--ledger-only'])
    assert json.loads((out / 'summary.json').read_text()) == result
