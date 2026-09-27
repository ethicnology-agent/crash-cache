"""Provision the authenticated app-usage workspace from explicit activity data."""
import datetime as dt

from explorer_activity import definitions
from provision_explorer import preserve_dashboard_tabs
from provision_metabase import (MARKER, ProvisionError, query_parameters, rows,
                                template_tags, unique_managed)


def provision(api, database_id, collection_id, project_id, start, end, grain='day'):
    """The common Explorer CLI accepts inclusive dates; SQL uses an exclusive end."""
    if project_id <= 0 or grain not in ('hour', 'day', 'week', 'month'):
        raise ProvisionError('Provide a positive project and a supported time bucket')
    if dt.date.fromisoformat(start) > dt.date.fromisoformat(end):
        raise ProvisionError('Provide ordered ISO dates')
    until = (dt.date.fromisoformat(end) + dt.timedelta(days=1)).isoformat()
    tags = template_tags(project_id, start, until, grain)
    parameters = query_parameters(project_id, start, until, grain)
    existing = rows(api.call('GET', '/card'))
    cards, specs = {}, definitions()
    for name, sql, display, settings, _ in specs:
        old = unique_managed(existing, name, collection_id)
        if old and old.get('public_uuid'):
            raise ProvisionError('Usage questions must remain authenticated')
        body = {'name': name, 'description': MARKER + ' Recorded activity; installations are client identities, not people or store downloads. UTC bounds are half-open.',
                'collection_id': collection_id, 'display': display, 'visualization_settings': settings,
                'dataset_query': {'database': database_id, 'type': 'native',
                                  'native': {'query': sql, 'template-tags': tags}}}
        card = api.call('PUT', f"/card/{old['id']}", body) if old else api.call('POST', '/card', body)
        result = api.call('POST', f"/card/{card['id']}/query", {'parameters': parameters})
        if result.get('status') != 'completed':
            raise ProvisionError('Usage query failed: ' + name)
        cards[name] = card['id']
    name = 'App usage'
    old = unique_managed(rows(api.call('GET', '/dashboard')), name, collection_id)
    if old and old.get('public_uuid'):
        raise ProvisionError('Usage dashboard must remain authenticated')
    dashboard = old or api.call('POST', '/dashboard', {'name': name, 'description': MARKER,
                                                     'collection_id': collection_id})
    current = api.call('GET', f"/dashboard/{dashboard['id']}")
    old_tiles = {tile['card_id']: tile['id'] for tile in current.get('dashcards', []) if tile.get('card_id')}
    tiles = []
    for index, (name, _, _, _, (row, col, width, height)) in enumerate(specs):
        card_id = cards[name]
        tiles.append({'id': old_tiles.get(card_id, -index-1), 'card_id': card_id,
                      'row': row, 'col': col, 'size_x': width, 'size_y': height, 'series': [],
                      'visualization_settings': {}, 'parameter_mappings': [
                          {'parameter_id': tag, 'card_id': card_id, 'target': ['variable', ['template-tag', tag]]}
                          for tag in tags]})
    filters = [
        {'id': 'project_id', 'name': 'Project', 'slug': 'project', 'type': 'number/=', 'default': [project_id], 'required': True, 'isMultiSelect': False},
        {'id': 'from', 'name': 'From (UTC)', 'slug': 'from', 'type': 'date/single', 'default': start, 'required': True},
        {'id': 'until', 'name': 'Until (exclusive, UTC)', 'slug': 'until', 'type': 'date/single', 'default': until, 'required': True},
        {'id': 'grain', 'name': 'Time bucket', 'slug': 'grain', 'type': 'category', 'default': [grain], 'required': True,
         'isMultiSelect': False, 'values_source_type': 'static-list',
         'values_source_config': {'values': ['hour', 'day', 'week', 'month']}},
    ]
    api.call('PUT', f"/dashboard/{dashboard['id']}", {'description': MARKER + ' Active installations, first observations and session starts; choose day, week or month for unique audience counts.',
                                                     'parameters': filters, **preserve_dashboard_tabs(current, tiles)})
    return {'dashboard_id': dashboard['id'], 'cards': cards}
