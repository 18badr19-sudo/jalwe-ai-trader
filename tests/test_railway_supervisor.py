import os
import signal
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from railway_supervisor import supervise


@unittest.skipUnless(os.name == 'posix', 'Linux process groups')
class SupervisorTests(unittest.TestCase):
    def run_pair(self, commands, stop=None):
        children = []
        popen = subprocess.Popen
        def launch(*a, **kw):
            child = popen(*a, **kw)
            children.append(child)
            return child
        with patch('railway_supervisor.subprocess.Popen', side_effect=launch):
            result = supervise(commands, stop or threading.Event(), grace=.2, interval=.01)
        self.assertTrue(all(c.poll() is not None for c in children))
        return result

    def test_research_exit_even_zero_fails_service_and_stops_dashboard(self):
        self.assertEqual(self.run_pair([
            ('research', [sys.executable, '-c', 'pass']),
            ('dashboard', [sys.executable, '-c', 'import time; time.sleep(60)']),
        ]), 1)

    def test_dashboard_failure_stops_research(self):
        self.assertEqual(self.run_pair([
            ('research', [sys.executable, '-c', 'import time; time.sleep(60)']),
            ('dashboard', [sys.executable, '-c', 'raise SystemExit(7)']),
        ]), 1)

    def test_shutdown_exits_cleanly(self):
        stop = threading.Event()
        timer = threading.Timer(.2, stop.set)
        timer.start()
        try:
            self.assertEqual(self.run_pair([
                ('research', [sys.executable, '-c', 'import time; time.sleep(60)']),
            ], stop), 0)
        finally:
            timer.join()

    def test_spawn_failure_cleans_started_child(self):
        children = []
        popen = subprocess.Popen
        def launch(*a, **kw):
            child = popen(*a, **kw)
            children.append(child)
            return child
        with patch('railway_supervisor.subprocess.Popen', side_effect=launch):
            with self.assertRaises(FileNotFoundError):
                supervise([
                    ('research', [sys.executable, '-c', 'import time; time.sleep(60)']),
                    ('dashboard', ['/nonexistent-supervisor-test-command']),
                ], threading.Event(), grace=.2)
        self.assertTrue(all(c.poll() is not None for c in children))
