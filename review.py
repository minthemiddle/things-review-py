import things
import argparse
import urllib.parse
import json
from datetime import datetime
import subprocess
import sys
import os

class ConfigError(Exception):
    """Base class for configuration errors"""
    pass

class MissingConfigError(ConfigError):
    """Raised when config file is missing"""
    pass

class InvalidConfigError(ConfigError):
    """Raised when config file is invalid"""
    pass

class AreaNotFoundError(Exception):
    """Raised when specified area is not found in config"""
    pass

class ThingsAPIError(Exception):
    """Raised when there's an error communicating with Things API"""
    pass

def generate_review_payload(projects_with_notes, area_id):
    """Generate the Things3 API payload for creating a review project.
    
    Args:
        projects_with_notes (list): List of project dictionaries containing 'title' and 'uuid'
        area_id (str): The Things3 area ID where the review should be created
        
    Returns:
        list: A list containing the Things3 API payload structure
    """
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
    
    try:
        if not os.path.exists('config.json'):
            raise MissingConfigError("config.json file not found")
            
        with open('config.json', 'r') as config_file:
            try:
                config = json.load(config_file)
            except json.JSONDecodeError as e:
                raise InvalidConfigError(f"Invalid JSON in config file: {str(e)}")
            
            if 'reviews' not in config:
                raise InvalidConfigError("Missing 'reviews' key in config")
                
            available_reviews = list(config['reviews'].keys())
            
            if not available_areas:
                raise InvalidConfigError("No areas defined in config")
                
            parser.add_argument("area", choices=available_reviews, 
                              help="Specify the area for which to generate the review")
            
        args = parser.parse_args()

        if args.area not in config['reviews']:
            raise AreaNotFoundError(f"Review configuration '{args.area}' not found in config")
            
        review_config = config['reviews'][args.area]
        search_tag = review_config['search_tag']
        save_area = review_config['save_area']
        
    except ConfigError as e:
        print(f"Configuration error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except AreaNotFoundError as e:
        print(f"Area error: {str(e)}", file=sys.stderr)
        sys.exit(1)

    try:
        areas = things.areas(tag=search_tag, include_items=True)
        if not areas:
            raise ThingsAPIError(f"No areas found with tag '{search_tag}'")
    except Exception as e:
        raise ThingsAPIError(f"Error communicating with Things API: {str(e)}")

    current_week_number = datetime.now().isocalendar()[1]
    
    projects_with_notes = []
    for area in areas:
        projects = area['items']
        for project in projects:
            projects_with_notes.append({
                'title': project['title'],
                'uuid': project['uuid']
            })

    things_payload = generate_review_payload(projects_with_notes, save_area)
    things_json = json.dumps(things_payload)
    things_json_encoded = urllib.parse.quote(things_json)
    things_url = f'things:///json?data={things_json_encoded}'

    subprocess.run(['open', things_url])
