"""Contracts for exact-event scope and safe operator-configured evidence origins."""
import unittest

from explorer_details import definitions
from provision_metabase import ProvisionError


class EventDetailsTests(unittest.TestCase):
    def test_every_panel_requires_project_and_event(self):
        panels = definitions('https://observability.example.com')
        self.assertEqual(len(panels), 6)
        for _, sql, _, _ in panels:
            self.assertIn('project_id={{project_id}}', sql)
            self.assertIn('{{report_id}}', sql)
            self.assertNotIn('compressed_payload', sql)
        logs = next(sql for name, sql, _, _ in panels if name == 'Correlated structured logs')
        self.assertIn('l.project_id=r.project_id', logs)

    def test_origins_cannot_inject_sql_or_credentials(self):
        for origin in ('javascript:alert(1)', 'https://user:secret@example.com',
                       'https://example.com/path', 'https://example.com/?key=secret',
                       "https://example.com';DROP TABLE report;--", 'https://example.com/#fragment'):
            with self.assertRaises(ProvisionError):
                definitions(origin)
        self.assertTrue(definitions(''))

    def test_metadata_only_details_do_not_link_to_a_disabled_binary_endpoint(self):
        panel = next(sql for name, sql, _, _ in definitions(None) if name == 'Event attachments')
        self.assertNotIn('/api/evidence/', panel)
        self.assertNotIn('image_preview', panel)
        enabled = next(sql for name, sql, _, _ in definitions('') if name == 'Event attachments')
        self.assertIn('/api/evidence/attachments/', enabled)

    def test_order_is_explicit_and_correlation_is_exact(self):
        panels = {name: sql for name, sql, _, _ in definitions('https://observability.example.com')}
        self.assertIn('ORDER BY position', panels['Stack trace'])
        self.assertIn('ORDER BY chronology', panels['Breadcrumb timeline'])
        self.assertIn('crash_cache_explorer.report_logs', panels['Correlated structured logs'])


if __name__ == '__main__':
    unittest.main()
