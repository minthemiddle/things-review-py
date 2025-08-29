#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pytest",
#     "pytest-mock",
# ]
# ///

"""
Comprehensive tests for review.py to ensure functionality is preserved during refactoring.

These tests validate:
- Configuration loading and validation
- Review state management 
- Project processing and sorting
- Things API integration
- Command line argument parsing
- Error handling scenarios

Why these tests? To provide safety net during refactoring - ensuring no functionality is lost
when modernizing the codebase structure.
"""

import pytest
import json
import os
import tempfile
import sys
from datetime import datetime
from unittest.mock import patch, mock_open, MagicMock

# Mock the things module before importing review
sys.modules['things'] = MagicMock()

from review import (
    load_review_state, save_review_state, load_config, parse_args,
    fetch_areas, process_projects, generate_review_payload,
    ConfigError, MissingConfigError, InvalidConfigError, 
    AreaNotFoundError, ThingsAPIError
)


class TestReviewStateManagement:
    """Test review state loading and saving functionality."""
    
    def test_load_review_state_file_not_exists(self):
        """What: Test loading state when file doesn't exist
        Result: Should return empty dict without error"""
        with tempfile.TemporaryDirectory() as tmpdir:
            non_existent_file = os.path.join(tmpdir, "nonexistent.json")
            result = load_review_state(non_existent_file)
            assert result == {}
    
    def test_load_review_state_valid_file(self):
        """What: Test loading valid state file
        Result: Should return parsed JSON content"""
        test_state = {"uuid1": "2024-01-01T10:00:00", "uuid2": "2024-01-02T11:00:00"}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_state, f)
            f.flush()
            result = load_review_state(f.name)
            assert result == test_state
            os.unlink(f.name)
    
    def test_load_review_state_invalid_json(self):
        """What: Test loading corrupted JSON file
        Result: Should return empty dict, not crash"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content {")
            f.flush()
            result = load_review_state(f.name)
            assert result == {}
            os.unlink(f.name)
    
    def test_save_review_state(self):
        """What: Test saving state to file
        Result: Should write JSON correctly and be readable"""
        test_state = {"uuid1": "2024-01-01T10:00:00"}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            save_review_state(test_state, f.name)
            # Verify it was saved correctly
            with open(f.name, 'r') as read_f:
                loaded = json.load(read_f)
                assert loaded == test_state
            os.unlink(f.name)


class TestConfigurationManagement:
    """Test configuration loading and validation."""
    
    def test_load_config_file_not_exists(self):
        """What: Test loading non-existent config file
        Result: Should raise MissingConfigError"""
        with pytest.raises(MissingConfigError):
            load_config("nonexistent.json")
    
    def test_load_config_invalid_json(self):
        """What: Test loading corrupted JSON config
        Result: Should raise InvalidConfigError"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json {")
            f.flush()
            with pytest.raises(InvalidConfigError):
                load_config(f.name)
            os.unlink(f.name)
    
    def test_load_config_missing_reviews_key(self):
        """What: Test config without required 'reviews' key
        Result: Should raise InvalidConfigError"""
        invalid_config = {"other_key": "value"}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_config, f)
            f.flush()
            with pytest.raises(InvalidConfigError):
                load_config(f.name)
            os.unlink(f.name)
    
    def test_load_config_valid(self):
        """What: Test loading valid configuration
        Result: Should return parsed config dict"""
        valid_config = {
            "reviews": {
                "work": {
                    "search_tag": "work",
                    "save_area": "work-area-id"
                }
            }
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_config, f)
            f.flush()
            result = load_config(f.name)
            assert result == valid_config
            os.unlink(f.name)


class TestProjectProcessing:
    """Test project processing and sorting logic."""
    
    def test_process_projects_empty_areas(self):
        """What: Test processing when no areas provided
        Result: Should return empty list"""
        result = process_projects([], None, {})
        assert result == []
    
    def test_process_projects_sorting_by_last_reviewed(self):
        """What: Test that projects are sorted by last reviewed date
        Result: Oldest reviews should come first"""
        areas = [{
            'items': [
                {'title': 'Project A', 'uuid': 'uuid-a', 'deadline': None},
                {'title': 'Project B', 'uuid': 'uuid-b', 'deadline': None}
            ]
        }]
        
        # Project B was reviewed more recently than Project A
        review_state = {
            'uuid-a': '2024-01-01T10:00:00',
            'uuid-b': '2024-01-02T10:00:00'
        }
        
        result = process_projects(areas, None, review_state)
        
        # Project A should come first (older review)
        assert result[0]['title'] == 'Project A'
        assert result[1]['title'] == 'Project B'
    
    def test_process_projects_with_limit(self):
        """What: Test limiting number of projects returned
        Result: Should return only specified number of projects"""
        areas = [{
            'items': [
                {'title': f'Project {i}', 'uuid': f'uuid-{i}', 'deadline': None}
                for i in range(5)
            ]
        }]
        
        result = process_projects(areas, 2, {})
        assert len(result) == 2
    
    def test_process_projects_never_reviewed_comes_first(self):
        """What: Test that never-reviewed projects come before reviewed ones
        Result: Projects without review state should be prioritized"""
        areas = [{
            'items': [
                {'title': 'Reviewed Project', 'uuid': 'reviewed-uuid', 'deadline': None},
                {'title': 'Never Reviewed', 'uuid': 'never-uuid', 'deadline': None}
            ]
        }]
        
        review_state = {'reviewed-uuid': '2024-01-01T10:00:00'}
        
        result = process_projects(areas, None, review_state)
        assert result[0]['title'] == 'Never Reviewed'


