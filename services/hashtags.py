from typing import List, Optional

class HashtagService:
    """Service for generating hashtags"""
    
    def generate_hashtags(self, category: str, subcategory: Optional[str] = None) -> List[str]:
        """Generate hashtags based on category and subcategory"""
        hashtags = []
        
        # Category hashtags
        category_tags = {
            "🗯️ Будапешт": "#Будапешт",
            "🕵️ Поиск": "#Поиск",
            "📃 Предложения": "#Предложения",
            "⭐️ Пиар": "#Пиар"
        }
        
        # Subcategory hashtags
        subcategory_tags = {
            "🗣️ Объявления": "#Объявления",
            "📺 Новости": "#Новости",
            "🤐 Подслушано": "#Подслушано",
            "🤮 Жалобы": "#Жалобы",
            "👷‍♀️ Работа": "#Работа",
            "🏠 Аренда": "#Аренда",
            "🔻 Куплю": "#Куплю",
            "🔺 Продам": "#Продам",
            "🎉 События": "#События",
            "📦 Отдам даром": "#ОтдамДаром",
            "🌪️ Важно": "#Важно",
            "❔ Другое": "#Другое"
        }
        
        # Add category hashtag
        if category in category_tags:
            hashtags.append(category_tags[category])
        
        # Add subcategory hashtag
        if subcategory:
            # For nested subcategories
            if subcategory in subcategory_tags:
                hashtags.append(subcategory_tags[subcategory])
            # Check if it's an announcement subcategory
            elif subcategory in ["👷‍♀️ Работа", "🏠 Аренда", "🔻 Куплю", "🔺 Продам", 
                                "🎉 События", "📦 Отдам даром", "🌪️ Важно", "❔ Другое"]:
                hashtags.append("#Объявления")
                if subcategory in subcategory_tags:
                    hashtags.append(subcategory_tags[subcategory])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_hashtags = []
        for tag in hashtags:
            if tag not in seen:
                seen.add(tag)
                unique_hashtags.append(tag)
        
        return unique_hashtags
    
    def format_hashtags(self, hashtags: List[str]) -> str:
        """Format hashtags for display"""
        return " ".join(hashtags)
    
    def parse_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text"""
        import re
        pattern = r'#\w+'
        return re.findall(pattern, text)
