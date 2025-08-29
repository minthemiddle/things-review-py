#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click",
#     "rich",
#     "python-dotenv",
# ]
# ///

"""
Refactored GTD review system with class-based architecture.

This module breaks down the monolithic review.py script into focused, maintainable classes:
- ReviewState: Manages persistence of review timestamps
- GTDReviewer: Orchestrates the full GTD review workflow
- ProjectProcessor: Handles project fetching and filtering logic
- ReviewCreator: Generates Things3 payloads and manages creation
- ReviewCLI: Handles command-line interface and user interaction

Why: Separation of concerns, better testability, easier maintenance and extension
Result: Modular, object-oriented codebase following modern Python practices
"""

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


@dataclass 
class ReviewConfig:
    """
    Configuration for a specific review area.
    
    Why: Structured configuration with validation and type hints
    Result: Prevents config errors and improves code clarity
    """
    search_tag: str
    save_area: str
    title_format: str = "🎥 Review - {year}-cw{cw:02d}{n}"


@dataclass
class GTDConfig:
    """
    Configuration for GTD review settings.
    
    Why: Centralized GTD-specific configuration with defaults
    Result: Easy to modify GTD review behavior and settings
    """
    waiting_for_tag: str = "waiting for"
    someday_tag: str = "someday"
    review_frequency_days: int = 7


class ThingsAPIProtocol(Protocol):
    """
    Protocol for Things API to enable mocking and testing.
    
    Why: Enables dependency injection and better testing strategies
    Result: Decouples from actual Things API for unit testing
    """
    def areas(self, tag: str, include_items: bool = True) -> List[Dict]: ...


class ReviewState:
    """
    Manages loading and saving of review state data.
    
    Why: Encapsulates file I/O logic and provides a clean interface for state management
    Result: Centralized state handling with error handling and validation
    """
    
    def __init__(self, state_file: str = "review_state.json"):
        self.state_file = Path(state_file)
        self._state: Dict[str, str] = {}
        self.load()
    
    def load(self) -> None:
        """
        Load review state from file.
        
        Why: Centralized loading logic with proper error handling
        Result: Robust state loading that handles missing/corrupted files gracefully
        """
        if not self.state_file.exists():
            self._state = {}
            return
            
        try:
            with open(self.state_file, "r") as f:
                self._state = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            console.print(f"[yellow]Warning: Could not load state file: {e}[/yellow]")
            self._state = {}
    
    def save(self) -> None:
        """
        Save current state to file.
        
        Why: Atomic save operation with error handling
        Result: Reliable state persistence with proper error reporting
        """
        try:
            with open(self.state_file, "w") as f:
                json.dump(self._state, f, indent=2)
        except IOError as e:
            console.print(f"[red]Error saving state file: {e}[/red]")
            raise
    
    def get_last_reviewed(self, project_uuid: str) -> Optional[datetime]:
        """
        Get last reviewed timestamp for a project.
        
        Why: Type-safe access to review timestamps with proper parsing
        Result: Returns datetime object or None, handles parsing errors gracefully
        """
        timestamp_str = self._state.get(project_uuid)
        if not timestamp_str:
            return None
            
        try:
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            return None
    
    def mark_reviewed(self, project_uuid: str, timestamp: Optional[datetime] = None) -> None:
        """
        Mark a project as reviewed at given timestamp.
        
        Why: Centralized way to update review timestamps with validation
        Result: Consistent timestamp format and optional current time default
        """
        if timestamp is None:
            timestamp = datetime.now()
        self._state[project_uuid] = timestamp.isoformat()
    
    def unmark_reviewed(self, project_uuid: str) -> None:
        """
        Remove review timestamp for a project.
        
        Why: Clean way to reset review state when needed
        Result: Project will be treated as never reviewed
        """
        self._state.pop(project_uuid, None)


