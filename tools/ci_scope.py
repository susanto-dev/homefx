"""Conservatively select documentation checks from a verified local Git diff."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
# Fixed Git operations only; no shell or remote requests.
import subprocess  # nosec B404

ROOT = Path(__file__).resolve().parents[1]
ROOT_DOCS = {'README.md', 'CONTRIBUTING.md', 'SECURITY.md'}
SHA = re.compile(r'[0-9a-f]{40}')


def classify(paths):
    """Only a nonempty allowlisted Markdown diff may omit runtime checks."""
    if not paths:
        return 'full', 'empty_diff'
    for path in paths:
        if (type(path) is not str or path.startswith('/') or '..' in path.split('/')
                or not (path in ROOT_DOCS or re.fullmatch(r'docs/[A-Za-z0-9_/-]+\.md', path))):
            return 'full', 'non_documentation'
    return 'docs', 'documentation_only'


def git_output(root, *args):
    git = shutil.which('git')
    if git is None:
        raise ValueError()
    # Fixed Git args; externally supplied refs are validated full hexadecimal SHAs.
    result = subprocess.run(  # nosec B603
        [git, *args], cwd=root, check=True, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, timeout=20, shell=False)
    if len(result.stdout) > 1024 * 1024:
        raise ValueError()
    return result.stdout


def select(event_name, event, root=ROOT, *, publication=False, published_base=None):
    if event_name not in {'pull_request', 'push'}:
        return 'full', 'manual_or_scheduled'
    try:
        if publication and event_name != 'push':
            return 'full', 'unknown_base'
        base = (published_base if publication else
                event['pull_request']['base']['sha'] if event_name == 'pull_request' else event['before'])
        if type(base) is not str or SHA.fullmatch(base) is None or base == '0' * 40:
            raise ValueError()
        # Missing/shallow history is a full run, never an empty documentation diff.
        git_output(root, 'cat-file', '-e', base + '^{commit}')
        if publication:
            git_output(root, 'merge-base', '--is-ancestor', base, 'HEAD')
        raw = git_output(root, 'diff', '--no-renames', '--name-only', '-z', base, 'HEAD', '--')
        if raw and not raw.endswith(b'\0'):
            raise ValueError()
        return classify([name.decode('utf-8') for name in raw.split(b'\0')[:-1]])
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return 'full', 'unknown_base'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publication', action='store_true',
                        help='compare against a verified publication, never the immediate push base')
    args = parser.parse_args()
    try:
        path = Path(os.environ['GITHUB_EVENT_PATH'])
        if path.stat().st_size > 1024 * 1024:
            raise ValueError()
        event = json.loads(path.read_text(encoding='utf-8'))
        mode, reason = select(os.environ.get('GITHUB_EVENT_NAME', ''), event,
                              publication=args.publication, published_base=os.environ.get('PUBLISHED_BASE'))
    except (KeyError, ValueError, OSError):
        mode, reason = 'full', 'unknown_base'
    # Fixed values only. No filenames, event payload or exception text is logged.
    print('Check scope: ' + mode + ' (' + reason + ').')
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
        output.write('mode=' + mode + '\n')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with Path(summary).open('a', encoding='utf-8') as output:
            output.write('Check scope: **' + mode + '** (' + reason + '). '
                         'Checks outside this scope are not claimed as passed.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
