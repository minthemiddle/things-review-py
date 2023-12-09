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
    "areas": {
        "work": { // name of review
            "tag": "🛠 Work", // all areas with this tag will be included
            "area_id": "YourWorkAreaID" // ID of area where the review will be saved
        }
    }
}
```