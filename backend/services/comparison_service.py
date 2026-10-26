"""Dated satellite comparisons, available independently of AI provider access."""
from datetime import date, timedelta
from copy import deepcopy
from pathlib import Path

from extensions import db
from models.analysis_incident import AgentLog
from services.gee_service import gee_service


def comparison_request(data, today=None):
    today = today or date.today()
    mode = data.get('comparison_mode')
    if mode not in ('latest', 'custom'):
        raise ValueError('Choose latest imagery or two selected dates.')
    try:
        historical = date.fromisoformat(data.get('historical_date', ''))
        current = today if mode == 'latest' else date.fromisoformat(data.get('comparison_date', ''))
    except (ValueError, TypeError):
        raise ValueError('Choose valid historical and comparison dates.')
    if historical >= current or current > today:
        raise ValueError('The comparison date must be after the historical date and no later than today.')
    # Equal windows, shortened for nearby dates so no observation occurs in both.
    days = min(30, (current - historical).days)
    def period(target):
        end = target + timedelta(days=1)
        return {'targetDate': target.isoformat(), 'startDate': (end-timedelta(days=days)).isoformat(),
                'endDate': end.isoformat(), 'throughDate': target.isoformat()}
    return {'mode': mode, 'windowDays': days, 'historical': period(historical), 'current': period(current)}


def save_comparison(analysis_id, comparison):
    log = AgentLog.query.filter_by(analysis_id=analysis_id, action='comparison_result').first()
    if log is None:
        log = AgentLog(analysis_id=analysis_id, agent_name='Satellite comparison',
                       action='comparison_result', status='info', reasoning='Dated comparison images and coverage.')
        db.session.add(log)
    log.details = deepcopy(comparison)
    db.session.commit()


def acquire_comparison(analysis_id, geometry, request):
    result = {**request, 'historical': dict(request['historical']), 'current': dict(request['current']),
              'metrics': None, 'aiStatus': 'pending', 'message': 'Loading both observation periods.'}
    images, paths = {}, {}
    for side in ('historical', 'current'):
        period = result[side]
        try:
            meta, image = gee_service.get_quality_imagery(
                geometry, period['startDate'], period['endDate'], adaptive=False)
            path = Path('static/images/analysis') / f'local_analysis_{analysis_id}_{side}.png'
            if not gee_service.download_image(meta['imageUrl'], str(path.resolve())):
                raise RuntimeError('Image download failed. Start another comparison to retry.')
            # Persist a local image; Earth Engine thumbnail URLs expire.
            period.update(meta)
            period['imageUrl'] = '/' + path.as_posix()
            period['state'] = 'ready'
            images[side], paths[side] = image, str(path.resolve())
        except Exception as exc:
            period.update(state='unavailable', error=str(exc))
        save_comparison(analysis_id, result)
    if len(images) == 2:
        try:
            result['metrics'] = gee_service.compare_composites(geometry, images['historical'], images['current'])
        except Exception as exc:
            result['metricsError'] = 'Vegetation comparison unavailable: ' + str(exc)
    result['message'] = 'Comparison images ready. Missing pixels are excluded from vegetation measurements.'
    save_comparison(analysis_id, result)
    return result, paths
