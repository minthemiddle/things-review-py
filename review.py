import things
import argparse
import urllib.parse
import json
from datetime import datetime

def get_projects_with_notes(areas):
    projects_with_notes = []

    for area in areas:
        projects = area['items']
        for project in projects:
            notes = ""
            for task in project['items']:
                notes += f"[Link](things:///show?id={task['uuid']})\n"
            projects_with_notes.append({
                'title': project['title'],
                'notes': notes
            })

    return projects_with_notes

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("area", choices=['work', 'private', 'test'], help="Specify the area for which to generate the review")
    args = parser.parse_args()

    # Replace with your actual tags
    work_tag = '🛠 Arbeit'
    private_tag = '💪 Ich'
    test_tag = 'TestTag'

    if args.area == 'work':
        areas = things.areas(tag=work_tag, include_items=True)
    elif args.area == 'private':
        areas = things.areas(tag=private_tag, include_items=True)
    elif args.area == 'test':
        areas = things.areas(tag=test_tag, include_items=True)

    projects_with_notes = get_projects_with_notes(areas)

    current_week_number = datetime.now().isocalendar()[1]
    review_title = f"🎥 Review {args.area.capitalize()} - Week {current_week_number}"

    payload = []
    for project in projects_with_notes:
        payload.append({
            'type': 'project',
            'attributes': {
                'title': project['title'],
                'items': [
                    {
                        'type': 'to-do',
                        'attributes': {
                            'title': project['notes']
                        }
                    }
                ]
            }
        })

    things_json = json.dumps(payload)
    things_json_encoded = urllib.parse.quote(things_json)
    things_url = f'things:///json?data={things_json_encoded}'
    
    print("Generated Things3 Review URL:")
    print(things_url)
