import things
import argparse
import urllib.parse
import json
from datetime import datetime
import subprocess
import sys
import os
import logging
from typing import List, Dict, Optional

STATE_FILE = "review_state.json"

def load_review_state(state_file: str = STATE_FILE) -> Dict[str, str]:
    """
    Load the review state mapping project UUIDs to last-reviewed timestamps.
    Returns an empty dict if the file does not exist or is invalid.
    """
    if not os.path.exists(state_file):
        return {}
    with open(state_file, "r") as f:
        try:
            state = json.load(f)
        except json.JSONDecodeError:
            state = {}
    return state

def save_review_state(state: Dict[str, str], state_file: str = STATE_FILE) -> None:
    """
    Save the review state mapping project UUIDs to last-reviewed timestamps.
    """
    with open(state_file, "w") as f:
        json.dump(state, f)

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

def load_config(config_path: str = 'config.json') -> dict:
    """
    Load and validate configuration from the given JSON file.
    Raises:
        MissingConfigError: If config file is missing.
        InvalidConfigError: If config file is invalid.
    Returns:
        dict: The configuration dictionary.
    """
    if not os.path.exists(config_path):
        raise MissingConfigError(f"{config_path} file not found")
    with open(config_path, 'r') as config_file:
        try:
            config = json.load(config_file)
        except json.JSONDecodeError as e:
            raise InvalidConfigError(f"Invalid JSON in config file: {str(e)}")
    if 'reviews' not in config or not config['reviews']:
        raise InvalidConfigError("Missing or empty 'reviews' key in config")
    return config

def parse_args(available_reviews: List[str]) -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("area", choices=available_reviews, help="Specify the area for which to generate the review")
    parser.add_argument("-n", "--number", type=int, help="Limit the number of projects to review")
    return parser.parse_args()

def fetch_areas(search_tag: str) -> list:
    """
    Fetch areas from Things API based on the search tag.
    """
    try:
        areas = things.areas(tag=search_tag, include_items=True)
        if not areas:
            raise ThingsAPIError(f"No areas found with tag '{search_tag}'")
        return areas
    except Exception as e:
        raise ThingsAPIError(f"Error communicating with Things API: {str(e)}")

def process_projects(areas: list, limit: Optional[int], review_state: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Process projects from areas, sorting by when they were last reviewed and deadline.
    Projects that have not been reviewed recently come first.
    """
    from datetime import datetime
    all_projects = []
    for area in areas:
        for project in area.get('items', []):
            deadline = project.get('deadline')
            if deadline is not None:
                try:
                    deadline_parsed = datetime.fromisoformat(deadline)
                except ValueError:
                    deadline_parsed = None
            else:
                deadline_parsed = None
            last_review_str = review_state.get(project['uuid'])
            if last_review_str:
                try:
                    last_reviewed = datetime.fromisoformat(last_review_str)
                except ValueError:
                    last_reviewed = datetime.min
            else:
                last_reviewed = datetime.min
            all_projects.append({
                'title': project['title'],
                'uuid': project['uuid'],
                'deadline': deadline_parsed,
                'last_reviewed': last_reviewed
            })
    all_projects.sort(key=lambda p: (p['last_reviewed'], p['deadline'] if p['deadline'] is not None else datetime.max))
    selected = all_projects[:limit] if limit else all_projects
    return [{'title': p['title'], 'uuid': p['uuid']} for p in selected]

def generate_review_payload(projects_with_notes: list, area_id: str, title: str) -> list:
    """
    Generate the Things3 API payload for creating a review project.
    
    Args:
        projects_with_notes (list): List of project dictionaries containing 'title' and 'uuid'
        area_id (str): The Things3 area ID where the review should be created
        title (str): The formatted title for the review project
        
    Returns:
        list: A list containing the Things3 API payload structure
    """
    payload = {
        'type': 'project',
        'attributes': {
            'title': title,
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

def main() -> None:
    logging.basicConfig(level=logging.ERROR)
    try:
        config = load_config()
        available_reviews = list(config['reviews'].keys())
        args = parse_args(available_reviews)
        if args.area not in config['reviews']:
            raise AreaNotFoundError(f"Review configuration '{args.area}' not found in config")
        review_config = config['reviews'][args.area]
        search_tag = review_config['search_tag']
        save_area = review_config['save_area']
    except (ConfigError, AreaNotFoundError) as e:
        logging.error(f"Configuration error: {str(e)}")
        sys.exit(1)

    try:
        areas = fetch_areas(search_tag)
    except ThingsAPIError as e:
        logging.error(str(e))
        sys.exit(1)
    review_state = load_review_state()

    current_year, current_week_number, _ = datetime.now().isocalendar()
    formatted_title = review_config.get('title_format', '🎥 Review - {year}-cw{cw:02d}{n}').format(
        year=str(current_year)[2:],
        cw=current_week_number,
        n=f"{args.number}" if args.number else ""
    )
    projects_with_notes = process_projects(areas, args.number, review_state)
    things_payload = generate_review_payload(projects_with_notes, save_area, formatted_title)
    things_json = json.dumps(things_payload)
    things_json_encoded = urllib.parse.quote(things_json)
    things_url = f'things:///json?data={things_json_encoded}'
    import webbrowser
    webbrowser.open(things_url)
    from datetime import datetime
    current_iso = datetime.now().isoformat()
    old_states = {}
    for project in projects_with_notes:
        old_states[project['uuid']] = review_state.get(project['uuid'])
        review_state[project['uuid']] = current_iso

    print("Review project created! By default, all projects are marked as reviewed.")
    print("If any projects were NOT actually reviewed, please enter their numbers (separated by comma):")
    for idx, project in enumerate(projects_with_notes, start=1):
        print(f"{idx}. {project['title']} (UUID: {project['uuid']})")
    not_reviewed_input = input("Enter project numbers separated by comma (e.g. 1,3,4) or press Enter if all were reviewed: ")
    if not_reviewed_input.strip():
        try:
            indices = [int(s.strip()) for s in not_reviewed_input.split(',')]
            for index in indices:
                if 1 <= index <= len(projects_with_notes):
                    project = projects_with_notes[index - 1]
                    if old_states[project['uuid']] is not None:
                        review_state[project['uuid']] = old_states[project['uuid']]
                    else:
                        if project['uuid'] in review_state:
                            del review_state[project['uuid']]
        except ValueError:
            print("Invalid input, no changes will be made to review state.")
    save_review_state(review_state)

if __name__ == "__main__":
    main()
