import os
import time
import logging
from typing import Optional
from linkedin_api import Linkedin

logger = logging.getLogger(__name__)

class LinkedInClient:
    def __init__(self):
        self.client_id = os.getenv('LINKEDIN_CLIENT_ID')
        self.client_secret = os.getenv('LINKEDIN_CLIENT_SECRET')
        self.access_token = os.getenv('LINKEDIN_ACCESS_TOKEN')
        
        if not all([self.client_id, self.client_secret, self.access_token]):
            raise ValueError("Missing required LinkedIn credentials in environment variables (LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_ACCESS_TOKEN)")
        
        try:
            # Initialize the client with access token authentication
            self.client = Linkedin(access_token=self.access_token)
            logger.info("Successfully authenticated with LinkedIn")
        except Exception as e:
            logger.error(f"Failed to authenticate with LinkedIn: {str(e)}")
            raise
        
        self.last_request_time = 0
        self.min_request_interval = 2  # Minimum seconds between requests to avoid rate limiting

    def _rate_limit(self):
        """Implement basic rate limiting"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)
        self.last_request_time = time.time()

    def post_update(self, content: str, visibility: str = "PUBLIC") -> Optional[str]:
        """
        Post a text update to LinkedIn.
        
        Args:
            content: The content to post
            visibility: Post visibility ("PUBLIC", "CONNECTIONS")
        
        Returns:
            str: Post ID if successful, None if failed
        """
        try:
            self._rate_limit()
            # The new API uses author_urn which is automatically handled by the client
            response = self.client.post(content, visibility=visibility)
            post_id = response.get('id') if response else None
            if post_id:
                logger.info(f"Successfully posted update to LinkedIn. Post ID: {post_id}")
            return post_id
        except Exception as e:
            logger.error(f"Failed to post update to LinkedIn: {str(e)}")
            raise

    def validate_credentials(self) -> bool:
        """
        Validate that the credentials are working by making a test API call
        """
        try:
            self._rate_limit()
            # Get own profile as a test
            self.client.get_profile()
            return True
        except Exception as e:
            logger.error(f"LinkedIn credentials validation failed: {str(e)}")
            return False

def create_linkedin_client() -> LinkedInClient:
    """
    Factory function to create and validate a LinkedIn client
    """
    client = LinkedInClient()
    if not client.validate_credentials():
        raise ValueError("Failed to validate LinkedIn credentials")
    return client

def generate_post_content(topic: str) -> str:
    """
    Generate a post content based on a topic.
    
    Args:
        topic: The topic to create content about
        
    Returns:
        str: Generated post content
    """
    # Simple template for post generation
    # In a real application, you might want to use a more sophisticated
    # content generation approach, perhaps with an LLM API
    
    templates = [
        f"Just published a new article about #{topic}! Check out our latest insights and best practices.",
        f"Excited to share some thoughts on #{topic}. What's your experience with this?",
        f"New post alert: Everything you need to know about #{topic}. Follow for more updates!",
        f"#{topic} is changing the way we work. Here's what you need to know...",
        f"Trending now: #{topic} - Our team has put together some key insights you won't want to miss."
    ]
    
    import random
    content = random.choice(templates)
    
    # Add some hashtags
    hashtags = f"\n\n#professional #{topic.replace(' ', '')} #innovation #growth"
    
    return content + hashtags

def post_on_topic(topic: str, visibility: str = "PUBLIC") -> Optional[str]:
    """
    Generate and post content about a specific topic to LinkedIn.
    
    Args:
        topic: The topic to create and post content about
        visibility: Post visibility ("PUBLIC", "CONNECTIONS")
        
    Returns:
        str: Post ID if successful, None if failed
    """
    try:
        client = create_linkedin_client()
        content = generate_post_content(topic)
        logger.info(f"Generated post about '{topic}'")
        return client.post_update(content, visibility)
    except Exception as e:
        logger.error(f"Failed to generate and post content about '{topic}': {str(e)}")
        raise
