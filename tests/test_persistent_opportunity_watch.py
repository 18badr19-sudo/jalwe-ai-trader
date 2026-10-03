import unittest
import os
from uuid import uuid4
from datetime import timedelta
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from setup_memory import SetupMemoryStore, SetupMemoryWatcher, utc_now, utc_iso


class PersistentOpportunityTests(unittest.TestCase):
    def store(self):
        store = SetupMemoryStore(database_url='', sqlite_path=':memory:')
        self.addCleanup(store.close)
        store.observe({'symbol':'OLD','status':'ACTIVE','score':70,'confidence':90,
            'current_price':9,'activation_price':10,'observed_at':utc_iso(utc_now()-timedelta(days=90))})
        return store

    def test_old_setup_remains_eligible_without_age_limit(self):
        store = self.store()
        self.assertEqual([r['symbol'] for r in store.list_due(limit=4,max_age_days=0)], ['OLD'])
        self.assertEqual(store.list_due(limit=4,max_age_days=30), [])

    def test_default_keeps_following_despite_legacy_thirty_day_setting(self):
        store = self.store()
        orchestrator = NS(prebreakout=NS(analyze_symbol=Mock(return_value=NS(score=20,data_confidence=90,current_price=9))))
        with patch.dict('os.environ', {'APEX_SETUP_MEMORY_MAX_AGE_DAYS':'30','APEX_SETUP_MEMORY_KEEP_UNTIL_OPPORTUNITY':'true'}):
            watcher = SetupMemoryWatcher(orchestrator,store=store)
            self.assertEqual(watcher.max_age_days,0)
            for _ in range(2):
                result = watcher.refresh_saved_setups()
                self.assertEqual(result['checked'],1)
                self.assertEqual(result['published'],[])
        self.assertEqual(orchestrator.prebreakout.analyze_symbol.call_count,2)
        self.assertEqual(store.get('OLD')['status'],'ACTIVE')

    def test_opt_in_expiry_and_inactive_records_are_respected(self):
        store = self.store()
        with patch.dict('os.environ', {'APEX_SETUP_MEMORY_KEEP_UNTIL_OPPORTUNITY':'false'}):
            watcher = SetupMemoryWatcher(NS(),store=store,max_age_days=30)
            self.assertEqual(watcher.refresh_saved_setups()['checked'],0)
        store.observe({'symbol':'OLD','status':'INACTIVE','score':20})
        self.assertEqual(store.list_due(limit=4,max_age_days=0),[])


@unittest.skipUnless(os.getenv('TEST_POSTGRES_DSN'), 'PostgreSQL integration requires TEST_POSTGRES_DSN')
class PostgresPersistenceTests(unittest.TestCase):
    def test_indefinite_and_expiring_query_on_real_postgres(self):
        store = SetupMemoryStore(database_url=os.environ['TEST_POSTGRES_DSN'])
        symbol = 'OLD' + uuid4().hex[:12].upper()
        try:
            store.observe({'symbol': symbol, 'status': 'ACTIVE', 'score': 70,
                'observed_at': utc_iso(utc_now()-timedelta(days=90))})
            self.assertIn(symbol, [row['symbol'] for row in store.list_due(limit=100, max_age_days=0)])
            self.assertNotIn(symbol, [row['symbol'] for row in store.list_due(limit=100, max_age_days=30)])
            store.observe({'symbol': symbol, 'status': 'INACTIVE', 'score': 20})
            self.assertNotIn(symbol, [row['symbol'] for row in store.list_due(limit=100, max_age_days=0)])
        finally:
            conn = store._connect_postgres()
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute('DELETE FROM apex_setup_memory WHERE symbol=%s', (symbol,))
            finally:
                conn.close()
                store.close()


if __name__=='__main__':
    unittest.main()
