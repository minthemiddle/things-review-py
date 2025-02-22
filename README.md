# Things Review

To create getting things done style reviews of your active Things3 projects.
Review is done for all areas that have the same tag (`$TAG`).
Review is saved in a specified area.

## Usage 

- `git clone $REPO`
- `pip install things.py`
- `cp config.json.example config.json`
- Get area ID where review should be stored (right-click in Things3, copy link, extract ID)
- Configure tags and area IDs in `config.json`
- `python review.py $TAG`, e.g. `python review.py work`

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
