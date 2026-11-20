from datetime import date

from scripts.watchlist_queue import schedule
from scripts.watchlist_queue_replay import replay


def row(number, day, product, story):
    return dict(report_no=number, publication_date=day, manufacturer_name='Example',
                model='E9871', brand='Example', product_type=product, product_description=product,
                incident_description=story, flags=[], strict={}, loose={}, prior=[])


def test_no_review_before_earning_capacity_and_no_future_posts():
    fork = row('fork','2024-05-06','Electric scooter',"The fork sheared while riding.")
    kettle = row('energy','2024-05-16','Power bank','The rechargeable battery caught fire while charging.')
    assert schedule([fork]) == {}
    assert schedule([fork,kettle]) == {'energy':date(2024,5,19)}
    # Two additional reports on the following week cannot change May 19's agenda.
    repeats = [{**kettle,'report_no':str(i),'publication_date':'2024-05-20'} for i in range(2)]
    assert schedule([*repeats,kettle,fork]) == schedule([fork,kettle])


def test_notice_on_review_day_is_too_late():
    case = row('a','2024-05-16','Toys','Part detached.')
    case.update(strict={'n1':3},loose={'n1':3,'later':10})
    result = replay([case],{'a':date(2024,5,19)})
    assert (result['flags'],result['notices'],result['loose'],result['prior']) == (1,0,0,1)
    assert result['reachable']==1


def test_protected_queue_uses_only_slots_freed_by_repeat_reports():
    from scripts.watchlist_queue import protect_first_schedule

    first = row('a','2024-05-06','Power bank','The battery caught fire while charging.')
    repeat = {**first,'report_no':'b','publication_date':'2024-05-13'}
    fork = row('c','2024-05-15','Electric scooter','The front fork sheared.')
    assert protect_first_schedule([fork,repeat,first]) == {
        'a':date(2024,5,6),'c':date(2024,5,19),
    }
