#!/usr/bin/env python3

"""
borg-summary.py

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
import subprocess
import argparse
import csv
import datetime


BORG_ENV = os.environ.copy()
# TODO: possibly want these configureable
BORG_ENV['BORG_RELOCATED_REPO_ACCESS_IS_OK'] = 'yes'
BORG_ENV['BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK'] = 'yes'

BACKUP_FIELDS = ['backup_name', 'start_time', 'end_time', 'num_files', 'original_size',
                 'dedup_size', 'all_original_size', 'all_dedup_size', 'command_line']

def print_error(message, stdout=None, stderr=None):
    """
    Print an error, optionally include stdout and/or stderr strings, using red for error.
    """
    # TODO: color should be optional
    print(f'\033[0;31m{message}\033[0m')
    if stdout or stderr:
        print('output from borg follows:')
        if stdout:
            print(stdout.decode().strip())
        if stderr:
            print('\033[0;31m{}\033[0m'.format(stderr.decode().strip()))


def get_backup_list(path):
    """
    Return a list of backups in <path> that get be queried with "borg info".
    Returns None if the directory is locked by borgbackup.
    Exits with 1 on error from borg.
    """
    # check for lock file
    if (Path(path) / 'lock.exclusive').is_file():
        return None
    result = subprocess.run(['borg', 'list', '--short', path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=BORG_ENV)
    if result.returncode != 0:
        print_error('Error running "{}"'.format(' '.join(result.args)), result.stdout, result.stderr)
        exit(1)
    backup_list = []
    for line in result.stdout.decode().split('\n'):
        # there is a blank newline at the end
        if line:
            backup_list.append(line)
    return backup_list


def get_backup_info(path, backup_name):
    """
    Returns a dictionary describing borg backup <backup_name> in <path>.
    Exits with 1 on error from borg.
    {
        'start_time': datetime,
        'end_time': datetime,
        'num_files': int,
        'original_size': str,
        'dedup_size': str,
        'all_original_size': str,
        'all_dedup_size': str,
        'command_line': str,
    }
    """
    result = subprocess.run(['borg', 'info', f'{path}::{backup_name}'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=BORG_ENV)
    if result.returncode != 0:
        print_error('Error running "{}"'.format(' '.join(result.args)), result.stdout, result.stderr)
        exit(1)
    borg_info = {'backup_name': backup_name}
    lines = result.stdout.decode().split('\n')
    for line in lines:
        s = line.split()
        if line.startswith('Time (start):'):
            borg_info['start_time'] = datetime.datetime.strptime('{} {}'.format(s[3], s[4]), '%Y-%m-%d %H:%M:%S')
        elif line.startswith('Time (end):'):
            borg_info['end_time'] = datetime.datetime.strptime('{} {}'.format(s[3], s[4]), '%Y-%m-%d %H:%M:%S')
        elif line.startswith('Number of files:'):
            borg_info['num_files'] = int(s[3])
        elif line.startswith('This archive:'):
            borg_info['original_size'] = '{} {}'.format(s[2], s[3])
            borg_info['dedup_size'] = '{} {}'.format(s[6], s[7])
        elif line.startswith('All archives:'):
            borg_info['all_original_size'] = '{} {}'.format(s[2], s[3])
            borg_info['all_dedup_size'] = '{} {}'.format(s[6], s[7])
        elif line.startswith('Command line:'):
            borg_info['command_line'] = line[14:]
    return borg_info


def write_backup_data_file(borg_path, data_filename):
    """
    Create a CSV file containing a list of backups for a borg repository,
    overwriting if it already exists.  Skip if borg has locked the repo
    (i.e., a backup is running).
    borg_path: the path to a borg backup pool
    data_filename: the Path to a CSV file describing the backup sets
    """
    backup_names = get_backup_list(borg_path)
    if not backup_names:  # either None - locked by borg; or [] - no backups
        return
    if not data_filename.parent.is_dir():
        print(f'Creating {data_filename.parent}')
        os.mkdir(data_filename.parent)
    with open(data_filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, BACKUP_FIELDS)
        writer.writeheader()
        for backup_name in backup_names:
            writer.writerow(get_backup_info(borg_path, backup_name))


def update_all_data_files(pool_path):
    """
    Updates all CSV data files from borg backups.
    pool_path is a Path to the root of the backup pool structure;
    see README for structural details.
    """
    for hostname in sorted(os.listdir(pool_path)):
        borg_path = pool_path / hostname / hostname
        # TODO: configureable location of CSV files
        data_filename = Path.home() / 'borg-summary' / (hostname + '.csv')
        # TODO: only write if the # of backups is different, or if it's been more than a day since the timestamp on the file
        write_backup_data_file(borg_path, data_filename)


def read_backup_data_file(data_filename):
    """
    Return a list of dicts representing the backups in a borg repository.
    data_filename: the Path to a CSV file describing the backup sets
    """
    backups = []
    with open(data_filename) as csvfile:
        reader = csv.DictReader(csvfile, BACKUP_FIELDS)
        for row in reader:
            backups.append(row)
            print(backups[-1])
    # make a list indexed by filename so we can get to O(1)
    # data_by_filename = build_dict(data, key='filename')


def read_all_backup_data_files(data_path):
    """
    Reads all CSV files in data_path (Path) into a list of dicts containig borg backup information.
    Returns a a dict of {'host': [list of backup dicts]}
    """
    backups = {}
    for data_filename in sorted(os.listdir(data_path)):
        backup_list = []
        with open((data_path / data_filename)) as csvfile:
            reader = csv.DictReader(csvfile, BACKUP_FIELDS)
            next(reader, None)  # skip header
            for row in reader:
                backup_list.append(row)
        if backup_list:
            host = Path(data_filename).with_suffix('')
            backups[host] = backup_list
    return backups

# -----

def main():
    """
    main
    """
    parser = argparse.ArgumentParser(description='Print a summary of borgbackup repositories',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('pool', help='The root directory of a set of borgbackup repositories')
    parser.add_argument('--update', action='store_true', default=False, help='Create CSV summary file(s)')
    args = parser.parse_args()

    pool_path = Path(args.pool)
    if not os.path.isdir(pool_path):
        print(f'{pool_path} not found!')
        exit(1)

    if args.update:
        update_all_data_files(pool_path)

    # read the data
    # TODO: maybe we want to specify a specific host or hosts

    # actual size of all backups
    result = subprocess.check_output('du -sh {}'.format(args.pool), shell=True)
    print('Size of pool: {}\n\n'.format(result.decode().split()[0]))

    backup_data = read_all_backup_data_files(Path.home() / 'borg-summary')
    for host in backup_data:
        backups = backup_data[host]
        print(host)
        print('-' * len(str(host)))

        print('\nCommand line: {}\n'.format(backups[-1]['command_line']))

        print('Size of all backups:              {:>10s}'.format(backups[-1]['all_original_size']))
        print('Deduplicated size of all backups: {:>10s}'.format(backups[-1]['all_dedup_size']))
        print()
        print('{:<20s}  {:<20s}  {:>10s}  {:>10s}  {:>10s}'.format('Start time', 'End time', '# files', 'Orig size', 'Dedup size'))
        print('{:<20s}  {:<20s}  {:>10s}  {:>10s}  {:>10s}'.format('----------', '--------', '-------', '---------', '----------'))
        for d in backups:
            print('{:<20s}  {:<20s}  {:>10s}  {:>10s}  {:>10s}'.format(d['start_time'], d['end_time'], d['num_files'], d['original_size'], d['dedup_size']))
        print()


if __name__ == '__main__':
    main()
