"""Arrange existing Explorer questions into native Metabase dashboard tabs.

Metabase v0.63.18 dashboards_rest/api.clj accepts temporary negative tab IDs in
PUT /dashboard/:id and rewrites matching dashboard_tab_id values atomically.
No question, query, filter default, permission or public link is created here.
"""
from copy import deepcopy
import os

from provision_metabase import ProvisionError


def _tile(source, tab_id, row, col, width, height):
    keys = ('id', 'card_id', 'series', 'parameter_mappings', 'visualization_settings',
            'inline_parameters', 'action_id')
    tile = {key: deepcopy(source[key]) for key in keys if key in source}
    tile.update(dashboard_tab_id=tab_id, row=row, col=col, size_x=width, size_y=height)
    return tile


def layout(current, sections, navigation):
    """Return one atomic layout update, preserving all question tiles exactly once."""
    if current.get('public_uuid'):
        raise ProvisionError('Explorer workspace must remain authenticated')
    cards = [tile for tile in current.get('dashcards', []) if tile.get('card_id')]
    by_card = {tile['card_id']: tile for tile in cards}
    requested = [entry[0] for _, _, entries in sections for entry in entries]
    if len(by_card) != len(cards) or len(requested) != len(set(requested)) or set(requested) != set(by_card):
        raise ProvisionError('Workspace layout must account for every question exactly once')
    old_tabs = {tab['name']: tab['id'] for tab in current.get('tabs', [])}
    old_notes = {tile.get('dashboard_tab_id'): tile for tile in current.get('dashcards', [])
                 if not tile.get('card_id')}
    tabs, tiles = [], []
    for index, (name, note, entries) in enumerate(sections):
        tab_id = old_tabs.get(name, -index-1)
        tabs.append({'id': tab_id, 'name': name})
        old_note = old_notes.get(tab_id)
        if not old_note and index == 0:
            old_note = old_notes.get(None)
        tiles.append({'id': old_note['id'] if old_note else -1000-index,
                      'card_id': None, 'dashboard_tab_id': tab_id,
                      'row': 0, 'col': 0, 'size_x': 24, 'size_y': 4,
                      'series': [], 'parameter_mappings': [],
                      'visualization_settings': {
                          'virtual_card': {'name': None, 'display': 'text', 'visualization_settings': {}},
                          'text': navigation + '\n\n' + note}})
        for card_id, row, col, width, height in entries:
            tiles.append(_tile(by_card[card_id], tab_id, row+4, col, width, height))
    return {'tabs': tabs, 'dashcards': tiles}


def _apply(api, dashboard_id, sections, navigation):
    current = api.call('GET', f'/dashboard/{dashboard_id}')
    api.call('PUT', f'/dashboard/{dashboard_id}', layout(current, sections, navigation))
    persisted = api.call('GET', f'/dashboard/{dashboard_id}')
    return {tab['name']: tab['id'] for tab in persisted['tabs']}


def organize(api, result, activity_result):
    """Organize freshly provisioned questions without changing existing URLs."""
    dashboards, cards = result['dashboards'], result['cards']
    health = dashboards['Health overview']
    usage = activity_result['dashboard_id']
    navigation = f'**[App usage](/dashboard/{usage}) · [Error reports](/dashboard/{health})**'
    if os.environ.get('EXPLORER_DEMO') == '1':
        navigation = '**Synthetic demo data.**\n\n' + navigation
    tabs = {}
    tabs['reports'] = _apply(api, health, [
        ('Overview', 'Start with error impact, then open **Problems** to choose an error and inspect its occurrences.', [
            (cards['count'],0,0,8,4),(cards['issues_count'],0,8,8,4),(cards['identities'],0,16,8,4),
            (cards['trend'],4,0,16,8),(cards['platforms'],4,16,8,8)]),
        ('Problems', f'Select a problem to open its occurrences; select an occurrence to read its stack trace. [Releases and devices](/dashboard/{dashboards["Releases and devices"]}) · [Sessions and logs](/dashboard/{dashboards["Sessions and logs"]})', [
            (cards['issue_activity'],0,0,24,12)]),
    ], navigation)
    detail = result.get('details')
    if detail:
        ids = detail['card_ids']
        if len(ids) != 6:
            raise ProvisionError('Event detail layout requires summary, stack, breadcrumbs, logs, attachments and metadata')
        tabs['event'] = _apply(api, detail['dashboard_id'], [
            ('Stack trace', 'The selected event is shown below. Frames are captured evidence; an empty stack is explicitly reported.', [
                (ids[0],0,0,24,5),(ids[1],5,0,24,10)]),
            ('Breadcrumbs & logs', 'Breadcrumbs precede the event. Logs are linked only by an exact project and trace match.', [
                (ids[2],0,0,24,9),(ids[3],9,0,24,8)]),
            ('Attachments', 'Open retained files or view available image previews. Attachment access requires an administrator.', [
                (ids[4],0,0,24,12)]),
            ('Context', 'Device, release, identifiers, tags and original captured context for this exact occurrence.', [
                (ids[5],0,0,24,12)]),
        ], navigation)
    a = activity_result['cards']
    tabs['usage'] = _apply(api, usage, [
        ('Overview', 'Installation IDs approximate the audience, not store downloads. Choose day, week or month.', [
            (a['Active installations in period'],0,0,8,4),
            (a['First observed installations in period'],0,8,8,4),
            (a['Sessions started in period'],0,16,8,4),
            (a['Active installations over time'],4,0,12,8),
            (a['Sessions started over time by system'],4,12,12,8),
            (a['First observed installations over time'],12,0,24,7)]),
        ('Platforms', 'Compare operating systems. Sessions use an exact app-session and installation match; unmatched sessions remain Unknown.', [
            (a['Active installations by system'],0,0,12,8),
            (a['Sessions started by system'],0,12,12,8),
            (a['Active installations over time by system'],8,0,24,8)]),
        ('Devices & versions', 'Distinct installations within each group. One installation can appear in several versions; do not sum these rows as unique players.', [
            (a['Active installations by system version'],0,0,12,8),
            (a['Active installations by device model'],0,12,12,8),
            (a['Active installations by app version'],8,0,24,7)]),
        ('Collection quality', 'Still open means no terminal update has been received. It does not count concurrent players. Missing identities and system matches expose collection gaps.', [
            (a['Started sessions still open'],0,0,8,4),
            (a['Session outcomes by start period'],4,0,24,8),
            (a['Activity collection coverage'],12,0,24,6)]),
    ], navigation)
    # Secondary dashboards keep their established layout and scopes, but share
    # the same two primary destinations rather than a growing navigation list.
    for title, dashboard_id in dashboards.items():
        if dashboard_id == health:
            continue
        current = api.call('GET', f'/dashboard/{dashboard_id}')
        if current.get('public_uuid'):
            raise ProvisionError('Explorer workspace must remain authenticated')
        tiles = []
        for tile in current.get('dashcards', []):
            value = _tile(tile, tile.get('dashboard_tab_id'), tile['row'], tile['col'], tile['size_x'], tile['size_y'])
            if not tile.get('card_id'):
                instruction = 'Select an event message or ID to open its stack trace.' if title == 'Event investigation' else 'Use the dashboard filters to inspect the selected scope.'
                value['visualization_settings']['text'] = navigation + '\n\n' + instruction
            tiles.append(value)
        api.call('PUT', f'/dashboard/{dashboard_id}', {'tabs': current.get('tabs', []), 'dashcards': tiles})
    return {'reports_dashboard_id': health, 'usage_dashboard_id': usage, 'tabs': tabs}
