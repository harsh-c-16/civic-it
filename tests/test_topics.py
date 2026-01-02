"""Unit tests for civic-issue topic detection."""

from app.services.topics import detect_topic


def test_water_english():
    assert detect_topic("water supply tanker shortage in the area") == "WATER"


def test_infrastructure_english():
    assert detect_topic("potholes on the road causing traffic") == "INFRASTRUCTURE"


def test_corruption_marathi():
    assert detect_topic("महापालिकेत भ्रष्टाचाराचा घोटाळा") == "CORRUPTION"


def test_no_topic():
    assert detect_topic("just a normal sentence about nothing specific") is None
