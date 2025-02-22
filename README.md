# Things Review

To create getting things done style reviews of your active Things3 projects.
Review is done for all areas that have the same tag (`$TAG`).
Review is saved in a specified area.

## Usage 

1. Clone the repository:
   ```bash
   git clone $REPO
   cd things-review
   ```

2. Set up Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Configure the application:
   ```bash
   cp config.json.example config.json
   ```
   - Get area ID where review should be stored (right-click in Things3, copy link, extract ID)
   - Configure tags and area IDs in `config.json`

4. Run the review:
   ```bash
   python review.py $TAG
   ```
   Example:
   ```bash
   python review.py work
   ```

5. When done, deactivate the virtual environment:
   ```bash
   deactivate
   ```

## Example config

```json
{
    "reviews": {
        "work": { // name of review
            "search_tag": "🛠 Work", // tag to find tasks to review
            "save_area": "YourWorkAreaID" // where to save the review
        }
    }
}
```
