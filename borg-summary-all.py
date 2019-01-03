#!/usr/bin/env python3

"""
borg-summary-all.py

Copyright 2019  John Begenisich

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
from pathlib import Path
import glob
import argparse
from tabulate import tabulate
from borg_summary import get_data_filename, write_backup_data_file, get_data_file_age
from borg_summary import check_data_file_age, read_backup_data_file


def read_all_backup_data_files(data_path):
    """
    Reads all CSV files in data_path (Path) into a list of dicts containig borg backup information.
    Returns a a dict of {'host': [list of backup dicts]}
    """
    backups = {}
    for data_filename in sorted(glob.glob(str(data_path / '*.csv'))):
        backup_list = read_backup_data_file(Path(data_filename))
        if backup_list:
            host = Path(data_filename).with_suffix('')
            backups[host] = backup_list
    return backups


def get_all_repos(pool_path):
    """
    Return a list of Paths in pool_path (a Path), each to a single borg backup repo.
    """
    repos = []
    for host in sorted(os.listdir(pool_path)):
        for repo in sorted(os.listdir(pool_path / host)):
            repos.append(Path(pool_path / host / repo))
    return repos


def get_summary_info_of_all_repos(all_repos):
    """
    Return a list of dicts, each dict containing some data about a borg backup repo.
    all_repos is a list of paths to borg backup repos.
    """
    backup_data = {}
    for borg_path in all_repos:
        data_filename = get_data_filename(borg_path)
        host = borg_path.parent.name
        repo = borg_path.name
        data = read_backup_data_file(data_filename)
        backup_data[host] = (repo, data)

    summaries = []
    for host in backup_data:
        repo, data = backup_data[host]
        if not data:
            # no data!
            summary = {'host': host, 'repo': repo, 'num_backups': 0}
        else:
            last_backup = data[-1]
            duration = last_backup['end_time'] - last_backup['start_time']
            # some info about all backups as well as the most recent one
            summary = {'host': host,
                       'repo': repo,
                       'backup_name': f'{host} - {repo}',
                       'start_time': last_backup['start_time'],
                       'end_time': last_backup['end_time'],
                       'duration': duration,
                       'num_backups': len(data),
                       'num_files': last_backup['num_files'],
                       'original_size': last_backup['original_size'],
                       'dedup_size': last_backup['dedup_size'],
                       'all_original_size': last_backup['all_original_size'],
                       'all_dedup_size': last_backup['all_dedup_size'],
                       'command_line': last_backup['command_line']}
        summaries.append(summary)
    return summaries


# -----

def main():
    """
    main
    """
    parser = argparse.ArgumentParser(description='Print a summary of borgbackup repositories',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('pool', help='The root directory of a set of borgbackup repositories')
    parser.add_argument('--data-path', type=str, default=Path.home() / 'borg-summary',
                        help='Path to CSV files holding backup info; default: {}'.format(Path.home() / 'borg-summary'))
    parser.add_argument('--update', action='store_true', default=False, help='Create CSV summary file(s)')
    parser.add_argument('--autoupdate', action='store_true', default=False,
                        help='Create CSV data files if current data file is older than 24 hours.')
    parser.add_argument('--check', action='store_true', default=False,
                        help='Print a warning if any CSV file is older than 24 hours.')
    args = parser.parse_args()

    pool_path = Path(args.pool)
    if not os.path.isdir(pool_path):
        print(f'{pool_path} not found!')
        exit(1)

    all_repos = get_all_repos(pool_path)

    if args.update:
        for repo in all_repos:
            data_filename = get_data_filename(repo)
            result = write_backup_data_file(repo, data_filename)
            if not result:
                print(f'Warning: Could not write {data_filename}; perhaps it is locked by borgbackup?')

    if args.autoupdate:
        for repo in all_repos:
            data_filename = get_data_filename(repo)
            if not data_filename.is_file() or get_data_file_age(data_filename) > 1440:
                result = write_backup_data_file(repo, data_filename)

    if args.update or args.autoupdate:
        return

    if args.check:
        for data_filename in [get_data_filename(repo) for repo in all_repos]:
            backup_name = f'{data_filename.parent.name} - {data_filename.name}'
            check_data_file_age(backup_name, data_filename)

    summaries = get_summary_info_of_all_repos(all_repos)

    # first warn if there are any repos with no backups
    # also, determine string length of longest name
    longest_name = 0
    for summary in list(summaries):
        if len(summary['backup_name']) > longest_name:
            longest_name = len(summary['backup_name'])
        if summary['num_backups'] == 0:
            print('Warning: No backups for {}'.format(summary['backup_name']))
            summaries.remove(summary)

    print(tabulate(summaries, headers='keys'))

    # print('{:<16s}  {:<16s}  {:>10s}  {:>10s}  {:>10s}'.format('Start time', 'End time', '# files', 'Orig size', 'Dedup size'))
    # print('{:<16s}  {:<16s}  {:>10s}  {:>10s}  {:>10s}'.format('----------', '--------', '-------', '---------', '----------'))
    # for summary in summaries:
    #     for backup in backups:
    #         print('{:%Y-%m-%d %H:%M}  {:%Y-%m-%d %H:%M}  {:>10s}  {:>10s}  {:>10s}'.format(backup['start_time'],
    #                                                                                     backup['end_time'],
    #                                                                                     backup['num_files'],
    #                                                                                     backup['original_size'],
    #                                                                                     backup['dedup_size']))


    # # actual size of all backups
    # result = subprocess.check_output('du -sh {}'.format(args.pool), shell=True)
    # print('Size of pool: {}\n\n'.format(result.decode().split()[0]))



if __name__ == '__main__':
    main()
