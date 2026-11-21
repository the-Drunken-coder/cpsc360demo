from datetime import date, timedelta

from cpsc360.heuristic_lab import Report
from scripts.replay_cooker_recalls import replay


def test_recurrence_requires_another_publication_day_at_the_same_maker():
    start = date(2018, 1, 1)

    def cooker(day, maker, text='The lid popped off.'):
        return Report(id=f'{day}-{maker}-{text}', available_on=start + timedelta(days=day),
                      product='Pressure Cookers or Canners', manufacturer_key=maker,
                      narrative=text, hazard=None, injury=False)

    rows = [cooker(0, 'a'), cooker(0, 'a', 'The lid flew off.'), cooker(1, 'b'),
            cooker(2, 'a', 'Power cord melted.'), cooker(365, 'a'), cooker(731, 'a')]
    matches = [labels for _, labels in replay(rows)]
    assert [i for i, labels in enumerate(matches) if 'Repeat mechanism at maker' in labels] == [4]
    assert matches[3] == {'All cookers'}
    assert 'Either mechanism' in matches[0]
