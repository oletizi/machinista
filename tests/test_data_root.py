import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import paths


def roots(environment):
    """Import app.paths in a clean interpreter with the given environment."""
    script = ('import json,sys;sys.path.insert(0,sys.argv[1]);from app import paths;'
              'print(json.dumps([str(paths.INSTALL),str(paths.DATA)]))')
    env = {k: v for k, v in os.environ.items() if k != 'MACHINISTA_DATA'}
    env.update(environment)
    output = subprocess.check_output([sys.executable, '-c', script, str(ROOT)], env=env, text=True)
    return [Path(v) for v in json.loads(output)]


class DataRootConfigurationTests(unittest.TestCase):
    def test_unset_keeps_data_in_the_checkout(self):
        install, data = roots({})
        self.assertEqual(install, ROOT)
        self.assertEqual(data, ROOT)

    def test_empty_value_keeps_data_in_the_checkout(self):
        self.assertEqual(roots({'MACHINISTA_DATA': '  '})[1], ROOT)

    def test_environment_selects_a_resolved_data_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / 'link'
            link.symlink_to(tmp)
            install, data = roots({'MACHINISTA_DATA': str(link)})
            self.assertEqual(install, ROOT)
            self.assertEqual(data, Path(tmp).resolve())

    def test_mk1_midi_manifest_follows_the_data_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items() if k != 'MACHINISTA_DATA'}
            env['MACHINISTA_DATA'] = tmp
            script = 'import sys;sys.path.insert(0,sys.argv[1]);from app.mk1_midi import MANIFEST;print(MANIFEST)'
            output = subprocess.check_output([sys.executable, '-c', script, str(ROOT)], env=env, text=True).strip()
            self.assertEqual(Path(output), Path(tmp).resolve() / 'samples/.mk1-midi.json')

    def test_home_is_expanded(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(roots({'MACHINISTA_DATA': '~/music', 'HOME': tmp})[1], Path(tmp).resolve() / 'music')


class SeparateRootTests(unittest.TestCase):
    def test_default_layout_never_redirects(self):
        with mock.patch.object(paths, 'DATA', paths.INSTALL), tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(paths.separate(paths.INSTALL))
            self.assertEqual(paths.code(paths.INSTALL), paths.INSTALL)
            self.assertEqual(paths.code(tmp), Path(tmp))
            self.assertIsNone(paths.factory(paths.INSTALL, 'presets/Oscillators'))

    def test_configured_data_root_reads_code_and_factory_content_from_the_checkout(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(paths, 'DATA', Path(tmp).resolve()):
            self.assertTrue(paths.separate(tmp))
            self.assertEqual(paths.code(tmp), paths.INSTALL)
            self.assertEqual(paths.factory(tmp, 'presets/Oscillators'), paths.INSTALL / 'presets/Oscillators')

    def test_other_roots_such_as_test_fixtures_are_unchanged(self):
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as other, \
                mock.patch.object(paths, 'DATA', Path(data).resolve()):
            self.assertFalse(paths.separate(other))
            self.assertEqual(paths.code(other), Path(other))
            self.assertIsNone(paths.factory(other, 'presets/Oscillators'))


FACTORY_WAVES = sorted(p.stem for p in (ROOT / 'presets/Oscillators').glob('*.json'))


class SeparateDataRoot(unittest.TestCase):
    """A temporary directory configured as the separate data root."""
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        patcher = mock.patch.object(paths, 'DATA', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)


class LayeredOscillatorTests(SeparateDataRoot):
    def setUp(self):
        super().setUp()
        from app import synth_library
        self.synth = synth_library
        synth_library._catalog_cache.clear()
        self.addCleanup(synth_library._catalog_cache.clear)

    def upload(self):
        import io
        from tests.test_native_synth import wav
        data = wav()
        return self.synth.upload(self.root, 'Mine.wav', io.BytesIO(data), len(data))

    def test_factory_waves_are_listed_and_resolved_from_the_checkout(self):
        self.assertTrue(FACTORY_WAVES)
        listed = {row['id'] for row in self.synth.listing(self.root)}
        self.assertEqual(listed, set(FACTORY_WAVES))
        self.assertEqual(self.synth.asset(self.root, FACTORY_WAVES[0]),
                         ROOT / 'presets/Oscillators/.assets' / (FACTORY_WAVES[0] + '.mwave'))

    def test_uploads_go_to_the_data_root_and_list_with_factory_waves(self):
        row = self.upload()
        self.assertTrue((self.root / 'presets/Oscillators' / (row['id'] + '.json')).is_file())
        self.assertTrue(self.synth.asset(self.root, row['id']).is_relative_to(self.root))
        self.assertFalse((ROOT / 'presets/Oscillators' / (row['id'] + '.json')).exists())
        listed = {r['id'] for r in self.synth.listing(self.root)}
        self.assertEqual(listed, set(FACTORY_WAVES) | {row['id']})

    def test_own_waves_can_be_edited_and_deleted(self):
        row = self.upload()
        self.assertEqual(self.synth.edit(self.root, row['id'], {'name': 'Renamed'})['name'], 'Renamed')
        self.synth.delete(self.root, row['id'])
        self.assertNotIn(row['id'], {r['id'] for r in self.synth.listing(self.root)})

    def test_factory_waves_are_read_only(self):
        identity = FACTORY_WAVES[0]
        manifest = ROOT / 'presets/Oscillators' / (identity + '.json')
        before = manifest.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Built-in'):
            self.synth.edit(self.root, identity, {'name': 'Changed'})
        with self.assertRaisesRegex(ValueError, 'Built-in'):
            self.synth.delete(self.root, identity)
        self.assertEqual(manifest.read_bytes(), before)

    def test_built_in_flags_only_factory_waves(self):
        row = self.upload()
        self.assertTrue(self.synth.built_in(self.root, FACTORY_WAVES[0]))
        self.assertFalse(self.synth.built_in(self.root, row['id']))
        with tempfile.TemporaryDirectory() as other:
            self.assertFalse(self.synth.built_in(other, FACTORY_WAVES[0]))

    def test_presets_may_reference_factory_waves(self):
        identity = FACTORY_WAVES[0]
        row = json.loads((ROOT / 'presets/Oscillators' / (identity + '.json')).read_text())
        preset = {'controls': {'osc1_wave': 32},
                  'synth_waves': {'1': {'id': identity, 'name': row['name'], 'frames': row['frames'], 'cycle': row['cycle']}}}
        self.assertEqual(self.synth.preset_waves(self.root, preset)['1']['id'], identity)

    def test_other_roots_do_not_see_factory_waves(self):
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(self.synth.listing(other), [])



FACTORY_OBXD = sorted(p.stem for p in (ROOT / 'presets/plugin-banks/obxd').glob('*.json'))


class LayeredPluginBankTests(SeparateDataRoot):
    def setUp(self):
        super().setUp()
        from app import plugin_profiles
        self.profiles = plugin_profiles
        self.obxd = next(p for p in plugin_profiles.profiles() if p['id'] == 'obxd')
        plugin_profiles._cache.clear()
        self.addCleanup(plugin_profiles._cache.clear)

    def own_bank(self):
        from app.plugin_bank_import import import_bank
        data = json.loads((ROOT / 'presets/plugin-banks/obxd' / (FACTORY_OBXD[0] + '.json')).read_text())
        data['name'] = 'Mine'
        return import_bank(self.root, 'obxd', 'Mine.json', json.dumps(data).encode())

    def ids(self, root):
        return {b['id'] for b in self.profiles.banks(root, self.obxd)}

    def test_factory_banks_are_listed_from_the_checkout(self):
        self.assertTrue(FACTORY_OBXD)
        self.assertEqual(self.ids(self.root), set(FACTORY_OBXD) | {'init'})

    def test_imports_go_to_the_data_root_and_list_with_factory_banks(self):
        bank = self.own_bank()
        self.assertTrue(Path(bank['path']).is_relative_to(self.root))
        self.assertEqual(self.ids(self.root), set(FACTORY_OBXD) | {'init', bank['id']})

    def test_only_own_banks_can_be_deleted(self):
        from app import web_plugin_banks
        bank = self.own_bank()
        rows = next(r for r in web_plugin_banks.listing(self.root) if r['id'] == 'obxd')['banks']
        deletable = {b['id']: b['canDelete'] for b in rows}
        self.assertTrue(deletable[bank['id']])
        self.assertFalse(any(deletable[i] for i in FACTORY_OBXD))
        factory = ROOT / 'presets/plugin-banks/obxd' / (FACTORY_OBXD[0] + '.json')
        with self.assertRaisesRegex(ValueError, 'built-in'):
            web_plugin_banks.delete(self.root, 'obxd', FACTORY_OBXD[0])
        self.assertTrue(factory.is_file())
        web_plugin_banks.delete(self.root, 'obxd', bank['id'])
        self.assertNotIn(bank['id'], self.ids(self.root))

    def test_saved_sounds_may_reference_factory_banks(self):
        from app.bank_sounds import bank_exists
        self.assertTrue(bank_exists(self.root, {'uri': self.obxd['uri'], 'bank': FACTORY_OBXD[0]}))

    def test_other_roots_do_not_see_factory_banks(self):
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(self.ids(other), {'init'})



class StorageLocationTests(unittest.TestCase):
    """The web UI shows where the internal storage is on disk, but only for a separate data root."""
    def rows(self, root):
        from app.web_server import Library
        return Library(root, source_scan=lambda: []).source_rows()

    def test_separate_data_root_reports_the_samples_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with mock.patch.object(paths, 'DATA', root):
                row = self.rows(root)[0]
        self.assertEqual(row['id'], 'sd')
        self.assertEqual(row['location'], str(root / 'samples'))

    def test_default_layout_keeps_the_original_listing(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(paths, 'DATA', paths.INSTALL):
            self.assertEqual(self.rows(tmp), [dict(id='sd', name='SD CARD', readOnly=False)])


class CodePathGuardTests(unittest.TestCase):
    """Code-side files must come from paths.code(root), never straight from a data root."""
    PATTERN = r"(?<![.\w])(?<!code_root\()(?<!paths\.code\()(?:self\.root|self\.library\.root|library\.root|root|ROOT)\)?\s*/\s*['\"](?:build|tools|web|captures)\b"

    def test_no_code_side_path_is_built_from_a_data_root(self):
        import re
        allowed = {'update_manager.py', 'paths.py'}  # the Pi updater rewrites the checkout itself
        offenders = []
        for path in sorted((ROOT / 'app').glob('*.py')):
            if path.name in allowed:
                continue
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if re.search(self.PATTERN, line):
                    offenders.append(f'{path.name}:{number}: {line.strip()[:100]}')
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main()
