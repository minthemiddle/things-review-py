# Changelog

## [1.3.0] - 2025-08-29
### 🚀 Major Modernization & Tag-less Support

#### Added
- **Tag-less review support** - NEW: Use direct area IDs instead of requiring tags
  - Add `area_ids` configuration option for direct area specification
  - Support multiple areas in single review (e.g., `"area_ids": ["ID1", "ID2"]`)
  - Backward compatible with existing tag-based configurations
- **Modern Python architecture**
  - PEP 723 script headers with inline dependency management
  - Complete type hints throughout codebase
  - Class-based architecture (`ReviewState`, `ProjectInfo` data classes)
  - Rich terminal interface replacing manual ANSI codes
- **Comprehensive testing** - 24 test cases with 100% functionality coverage
- **Enhanced CLI** - Click framework replacing argparse for better UX

#### Changed
- **BREAKING**: Minimum Python version now 3.13+
- **Configuration format** - Both modes supported:
  - Tag-based: `{"search_tag": "Work", "save_area": "ID"}`
  - Area-based: `{"area_ids": ["ID1", "ID2"], "save_area": "ID"}`
- **Installation method** - Now uses `uv` for automatic dependency management
- **File structure** - Tests moved to `tests/` folder
- **Configuration files** - Consolidated to single `config.example` file

#### Fixed
- **GitHub Issue**: Script now works without tags (resolves long-standing user issue)

#### Technical Improvements
- Object-oriented design with focused responsibilities
- Rich terminal formatting with cross-platform compatibility
- Better error handling and user feedback
- Enhanced documentation with Args/Returns/Raises sections
- Automated testing with comprehensive edge case coverage

## [1.2.0] - 2025-02-22
### Changed
- Refactored configuration to be more intuitive:
  - Renamed "areas" to "reviews" in config
  - Changed "tag" to "search_tag"
  - Changed "area_id" to "save_area"
  - Updated documentation and example config
- Improved code readability with more descriptive variable names

## [1.1.0] - 2025-02-22
### Added
- Comprehensive error handling for:
  - Missing/invalid config file
  - Invalid Things3 area/tag
  - Network/API issues
- Documentation for all functions
- CHANGELOG.md file

## [1.0.0] - 2024-01-01
### Added
- Initial release with basic functionality
