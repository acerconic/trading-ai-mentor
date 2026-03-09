import spacy
from thefuzz import process
import logging
from bot.utils.constants import TRADING_FACTS
import os

logger = logging.getLogger(__name__)

# Try to load, if fails, download silently
try:
    nlp = spacy.load("ru_core_news_sm")
except OSError:
    logger.info("Downloading spacy model...")
    os.system("python -m spacy download ru_core_news_sm")
    nlp = spacy.load("ru_core_news_sm")

class NLPService:
    @staticmethod
    def get_best_trading_fact(query: str, lang: str = "ru") -> str:
        # Use spaCy to extract nouns (keywords) to remove stopwords like "Что такое", "Объясни"
        # Since spacy parser might be too heavy for some basic words, we process query directly
        doc = nlp(query.lower())
        keywords = " ".join([token.text for token in doc if token.pos_ in ("NOUN", "PROPN", "VERB", "ADJ")])
        search_query = keywords if keywords.strip() else query
        
        facts = TRADING_FACTS.get(lang, TRADING_FACTS["ru"])
        
        # Fuzzy match keywords against facts
        best_match, score = process.extractOne(search_query, facts)
        
        # If the score is decent, we return the fact
        if score > 50:
            return best_match
        else:
            if lang == "uz":
                return "💡 Кечирасиз, ушбу саволга базада аниқ жавоб топилмади."
            return "💡 Извините, я не нашел точного правила в базе знаний по вашему вопросу."

nlp_service = NLPService()
