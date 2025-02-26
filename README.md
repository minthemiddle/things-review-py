# Things Review

A command-line tool to create Getting Things Done (GTD) style reviews of your active Things3 projects.
The tool offers two main features:
1. Area-specific reviews - Review projects from areas with a specific tag
2. Full GTD reviews - Comprehensive step-by-step GTD workflow review

## Installation and Usage

### 1. Clone the Repository
Clone this repository to your local machine:
```bash
git clone https://github.com/minthemiddle/things-review-py.git
cd things-review
```

### 2. Set Up Python Virtual Environment
Create and activate a Python virtual environment:

For macOS/Linux:
```bash
python -m venv venv
source venv/bin/activate
```

For Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

Install required dependencies:
```bash
pip install -r requirements.txt
```

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

### 4. Running a Review

#### Area-Specific Review
To generate a review for a specific tag:
```bash
python review.py TAG_NAME [-n NUMBER]
```

Examples:
```bash
# Review all work projects
python review.py work

# Review only 5 work projects
python review.py work -n 5
```

This will:
1. Find all projects within an area tagged with your configured `search_tag`
2. Create a new review project in your specified `save_area`
3. Include links to all the original projects

#### Full GTD Review
To run a comprehensive GTD review process:
```bash
python review.py full
# or
python review.py --full
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

The application uses the Rich library to provide a colorful, well-formatted terminal interface that:
- Highlights important information
- Shows progress indicators
- Provides clear step-by-step guidance during reviews
- Makes the review process more engaging and easier to follow

### 7. Deactivate Virtual Environment
When you're done, deactivate the virtual environment:
```bash
deactivate
```

### Troubleshooting
- If you get "config.json not found" errors, ensure you copied the example file
- If you get "No areas found" errors, verify your tags exist in Things3
- If you get "Invalid area ID" errors, double-check your area IDs
- If you get display issues in the terminal, ensure your terminal supports colors

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
