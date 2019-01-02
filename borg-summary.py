#!/bin/env python3

"""
borg-summary.py   John Begenisich

Copyright 2018  John Begenisich

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import subprocess
import argparse


def main():
    parser = argparse.ArgumentParser(description='Print a summary of borgbackup repositories',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('pool', help='The root directory of a set of borgbackup repositories')
    parser.add_argument('--first', action='store_true', default=False, help='Only show first repo (for debugging)')
    args = parser.parse_args()

    if not os.path.isdir(args.pool):
        print('{} not found!'.format(args.pool))
        exit(1)

    my_env = os.environ.copy()
    my_env['BORG_RELOCATED_REPO_ACCESS_IS_OK'] = 'yes'
    my_env['BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK'] = 'yes'

    result = subprocess.check_output('du -sh {}'.format(args.pool), shell=True)
    print('Size of pool: {}\n\n'.format(result.decode().split()[0]))

    first = True
    for hostname in sorted(os.listdir(args.pool)):
        borg_path = os.path.join(args.pool, hostname, hostname)
        result = subprocess.check_output('borg list {}'.format(borg_path), shell=True, env=my_env)
        backup_names = []
        for line in result.decode().split('\n'):
            if len(line) < 1:
                continue
            backup_names.append(line)

        if args.first:
            backup_names = [backup_names[-1]]

        backups = []  # list of dicts
        for line in backup_names:
            d = {}

            cmd = ['borg', 'info', '{}::{}'.format(borg_path, line.split()[0])]
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, env=my_env) as proc:
                lines = proc.stdout.read().decode().split('\n')
                for l in lines:
                    s = l.split()
                    if l.startswith('Time (start):'):
                        d['start_time'] = '{} {}'.format(s[3], s[4])
                    elif l.startswith('Time (end):'):
                        d['end_time'] = '{} {}'.format(s[3], s[4])
                    elif l.startswith('Number of files:'):
                        d['num_files'] = s[3]
                    elif l.startswith('This archive:'):
                        d['original_size'] = '{} {}'.format(s[2], s[3])
                        d['dedup_size'] = '{} {}'.format(s[6], s[7])
                    elif l.startswith('All archives:'):
                        d['all_original_size'] = '{} {}'.format(s[2], s[3])
                        d['all_dedup_size'] = '{} {}'.format(s[6], s[7])
                    elif l.startswith('Command line:'):
                        d['command_line'] = l[14:]
            backups.append(d)

        if first:
            first = False
        else:
            print('\n\n')

        print(hostname)
        print('-' * len(hostname))

        print('\nCommand line: {}\n'.format(backups[-1]['command_line']))

        print('Size of all backups:              {:>10s}'.format(backups[-1]['all_original_size']))
        print('Deduplicated size of all backups: {:>10s}'.format(backups[-1]['all_dedup_size']))
        print()
        print('{:<20s}  {:<20s}  {:>10s}  {:>10s}  {:>10s}'.format('Start time', 'End time', '# files', 'Orig size', 'Dedup size'))
        print('{:<20s}  {:<20s}  {:>10s}  {:>10s}  {:>10s}'.format('----------', '--------', '-------', '---------', '----------'))
        for d in backups:
            print('{:<20s}  {:<20s}  {:>10s}  {:>10s}  {:>10s}'.format(d['start_time'], d['end_time'], d['num_files'], d['original_size'], d['dedup_size']))


if __name__ == '__main__':
    main()
