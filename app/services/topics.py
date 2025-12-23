"""
Topic Detection Service for SentimentPulse
Identifies key civic issues from post text in English and Marathi
"""

import re
from typing import Optional

from app.config import watchlist


# Default topic keywords (Marathi + English)
DEFAULT_TOPIC_KEYWORDS = {
    "EDUCATION": {
        "english": [
            "education", "school", "college", "university", "student", "students",
            "teacher", "teachers", "learning", "exam", "exams", "syllabus",
            "scholarship", "literacy", "academic", "classroom", "degree"
        ],
        "marathi": [
            "शिक्षण", "शाळा", "कॉलेज", "विद्यापीठ", "विद्यार्थी", "शिक्षक",
            "परीक्षा", "अभ्यासक्रम", "शिष्यवृत्ती", "साक्षरता", "वर्ग", "पदवी"
        ]
    },
    "JOBS": {
        "english": [
            "job", "jobs", "employment", "unemployment", "work", "worker", "workers",
            "salary", "wage", "wages", "hiring", "recruit", "career", "layoff",
            "rojgar", "naukri", "berojgari"
        ],
        "marathi": [
            "नोकरी", "रोजगार", "बेरोजगारी", "कामगार", "पगार", "वेतन",
            "भरती", "कारकून", "चाकरी", "उद्योग"
        ]
    },
    "WATER": {
        "english": [
            "water", "drinking water", "supply", "tanker", "pipeline", "dam",
            "drought", "shortage", "pani", "paani"
        ],
        "marathi": [
            "पाणी", "पाणीपुरवठा", "टँकर", "जलवाहिनी", "धरण", "दुष्काळ",
            "पाणीटंचाई", "विहीर", "बोअरवेल", "नळ"
        ]
    },
    "INFRASTRUCTURE": {
        "english": [
            "road", "roads", "pothole", "potholes", "traffic", "metro", "bridge",
            "flyover", "highway", "construction", "footpath", "drainage", "sewer",
            "building", "infrastructure", "railway", "station"
        ],
        "marathi": [
            "रस्ता", "रस्ते", "खड्डे", "खड्डा", "वाहतूक", "वाहतूककोंडी",
            "मेट्रो", "पूल", "उड्डाणपूल", "महामार्ग", "बांधकाम", "पदपथ",
            "गटार", "इमारत", "रेल्वे", "स्टेशन"
        ]
    },
    "CORRUPTION": {
        "english": [
            "corrupt", "corruption", "scam", "bribe", "bribery", "fraud",
            "embezzle", "kickback", "nepotism", "crony", "rigged", "laundering"
        ],
        "marathi": [
            "भ्रष्टाचार", "भ्रष्ट", "घोटाळा", "लाच", "लाचखोरी", "गैरव्यवहार",
            "फसवणूक", "वशिलेबाजी", "नातेवाईकशाहि", "काळा पैसा"
        ]
    },
    "HEALTHCARE": {
        "english": [
            "hospital", "health", "healthcare", "doctor", "doctors", "medicine",
            "medical", "patient", "clinic", "pharmacy", "treatment", "disease",
            "vaccine", "ambulance"
        ],
        "marathi": [
            "रुग्णालय", "आरोग्य", "डॉक्टर", "औषध", "रुग्ण", "दवाखाना",
            "उपचार", "रोग", "लस", "रुग्णवाहिका", "वैद्यकीय"
        ]
    },
    "HOUSING": {
        "english": [
            "housing", "house", "home", "slum", "slums", "redevelopment",
            "flat", "apartment", "rent", "homeless", "eviction", "rehabilitation",
            "chawl", "builders"
        ],
        "marathi": [
            "घर", "घरे", "झोपडपट्टी", "पुनर्विकास", "फ्लॅट", "भाडे",
            "बेघर", "पुनर्वसन", "चाळ", "बिल्डर", "इमारत"
        ]
    },
    "ELECTRICITY": {
        "english": [
            "electricity", "power", "power cut", "load shedding", "bill",
            "current", "voltage", "transformer", "meter", "bijli"
        ],
        "marathi": [
            "वीज", "विद्युत", "लोडशेडिंग", "बिल", "ट्रान्सफॉर्मर",
            "मीटर", "वीजपुरवठा", "वीजबिल"
        ]
    },
    "SAFETY": {
        "english": [
            "safety", "crime", "police", "security", "theft", "murder",
            "assault", "harassment", "women safety", "cctv"
        ],
        "marathi": [
            "सुरक्षा", "गुन्हा", "गुन्हेगारी", "पोलीस", "चोरी", "खून",
            "मारहाण", "छेडछाड", "महिला सुरक्षा", "सीसीटीव्ही"
        ]
    },
    "ENVIRONMENT": {
        "english": [
            "environment", "pollution", "air quality", "garbage", "waste",
            "cleanliness", "green", "tree", "trees", "climate", "swachh"
        ],
        "marathi": [
            "पर्यावरण", "प्रदूषण", "हवा", "कचरा", "स्वच्छता",
            "हरित", "झाड", "झाडे", "वातावरण"
        ]
    }
}


