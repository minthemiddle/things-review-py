#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click",
#     "rich",
#     "python-dotenv",
# ]
# ///

import things
import click
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

def validate_area_choice(ctx, param, value):
    """
    Validate that the area choice is either 'full' or exists in config.
    
    Why: Click doesn't have dynamic choices like argparse, so we validate manually
    Result: Returns validated area choice or raises click.BadParameter
    """
    if value == "full":
        return value
    
    try:
        config = load_config()
        available_reviews = list(config['reviews'].keys())
        if value in available_reviews:
            return value
        raise click.BadParameter(f"'{value}' is not a valid area. Choose from: {', '.join(available_reviews + ['full'])}")
    except (ConfigError, FileNotFoundError):
        # If config can't be loaded, we'll handle it in main
        return value

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

def print_step_header(step_num, title):
    """Print a formatted step header for the GTD review process."""
    print(f"\n\033[1;36m=== STEP {step_num}: {title} ===\033[0m")

def print_section_header(title):
    """Print a formatted section header."""
    print(f"\n\033[1;33m{title}\033[0m")

def print_success(message):
    """Print a success message."""
    print(f"\033[1;32m✓ {message}\033[0m")

def print_info(message):
    """Print an informational message."""
    print(f"\033[0;34m→ {message}\033[0m")

def print_warning(message):
    """Print a warning message."""
    print(f"\033[1;33m! {message}\033[0m")

def print_error(message):
    """Print an error message."""
    print(f"\033[1;31m✗ {message}\033[0m")

def get_user_confirmation(prompt="Continue?", default="y"):
    """Get user confirmation with a formatted prompt."""
    valid_responses = {"y": True, "n": False}
    default_display = default.upper() if default.lower() in valid_responses else "Y/N"
    options = "[Y/n]" if default.lower() == "y" else "[y/N]" if default.lower() == "n" else "[Y/N]"
    
    while True:
        response = input(f"\033[1;35m{prompt} {options}\033[0m ").lower() or default.lower()
        if response in valid_responses:
            return valid_responses[response]
        print_warning("Please answer with 'y' or 'n'")

