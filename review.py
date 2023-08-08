import things
import argparse
import urllib.parse
import json
from datetime import datetime
import subprocess

def generate_review_payload(projects_with_notes, area_id):
    payload = {
        'type': 'project',
        'attributes': {
            'title': f'🎥 Review - Week {current_week_number}',
            'area-id': area_id,
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
    
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
        
        available_areas = config['available_areas']
        parser.add_argument("area", choices=available_areas, help="Specify the area for which to generate the review")
    
    args = parser.parse_args()

    area_info = config['areas'][args.area]
    area_tag = area_info['tag']
    area_id = area_info['area_id']

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

    things_payload = generate_review_payload(projects_with_notes, area_id)
    things_json = json.dumps(things_payload)
    things_json_encoded = urllib.parse.quote(things_json)
    things_url = f'things:///json?data={things_json_encoded}'

    subprocess.run(['open', things_url])
