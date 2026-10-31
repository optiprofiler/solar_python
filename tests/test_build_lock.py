"""SOLAR first-build safety: no stale lock, no partial executable, exact cache.

Compilation is replaced by a small shell command where only the coordination is
under test; test_solar_python.py covers real compilation by parallel workers.
"""
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solar_python import solar_python_tools as tools


def hold_lock(cache, entered, release):
    with tools._build_lock(Path(cache)):
        entered.set()
        if not release.wait(60):
            raise TimeoutError('The lock owner received no release signal.')


def hanging_build(cache, started):
    """A builder that is killed while its compiler still runs."""
    os.environ['SOLAR_CACHE_DIR'] = cache
    command = ['sh', '-c', 'touch "$0/started"; sleep 60', cache]
    executable = tools._runtime_cache_dir() / 'bin' / 'solar'
    with mock.patch.object(tools, '_make_command', return_value=command), \
            mock.patch.object(tools, '_default_executable', return_value=executable):
        started.set()
        tools._ensure_executable()


def write_executable(text, status=0):
    """A make command that writes ../bin/solar relative to the source tree."""
    def command(source_dir):
        script = f'printf %s "{text}" > "$0/../bin/solar"; exit {status}'
        return ['sh', '-c', script, str(source_dir)]
    return command


@unittest.skipIf(os.name == 'nt', 'The substitute build commands use a POSIX shell.')
class BuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        patcher = mock.patch.dict(os.environ, {'SOLAR_CACHE_DIR': str(self.root)})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('SOLAR_EXECUTABLE', None)
        self.context = mp.get_context('spawn')
        self.cache = tools._runtime_cache_dir()
        self.executable = self.cache / 'bin' / 'solar'
        self.cache.mkdir(parents=True)
        # A source-checkout binary would take precedence over the cache.
        patcher = mock.patch.object(tools, '_default_executable', return_value=self.executable)
        patcher.start()
        self.addCleanup(patcher.stop)

    def start(self, target, *args):
        process = self.context.Process(target=target, args=args)
        process.start()
        self.addCleanup(self.stop, process)
        return process

    @staticmethod
    def stop(process):
        if process.is_alive():
            process.kill()
        process.join(10)

    def test_killed_owner_leaves_no_stale_lock(self):
        entered, release = self.context.Event(), self.context.Event()
        process = self.start(hold_lock, str(self.cache), entered, release)
        self.assertTrue(entered.wait(30))
        os.kill(process.pid, signal.SIGKILL)
        process.join(10)
        started = time.monotonic()
        with tools._build_lock(self.cache, timeout_sec=5):
            self.assertLess(time.monotonic() - started, 2)

    def test_wait_for_a_live_build_is_bounded(self):
        entered, release = self.context.Event(), self.context.Event()
        process = self.start(hold_lock, str(self.cache), entered, release)
        self.assertTrue(entered.wait(30))
        started = time.monotonic()
        with self.assertRaisesRegex(tools.SolarExecutionError, 'Timed out after 0.3 s'):
            with tools._build_lock(self.cache, timeout_sec=0.3):
                self.fail('A live lock was taken.')
        self.assertLess(time.monotonic() - started, 5)
        release.set()
        process.join(30)
        self.assertEqual(process.exitcode, 0)
        with tools._build_lock(self.cache, timeout_sec=5):
            pass

    def test_lock_is_released_after_a_failure(self):
        with self.assertRaises(ArithmeticError):
            with tools._build_lock(self.cache, timeout_sec=1):
                raise ArithmeticError
        with tools._build_lock(self.cache, timeout_sec=1):
            pass

    def test_successful_build_is_published(self):
        with mock.patch.object(tools, '_make_command', write_executable('built')):
            self.assertEqual(tools._ensure_executable(), self.executable)
        self.assertEqual(self.executable.read_text(), 'built')
        self.assertEqual(list(self.cache.glob('.build-*')), [])

    def test_failed_build_publishes_no_partial_executable(self):
        with mock.patch.object(tools, '_make_command', write_executable('partial', 3)):
            with self.assertRaisesRegex(tools.SolarExecutionError, 'Failed to build'):
                tools._ensure_executable()
        self.assertFalse(self.executable.exists())
        self.assertEqual(list(self.cache.glob('.build-*')), [])

    def test_build_without_an_executable_fails_clearly(self):
        with mock.patch.object(tools, '_make_command', return_value=['true']):
            with self.assertRaisesRegex(tools.SolarExecutionError, 'was not built'):
                tools._ensure_executable()

    def test_killed_build_does_not_block_or_poison_the_next_one(self):
        started = self.context.Event()
        process = self.start(hanging_build, str(self.root), started)
        self.assertTrue(started.wait(30))
        marker = self.root / 'started'
        deadline = time.monotonic() + 30
        while not marker.exists():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.05)
        self.assertFalse(self.executable.exists())
        os.kill(process.pid, signal.SIGKILL)
        process.join(10)
        leftover = list(self.cache.glob('.build-*'))
        self.assertEqual(len(leftover), 1)
        started = time.monotonic()
        with mock.patch.object(tools, '_make_command', write_executable('rebuilt')):
            tools._ensure_executable()
        self.assertLess(time.monotonic() - started, 30)
        self.assertEqual(self.executable.read_text(), 'rebuilt')
        self.assertEqual(list(self.cache.glob('.build-*')), [])

    def test_orphaned_compiler_cannot_reach_the_published_executable(self):
        # The substitute compiler outlives the build and writes where it was started.
        def orphan(source_dir):
            late = ('(sleep 0.5; printf corrupt > "$0/../bin/solar") '
                    '> /dev/null 2>&1 < /dev/null & printf good > "$0/../bin/solar"')
            return ['sh', '-c', late, str(source_dir)]
        with mock.patch.object(tools, '_make_command', orphan):
            tools._ensure_executable()
        time.sleep(1)
        self.assertEqual(self.executable.read_text(), 'good')

    def test_existing_executable_needs_no_lock(self):
        self.executable.parent.mkdir(parents=True)
        self.executable.write_text('ready')
        with mock.patch.object(tools, '_build_lock', side_effect=AssertionError):
            self.assertEqual(tools._ensure_executable(), self.executable)


class CacheKeyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.runtime = Path(temporary.name) / 'solar'
        shutil.copytree(tools.RUNTIME_DIR / 'src', self.runtime / 'src',
                        ignore=shutil.ignore_patterns('*.o'))
        shutil.copyfile(tools.RUNTIME_DIR / 'manifest.json', self.runtime / 'manifest.json')
        patcher = mock.patch.object(tools, 'RUNTIME_DIR', self.runtime)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(tools._runtime_cache_key.cache_clear)

    def key(self):
        tools._runtime_cache_key.cache_clear()
        return tools._runtime_cache_key()

    def test_key_names_the_commit_and_is_stable(self):
        key = self.key()
        self.assertRegex(key, r'^[0-9a-f]{12}-[0-9a-f]{12}$')
        self.assertEqual(key, self.key())

    def test_local_source_patch_gets_its_own_cache(self):
        key = self.key()
        source = self.runtime / 'src' / 'main.cpp'
        source.write_bytes(source.read_bytes() + b'\n// local patch\n')
        self.assertNotEqual(key, self.key())

    def test_makefile_change_gets_its_own_cache(self):
        key = self.key()
        makefile = self.runtime / 'src' / 'makefile'
        makefile.write_bytes(makefile.read_bytes() + b'\n# flags\n')
        self.assertNotEqual(key, self.key())

    def test_build_products_do_not_change_the_key(self):
        key = self.key()
        (self.runtime / 'src' / 'main.o').write_bytes(b'object')
        self.assertEqual(key, self.key())

    def test_missing_manifest_still_binds_the_sources(self):
        (self.runtime / 'manifest.json').unlink()
        self.assertRegex(self.key(), r'^unversioned-[0-9a-f]{12}$')


if __name__ == '__main__':
    unittest.main()