class ProjectProcessor:
    """
    Handles fetching, filtering, and sorting projects for review.
    
    Why: Separates project processing logic from UI and persistence concerns
    Result: Focused class with single responsibility, easily testable
    """
    
    def __init__(self, things_api: ThingsAPIProtocol = things):
        self.things_api = things_api
    
    def fetch_areas(self, search_tag: str) -> List[Dict]:
        """
        Fetch areas from Things API based on search tag.
        
        Why: Encapsulates API interaction with proper error handling
        Result: Returns areas list or raises descriptive errors
        """
        try:
            areas = self.things_api.areas(tag=search_tag, include_items=True)
            if not areas:
                raise ValueError(f"No areas found with tag '{search_tag}'")
            return areas
        except Exception as e:
            raise RuntimeError(f"Error communicating with Things API: {str(e)}") from e
    
    def process_projects(self, areas: List[Dict], review_state: ReviewState, limit: Optional[int] = None) -> List[ProjectInfo]:
        """
        Process and sort projects from areas based on review history.
        
        Why: Complex sorting logic deserves its own method with clear parameters
        Result: Returns prioritized project list with proper type safety
        """
        all_projects = []
        
        for area in areas:
            for project_data in area.get('items', []):
                # Parse deadline if present
                deadline = None
                if project_data.get('deadline'):
                    try:
                        deadline = datetime.fromisoformat(project_data['deadline'])
                    except ValueError:
                        pass  # Invalid deadline format, skip
                
                # Get last reviewed timestamp
                last_reviewed = review_state.get_last_reviewed(project_data['uuid'])
                
                project = ProjectInfo(
                    title=project_data['title'],
                    uuid=project_data['uuid'],
                    deadline=deadline,
                    last_reviewed=last_reviewed
                )
                all_projects.append(project)
        
        # Sort by last reviewed (oldest first), then by deadline
        all_projects.sort(key=lambda p: (
            p.last_reviewed or datetime.min,
            p.deadline or datetime.max
        ))
        
        if limit:
            all_projects = all_projects[:limit]
        
        return all_projects


