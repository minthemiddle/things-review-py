import things
import argparse
import urllib.parse
import json
from datetime import datetime
import subprocess

def generate_review_payload(projects_with_notes, area_name):
    payload = {
        'type': 'project',
        'attributes': {
            'title': f'🎥 Review {area_name.capitalize()} - Week {current_week_number}',
            'area-id': '9nNDw4EjbzdPhQkKshBeAZ',
            'items': [
                {
                    'type': 'to-do',
                    'attributes': {
                        'title': project['title'],
                        'notes': f"[Link](things:///show?id={project['uuid']})"
                    }
                }
                for project in projects_with_notes
            ]
        }
    }
    return [payload]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("area", choices=['work', 'private', 'test'], help="Specify the area for which to generate the review")
    args = parser.parse_args()

    # Replace with your actual tags
    tag_mapping = {
        'work': '🛠 Arbeit',
        'private': '💪 Ich',
        'test': 'TestTag'
    }

    if args.area not in tag_mapping:
        print("Invalid area specified.")
        exit()

    area_tag = tag_mapping[args.area]
    areas = things.areas(tag=area_tag, include_items=True)

    current_week_number = datetime.now().isocalendar()[1]
    
    projects_with_notes = []
    for area in areas:
        projects = area['items']
        for project in projects:
            projects_with_notes.append({
                'title': project['title'],
                'uuid': project['uuid']
            })

    things_payload = generate_review_payload(projects_with_notes, args.area)
    things_json = json.dumps(things_payload)
    things_json_encoded = urllib.parse.quote(things_json)
    things_url = f'things:///json?data={things_json_encoded}'

    subprocess.run(['open', things_url])
