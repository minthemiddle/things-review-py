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
from datetime import datetime, timedelta
import subprocess
import sys
import os
import logging
import webbrowser
from typing import List, Dict, Optional, Protocol
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text
from rich import print as rich_print
from rich.logging import RichHandler

STATE_FILE = "review_state.json"

# Initialize Rich console for better terminal output
console = Console()


@dataclass
class ProjectInfo:
    """
    Data class representing a project for review.
    
    Why: Type safety and structured data instead of loose dictionaries
    Result: Better IDE support, validation, and cleaner code
    """
    title: str
    uuid: str
    deadline: Optional[datetime] = None
    last_reviewed: Optional[datetime] = None


class ReviewState:
    """
    Manages loading and saving of review state data.
    
    Why: Encapsulates file I/O logic and provides a clean interface for state management
    Result: Centralized state handling with error handling and validation
    """
    
    def __init__(self, state_file: str = STATE_FILE):
        self.state_file = Path(state_file)
        self._state: Dict[str, str] = {}
        self.load()
    
    def load(self) -> None:
        """Load review state from file with proper error handling."""
        if not self.state_file.exists():
            self._state = {}
            return
            
        try:
            with open(self.state_file, "r") as f:
                self._state = json.load(f)
        except (json.JSONDecodeError, IOError):
            self._state = {}
    
    def save(self) -> None:
        """Save current state to file with error handling."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self._state, f, indent=2)
        except IOError as e:
            console.print(f"[red]Error saving state file: {e}[/red]")
            raise
    
    def get_last_reviewed(self, project_uuid: str) -> Optional[datetime]:
        """Get last reviewed timestamp for a project."""
        timestamp_str = self._state.get(project_uuid)
        if not timestamp_str:
            return None
            
        try:
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            return None
    
    def mark_reviewed(self, project_uuid: str, timestamp: Optional[datetime] = None) -> None:
        """Mark a project as reviewed at given timestamp."""
        if timestamp is None:
            timestamp = datetime.now()
        self._state[project_uuid] = timestamp.isoformat()
    
    def unmark_reviewed(self, project_uuid: str) -> None:
        """Remove review timestamp for a project."""
        self._state.pop(project_uuid, None)

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

def load_config(config_path: str = 'config.json') -> Dict:
    """
    Load and validate configuration from the given JSON file.
    
    Args:
        config_path: Path to the JSON configuration file
        
    Returns:
        Dict: The parsed and validated configuration dictionary containing 'reviews' key
              with area configurations and optional 'gtd_review' settings
    
    Raises:
        MissingConfigError: If config file is missing at the specified path
        InvalidConfigError: If config file contains invalid JSON or missing required keys
        
    Why: Configuration validation prevents runtime errors and provides clear feedback
    Result: Returns validated config dict or raises descriptive errors for troubleshooting
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

def validate_area_choice(ctx: click.Context, param: click.Parameter, value: str) -> str:
    """
    Validate that the area choice is either 'full' or exists in config.
    
    Args:
        ctx: Click context object (unused but required by Click callback signature)
        param: Click parameter object (unused but required by Click callback signature)
        value: The area name provided by the user
    
    Returns:
        str: The validated area choice
        
    Raises:
        click.BadParameter: If the area choice is invalid
    
    Why: Click doesn't have dynamic choices like argparse, so we validate manually
    Result: Returns validated area choice or raises descriptive error for invalid choices
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

def fetch_areas(search_tag: str) -> List[Dict]:
    """
    Fetch areas from Things API based on the search tag.
    
    Args:
        search_tag: The tag to search for in Things areas
        
    Returns:
        List[Dict]: List of area dictionaries from Things API, each containing items
        
    Raises:
        ThingsAPIError: If no areas are found or API communication fails
    
    Why: Encapsulates Things API interaction with proper error handling and validation
    Result: Returns validated areas list or raises descriptive errors for debugging
    """
    try:
        areas = things.areas(tag=search_tag, include_items=True)
        if not areas:
            raise ThingsAPIError(f"No areas found with tag '{search_tag}'")
        return areas
    except Exception as e:
        raise ThingsAPIError(f"Error communicating with Things API: {str(e)}")

def process_projects(areas: List[Dict], limit: Optional[int], review_state: ReviewState) -> List[Dict[str, str]]:
    """
    Process projects from areas, sorting by when they were last reviewed and deadline.
    
    Args:
        areas: List of area dictionaries from Things API, each containing 'items'
        limit: Maximum number of projects to return, None for no limit
        review_state: ReviewState instance for tracking review timestamps
        
    Returns:
        List[Dict[str, str]]: List of project dictionaries with title and uuid keys,
                              sorted by review priority (oldest reviews first)
    
    Why: Complex sorting logic needs proper encapsulation and clear parameter validation
    Result: Returns prioritized project list for review, with never-reviewed projects first,
            then sorted by last review date and deadline for optimal review workflow
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
            last_reviewed = review_state.get_last_reviewed(project['uuid'])
            if last_reviewed is None:
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

