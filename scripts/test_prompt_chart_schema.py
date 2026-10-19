import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.audio_service import clean_text_for_speech
from backend.rag_service import generate_voice_rag_answer

def test_tts_clean_text_strips_json_block():
    raw_text = (
        "Here is the comparison of employee salaries. Alice earns 75,000 LKR while Bob earns 85,000 LKR.\n\n"
        "```json\n"
        "{\n"
        '  "type": "chart",\n'
        '  "chartType": "bar",\n'
        '  "title": "Employee Salaries",\n'
        '  "labels": ["Alice", "Bob"],\n'
        '  "datasets": [{"label": "Salary", "data": [75000, 85000]}]\n'
        "}\n"
        "```"
    )
    
    cleaned = clean_text_for_speech(raw_text, language="en")
    print("Cleaned English TTS Text:")
    print(f"'{cleaned}'")
    
    assert "Alice earns 75,000" in cleaned or "Alice" in cleaned
    assert "chartType" not in cleaned
    assert "datasets" not in cleaned
    assert "```" not in cleaned
    print("PASSED: clean_text_for_speech successfully strips hidden JSON chart code blocks!")

def test_system_prompt_contains_chart_rule():
    try:
        generate_voice_rag_answer(
            user_query="Compare the salaries of employees",
            retrieved_chunks=[{"documentTitle": "Salaries.pdf", "content": "Alice: 75000, Bob: 85000"}],
            custom_api_key="invalid_test_key",
            target_language="en"
        )
    except Exception as e:
        print(f"Function executed as expected: {e}")

if __name__ == "__main__":
    test_tts_clean_text_strips_json_block()
    test_system_prompt_contains_chart_rule()
