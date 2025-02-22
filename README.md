# Things Review

To create getting things done style reviews of your active Things3 projects.
Review is done for projects from all areas that have the same tag (`$TAG`).
Review is saved as project in a specified area.

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

### 5. Title Format Placeholders

The review title can be customized using these placeholders in the title_format:

- `{year}`: Two-digit year (e.g., 25)
- `{cw:02d}`: Calendar week with leading zero (e.g., 05)
- `{n}`: Will show "n" when using -n flag, empty otherwise

### 6. Deactivate Virtual Environment
When you're done, deactivate the virtual environment:
```bash
deactivate
```

### Troubleshooting
- If you get "config.json not found" errors, ensure you copied the example file
- If you get "No areas found" errors, verify your tags exist in Things3
- If you get "Invalid area ID" errors, double-check your area IDs

## Example config

```json
{
    "title_format": "🎥 Review - {year}-cw{cw:02d}{n}",
    "reviews": {
        "work": { 
            "search_tag": "🛠 Work",
            "save_area": "YourWorkAreaID"
        }
    }
}
```

Where:

- `work`: name of review
- `search_tag`: tag to find tasks to review
- `save_area`: where to save the review