class TopicDetector:
    """
    Detect civic-issue topics from post text
    Supports both English and Marathi keywords
    """
    
    def __init__(self):
        # Load topics from config or use defaults
        self.topics = self._load_topics()
        # Compile regex patterns for efficient matching
        self.patterns = self._compile_patterns()
    
    def _load_topics(self) -> dict:
        """Load topics from config, merge with defaults"""
        config_topics = watchlist.topics
        
        # If config has topics, convert to same format as defaults
        topics = {}
        for topic_name, keywords in config_topics.items():
            if isinstance(keywords, list):
                # Config format: simple list of keywords
                topics[topic_name] = {
                    "english": [k for k in keywords if not self._is_marathi(k)],
                    "marathi": [k for k in keywords if self._is_marathi(k)]
                }
        
        # Merge with defaults (defaults take precedence for structure)
        for topic_name, topic_data in DEFAULT_TOPIC_KEYWORDS.items():
            if topic_name not in topics:
                topics[topic_name] = topic_data
            else:
                # Extend with default keywords
                topics[topic_name]["english"].extend(topic_data["english"])
                topics[topic_name]["marathi"].extend(topic_data["marathi"])
                # Remove duplicates
                topics[topic_name]["english"] = list(set(topics[topic_name]["english"]))
                topics[topic_name]["marathi"] = list(set(topics[topic_name]["marathi"]))
        
        return topics
    
    def _is_marathi(self, text: str) -> bool:
        """Check if text contains Marathi (Devanagari) characters"""
        return bool(re.search(r'[\u0900-\u097F]', text))
    
    def _compile_patterns(self) -> dict:
        """Compile regex patterns for each topic"""
        patterns = {}
        for topic_name, topic_data in self.topics.items():
            all_keywords = topic_data.get("english", []) + topic_data.get("marathi", [])
            if all_keywords:
                # Create pattern that matches whole words
                # For Marathi, we don't use word boundaries as they don't work well
                english_pattern = r'\b(' + '|'.join(
                    re.escape(k.lower()) for k in topic_data.get("english", [])
                ) + r')\b' if topic_data.get("english") else None
                
                marathi_pattern = r'(' + '|'.join(
                    re.escape(k) for k in topic_data.get("marathi", [])
                ) + r')' if topic_data.get("marathi") else None
                
                patterns[topic_name] = {
                    "english": re.compile(english_pattern, re.IGNORECASE) if english_pattern else None,
                    "marathi": re.compile(marathi_pattern) if marathi_pattern else None
                }
        
        return patterns
    
    def detect(self, text: str) -> Optional[str]:
        """
        Detect the primary topic in the given text
        
        Args:
            text: Tweet text in English or Marathi
            
        Returns:
            Topic name (e.g., 'EDUCATION', 'JOBS') or None if no topic detected
        """
        if not text:
            return None
        
        text_lower = text.lower()
        topic_scores = {}
        
        for topic_name, patterns in self.patterns.items():
            score = 0
            
            # Check English pattern
            if patterns.get("english"):
                matches = patterns["english"].findall(text_lower)
                score += len(matches)
            
            # Check Marathi pattern
            if patterns.get("marathi"):
                matches = patterns["marathi"].findall(text)
                score += len(matches) * 1.2  # Slight boost for Marathi matches
            
            if score > 0:
                topic_scores[topic_name] = score
        
        if not topic_scores:
            return None
        
        # Return topic with highest score
        return max(topic_scores, key=topic_scores.get)
    
    def detect_all(self, text: str) -> list[tuple[str, int]]:
        """
        Detect all topics in text with their match counts
        
        Returns:
            List of (topic_name, match_count) tuples, sorted by count descending
        """
        if not text:
            return []
        
        text_lower = text.lower()
        topic_scores = []
        
        for topic_name, patterns in self.patterns.items():
            score = 0
            
            if patterns.get("english"):
                matches = patterns["english"].findall(text_lower)
                score += len(matches)
            
            if patterns.get("marathi"):
                matches = patterns["marathi"].findall(text)
                score += len(matches)
            
            if score > 0:
                topic_scores.append((topic_name, score))
        
        return sorted(topic_scores, key=lambda x: x[1], reverse=True)


# Global instance
_detector = TopicDetector()


def detect_topic(text: str) -> Optional[str]:
    """
    Detect primary topic in text
    
    Args:
        text: Input text (English or Marathi)
        
    Returns:
        Topic name or None
    """
    return _detector.detect(text)


def detect_all_topics(text: str) -> list[tuple[str, int]]:
    """
    Detect all topics with scores
    
    Returns:
        List of (topic_name, score) tuples
    """
    return _detector.detect_all(text)
