"""
Sentiment Analysis Service for SentimentPulse
Supports both English and Marathi text using VADER with Marathi lexicon enhancement
"""

import re
from typing import Literal, Tuple

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Marathi sentiment lexicon - positive and negative words
# This provides basic Marathi sentiment support when VADER alone isn't enough
MARATHI_POSITIVE_WORDS = {
    # General positive
    "चांगले", "छान", "उत्तम", "अप्रतिम", "सुंदर", "महान", "प्रगती", "यश",
    "विकास", "आनंद", "खुश", "समाधान", "धन्यवाद", "अभिनंदन", "शुभेच्छा",
    "स्वागत", "प्रशंसा", "उद्धार", "सुधारणा", "वाढ", "जिंकला", "जय",
    "फायदा", "लाभ", "जबरदस्त", "भारी", "मस्त", "झकास", "एकदम",
    # Governance / civic specific
    "विश्वास", "नेतृत्व", "कार्य", "सेवा", "समर्पण", "प्रामाणिक", "पारदर्शक",
    "जनता", "विकासकामे", "प्रगतीशील", "कार्यकर्ता", "जनहित", "लोकप्रिय",
    # Achievements
    "उद्घाटन", "पूर्ण", "यशस्वी", "साध्य", "कामगिरी", "पुरस्कार",
}

MARATHI_NEGATIVE_WORDS = {
    # General negative
    "वाईट", "खराब", "भ्रष्ट", "घोटाळा", "लबाड", "खोटे", "अपयश", "नुकसान",
    "समस्या", "त्रास", "अडचण", "गैरव्यवहार", "बेकायदेशीर", "अन्याय",
    "दुर्दैव", "निराशा", "राग", "चिंता", "भय", "हार", "पराभव",
    # Governance / civic specific
    "भ्रष्टाचार", "लाचखोर", "जुमलेबाज", "खोटे वचन", "धोकेबाज", "फसवणूक",
    "निष्क्रिय", "अपयशी", "निकामी", "बेरोजगारी", "महागाई", "दंगल",
    # Problems
    "खड्डे", "पाणीटंचाई", "वाहतूककोंडी", "प्रदूषण", "गरिबी", "भूकबळी",
    "आंदोलन", "मोर्चा", "बंद", "विरोध", "आरोप", "टीका",
}

MARATHI_INTENSIFIERS = {
    "खूप": 1.5, "अत्यंत": 1.8, "फार": 1.5, "अगदी": 1.3,
    "एकदम": 1.5, "पूर्णपणे": 1.8, "जास्त": 1.3, "सगळ्यात": 1.5,
}

MARATHI_NEGATIONS = {"नाही", "नको", "कधी नाही", "काहीच नाही", "नसते"}


class SentimentAnalyzer:
    """
    Hybrid sentiment analyzer supporting English and Marathi
    Uses VADER for English with custom Marathi lexicon enhancement
    """
    
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        # Add common English words used in Indian social media
        self.vader.lexicon.update({
            "development": 1.5,
            "progress": 1.5,
            "corrupt": -2.5,
            "scam": -2.5,
            "pothole": -1.5,
            "traffic": -1.0,
            "clean": 1.0,
            "smart": 1.5,
        })
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection based on character set"""
        # Devanagari Unicode range: \u0900-\u097F
        devanagari_chars = len(re.findall(r'[\u0900-\u097F]', text))
        latin_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if devanagari_chars > latin_chars:
            return "marathi"
        return "english"
    
    def _analyze_marathi(self, text: str) -> Tuple[str, float]:
        """Analyze Marathi text using custom lexicon"""
        words = re.findall(r'[\u0900-\u097F]+|[a-zA-Z]+', text)
        
        positive_score = 0.0
        negative_score = 0.0
        intensifier = 1.0
        
        for i, word in enumerate(words):
            # Check for intensifiers
            if word in MARATHI_INTENSIFIERS:
                intensifier = MARATHI_INTENSIFIERS[word]
                continue
            
            # Check for negations (affects next word)
            if word in MARATHI_NEGATIONS:
                intensifier *= -1
                continue
            
            # Score positive/negative words
            if word in MARATHI_POSITIVE_WORDS:
                positive_score += 1.0 * intensifier
            elif word in MARATHI_NEGATIVE_WORDS:
                negative_score += 1.0 * intensifier
            
            # Reset intensifier after use
            intensifier = 1.0
        
        # Calculate compound score (-1 to 1)
        total = positive_score + negative_score
        if total == 0:
            compound = 0.0
        else:
            compound = (positive_score - negative_score) / (positive_score + negative_score + 1)
        
        # Determine sentiment label
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        
        return label, compound
    
    def _analyze_english(self, text: str) -> Tuple[str, float]:
        """Analyze English text using VADER"""
        scores = self.vader.polarity_scores(text)
        compound = scores['compound']
        
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        
        return label, compound
    
    def analyze(self, text: str) -> Tuple[str, float]:
        """
        Analyze sentiment of text (auto-detects language)
        
        Args:
            text: Input text in English or Marathi
            
        Returns:
            Tuple of (sentiment_label, confidence_score)
            - sentiment_label: 'positive', 'neutral', or 'negative'
            - confidence_score: -1.0 to 1.0 (negative to positive)
        """
        if not text or not text.strip():
            return "neutral", 0.0
        
        language = self._detect_language(text)
        
        if language == "marathi":
            marathi_label, marathi_score = self._analyze_marathi(text)
            # Also run VADER on any English words present
            english_label, english_score = self._analyze_english(text)
            
            # Combine scores (weighted average, favor Marathi for Marathi text)
            combined_score = (marathi_score * 0.7) + (english_score * 0.3)
            
            if combined_score >= 0.05:
                return "positive", combined_score
            elif combined_score <= -0.05:
                return "negative", combined_score
            else:
                return "neutral", combined_score
        else:
            return self._analyze_english(text)


# Global instance
_analyzer = SentimentAnalyzer()


def analyze_sentiment(text: str) -> Tuple[Literal["positive", "neutral", "negative"], float]:
    """
    Analyze sentiment of text (English or Marathi)
    
    Args:
        text: Input text
        
    Returns:
        Tuple of (sentiment_label, confidence_score)
    """
    return _analyzer.analyze(text)
