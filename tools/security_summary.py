"""Write bounded scan counts, without interpreting missing evidence as success."""
import json
import os
from pathlib import Path


def summary(directory):
    lines = ['# Security scans', '', 'Manual triage only: no fixes, issues or PRs are created.', '']
    for name, outcome in [('bandit', 'CODE_OUTCOME'), ('runtime', 'RUNTIME_OUTCOME'),
                          ('tooling', 'TOOLING_OUTCOME')]:
        path = directory / (name + '.json')
        status = os.environ.get(outcome, 'not supplied')
        try:
            data = json.loads(path.read_text())
            if name == 'bandit':
                detail = str(len(data['results'])) + ' findings; ' + str(len(data['errors'])) + ' scan errors'
            else:
                deps = data['dependencies']
                count = sum(len(x.get('vulns', [])) for x in deps)
                skipped = sum('skip_reason' in x for x in deps)
                detail = f'{len(deps)} dependency entries; {count} advisories; {skipped} skipped'
                if not deps:
                    detail += ' — empty inventory, not evidence of external dependency coverage'
            lines.append(f'- {name}: {status}; {detail}.')
        except (OSError, ValueError, KeyError, TypeError):
            lines.append(f'- {name}: {status}; report missing or invalid. Scan is unverified.')
    lines += ['', 'Reports are attached to this run. Findings and tool failures make the job fail.',
              'Coverage: production/build Python and declared Python dependency inventories.',
              'Kodi, Android, GitHub Actions transitive dependencies and private account data are not scanned.']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    result = summary(Path('dist/security'))
    print(result)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as report:
            report.write(result)
