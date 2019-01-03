# borg-summary changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Read & write CSV data files containing backup info for each host.
- Better error checking from borg output.

### Changed
- Split into two scripts; borg-summary.py reports on just one borg backup; borg-summary-all.py is a wrapper script which handles multiple borg repos.

### Removed
- Because it's no longer applicable, removed --first option.

## Initial version
- Prints a simple summary of multiple borg backup repositories.
