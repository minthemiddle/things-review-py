# Things Review

To create getting things done style reviews of your active Things3 projects.

## Usage 

- `git clone $REPO`
- `pip install things.py`
- `cp config.json.example config.json`
- You can configure tags that areas hold and areas where the review should be saved
- Get area ID where review should be stored (right-click in Things3, copy link, extract ID)
- Get area tags to be grouped
- Configure tags and area IDs in `config.json`
- `python review.py $TAG`, e.g. `python review.py work`