def generate_review_payload(projects_with_notes: List[Dict[str, str]], area_id: str, title: str) -> List[Dict]:
    """
    Generate the Things3 API payload for creating a review project.
    
    Args:
        projects_with_notes: List of project dictionaries containing 'title' and 'uuid' keys
        area_id: The Things3 area ID where the review should be created  
        title: The formatted title for the review project (e.g., "Work Review - 24-cw34")
        
    Returns:
        List[Dict]: A list containing the Things3 API payload structure ready for JSON encoding
        
    Why: Things3 API requires specific payload structure with nested project/todo hierarchy
    Result: Returns properly formatted payload that Things3 can process to create review project
            with clickable links back to original projects for easy navigation
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

def print_step_header(step_num: int, title: str) -> None:
    """
    Print a formatted step header for the GTD review process.
    
    Why: Rich provides better formatting and color consistency across terminals
    Result: Displays professional-looking step headers with consistent styling
    """
    console.print()
    console.print(Panel(f"STEP {step_num}: {title}", style="bold cyan", padding=(0, 1)))

def print_section_header(title: str) -> None:
    """
    Print a formatted section header.
    
    Why: Rich provides better typography and color handling than manual ANSI codes
    Result: Clean, readable section headers with consistent styling
    """
    console.print()
    console.print(f"[bold yellow]{title}[/bold yellow]")

def print_success(message: str) -> None:
    """
    Print a success message with checkmark.
    
    Why: Rich handles unicode symbols and colors better across different terminals
    Result: Consistent success messages with proper checkmark display
    """
    console.print(f"[bold green]✓ {message}[/bold green]")

def print_info(message: str) -> None:
    """
    Print an informational message with arrow.
    
    Why: Rich provides better color control and text rendering
    Result: Clean informational messages with consistent blue styling
    """
    console.print(f"[blue]→ {message}[/blue]")

def print_warning(message: str) -> None:
    """
    Print a warning message with exclamation.
    
    Why: Rich ensures warning colors are visible across different terminal themes
    Result: Attention-grabbing warning messages with consistent styling
    """
    console.print(f"[bold yellow]! {message}[/bold yellow]")

def print_error(message: str) -> None:
    """
    Print an error message with X mark.
    
    Why: Rich provides better error formatting and color consistency
    Result: Clear error messages that stand out with proper red coloring
    """
    console.print(f"[bold red]✗ {message}[/bold red]")

def get_user_confirmation(prompt: str = "Continue?", default: str = "y") -> bool:
    """
    Get user confirmation with Rich prompt.
    
    Why: Rich Confirm provides better UX with proper formatting and validation
    Result: Professional-looking prompts with built-in validation and styling
    """
    return Confirm.ask(prompt, default=(default.lower() == "y"))

def perform_full_gtd_review(config: dict, review_state: ReviewState) -> None:
    """
    Perform a full GTD-style review process, guiding the user through each step.
    """
    console.print()
    console.print(Panel(
        "[bold white]FULL GTD REVIEW[/bold white]", 
        style="bold cyan",
        padding=(1, 2)
    ))
    console.print()
    
    print_info("This process will guide you through a complete GTD review.")
    print_info("You can quit at any time by pressing Ctrl+C.")
    console.print()
    
    if not get_user_confirmation("Ready to begin the review?"):
        print_info("Review cancelled. No changes were made.")
        return
    
    # Step 1: Collect loose papers and materials
    print_step_header(1, "COLLECT LOOSE PAPERS AND MATERIALS")
    console.print("Gather all physical items, notes, and digital information that needs processing.")
    console.print("This includes papers, receipts, business cards, and any other items in your physical inbox.")
    if not get_user_confirmation("Have you gathered all physical items?"):
        print_warning("Take some time to collect everything before continuing.")
        console.input("[bold magenta]Press Enter when ready...[/bold magenta]")
    
    # Step 2: Process all inbox items
    print_step_header(2, "PROCESS ALL INBOX ITEMS")
    print_info("Opening Things inbox...")
    webbrowser.open("things:///show?id=inbox")
    console.print("Process each item in your inbox according to the GTD workflow:")
    console.print(" • If it takes less than 2 minutes, do it now")
    console.print(" • Delegate what you can")
    console.print(" • Defer actionable items as tasks")
    console.print(" • File reference materials")
    console.print(" • Trash what's not needed")
    console.input("[bold magenta]Press Enter when you've processed your inbox...[/bold magenta]")
    
    # Step 3: Review previous calendar data
    print_step_header(3, "REVIEW PREVIOUS CALENDAR DATA")
    console.print("Look at your calendar for the past week:")
    console.print(" • Capture any missed actions or follow-ups")
    console.print(" • Note any lessons learned from meetings or events")
    console.print(" • Transfer any relevant information to your system")
    console.input("[bold magenta]Press Enter when you've reviewed your past calendar...[/bold magenta]")
    
    # Step 4: Review upcoming calendar
    print_step_header(4, "REVIEW UPCOMING CALENDAR")
    console.print("Look at your calendar for the next two weeks:")
    console.print(" • Identify any preparation tasks needed for upcoming events")
    console.print(" • Block time for important work")
    console.print(" • Ensure you're prepared for all commitments")
    console.input("[bold magenta]Press Enter when you've reviewed your upcoming calendar...[/bold magenta]")
    
    # Step 5: Review waiting for list
    print_step_header(5, "REVIEW WAITING FOR LIST")
    waiting_tag = config.get('gtd_review', {}).get('waiting_for_tag', 'waiting for')
    print_info(f"Opening Things '{waiting_tag}' tag...")
    webbrowser.open(f"things:///show?query={urllib.parse.quote(waiting_tag)}")
    console.print("Review items you're waiting on others for:")
    console.print(" • Follow up on any items that are taking too long")
    console.print(" • Update status of items as needed")
    console.print(" • Remove completed items")
    console.input("[bold magenta]Press Enter when you've reviewed your waiting for items...[/bold magenta]")
    
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
                console.print(f"\n[bold]{idx}/{len(projects)}: {project['title']}[/bold]")
                print_info("Opening project in Things...")
                webbrowser.open(f"things:///show?id={project['uuid']}")
                
                console.print("For each project, ensure:")
                console.print(" • The project has a clear outcome/goal")
                console.print(" • There's at least one next action")
                console.print(" • All tasks are up to date")
                console.print()
                
                console.print("[bold magenta]Actions:[/bold magenta]")
                console.print(" [bold green][d][/bold green] - Mark as done/reviewed")
                console.print(" [bold yellow][n][/bold yellow] - Next project (without marking as reviewed)")
                console.print(" [bold yellow][s][/bold yellow] - Skip this project for now")
                console.print(" [bold red][q][/bold red] - Quit project review")
                console.print()
                
                action = console.input("[bold magenta]Your choice [d/n/s/q]: [/bold magenta]").lower()
                if action == 'q':
                    print_warning("Quitting project review")
                    break
                elif action == 'd':
                    review_state.mark_reviewed(project['uuid'])
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
    console.print("Take time to review your goals and objectives:")
    console.print(" • Are your projects aligned with your goals?")
    console.print(" • Do you need to adjust any goals?")
    console.print(" • Are there new projects needed to achieve your goals?")
    console.input("[bold magenta]Press Enter when you've reviewed your goals...[/bold magenta]")
    
    # Step 8: Review Areas of Focus/Responsibility
    print_step_header(8, "REVIEW AREAS OF FOCUS/RESPONSIBILITY")
    print_info("Opening Things areas view...")
    webbrowser.open("things:///show?id=areas")
    console.print("Review your areas of responsibility:")
    console.print(" • Are all areas of your life and work represented?")
    console.print(" • Are there projects needed in any neglected areas?")
    console.print(" • Should any areas be added or removed?")
    console.input("[bold magenta]Press Enter when you've reviewed your areas of responsibility...[/bold magenta]")
    
    # Step 9: Review Someday/Maybe list
    print_step_header(9, "REVIEW SOMEDAY/MAYBE LIST")
    someday_tag = config.get('gtd_review', {}).get('someday_tag', 'someday')
    print_info(f"Opening Things '{someday_tag}' tag...")
    webbrowser.open(f"things:///show?query={urllib.parse.quote(someday_tag)}")
    console.print("Review your someday/maybe items:")
    console.print(" • Are there items you want to activate now?")
    console.print(" • Are there items you can delete?")
    console.print(" • Are there new someday/maybe items to add?")
    console.input("[bold magenta]Press Enter when you've reviewed your someday/maybe items...[/bold magenta]")
    
    # Step 10: Be creative and courageous
    print_step_header(10, "BE CREATIVE AND COURAGEOUS")
    console.print("Take some time to think about new ideas or projects:")
    console.print(" • What new initiatives would you like to start?")
    console.print(" • Are there any bold moves you should make?")
    console.print(" • What would make the biggest positive difference in your life or work?")
    console.input("[bold magenta]Press Enter when you're done with your creative thinking...[/bold magenta]")
    
    console.print()
    console.print(Panel(
        "[bold white]FULL GTD REVIEW COMPLETED[/bold white]", 
        style="bold green",
        padding=(1, 2)
    ))
    console.print()
    
    print_info("Saving review state...")
    review_state.save()
    print_success("Review state saved successfully!")
    
    next_review = datetime.now() + datetime.timedelta(days=config.get('gtd_review', {}).get('review_frequency_days', 7))
    console.print(f"\nNext scheduled review: [bold]{next_review.strftime('%A, %B %d')}[/bold]")

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
    # Set up colorful logging with Rich
    from rich.logging import RichHandler
    logging.basicConfig(
        level=logging.ERROR,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True)]
    )
    
    try:
        # Display welcome banner with Rich
        console.print()
        console.print(Panel(
            "[bold white]THINGS GTD REVIEW TOOL[/bold white]", 
            style="bold cyan",
            padding=(1, 2)
        ))
        console.print()
        
        config = load_config()
        review_state = ReviewState()
        
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
    current_time = datetime.now()
    old_states = {}
    for project in projects_with_notes:
        old_states[project['uuid']] = review_state.get_last_reviewed(project['uuid'])
        review_state.mark_reviewed(project['uuid'], current_time)

    print_section_header("REVIEW COMPLETION")
    print_success("Review project created in Things!")
    print_info("By default, all projects are marked as reviewed.")
    
    # Display projects in a more readable format
    console.print("\nIncluded projects:")
    for idx, project in enumerate(projects_with_notes, start=1):
        last_reviewed = old_states[project['uuid']]
        last_reviewed_str = ""
        if last_reviewed:
            try:
                last_date = datetime.fromisoformat(last_reviewed)
                last_reviewed_str = f" (Last reviewed: {last_date.strftime('%Y-%m-%d')})"
            except ValueError:
                pass
        console.print(f"  [bold]{idx}.[/bold] {project['title']}{last_reviewed_str}")
    
    console.print()
    console.print("[bold magenta]If any projects were NOT actually reviewed, please enter their numbers.[/bold magenta]")
    not_reviewed_input = console.input("Enter numbers separated by comma (e.g. 1,3,4) or press Enter if all were reviewed: ")
    
    if not_reviewed_input.strip():
        try:
            indices = [int(s.strip()) for s in not_reviewed_input.split(',')]
            skipped_projects = []
            
            for index in indices:
                if 1 <= index <= len(projects_with_notes):
                    project = projects_with_notes[index - 1]
                    skipped_projects.append(project['title'])
                    if old_states[project['uuid']] is not None:
                        review_state.mark_reviewed(project['uuid'], old_states[project['uuid']])
                    else:
                        review_state.unmark_reviewed(project['uuid'])
            
            if skipped_projects:
                print_info(f"Marked {len(skipped_projects)} projects as not reviewed:")
                for project in skipped_projects:
                    print(f"  • {project}")
        except ValueError:
            print_warning("Invalid input, all projects will remain marked as reviewed.")
    
    # Save the updated review state
    review_state.save()
    print_success("Review state saved successfully!")
    
    # Show next scheduled review date
    next_review = datetime.now() + datetime.timedelta(days=config.get('gtd_review', {}).get('review_frequency_days', 7))
    console.print(f"\nNext scheduled review: [bold]{next_review.strftime('%A, %B %d')}[/bold]")

if __name__ == "__main__":
    main()
