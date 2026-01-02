"""Unit tests for the sentiment analyzer (English + Marathi)."""

from app.services.sentiment import analyze_sentiment


def test_positive_english():
    label, score = analyze_sentiment("The new road work is excellent and clean")
    assert label == "positive"
    assert score > 0


def test_negative_english():
    label, score = analyze_sentiment("terrible corruption and potholes everywhere")
    assert label == "negative"
    assert score < 0


def test_neutral_or_empty():
    assert analyze_sentiment("") == ("neutral", 0.0)


def test_marathi_positive():
    label, _ = analyze_sentiment("पाणीपुरवठा सुधारला, खूप चांगले काम")
    assert label == "positive"


def test_marathi_negative():
    label, _ = analyze_sentiment("भ्रष्टाचार वाढला, खूप वाईट परिस्थिती")
    assert label == "negative"