def perform_full_gtd_review(config: dict, review_state: Dict[str, str]) -> None:
    """
    Perform a full GTD-style review process, guiding the user through each step.
    """
    print("\n\033[1;36m╔════════════════════════════════════════╗")
    print("║           FULL GTD REVIEW             ║")
    print("╚════════════════════════════════════════╝\033[0m\n")
    
    print_info("This process will guide you through a complete GTD review.")
    print_info("You can quit at any time by pressing Ctrl+C.")
    print()
    
    if not get_user_confirmation("Ready to begin the review?"):
        print_info("Review cancelled. No changes were made.")
        return
    
    # Step 1: Collect loose papers and materials
    print_step_header(1, "COLLECT LOOSE PAPERS AND MATERIALS")
    print("Gather all physical items, notes, and digital information that needs processing.")
    print("This includes papers, receipts, business cards, and any other items in your physical inbox.")
    if not get_user_confirmation("Have you gathered all physical items?"):
        print_warning("Take some time to collect everything before continuing.")
        input("Press Enter when ready...")
    
    # Step 2: Process all inbox items
    print_step_header(2, "PROCESS ALL INBOX ITEMS")
    print_info("Opening Things inbox...")
    webbrowser.open("things:///show?id=inbox")
    print("Process each item in your inbox according to the GTD workflow:")
    print(" • If it takes less than 2 minutes, do it now")
    print(" • Delegate what you can")
    print(" • Defer actionable items as tasks")
    print(" • File reference materials")
    print(" • Trash what's not needed")
    input("\033[1;35mPress Enter when you've processed your inbox...\033[0m ")
    
    # Step 3: Review previous calendar data
    print_step_header(3, "REVIEW PREVIOUS CALENDAR DATA")
    print("Look at your calendar for the past week:")
    print(" • Capture any missed actions or follow-ups")
    print(" • Note any lessons learned from meetings or events")
    print(" • Transfer any relevant information to your system")
    input("\033[1;35mPress Enter when you've reviewed your past calendar...\033[0m ")
    
    # Step 4: Review upcoming calendar
    print_step_header(4, "REVIEW UPCOMING CALENDAR")
    print("Look at your calendar for the next two weeks:")
    print(" • Identify any preparation tasks needed for upcoming events")
    print(" • Block time for important work")
    print(" • Ensure you're prepared for all commitments")
    input("\033[1;35mPress Enter when you've reviewed your upcoming calendar...\033[0m ")
    
    # Step 5: Review waiting for list
    print_step_header(5, "REVIEW WAITING FOR LIST")
    waiting_tag = config.get('gtd_review', {}).get('waiting_for_tag', 'waiting for')
    print_info(f"Opening Things '{waiting_tag}' tag...")
    webbrowser.open(f"things:///show?query={urllib.parse.quote(waiting_tag)}")
    print("Review items you're waiting on others for:")
    print(" • Follow up on any items that are taking too long")
    print(" • Update status of items as needed")
    print(" • Remove completed items")
    input("\033[1;35mPress Enter when you've reviewed your waiting for items...\033[0m ")
    
    # Step 6: Review project lists
    print_step_header(6, "REVIEW PROJECT LISTS")
    
    total_projects = 0
    reviewed_projects = 0
    
    for area_name, area_config in config['reviews'].items():
        print_section_header(f"Area: {area_name}")
        try:
            areas = fetch_areas(area_config['search_tag'])
            projects = process_projects(areas, None, review_state)
            total_projects += len(projects)
            
            if not projects:
                print_info(f"No projects found in {area_name}")
                continue
                
            print_info(f"Found {len(projects)} projects to review")
            
            for idx, project in enumerate(projects, start=1):
                print(f"\n\033[1m{idx}/{len(projects)}: {project['title']}\033[0m")
                print_info("Opening project in Things...")
                webbrowser.open(f"things:///show?id={project['uuid']}")
                
                print("For each project, ensure:")
                print(" • The project has a clear outcome/goal")
                print(" • There's at least one next action")
                print(" • All tasks are up to date")
                
                print("\033[1;35mActions:\033[0m")
                print(" \033[1;32m[d]\033[0m - Mark as done/reviewed")
                print(" \033[1;33m[n]\033[0m - Next project (without marking as reviewed)")
                print(" \033[1;33m[s]\033[0m - Skip this project for now")
                print(" \033[1;31m[q]\033[0m - Quit project review")
                
                action = input("\033[1;35mYour choice [d/n/s/q]:\033[0m ").lower()
                if action == 'q':
                    print_warning("Quitting project review")
                    break
                elif action == 'd':
                    review_state[project['uuid']] = datetime.now().isoformat()
                    reviewed_projects += 1
                    print_success(f"Marked '{project['title']}' as reviewed")
                elif action == 's':
                    print_info(f"Skipped '{project['title']}'")
                    continue
                else:
                    print_info(f"Moving to next project without marking as reviewed")
            
            if action == 'q':
                break
                
        except (ThingsAPIError, AreaNotFoundError) as e:
            print_error(f"Error reviewing {area_name}: {str(e)}")
    
    print_section_header("Project Review Summary")
    print_info(f"Total projects: {total_projects}")
    print_info(f"Projects reviewed: {reviewed_projects}")
    
    # Step 7: Review Goals and Objectives
    print_step_header(7, "REVIEW GOALS AND OBJECTIVES")
    print("Take time to review your goals and objectives:")
    print(" • Are your projects aligned with your goals?")
    print(" • Do you need to adjust any goals?")
    print(" • Are there new projects needed to achieve your goals?")
    input("\033[1;35mPress Enter when you've reviewed your goals...\033[0m ")
    
    # Step 8: Review Areas of Focus/Responsibility
    print_step_header(8, "REVIEW AREAS OF FOCUS/RESPONSIBILITY")
    print_info("Opening Things areas view...")
    webbrowser.open("things:///show?id=areas")
    print("Review your areas of responsibility:")
    print(" • Are all areas of your life and work represented?")
    print(" • Are there projects needed in any neglected areas?")
    print(" • Should any areas be added or removed?")
    input("\033[1;35mPress Enter when you've reviewed your areas of responsibility...\033[0m ")
    
    # Step 9: Review Someday/Maybe list
    print_step_header(9, "REVIEW SOMEDAY/MAYBE LIST")
    someday_tag = config.get('gtd_review', {}).get('someday_tag', 'someday')
    print_info(f"Opening Things '{someday_tag}' tag...")
    webbrowser.open(f"things:///show?query={urllib.parse.quote(someday_tag)}")
    print("Review your someday/maybe items:")
    print(" • Are there items you want to activate now?")
    print(" • Are there items you can delete?")
    print(" • Are there new someday/maybe items to add?")
    input("\033[1;35mPress Enter when you've reviewed your someday/maybe items...\033[0m ")
    
    # Step 10: Be creative and courageous
    print_step_header(10, "BE CREATIVE AND COURAGEOUS")
    print("Take some time to think about new ideas or projects:")
    print(" • What new initiatives would you like to start?")
    print(" • Are there any bold moves you should make?")
    print(" • What would make the biggest positive difference in your life or work?")
    input("\033[1;35mPress Enter when you're done with your creative thinking...\033[0m ")
    
    print("\n\033[1;32m╔════════════════════════════════════════╗")
    print("║       FULL GTD REVIEW COMPLETED       ║")
    print("╚════════════════════════════════════════╝\033[0m\n")
    
    print_info("Saving review state...")
    save_review_state(review_state)
    print_success("Review state saved successfully!")
    
    print("\nNext scheduled review: " + 
          (datetime.now() + datetime.timedelta(days=config.get('gtd_review', {}).get('review_frequency_days', 7))).strftime("%A, %B %d"))

