"""Offline bounded study phases; none can access a provider."""
import argparse
import json

from .study import STUDY, develop, freeze, prepare, run, verify_freeze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'develop', 'freeze', 'verify', 'run'))
    parser.add_argument('--output', default=str(STUDY / 'results'))
    args = parser.parse_args()
    if args.phase == 'prepare':
        result = prepare()
    elif args.phase == 'develop':
        result = develop()
    elif args.phase == 'freeze':
        result = freeze()
    elif args.phase == 'verify':
        result = {'status': 'verified', 'files': len(verify_freeze()['files_sha256'])}
    else:
        result = run(args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
