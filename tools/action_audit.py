"""Verify Action pins and report stable upstream releases; never mutate GitHub."""
import argparse
import base64
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

import requests
import yaml
from requests.exceptions import HTTPError

SHA = re.compile(r'^[0-9a-f]{40}$')
REFERENCE = re.compile(r'^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(/[^@]+)?@([^@]+)$')


def uses(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'uses':
                if not isinstance(child, str):
                    raise ValueError('uses must be a literal string')
                yield child
            else:
                yield from uses(child)
    elif isinstance(value, list):
        for child in value:
            yield from uses(child)


def reference(value):
    match = REFERENCE.fullmatch(value)
    if not match or not SHA.fullmatch(match[3]):
        raise ValueError('External Action must use a full lowercase commit SHA: ' + value)
    repo, path, sha = match[1], (match[2] or '').lstrip('/'), match[3]
    if '..' in path.split('/') or '${{' in value:
        raise ValueError('Unsafe Action path: ' + value)
    return repo, path, sha


def api(path):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'HomeFX-action-audit'}
    if os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    response = requests.get('https://api.github.com/' + path, headers=headers,
                            timeout=30, allow_redirects=False)
    response.raise_for_status()
    return response.json()


def tag_commit(repo, tag, get):
    obj = get('repos/' + repo + '/git/ref/tags/' + quote(tag, safe=''))['object']
    for _ in range(5):
        if obj['type'] == 'commit':
            if not SHA.fullmatch(obj['sha']):
                raise ValueError('Invalid upstream commit')
            return obj['sha']
        if obj['type'] != 'tag':
            break
        obj = get('repos/' + repo + '/git/tags/' + obj['sha'])['object']
    raise ValueError('Unable to resolve release tag')


def audit(root, online=False, get=api):
    errors, updates, visited, releases = [], [], set(), {}
    def inspect(value, source, parent=None):
        if value.startswith('./'):
            path = value[2:]
            if '..' in path.split('/'):
                errors.append(source + ': unsafe local Action path')
                return
            if parent:
                value = parent[0] + '/' + path + '@' + parent[1]
            else:
                # Local composite definitions are included by the .github tree scan.
                resolved = root / path
                if not path.startswith('.github/') or not any((resolved / x).is_file() for x in ('action.yml', 'action.yaml')):
                    errors.append(source + ': local Action must exist beneath .github: ' + path)
                return
        try:
            repo, path, sha = reference(value)
        except ValueError as exc:
            errors.append(source + ': ' + str(exc))
            return
        if value in visited:
            return
        visited.add(value)
        if len(visited) > 100:
            raise ValueError('Action dependency graph exceeds audit limit')
        if not online:
            return
        try:
            if repo not in releases:
                try:
                    release = get('repos/' + repo + '/releases/latest')
                    releases[repo] = (release['tag_name'], tag_commit(repo, release['tag_name'], get))
                except HTTPError as exc:
                    if exc.response.status_code != 404:
                        raise
                    releases[repo] = None
            latest = releases[repo]
            if latest:
                tag, latest_sha = latest
                status = 'matches latest stable release'
                if sha != latest_sha:
                    comparison = get('repos/' + repo + '/compare/' + sha + '...' + latest_sha)['status']
                    status = {'ahead': 'update available; manual review required',
                              'behind': 'pin is ahead of latest release; review provenance',
                              'diverged': 'pin diverges from latest release; review provenance',
                              'identical': 'equivalent history; different commit identity'}.get(comparison, 'comparison unverified')
                updates.append(dict(action=value, latest_tag=tag, latest_sha=latest_sha, status=status))
            else:
                updates.append(dict(action=value, status='no stable release; manual tag review required'))
            names = [path] if path.endswith(('.yml', '.yaml')) else [
                (path + '/' if path else '') + 'action.yml',
                (path + '/' if path else '') + 'action.yaml']
            content = None
            for name in names:
                try:
                    blob = get('repos/' + repo + '/contents/' + quote(name, safe='/') + '?ref=' + sha)
                    content = base64.b64decode(blob['content']).decode('utf-8')
                    break
                except HTTPError as exc:
                    if exc.response.status_code != 404:
                        raise
            if content is None:
                raise ValueError('Action/workflow definition unavailable')
            for child in uses(yaml.safe_load(content)):
                inspect(child, value, (repo, sha))
        except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
            errors.append(value + ': audit incomplete (' + type(exc).__name__ + ')')
    files = sorted(set((root / '.github').rglob('*.yml')) | set((root / '.github').rglob('*.yaml')))
    if not files:
        errors.append('No workflow or Action definitions found')
    for file in files:
        for value in uses(yaml.safe_load(file.read_text())):
            inspect(value, str(file.relative_to(root)))
    return {'online': online, 'references_checked': sorted(visited), 'errors': errors, 'releases': updates}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--online', action='store_true')
    args = parser.parse_args()
    result = audit(Path(__file__).resolve().parents[1], args.online)
    output = Path('dist/action-audit')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['# External Action audit', '',
             'Manual review only. No pins, PRs, issues or settings are changed.', '',
             f"Checked {len(result['references_checked'])} unique references."]
    for entry in result['releases']:
        lines.append('- `' + entry['action'] + '`: ' + entry['status'] +
                     ('; latest `' + entry['latest_tag'] + '` at `' + entry['latest_sha'] + '`' if 'latest_tag' in entry else ''))
    lines.extend('- ERROR: ' + error for error in result['errors'])
    lines += ['', 'Full SHAs prevent tag movement from changing selected code; they do not prove trust.',
              'Nested uses are checked online. Runtime downloads, bundled libraries and Docker images are not audited.']
    report = '\n'.join(lines) + '\n'
    (output / 'summary.md').write_text(report)
    print(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            stream.write(report)
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
