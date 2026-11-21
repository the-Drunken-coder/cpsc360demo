from scripts.watchlist_climb import candidates, climb


def row(number, day, maker='Acme', model='X431', notice=None):
    return dict(report_no=number, publication_date=day, manufacturer_name=maker, model=model,
                brand=maker, retailer='', serial_number=None, severity='Incident, No Injury',
                product_type='Garden hose', incident_description='The hose burst during use.',
                product_description='Garden hose', flags=['specific'], prior=[],
                strict={notice: 60} if notice else {}, loose={})


def test_replay_ignores_future_notices_and_same_day_history():
    rows = [row('a','2024-02-01'),row('b','2024-02-01'),row('c','2024-02-02')]
    for r in rows:
        r['incident_description'] += ' The detached fitting broke apart.'
    f = candidates(rows, list(reversed(rows)), [{'RecallDate':'2025-01-01'}])
    assert all('hose or fitting bursts' in f[r['report_no']] for r in rows)
    assert all('repeat model with hazard' not in f[k] for k in ['a','b'])
    assert 'repeat model with hazard' in f['c']


def test_transfer_rule_needs_support_across_manufacturers():
    rows = [row(str(i),'2024-03-01',maker,notice=notice) for i,(maker,notice) in
            enumerate([('A','1'),('A','1'),('B','2'),('C','3'),('D',None)])]
    features = {r['report_no']:{'general'} for r in rows}
    features['0'].add('one manufacturer')
    result = climb(rows, features, 20, minimum_makers=3)
    assert result['rules'] == ['general']
    assert result['steps'][-1]['notices'] == 3
