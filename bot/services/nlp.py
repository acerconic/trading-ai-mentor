import spacy
import logging
import os
from thefuzz import process
from utils.constants import TRADING_FACTS

logger = logging.getLogger(__name__)

# Load spacy model. On first run it downloads automatically.
_nlp = None

def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("ru_core_news_sm")
            logger.info("spaCy model loaded successfully.")
        except OSError:
            logger.info("spaCy model not found. Downloading ru_core_news_sm...")
            os.system("python -m spacy download ru_core_news_sm")
            try:
                _nlp = spacy.load("ru_core_news_sm")
            except Exception as e:
                logger.error(f"Failed to load spaCy model after download: {e}")
                _nlp = None
    return _nlp


class NLPService:
    @staticmethod
    def get_best_trading_fact(query: str, lang: str = "ru") -> str:
        """
        Uses spaCy to extract key nouns from the user query,
        then fuzzy-matches them against the local TRADING_FACTS knowledge base.
        """
        nlp = get_nlp()
        search_query = query  # fallback if spaCy fails

        if nlp:
            try:
                doc = nlp(query.lower())
                # Extract meaningful tokens (nouns, proper nouns, verbs, adjectives)
                keywords = " ".join([
                    token.text for token in doc
                    if token.pos_ in ("NOUN", "PROPN", "VERB", "ADJ") and not token.is_stop
                ])
                if keywords.strip():
                    search_query = keywords
            except Exception as e:
                logger.warning(f"spaCy processing failed, using raw query: {e}")

        facts = TRADING_FACTS.get(lang, TRADING_FACTS["ru"])

        if not facts:
            return "💡 База знаний пуста. Обратитесь к администратору."

        try:
            best_match, score = process.extractOne(search_query, facts)
            logger.info(f"NLP query: '{search_query}' → score: {score}")

            if score >= 45:
                return best_match
        except Exception as e:
            logger.error(f"Fuzzy matching failed: {e}")

        # Fallback response
        if lang == "uz":
            return "💡 Кечирасиз, ушбу саволга базада аниқ жавоб топилмади. Саволингизни бошқача тарзда беринг."
        return "💡 Точного ответа в базе знаний не найдено. Попробуйте переформулировать вопрос или задайте более конкретный термин."


nlp_service = NLPService()
