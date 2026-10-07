from src.schema import DEFAULT_DB_PATH
from src.value_hints import value_hints


def test_value_hints_name_similar_stored_values() -> None:
    hints = value_hints("SELECT Name FROM Artist WHERE Name = 'ac/dc '", DEFAULT_DB_PATH)
    assert hints and "'AC/DC'" in hints[0]
    assert value_hints("SELECT Name FROM Artist WHERE Name = 'AC/DC'", DEFAULT_DB_PATH) == []  # stored: no hint
