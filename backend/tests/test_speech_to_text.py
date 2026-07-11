from services.speech_to_text import _parse_result


def test_salute_result_prefers_normalized_text():
    payload = {"result": [
        {"normalized_text": "нужно пять кубов", "text": "raw"},
        {"text": "бетона м300"},
    ]}

    assert _parse_result(payload) == "нужно пять кубов бетона м300"
