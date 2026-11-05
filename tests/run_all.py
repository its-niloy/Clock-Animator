"""Run formula, lint, real Blender, UI and package checks with isolated profiles."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / 'tests' / 'output'


def run(label, command, env=None, ui=False):
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    startup = None
    if ui and os.name == 'nt':
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                            timeout=240, creationflags=flags, startupinfo=startup)
    output = result.stdout + result.stderr
    (LOGS / f'{label}.log').write_text(output, encoding='utf-8')
    if result.returncode:
        print(output)
        raise RuntimeError(f'{label}: process exit {result.returncode}')
    if 'headless' in label:
        print(output[output.index('TEST SUMMARY'):].strip())
    elif ui:
        print('\n'.join(line for line in output.splitlines() if 'UI SMOKE' in line))
        assert 'UI SMOKE PASS' in output
    else:
        print(f'{label}: PASS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', action='append', required=True, help='Repeat for each Blender binary')
    parser.add_argument('--ui', action='store_true', help='Also launch hidden Blender windows for actual panel draws')
    args = parser.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)
    run('math', [sys.executable, str(ROOT / 'tests' / 'test_math.py')])
    run('motion-math', [sys.executable, str(ROOT / 'tests' / 'test_motion.py')])
    run('build-safety', [sys.executable, str(ROOT / 'tests' / 'test_build.py')])
    try:
        import ruff  # noqa: F401
    except ImportError:
        print('ruff: SKIP (not installed)')
    else:
        run('ruff', [sys.executable, '-m', 'ruff', 'check', 'clock_animator', 'tests', 'build.py'])
    run('build-fallback', [sys.executable, 'build.py', '--plain-zip'])
    run('build-extension', [sys.executable, 'build.py', '--blender', args.blender[-1]])
    for index, binary in enumerate(args.blender):
        profile = ROOT / '.tools' / f'test-profile-{index}'
        profile.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env['BLENDER_USER_RESOURCES'] = str(profile)
        env['BLENDER_USER_CONFIG'] = str(profile / 'config')
        env['BLENDER_USER_SCRIPTS'] = str(profile / 'scripts')
        env['BLENDER_USER_EXTENSIONS'] = str(profile / 'extensions')
        print(f'\nBlender: {binary}', flush=True)
        run(f'{index}-probe', [binary, '-b', '--factory-startup', '--python-exit-code', '1', '--python', 'tests/verify_first.py'], env)
        run(f'{index}-headless', [binary, '-b', '--factory-startup', '--python-exit-code', '1', '--python', 'tests/run_tests.py'], env)
        run(f'{index}-advanced-headless', [binary, '-b', '--factory-startup', '--python-exit-code', '1', '--python', 'tests/advanced_tests.py'], env)
        run(f'{index}-audit', [binary, '-b', '--factory-startup', '--python-exit-code', '1', '--python', 'tests/audit_tests.py'], env)
        run(f'{index}-ux-flow', [binary, '-b', '--factory-startup', '--python-exit-code', '1', '--python', 'tests/ui_flow_tests.py'], env)
        run(f'{index}-export', [binary, '-b', '--factory-startup', '--python-exit-code', '1', '--python', 'tests/export_roundtrip.py'], env)
        if args.ui:
            run(f'{index}-ui', [binary, '--factory-startup', '--disable-autoexec', '--enable-event-simulate', '--python-exit-code', '1', '--python', 'tests/ui_smoke.py'], env, ui=True)
        run(f'{index}-packages', [binary, '-b', '--factory-startup', '--python-exit-code', '1', '--python', 'tests/package_smoke.py'], env)
    print('\nALL IMPLEMENTATION CHECKS PASSED. Spec assumption e remains FAIL. Raw logs: tests/output/')


if __name__ == '__main__':
    main()
