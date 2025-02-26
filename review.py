import things
import argparse
import urllib.parse
import json
from datetime import datetime
import subprocess
import sys
import os
import logging
import webbrowser
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
    parser.add_argument("area", choices=available_reviews + ["full"], nargs="?", default="full",
                        help="Specify the area for which to generate the review, or 'full' for a complete GTD review")
    parser.add_argument("-n", "--number", type=int, help="Limit the number of projects to review")
    parser.add_argument("--full", action="store_true", help="Perform a full GTD-style review")
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

def perform_full_gtd_review(config: dict, review_state: Dict[str, str]) -> None:
    """
    Perform a full GTD-style review process, guiding the user through each step.
    """
    print("\n===== FULL GTD REVIEW =====\n")
    
    # Step 1: Collect loose papers and materials
    print("Step 1: Collect loose papers and materials")
    input("Press Enter when you've gathered all physical items that need processing...")
    
    # Step 2: Process all inbox items
    print("\nStep 2: Process all inbox items")
    print("Opening Things inbox...")
    webbrowser.open("things:///show?id=inbox")
    input("Process your inbox items and press Enter when done...")
    
    # Step 3: Review previous calendar data
    print("\nStep 3: Review previous calendar data")
    input("Review your calendar for the past week. Press Enter when done...")
    
    # Step 4: Review upcoming calendar
    print("\nStep 4: Review upcoming calendar")
    input("Review your calendar for the upcoming two weeks. Press Enter when done...")
    
    # Step 5: Review waiting for list
    print("\nStep 5: Review waiting for list")
    waiting_tag = config.get('gtd_review', {}).get('waiting_for_tag', 'waiting for')
    print(f"Opening Things '{waiting_tag}' tag...")
    webbrowser.open(f"things:///show?query={urllib.parse.quote(waiting_tag)}")
    input("Review your waiting for items. Press Enter when done...")
    
    # Step 6: Review project lists
    print("\nStep 6: Review project lists")
    for area_name, area_config in config['reviews'].items():
        print(f"\nReviewing projects in area: {area_name}")
        try:
            areas = fetch_areas(area_config['search_tag'])
            projects = process_projects(areas, None, review_state)
            
            for idx, project in enumerate(projects, start=1):
                print(f"\nProject {idx}/{len(projects)}: {project['title']}")
                print(f"Opening project in Things...")
                webbrowser.open(f"things:///show?id={project['uuid']}")
                
                action = input("Actions: [n]ext, [s]kip, [d]one, [q]uit review: ").lower()
                if action == 'q':
                    break
                elif action == 'd':
                    review_state[project['uuid']] = datetime.now().isoformat()
                elif action == 's':
                    continue
                # 'n' or any other input continues to next project
            
            if action == 'q':
                break
                
        except (ThingsAPIError, AreaNotFoundError) as e:
            print(f"Error reviewing {area_name}: {str(e)}")
    
    # Step 7: Review Goals and Objectives
    print("\nStep 7: Review Goals and Objectives")
    input("Review your goals and objectives. Press Enter when done...")
    
    # Step 8: Review Areas of Focus/Responsibility
    print("\nStep 8: Review Areas of Focus/Responsibility")
    print("Opening Things areas view...")
    webbrowser.open("things:///show?id=areas")
    input("Review your areas of responsibility. Press Enter when done...")
    
    # Step 9: Review Someday/Maybe list
    print("\nStep 9: Review Someday/Maybe list")
    someday_tag = config.get('gtd_review', {}).get('someday_tag', 'someday')
    print(f"Opening Things '{someday_tag}' tag...")
    webbrowser.open(f"things:///show?query={urllib.parse.quote(someday_tag)}")
    input("Review your someday/maybe items. Press Enter when done...")
    
    # Step 10: Be creative and courageous
    print("\nStep 10: Be creative and courageous")
    print("Take some time to think about new ideas or projects you might want to start.")
    input("Press Enter when you're done with your review...")
    
    print("\n===== FULL GTD REVIEW COMPLETED =====\n")
    print("Saving review state...")
    save_review_state(review_state)

def main() -> None:
    logging.basicConfig(level=logging.ERROR)
    try:
        config = load_config()
        available_reviews = list(config['reviews'].keys())
        args = parse_args(available_reviews)
        
        review_state = load_review_state()
        
        # Handle full GTD review
        if args.full or args.area == "full":
            perform_full_gtd_review(config, review_state)
            return
            
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
