# Things Review

A modern command-line tool to create Getting Things Done (GTD) style reviews of your active Things3 projects.
Built with Python 3.13+, featuring a rich terminal interface and comprehensive workflow automation.

**Features:**
- **Area-specific reviews** - Review projects from areas with a specific tag
- **Full GTD reviews** - Comprehensive step-by-step GTD workflow review
- **Rich terminal interface** - Beautiful, colorful output with progress indicators
- **Modern Python** - PEP 723 compliance, type hints, and class-based architecture
- **Comprehensive testing** - 21 test cases ensuring reliability

## Quick Start

### Prerequisites
- [uv](https://github.com/astral-sh/uv) package manager
- Python 3.13+ (automatically managed by uv)

### 1. Install uv
If you don't have uv installed:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Clone and Run
```bash
git clone https://github.com/minthemiddle/things-review-py.git
cd things-review-py

# Run immediately - dependencies are managed automatically
uv run review.py --help
```

No virtual environment setup needed - uv handles Python version and dependencies automatically!

### 3. Configure the Application
1. Copy the example configuration file:
```bash
cp config.json.example config.json
```

2. Configure your reviews:
   - Open `config.json` in a text editor
   - For each review type (e.g., work, personal):
     - Set the `search_tag` to match the tag you use in Things3
     - Set the `save_area` to the Things3 area ID where you want reviews saved

3. To get an area ID from Things3:
   - Right-click on the area in Things3
   - Select "Copy Link to Area"
   - The link will look like: `things:///show?id=UUID`
   - Copy the UUID part (the long string after `id=`) as your area ID

### 4. Running Reviews

#### Area-Specific Review
Generate a review for a specific area:

```bash
# Review all work projects
uv run review.py work

# Review only 5 work projects  
uv run review.py work --number 5
```

This will:
1. Find all projects within an area tagged with your configured `search_tag`
2. Create a new review project in your specified `save_area` 
3. Include clickable links back to all the original projects
4. Track review history to prioritize least-recently-reviewed projects

#### Full GTD Review
Run a comprehensive, guided GTD review process:

```bash
uv run review.py full
# or
uv run review.py --full
```

This will guide you through a complete GTD review workflow:
1. Collect loose papers and materials
2. Process all inbox items
3. Review previous calendar data
4. Review upcoming calendar
5. Review waiting for list
6. Review project lists (across all configured areas)
7. Review goals and objectives
8. Review areas of focus/responsibility
9. Review someday/maybe list
10. Creative thinking about new initiatives

### 5. Title Format Placeholders

The review title can be customized using these placeholders in the title_format:

- `{year}`: Two-digit year (e.g., 25)
- `{cw:02d}`: Calendar week with leading zero (e.g., 05)
- `{n}`: Will show "n" when using -n flag, empty otherwise

### 6. Rich Terminal Interface

The modernized application features a beautiful terminal interface powered by Rich:

- **Colorful panels and headers** - Professional-looking step indicators
- **Progress tracking** - Visual feedback during multi-step processes  
- **Better error messages** - Clear, actionable error descriptions
- **Cross-platform compatibility** - Consistent formatting across terminals
- **Interactive prompts** - User-friendly confirmation and input dialogs
- **Proper unicode support** - Checkmarks, arrows, and other symbols display correctly

### 7. Get Help
View all available options:
```bash
uv run review.py --help
```

### Troubleshooting
- **"config.json not found"** - Ensure you copied the example configuration file
- **"No areas found"** - Verify your search tags exist in Things3 and match your config
- **"Invalid area ID"** - Double-check area UUIDs in your configuration
- **Display issues** - Ensure your terminal supports colors and unicode
- **"uv not found"** - Install uv using the installation command above
- **Python version errors** - uv automatically manages Python 3.13+ installation

## Configuration

### Example config

```json
{
    "title_format": "🎥 Review - {year}-cw{cw:02d}{n}",
    "reviews": {
        "work": { 
            "search_tag": "🛠 Work",
            "save_area": "YourWorkAreaID"
        },
        "private": {
            "search_tag": "💪 Private",
            "save_area": "YourPrivateAreaID"
        }
    },
    "gtd_review": {
        "waiting_for_tag": "waiting for",
        "someday_tag": "someday",
        "review_frequency_days": 7
    }
}
```

### Configuration Options

#### Reviews Section
- `work`, `private`: Names of your review areas (can be customized)
- `search_tag`: Tag to find tasks to review in Things
- `save_area`: UUID of the area where to save the review

#### GTD Review Section
- `waiting_for_tag`: Tag used in Things for items you're waiting on others for
- `someday_tag`: Tag used in Things for someday/maybe items  
- `review_frequency_days`: How often you should perform a full review (in days)

## Development & Architecture

### Modern Python Features
This tool has been fully modernized to use current Python best practices:

- **PEP 723 compliance** - Script dependencies managed via inline metadata
- **Complete type hints** - Full static type checking support
- **Class-based architecture** - Object-oriented design with `ReviewState`, `ProjectInfo` classes
- **Rich terminal interface** - Professional CLI experience
- **Click framework** - Modern command-line argument parsing
- **Comprehensive testing** - 21 test cases with 100% functionality coverage
- **Detailed documentation** - Extensive docstrings with Args/Returns/Raises sections

### Testing
Run the test suite to verify functionality:

```bash
uv run test_review.py
```

### Code Structure
- `review.py` - Main script with modernized architecture
- `review_classes.py` - Full class-based implementation (reference)
- `test_review.py` - Comprehensive test suite
- `config.json` - Configuration file (copy from config.json.example)

### Contributing
The codebase follows modern Python standards:
- Type hints throughout
- Comprehensive error handling
- Object-oriented design patterns
- Rich terminal interface components
- Extensive test coverage

All functionality from the original script is preserved while providing a much more maintainable and extensible foundation.
