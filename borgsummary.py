#!/usr/bin/env python3

"""
borgsummary.py

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
import subprocess
import argparse
import csv
import datetime
from pathlib import Path
from dataclasses import dataclass


BORG_ENV = os.environ.copy()
# TODO: possibly want these configureable
BORG_ENV['BORG_RELOCATED_REPO_ACCESS_IS_OK'] = 'yes'
BORG_ENV['BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK'] = 'yes'

BACKUP_FIELDS = ['backup_name', 'start_time', 'end_time', 'num_files', 'original_size',
                 'dedup_size', 'all_original_size', 'all_dedup_size', 'command_line']


def get_xdg():
    """
    Return a Path to the XDG_DATA_HOME for borg-summary.
    """
    if 'XDG_DATA_HOME' in os.environ:
        return os.environ['XDG_DATA_HOME'] / '.local' / 'share' / 'borg-summary'
    return Path.home() / '.local' / 'share' / 'borg-summary'


def size_to_gb(size):
    """
    Convert string size into GB float.
    size is a string like "43.1 GB" or "37.88 T", etc.
    Must end in 'GB', 'G', 'TB', etc.
    """
    import re
    value = float(re.sub('[^0-9\.]', '', size))  # remove everything except numbers & '.'
    size = size.lower()
    if size.endswith('g') or size.endswith('gb'):
        pass
    elif size.endswith('t') or size.endswith('tb'):
        value = value * 1024
    elif size.endswith('m') or size.endswith('mb'):
        value = value / 1024
    elif size.endswith('k') or size.endswith('kb'):
        value = value / 1024 / 1024
    else:
        # I guess we should throw an exception, but...
        print(f'Warning: size_to_gb() can\'t process "{size}"')
    return round(value, 1)


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


@dataclass
class BorgBackup:
    """
    A dataclass representing a single Borg backup.
    """
    start_time: datetime
    end_time: datetime
    num_files: int
    original_size: float      # GB
    dedup_size: float         # GB
    all_original_size: float  # GB
    all_dedup_size: float     # GB
    command_line: str


class BorgBackupRepo:
    """
    A class representing a borg backup repo consisting of multiple backups.
    """

    def __init__(self, repo_path, csv_filename=None):
        self.repo_path = Path(repo_path)
        if not self.repo_path.is_dir():
            print(f'{self.repo_path} not found!')
            # TODO: throw exception instead of exiting
            exit(1)
        if csv_filename:
            self.csv_filename = Path(csv_filename)
            self.repo_name = csv_filename
            self.host = None  # we can't determine the host or repo
            self.repo = None
        else:
            self.host = self.repo_path.parent.name
            self.repo = self.repo_path.name
            self.csv_filename = get_xdg() / self.host / (self.repo + '.csv')
            self.repo_name = f'{self.host} - {self.repo}'
        # create location to place CSV file
        # do this here so we don't have to check it in several places later
        if not self.csv_filename.parent.is_dir():
            os.makedirs(self.csv_filename.parent)

    def __repr__(self):
        return self.repo_name

    def get_backup_list(self):
        """
        Return a list of backups in <path> that get be queried with "borg info".
        Returns None if the directory is locked by borgbackup.
        Exits with 1 on error from borg.
        """
        # check for lock file
        if (Path(self.repo_path) / 'lock.exclusive').exists():
            return None
        result = subprocess.run(['borg', 'list', '--short', str(self.repo_path)],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=BORG_ENV)
        if result.returncode != 0:
            print_error('Error running: {}'.format(' '.join(result.args)), result.stdout, result.stderr)
            exit(1)
        backup_list = []
        for line in result.stdout.decode().split('\n'):
            # there is a blank newline at the end
            if line:
                backup_list.append(line)
        return backup_list

    def get_backup_info(self, backup_name):
        """
        Returns a BorgBackup dataclass describing the borg backup <backup_name> in our repo_path.
        Exits with 1 on error from borg.
        TODO: throw an exception instead of exiting
        """
        result = subprocess.run(['borg', 'info', f'{self.repo_path}::{backup_name}'],
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
                borg_info['original_size'] = size_to_gb('{} {}'.format(s[2], s[3]))
                borg_info['dedup_size'] = size_to_gb('{} {}'.format(s[6], s[7]))
            elif line.startswith('All archives:'):
                borg_info['all_original_size'] = size_to_gb('{} {}'.format(s[2], s[3]))
                borg_info['all_dedup_size'] = size_to_gb('{} {}'.format(s[6], s[7]))
            elif line.startswith('Command line:'):
                borg_info['command_line'] = line[14:]
        return borg_info

    def write_backup_data_file(self):
        """
        Create a CSV file containing a list of backups for a borg repository,
        overwriting if it already exists.  Skip if borg has locked the repo
        (i.e., a backup is running).
        Returns True if successful; False if couldn't get backup info (i.e., locked by borgbackup)
        """
        backup_names = self.get_backup_list()
        if not backup_names:  # either None - locked by borg; or [] - no backups
            return False
        if not self.csv_filename.parent.is_dir():
            os.makedirs(self.csv_filename.parent)
        with open(self.csv_filename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, BACKUP_FIELDS)
            writer.writeheader()
            for backup_name in backup_names:
                writer.writerow(self.get_backup_info(backup_name))
        return True

    def read_backup_data_file(self):
        """
        Return a list of dicts representing the backups in a borg repository.
        See get_backup_info() for the dict format.
        """
        if not self.csv_filename.is_file():
            print(f'{self.csv_filename} not found!')
            # TODO: throw exception
            exit(1)
        backup_list = []
        with open(self.csv_filename) as csvfile:
            reader = csv.DictReader(csvfile, BACKUP_FIELDS)
            next(reader, None)  # skip header
            for row in reader:
                row['start_time'] = datetime.datetime.strptime(row['start_time'], '%Y-%m-%d %H:%M:%S')
                row['end_time'] = datetime.datetime.strptime(row['end_time'], '%Y-%m-%d %H:%M:%S')
                backup_list.append(row)
        return backup_list

    def get_data_file_age(self):
        """
        Returns an int representing the age of csv_filename in number of minutes.
        """
        mtime = datetime.datetime.fromtimestamp(self.csv_filename.stat().st_mtime)
        deltat = datetime.datetime.now() - mtime
        return deltat.days * 1440 + deltat.seconds // 60

    def check_data_file_age(self):
        """
        Print a warning if Path csv_filename is older than 24 hours.
        """
        age_in_days = self.get_data_file_age() // 1440
        if age_in_days >= 1:
            print('Warning: backup information for {} is {} {} old'.format(self.repo_name, age_in_days, 'day' if age_in_days == 1 else 'days'))

    def update(self):
        """
        Update the CSV data file from the content of the borg backup repo.
        """
        result = self.write_backup_data_file()
        if not result:
            print(f'Warning: Could not write {self.csv_filename}; perhaps it is locked by borgbackup?')

    def autoupdate(self):
        """
        Write CSV file if it's more than 24 hours old.
        """
        if not self.csv_filename.is_file() or self.get_data_file_age() > 1440:
            self.write_backup_data_file()

    def check(self):
        """
        Run some checks.  Currently just check age of CSV file.
        """
        self.check_data_file_age()
        # TODO: check start_time of last backup

    def print_summary(self):
        """
        Normal operation - print a summary about the backups in this borg backup repo.
        """
        backups = self.read_backup_data_file()
        print(self.repo_name)
        print('-' * len(self.repo_name))

        print('\nCommand line: {}\n'.format(backups[-1]['command_line']))

        # TODO: switch to tabulate, I guess
        print('Size of all backups (GB):              {:>8s}'.format(backups[-1]['all_original_size']))
        print('Deduplicated size of all backups (GB): {:>8s}'.format(backups[-1]['all_dedup_size']))
        result = subprocess.check_output('du -sh {}'.format(self.repo_path), shell=True)
        print('Actual size on disk (GB):              {:>8s}'.format(str(size_to_gb(result.decode().split()[0]))))
        print()
        print('{:<16s}  {:<16s}  {:>10s}  {:>10s}  {:>10s}'.format('Start time', 'End time', '# files', 'Orig size', 'Dedup size'))
        print('{:<16s}  {:<16s}  {:>10s}  {:>10s}  {:>10s}'.format('----------', '--------', '-------', '---------', '----------'))
        for backup in backups:
            print('{:%Y-%m-%d %H:%M}  {:%Y-%m-%d %H:%M}  {:>10s}  {:>10s}  {:>10s}'.format(backup['start_time'],
                                                                                        backup['end_time'],
                                                                                        backup['num_files'],
                                                                                        backup['original_size'],
                                                                                        backup['dedup_size']))


# -----

def main():
    """
    main
    """
    parser = argparse.ArgumentParser(description='Print a summary of a borgbackup repository',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('path', help='The path to a borgbackup repository')
    parser.add_argument('--csv', type=str, default=None,
                        help='The path to a CSV file holding backup info; generated automatically if not specified.')
    parser.add_argument('--data-path', type=str, default=Path.home() / 'borg-summary',
                        help='The path to CSV data files holding backup info; default: {}'.format(Path.home() / 'borg-summary'))
    parser.add_argument('--update', action='store_true', default=False, help='Create CSV data file')
    parser.add_argument('--autoupdate', action='store_true', default=False,
                        help='Create CSV data file if current data file is older than 24 hours.')
    parser.add_argument('--check', action='store_true', default=False,
                        help='Print a warning if the CSV data file is older than 24 hours, otherwise no output.')
    args = parser.parse_args()

    borgbackup = BorgBackupRepo(args.path, args.csv)

    if args.update:
        borgbackup.update()

    if args.autoupdate:
        borgbackup.autoupdate()

    if args.update or args.autoupdate:
        return

    if args.check:
        borgbackup.check()
        return

    borgbackup.print_summary()


if __name__ == '__main__':
    main()