class ReviewCreator:
    """
    Handles creation of review projects in Things.
    
    Why: Encapsulates Things3 API payload generation and project creation
    Result: Clean interface for creating reviews with proper error handling
    """
    
    def generate_payload(self, projects: List[ProjectInfo], area_id: str, title: str) -> List[Dict]:
        """
        Generate Things3 API payload for creating a review project.
        
        Why: Separates payload generation logic for better testability
        Result: Returns properly formatted Things3 API payload
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
                            'title': project.title,
                            'notes': f"[Link](things:///show?id={project.uuid})"
                        }
                    }
                    for project in projects
                ]
            }
        }
        return [payload]
    
    def create_review_project(self, projects: List[ProjectInfo], area_id: str, title: str) -> None:
        """
        Create a review project in Things by opening the URL.
        
        Why: Handles the complete review creation workflow
        Result: Opens Things with the review project ready to be created
        """
        payload = self.generate_payload(projects, area_id, title)
        things_json = json.dumps(payload)
        things_json_encoded = urllib.parse.quote(things_json)
        things_url = f'things:///json?data={things_json_encoded}'
        
        console.print("[blue]→ Opening Things to create review project...[/blue]")
        webbrowser.open(things_url)


class GTDReviewer:
    """
    Orchestrates the full GTD review process.
    
    Why: Manages the complex GTD workflow with proper separation of concerns
    Result: Clear, maintainable implementation of the full GTD review process
    """
    
    def __init__(self, config: GTDConfig, review_state: ReviewState, project_processor: ProjectProcessor):
        self.config = config
        self.review_state = review_state
        self.project_processor = project_processor
    
    def run_full_review(self, reviews_config: Dict[str, ReviewConfig]) -> None:
        """
        Execute the complete GTD review process.
        
        Why: Main orchestration method that coordinates all review steps
        Result: Guides user through complete GTD review with progress tracking
        """
        console.print()
        console.print(Panel(
            "[bold white]FULL GTD REVIEW[/bold white]", 
            style="bold cyan",
            padding=(1, 2)
        ))
        console.print()
        
        console.print("[blue]→ This process will guide you through a complete GTD review.[/blue]")
        console.print("[blue]→ You can quit at any time by pressing Ctrl+C.[/blue]")
        console.print()
        
        if not Confirm.ask("Ready to begin the review?", default=True):
            console.print("[blue]→ Review cancelled. No changes were made.[/blue]")
            return
        
        # Execute all review steps
        self._step_collect_materials()
        self._step_process_inbox()
        self._step_review_past_calendar()
        self._step_review_upcoming_calendar()
        self._step_review_waiting_for()
        self._step_review_projects(reviews_config)
        self._step_review_goals()
        self._step_review_areas()
        self._step_review_someday_maybe()
        self._step_creative_thinking()
        
        self._complete_review()
    
    def _step_collect_materials(self) -> None:
        """Step 1: Collect loose papers and materials."""
        console.print()
        console.print(Panel("STEP 1: COLLECT LOOSE PAPERS AND MATERIALS", style="bold cyan", padding=(0, 1)))
        console.print("Gather all physical items, notes, and digital information that needs processing.")
        console.print("This includes papers, receipts, business cards, and any other items in your physical inbox.")
        
        if not Confirm.ask("Have you gathered all physical items?", default=True):
            console.print("[yellow]! Take some time to collect everything before continuing.[/yellow]")
            console.input("[bold magenta]Press Enter when ready...[/bold magenta]")
    
    def _step_process_inbox(self) -> None:
        """Step 2: Process all inbox items."""
        console.print()
        console.print(Panel("STEP 2: PROCESS ALL INBOX ITEMS", style="bold cyan", padding=(0, 1)))
        console.print("[blue]→ Opening Things inbox...[/blue]")
        webbrowser.open("things:///show?id=inbox")
        
        console.print("Process each item in your inbox according to the GTD workflow:")
        console.print(" • If it takes less than 2 minutes, do it now")
        console.print(" • Delegate what you can")
        console.print(" • Defer actionable items as tasks")
        console.print(" • File reference materials")
        console.print(" • Trash what's not needed")
        
        console.input("[bold magenta]Press Enter when you've processed your inbox...[/bold magenta]")
    
    def _step_review_past_calendar(self) -> None:
        """Step 3: Review previous calendar data."""
        console.print()
        console.print(Panel("STEP 3: REVIEW PREVIOUS CALENDAR DATA", style="bold cyan", padding=(0, 1)))
        console.print("Look at your calendar for the past week:")
        console.print(" • Capture any missed actions or follow-ups")
        console.print(" • Note any lessons learned from meetings or events")
        console.print(" • Transfer any relevant information to your system")
        
        console.input("[bold magenta]Press Enter when you've reviewed your past calendar...[/bold magenta]")
    
    def _step_review_upcoming_calendar(self) -> None:
        """Step 4: Review upcoming calendar."""
        console.print()
        console.print(Panel("STEP 4: REVIEW UPCOMING CALENDAR", style="bold cyan", padding=(0, 1)))
        console.print("Look at your calendar for the next two weeks:")
        console.print(" • Identify any preparation tasks needed for upcoming events")
        console.print(" • Block time for important work")
        console.print(" • Ensure you're prepared for all commitments")
        
        console.input("[bold magenta]Press Enter when you've reviewed your upcoming calendar...[/bold magenta]")
    
    def _step_review_waiting_for(self) -> None:
        """Step 5: Review waiting for list."""
        console.print()
        console.print(Panel("STEP 5: REVIEW WAITING FOR LIST", style="bold cyan", padding=(0, 1)))
        console.print(f"[blue]→ Opening Things '{self.config.waiting_for_tag}' tag...[/blue]")
        webbrowser.open(f"things:///show?query={urllib.parse.quote(self.config.waiting_for_tag)}")
        
        console.print("Review items you're waiting on others for:")
        console.print(" • Follow up on any items that are taking too long")
        console.print(" • Update status of items as needed")
        console.print(" • Remove completed items")
        
        console.input("[bold magenta]Press Enter when you've reviewed your waiting for items...[/bold magenta]")
    
    def _step_review_projects(self, reviews_config: Dict[str, ReviewConfig]) -> None:
        """Step 6: Review project lists."""
        console.print()
        console.print(Panel("STEP 6: REVIEW PROJECT LISTS", style="bold cyan", padding=(0, 1)))
        
        total_projects = 0
        reviewed_projects = 0
        
        for area_name, area_config in reviews_config.items():
            console.print(f"\n[bold yellow]Area: {area_name}[/bold yellow]")
            
            try:
                areas = self.project_processor.fetch_areas(area_config.search_tag)
                projects = self.project_processor.process_projects(areas, self.review_state)
                total_projects += len(projects)
                
                if not projects:
                    console.print(f"[blue]→ No projects found in {area_name}[/blue]")
                    continue
                
                console.print(f"[blue]→ Found {len(projects)} projects to review[/blue]")
                
                for idx, project in enumerate(projects, start=1):
                    console.print(f"\n[bold]{idx}/{len(projects)}: {project.title}[/bold]")
                    console.print("[blue]→ Opening project in Things...[/blue]")
                    webbrowser.open(f"things:///show?id={project.uuid}")
                    
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
                        console.print("[yellow]! Quitting project review[/yellow]")
                        return
                    elif action == 'd':
                        self.review_state.mark_reviewed(project.uuid)
                        reviewed_projects += 1
                        console.print(f"[green]✓ Marked '{project.title}' as reviewed[/green]")
                    elif action == 's':
                        console.print(f"[blue]→ Skipped '{project.title}'[/blue]")
                        continue
                    else:
                        console.print("[blue]→ Moving to next project without marking as reviewed[/blue]")
                        
            except (RuntimeError, ValueError) as e:
                console.print(f"[red]✗ Error reviewing {area_name}: {str(e)}[/red]")
        
        console.print(f"\n[bold yellow]Project Review Summary[/bold yellow]")
        console.print(f"[blue]→ Total projects: {total_projects}[/blue]")
        console.print(f"[blue]→ Projects reviewed: {reviewed_projects}[/blue]")
    
    def _step_review_goals(self) -> None:
        """Step 7: Review Goals and Objectives."""
        console.print()
        console.print(Panel("STEP 7: REVIEW GOALS AND OBJECTIVES", style="bold cyan", padding=(0, 1)))
        console.print("Take time to review your goals and objectives:")
        console.print(" • Are your projects aligned with your goals?")
        console.print(" • Do you need to adjust any goals?")
        console.print(" • Are there new projects needed to achieve your goals?")
        
        console.input("[bold magenta]Press Enter when you've reviewed your goals...[/bold magenta]")
    
    def _step_review_areas(self) -> None:
        """Step 8: Review Areas of Focus/Responsibility."""
        console.print()
        console.print(Panel("STEP 8: REVIEW AREAS OF FOCUS/RESPONSIBILITY", style="bold cyan", padding=(0, 1)))
        console.print("[blue]→ Opening Things areas view...[/blue]")
        webbrowser.open("things:///show?id=areas")
        
        console.print("Review your areas of responsibility:")
        console.print(" • Are all areas of your life and work represented?")
        console.print(" • Are there projects needed in any neglected areas?")
        console.print(" • Should any areas be added or removed?")
        
        console.input("[bold magenta]Press Enter when you've reviewed your areas of responsibility...[/bold magenta]")
    
    def _step_review_someday_maybe(self) -> None:
        """Step 9: Review Someday/Maybe list."""
        console.print()
        console.print(Panel("STEP 9: REVIEW SOMEDAY/MAYBE LIST", style="bold cyan", padding=(0, 1)))
        console.print(f"[blue]→ Opening Things '{self.config.someday_tag}' tag...[/blue]")
        webbrowser.open(f"things:///show?query={urllib.parse.quote(self.config.someday_tag)}")
        
        console.print("Review your someday/maybe items:")
        console.print(" • Are there items you want to activate now?")
        console.print(" • Are there items you can delete?")
        console.print(" • Are there new someday/maybe items to add?")
        
        console.input("[bold magenta]Press Enter when you've reviewed your someday/maybe items...[/bold magenta]")
    
    def _step_creative_thinking(self) -> None:
        """Step 10: Be creative and courageous."""
        console.print()
        console.print(Panel("STEP 10: BE CREATIVE AND COURAGEOUS", style="bold cyan", padding=(0, 1)))
        console.print("Take some time to think about new ideas or projects:")
        console.print(" • What new initiatives would you like to start?")
        console.print(" • Are there any bold moves you should make?")
        console.print(" • What would make the biggest positive difference in your life or work?")
        
        console.input("[bold magenta]Press Enter when you're done with your creative thinking...[/bold magenta]")
    
    def _complete_review(self) -> None:
        """Complete the review and save state."""
        console.print()
        console.print(Panel(
            "[bold white]FULL GTD REVIEW COMPLETED[/bold white]", 
            style="bold green",
            padding=(1, 2)
        ))
        console.print()
        
        console.print("[blue]→ Saving review state...[/blue]")
        self.review_state.save()
        console.print("[green]✓ Review state saved successfully![/green]")
        
        next_review = datetime.now() + timedelta(days=self.config.review_frequency_days)
        console.print(f"\nNext scheduled review: [bold]{next_review.strftime('%A, %B %d')}[/bold]")


# Configuration loading functions (kept as functions for backward compatibility)
def load_config(config_path: str = 'config.json') -> Dict:
    """
    Load and validate configuration from JSON file.
    
    Why: Maintains backward compatibility while providing validation
    Result: Returns parsed configuration or raises descriptive errors
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"{config_path} file not found")
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {str(e)}") from e
    
    if 'reviews' not in config or not config['reviews']:
        raise ValueError("Missing or empty 'reviews' key in config")
    
    return config


if __name__ == "__main__":
    # This is a refactored version - the CLI will be implemented separately
    console.print("[yellow]This is the refactored class-based version.[/yellow]")
    console.print("[yellow]The CLI interface will be implemented in the main script.[/yellow]")