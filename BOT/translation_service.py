import google.generativeai as genai
import logging
import threading

from gtts import gTTS
import os

from constants import VALID_LANGUAGE_CODES

logger = logging.getLogger(__name__)

class TranslationError(Exception):
    """Custom exception for translation-related errors."""
    pass

# --- Model Selection ---
MODEL_NAME = 'gemini-pro'  # Using 'gemini-pro' for stability
# --- End Model Selection ---

_model = None  # Model instance, private

def get_model():
    """Singleton pattern to get the Gemini model instance."""
    global _model
    if _model is None:
        try:
            _model = genai.GenerativeModel(MODEL_NAME)
        except Exception as e:
            raise TranslationError(f"Failed to initialize the Gemini model: {e}")
    return _model

# Thread-safe cache for translations
_translation_cache = {}  # type: dict[str, str]
_cache_lock = threading.Lock()

def translate_text(text: str, target_language: str, source_language: str = None) -> str:
    """
    Translates text from a source language to a target language using the Gemini API.

    Args:
        text: The text to translate.
        target_language: The target language code (e.g., 'en', 'de').
        source_language: The source language code (optional). If None, the API will attempt to detect it.

    Returns:
        The translated text.

    Raises:
        TranslationError: If the translation fails.
    """
    if not text:
        return ""

    # 1. Check if target_language is valid before anything else
    if target_language not in VALID_LANGUAGE_CODES:
        raise TranslationError(f"Invalid target language: {target_language}")

    # 2. Check the cache
    cache_key = f"{text}_{source_language}_{target_language}"
    with _cache_lock:
        if cache_key in _translation_cache:
            logger.debug("Translation from cache.") #Added Debug
            return _translation_cache[cache_key]

    try:
        model = get_model()

        if not source_language:
            prompt_detect = f"""
            Task: Detect the language of the following text.

            Instructions:
            1. Analyze the text thoroughly to identify the language used.
            2. Respond with the language code of the detected language.

            Text:
            "{text}"

            Language code:
            """
            response_detect = model.generate_content(prompt_detect)
            source_language = response_detect.text.strip()

        if source_language not in VALID_LANGUAGE_CODES:
            source_language = "the source language"  # Fallback

        prompt = f"""
        Task: Translate the following text from {source_language} to {target_language} with extreme precision and accuracy.

        Instructions:
        1. Analyze the text thoroughly to understand its full context, tone, and intent.
        2. Consider any cultural nuances, idioms, or specific terminology in the source text.
        3. Translate the text maintaining the original meaning, tone, and style as closely as possible.
        4. Ensure proper grammar, punctuation, and formatting in the target language.
        5. If there are multiple possible interpretations, choose the most appropriate one based on context.
        6. For any ambiguous terms or phrases, provide the most likely translation and include a brief explanation in parentheses if necessary.
        7. Double-check the translation for accuracy, paying special attention to:
           - Correct use of tenses
           - Proper noun translations (names, places, etc.)
           - Numerical values and units of measurement
           - Technical or specialized vocabulary
        8. Verify that no part of the original text has been omitted in the translation.
        9. Ensure that the translation reads naturally in the target language.
        10. If the text contains humor, wordplay, or cultural references, adapt them appropriately for the target language and culture.

        Original text:
        "{text}"

        Translated text (in {target_language}):
        """

        response = model.generate_content(prompt)
        translated_text = response.text.strip()

        # Verification Step
        verification_prompt = f"""
        Verify the accuracy of the following translation from {source_language} to {target_language}:

        Original: "{text}"
        Translation: "{translated_text}"

        Instructions:
        1. Check for any mistranslations or inaccuracies.
        2. Verify that the tone and style are preserved.
        3. Ensure all content from the original is included in the translation.
        4. Check for proper grammar and natural flow in the target language.

        If any issues are found, provide a corrected version. If no issues are found, respond with "Translation is accurate."

        Verification result:
        """

        verification_response = model.generate_content(verification_prompt)
        verification_result = verification_response.text.strip()

        if verification_result != "Translation is accurate.":
             translated_text = verification_result.split("\n")[-1]  # Get the last line of the response

        # 3. Store in the cache
        with _cache_lock:
            _translation_cache[cache_key] = translated_text
        return translated_text

    except Exception as e:
        logger.exception(f"Translation failed for text '{text}': {e}")  # Log the original text and the error
        raise TranslationError(f"Translation failed: {e}")  # Re-raise as TranslationError

def text_to_speech(text: str, lang: str) -> str | None:
    """
    Converts text to speech using the gTTS library.

    Args:
        text: The text to convert.
        lang: The language code (e.g., 'en', 'de').

    Returns:
        The path to the generated MP3 file, or None if an error occurred.
    """
    try:
        model = get_model()

        prompt_improve = f"""
        Task: Improve the text for text to speech.

        Instructions:
        1. Analyze the text thoroughly to understand its full context, tone, and intent.
        2. Correct any grammar issues to make the text perfect for a text to speech application.
        3. If the text contains humor, wordplay, or cultural references make sure that these are also present when reading it out loud.
        4. Remove all Anführungszeichen und sonderzeichen wie ! " # $ % & / ( ) = ? ~ etc. die eine korrekte Text zu Sprache ausgabe behindern.

        Text:
        "{text}"

        Improved Text:
        """
        response_improve = model.generate_content(prompt_improve)
        improved_text = response_improve.text.strip()

        characters_to_remove = ['"', "'", '!', '#', '$', '%', '&', '/', '(', ')', '=', '?', '~', '<', '>', ',', '.']
        for char in characters_to_remove:
            improved_text = improved_text.replace(char, '')

        tts = gTTS(text=improved_text, lang=lang)
        temp_file = "temp.mp3"
        tts.save(temp_file)
        return temp_file
    except Exception as e:
        logger.error(f"Error generating TTS: {e}")
        return None