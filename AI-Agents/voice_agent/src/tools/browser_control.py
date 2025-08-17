"""
Browser control module for voice_crew.

This module provides functionality to:
1. Open Chrome browser on macOS
2. Format and execute Google searches
3. Process voice commands for search operations
"""

import webbrowser
import urllib.parse
import subprocess
import logging
import re
import time
from typing import Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Chrome browser path on macOS
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_PATH_ALTERNATIVE = "/Applications/Google Chrome.app"


def open_chrome() -> None:
    """
    Open Chrome browser on macOS.
    
    Returns:
        None
    
    Raises:
        RuntimeError: If Chrome cannot be opened
    """
    try:
        # Try to open Chrome using subprocess
        subprocess.Popen([CHROME_PATH, "--new-window"], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE)
        logger.info("Chrome browser opened successfully")
    except (FileNotFoundError, PermissionError) as e:
        # Fallback to webbrowser module if subprocess fails
        logger.warning(f"Failed to open Chrome using subprocess: {e}")
        try:
            # Register Chrome with webbrowser module
            webbrowser.register('chrome', None,
                               webbrowser.BackgroundBrowser(CHROME_PATH_ALTERNATIVE))
            webbrowser.get('chrome').open('about:blank')
            logger.info("Chrome browser opened via webbrowser module")
        except Exception as e:
            # Fallback to default browser if Chrome cannot be opened
            logger.error(f"Failed to open Chrome browser: {e}")
            webbrowser.open('about:blank')
            logger.info("Opened default browser instead")


def format_search_query(query: str) -> str:
    """
    Format the search query for Google search.
    
    Args:
        query (str): The raw search query
        
    Returns:
        str: URL-encoded search query
    """
    # Clean up the query by removing excess whitespace
    cleaned_query = ' '.join(query.split())
    
    # URL encode the query for safe browser handling
    encoded_query = urllib.parse.quote_plus(cleaned_query)
    
    return encoded_query


def perform_google_search(query: str) -> None:
    """
    Perform a Google search with the given query.
    
    Args:
        query (str): The search query
        
    Returns:
        None
        
    Raises:
        RuntimeError: If the search cannot be performed
    """
    try:
        # Format the query for search
        encoded_query = format_search_query(query)
        
        # Construct the Google search URL
        search_url = f"https://www.google.com/search?q={encoded_query}"
        
        logger.info(f"Performing Google search for: {query}")
        
        # Try to open Chrome and navigate to the search URL
        try:
            # First try to open Chrome
            open_chrome()
            time.sleep(1)  # Give Chrome time to open
            
            # Open the search URL using the webbrowser module
            webbrowser.get('chrome').open(search_url)
        except Exception as e:
            # Fallback to default browser if Chrome fails
            logger.warning(f"Failed to use Chrome for search: {e}")
            webbrowser.open(search_url)
            
        logger.info(f"Search executed successfully for: {query}")
        
    except Exception as e:
        error_msg = f"Failed to perform Google search: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


def detect_search_command(transcript: str) -> Tuple[bool, Optional[str]]:
    """
    Detect if the transcript contains a search command and extract the query.
    
    Args:
        transcript (str): The transcript text from voice recognition
        
    Returns:
        Tuple[bool, Optional[str]]: A tuple containing:
            - Boolean indicating if a search command was detected
            - The search query if a command was detected, otherwise None
    """
    # Convert transcript to lowercase for case-insensitive matching
    lower_transcript = transcript.lower().strip()
    
    # Check if the transcript starts with "search"
    if lower_transcript.startswith("search "):
        # Extract the query (everything after "search ")
        search_query = transcript[7:].strip()
        if search_query:
            logger.info(f"Search command detected with query: {search_query}")
            return True, search_query
    
    # No search command detected
    return False, None


def process_voice_command(transcript: str) -> bool:
    """
    Process a voice transcript to detect and execute search commands.
    
    Args:
        transcript (str): The transcript text from voice recognition
        
    Returns:
        bool: True if a command was processed, False otherwise
    """
    # Detect if this is a search command
    is_search, query = detect_search_command(transcript)
    
    if is_search and query:
        try:
            # Perform the search
            perform_google_search(query)
            return True
        except Exception as e:
            logger.error(f"Error processing search command: {e}")
            return False
    
    return False


if __name__ == "__main__":
    # Test the functionality with a sample search
    test_query = "Python programming tutorials"
    print(f"Testing with query: {test_query}")
    perform_google_search(test_query)