class TestThingsAPIIntegration:
    """Test Things API related functionality."""
    
    @patch('review.things.areas')
    def test_fetch_areas_success(self, mock_areas):
        """What: Test successful area fetching from Things API
        Result: Should return areas list from API"""
        mock_areas.return_value = [{'id': 'area1', 'title': 'Work'}]
        
        result = fetch_areas('work')
        assert result == [{'id': 'area1', 'title': 'Work'}]
        mock_areas.assert_called_once_with(tag='work', include_items=True)
    
    @patch('review.things.areas')
    def test_fetch_areas_no_results(self, mock_areas):
        """What: Test when no areas found with given tag
        Result: Should raise ThingsAPIError"""
        mock_areas.return_value = []
        
        with pytest.raises(ThingsAPIError):
            fetch_areas('nonexistent')
    
    @patch('review.things.areas')
    def test_fetch_areas_api_error(self, mock_areas):
        """What: Test when Things API raises exception
        Result: Should wrap in ThingsAPIError"""
        mock_areas.side_effect = Exception("API Error")
        
        with pytest.raises(ThingsAPIError):
            fetch_areas('work')


class TestPayloadGeneration:
    """Test Things3 API payload generation."""
    
    def test_generate_review_payload_structure(self):
        """What: Test generated payload has correct structure
        Result: Should create valid Things3 API format"""
        projects = [
            {'title': 'Project 1', 'uuid': 'uuid-1'},
            {'title': 'Project 2', 'uuid': 'uuid-2'}
        ]
        
        result = generate_review_payload(projects, 'area-id', 'Review Title')
        
        assert len(result) == 1
        payload = result[0]
        
        assert payload['type'] == 'project'
        assert payload['attributes']['title'] == 'Review Title'
        assert payload['attributes']['area-id'] == 'area-id'
        assert len(payload['attributes']['items']) == 2
        
        # Check first item structure
        item = payload['attributes']['items'][0]
        assert item['type'] == 'to-do'
        assert item['attributes']['title'] == 'Project 1'
        assert 'uuid-1' in item['attributes']['notes']


class TestArgumentParsing:
    """Test command line argument parsing."""
    
    def test_parse_args_default_full(self):
        """What: Test default behavior when no args provided
        Result: Should default to 'full' area"""
        with patch('sys.argv', ['review.py']):
            args = parse_args(['work', 'personal'])
            assert args.area == 'full'
            assert args.number is None
            assert args.full is False
    
    def test_parse_args_specific_area(self):
        """What: Test parsing specific area argument
        Result: Should set area correctly"""
        with patch('sys.argv', ['review.py', 'work']):
            args = parse_args(['work', 'personal'])
            assert args.area == 'work'
    
    def test_parse_args_with_number_limit(self):
        """What: Test parsing number limit option
        Result: Should set number correctly"""
        with patch('sys.argv', ['review.py', '--number', '5']):
            args = parse_args(['work'])
            assert args.number == 5
    
    def test_parse_args_full_flag(self):
        """What: Test parsing full review flag
        Result: Should set full flag to True"""
        with patch('sys.argv', ['review.py', '--full']):
            args = parse_args(['work'])
            assert args.full is True


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_config_error_inheritance(self):
        """What: Test that config errors inherit correctly
        Result: All config errors should be catchable as ConfigError"""
        assert issubclass(MissingConfigError, ConfigError)
        assert issubclass(InvalidConfigError, ConfigError)
    
    def test_custom_exceptions_can_be_raised(self):
        """What: Test that custom exceptions work properly
        Result: Should be able to raise and catch custom exceptions"""
        with pytest.raises(AreaNotFoundError):
            raise AreaNotFoundError("Test error")
        
        with pytest.raises(ThingsAPIError):
            raise ThingsAPIError("Test API error")


if __name__ == "__main__":
    pytest.main([__file__])