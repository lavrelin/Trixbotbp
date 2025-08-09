from config import Config
import re
from typing import List, Tuple

class FilterService:
    """Service for filtering content"""
    
    def __init__(self):
        self.banned_domains = Config.BANNED_DOMAINS
        
    def contains_banned_link(self, text: str) -> bool:
        """Check if text contains banned links"""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Check for banned domains
        for domain in self.banned_domains:
            if domain in text_lower:
                return True
        
        # Check for URL patterns
        url_pattern = r'(?:(?:https?|ftp):\/\/)?(?:[\w-]+\.)+[a-z]{2,}'
        urls = re.findall(url_pattern, text_lower)
        
        if urls:
            # Check if any found URL is in banned list
            for url in urls:
                for domain in self.banned_domains:
                    if domain in url:
                        return True
        
        return False
    
    def extract_links(self, text: str) -> List[str]:
        """Extract all links from text"""
        if not text:
            return []
        
        # Pattern for URLs
        url_pattern = r'(?:(?:https?|ftp):\/\/)?(?:[\w-]+\.)+[a-z]{2,}(?:\/[^\s]*)?'
        urls = re.findall(url_pattern, text, re.IGNORECASE)
        
        # Pattern for Telegram usernames
        tg_pattern = r'@[a-zA-Z][a-zA-Z0-9_]{4,}'
        tg_usernames = re.findall(tg_pattern, text)
        
        return urls + tg_usernames
    
    def clean_text(self, text: str) -> str:
        """Clean text from unwanted content"""
        if not text:
            return ""
        
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def check_spam_patterns(self, text: str) -> Tuple[bool, str]:
        """
        Check for spam patterns
        Returns: (is_spam: bool, reason: str)
        """
        if not text:
            return False, ""
        
        text_lower = text.lower()
        
        # Common spam patterns
        spam_patterns = [
            (r'(?:earn|make)\s+\$?\d+\s*(?:daily|weekly|monthly)', "Financial spam"),
            (r'(?:click|visit)\s+(?:here|this|link)', "Clickbait spam"),
            (r'(?:100%|guaranteed)\s+(?:free|profit|income)', "Guarantee spam"),
            (r'(?:whatsapp|telegram|viber)\s*:\s*\+?\d{10,}', "Contact spam"),
            (r'(?:crypto|bitcoin|forex)\s+(?:signals|trading|investment)', "Crypto spam")
        ]
        
        for pattern, reason in spam_patterns:
            if re.search(pattern, text_lower):
                return True, reason
        
        # Check for excessive caps
        if len(text) > 20:
            caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
            if caps_ratio > 0.7:
                return True, "Excessive capital letters"
        
        # Check for repeated characters
        if re.search(r'(.)\1{5,}', text):
            return True, "Repeated characters spam"
        
        return False, ""
    
    def is_valid_phone(self, phone: str) -> bool:
        """Validate phone number format"""
        # Remove spaces and dashes
        phone = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Check if it matches phone pattern
        pattern = r'^\+?\d{10,15}$'
        return bool(re.match(pattern, phone))
    
    def is_valid_username(self, username: str) -> bool:
        """Validate Telegram username"""
        pattern = r'^@?[a-zA-Z][a-zA-Z0-9_]{4,31}$'
        return bool(re.match(pattern, username))
    
    def sanitize_html(self, text: str) -> str:
        """Sanitize text for HTML display"""
        if not text:
            return ""
        
        # Escape HTML special characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#39;')
        
        return text