@click.command()
@click.argument('area', default='full', callback=validate_area_choice)
@click.option('-n', '--number', type=int, help='Limit the number of projects to review')
@click.option('--full', is_flag=True, help='Perform a full GTD-style review')
def main(area: str, number: Optional[int], full: bool) -> None:
    """
    Main function to run the GTD review process.
    
    AREA: Specify the area for review, or 'full' for a complete GTD review
    
    Why: Converted from argparse to Click for better CLI UX and modern Python practices
    Result: Same functionality with improved user experience and error messages
    """
    # Set up colorful logging
    logging.basicConfig(
        level=logging.ERROR,
        format="\033[1;31m%(levelname)s: %(message)s\033[0m"
    )
    
    try:
        # Display welcome banner
        print("\n\033[1;36m╔════════════════════════════════════════╗")
        print("║           THINGS GTD REVIEW TOOL        ║")
        print("╚════════════════════════════════════════╝\033[0m\n")
        
        config = load_config()
        review_state = load_review_state()
        
        # Handle full GTD review
        if full or area == "full":
            perform_full_gtd_review(config, review_state)
            return
            
        if area not in config['reviews']:
            raise AreaNotFoundError(f"Review configuration '{area}' not found in config")
        
        print_section_header(f"AREA REVIEW: {area.upper()}")
        
        review_config = config['reviews'][area]
        search_tag = review_config['search_tag']
        save_area = review_config['save_area']
        
        print_info(f"Searching for projects with tag: {search_tag}")
        print_info(f"Review will be saved to area: {save_area}")
        if number:
            print_info(f"Limiting review to {number} projects")
            
    except (ConfigError, AreaNotFoundError) as e:
        print_error(f"Configuration error: {str(e)}")
        sys.exit(1)

    try:
        print_info("Fetching areas from Things...")
        areas = fetch_areas(search_tag)
        print_success(f"Found {len(areas)} areas matching tag '{search_tag}'")
    except ThingsAPIError as e:
        print_error(str(e))
        sys.exit(1)

    # Generate review title with current date information
    current_year, current_week_number, _ = datetime.now().isocalendar()
    formatted_title = review_config.get('title_format', '🎥 Review - {year}-cw{cw:02d}{n}').format(
        year=str(current_year)[2:],
        cw=current_week_number,
        n=f"{number}" if number else ""
    )
    
    print_info(f"Creating review project: \"{formatted_title}\"")
    
    # Process projects and create review
    projects_with_notes = process_projects(areas, number, review_state)
    
    if not projects_with_notes:
        print_warning("No projects found to review!")
        return
        
    print_success(f"Found {len(projects_with_notes)} projects to include in review")
    
    # Generate Things URL and open it
    things_payload = generate_review_payload(projects_with_notes, save_area, formatted_title)
    things_json = json.dumps(things_payload)
    things_json_encoded = urllib.parse.quote(things_json)
    things_url = f'things:///json?data={things_json_encoded}'
    
    print_info("Opening Things to create review project...")
    webbrowser.open(things_url)
    
    # Update review state
    current_iso = datetime.now().isoformat()
    old_states = {}
    for project in projects_with_notes:
        old_states[project['uuid']] = review_state.get(project['uuid'])
        review_state[project['uuid']] = current_iso

    print_section_header("REVIEW COMPLETION")
    print_success("Review project created in Things!")
    print_info("By default, all projects are marked as reviewed.")
    
    # Display projects in a more readable format
    print("\nIncluded projects:")
    for idx, project in enumerate(projects_with_notes, start=1):
        last_reviewed = old_states[project['uuid']]
        last_reviewed_str = ""
        if last_reviewed:
            try:
                last_date = datetime.fromisoformat(last_reviewed)
                last_reviewed_str = f" (Last reviewed: {last_date.strftime('%Y-%m-%d')})"
            except ValueError:
                pass
        print(f"  \033[1m{idx}.\033[0m {project['title']}{last_reviewed_str}")
    
    print("\n\033[1;35mIf any projects were NOT actually reviewed, please enter their numbers.\033[0m")
    not_reviewed_input = input("Enter numbers separated by comma (e.g. 1,3,4) or press Enter if all were reviewed: ")
    
    if not_reviewed_input.strip():
        try:
            indices = [int(s.strip()) for s in not_reviewed_input.split(',')]
            skipped_projects = []
            
            for index in indices:
                if 1 <= index <= len(projects_with_notes):
                    project = projects_with_notes[index - 1]
                    skipped_projects.append(project['title'])
                    if old_states[project['uuid']] is not None:
                        review_state[project['uuid']] = old_states[project['uuid']]
                    else:
                        if project['uuid'] in review_state:
                            del review_state[project['uuid']]
            
            if skipped_projects:
                print_info(f"Marked {len(skipped_projects)} projects as not reviewed:")
                for project in skipped_projects:
                    print(f"  • {project}")
        except ValueError:
            print_warning("Invalid input, all projects will remain marked as reviewed.")
    
    # Save the updated review state
    save_review_state(review_state)
    print_success("Review state saved successfully!")
    
    # Show next scheduled review date
    next_review = datetime.now() + datetime.timedelta(days=config.get('gtd_review', {}).get('review_frequency_days', 7))
    print(f"\nNext scheduled review: \033[1m{next_review.strftime('%A, %B %d')}\033[0m")

if __name__ == "__main__":
    main()
