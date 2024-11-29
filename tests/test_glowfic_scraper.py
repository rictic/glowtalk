import pytest
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from glowtalk.models import Base, ContentPiece
from glowtalk.glowfic_scraper import create_from_glowfic

@pytest.fixture
def db_session():
    """Create an in-memory database session for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def mock_glowfic_html():
    """Create a mock Glowfic HTML page"""
    return """
    <div class="content-header">
        <span id="post-title">Title of work number 1</span>
    </div>
    <div class="post-container">
        <div class="post-post">
            <div class="post-info-text">
                <div class="post-character">Alice</div>
                <div class="post-icon">
                    <img class="icon" src="http://example.com/icon.jpg" title="Happy">
                </div>
                <div class="post-screenname">AliceScreen</div>
                <div class="post-author">AuthorOne</div>
            </div>
            <div class="post-content">
                <p>Hello there! <em>This</em> is the first post.</p>
                <p>This is a second paragraph.</p>
            </div>
        </div>
        <div class="post-reply">
            <div class="post-info-text">
                <div class="post-character">Bob</div>
                <div class="post-screenname">BobScreen</div>
                <div class="post-author">AuthorTwo</div>
            </div>
            <div class="post-content">
                <p>Hi Alice! This is a reply.</p>
                <p>With <em>formatted</em> text.</p>
            </div>
        </div>
    </div>
    """

def test_create_from_glowfic(db_session: Session, mock_glowfic_html: str):
    # Create BeautifulSoup object from mock HTML
    soup = BeautifulSoup(mock_glowfic_html, 'html.parser')

    # Test URL
    test_url = "https://glowfic.com/posts/12345"

    # Create work from mock data
    work = create_from_glowfic(test_url, db_session, soup)

    # Verify the work was created
    assert work.url == test_url
    assert work.title == "Title of work number 1"

    # Verify parts were created
    assert len(work.parts) == 2

    # Check first part
    first_part = work.parts[0]
    assert first_part.character == "Alice"
    assert first_part.screenname == "AliceScreen"
    assert first_part.author == "AuthorOne"
    assert first_part.icon_url == "http://example.com/icon.jpg"
    assert first_part.icon_title == "Happy"

    # Check second part
    second_part = work.parts[1]
    assert second_part.character == "Bob"
    assert second_part.screenname == "BobScreen"
    assert second_part.author == "AuthorTwo"

    # Verify content pieces were created
    first_content = first_part.content_pieces
    assert len(first_content) > 0
    voiced_first_texts = [cp.text for cp in first_content if cp.should_voice]
    assert voiced_first_texts == [
        "Alice (AliceScreen) (by AuthorOne):",
        "Hello there!",
        "This is the first post.",
        "This is a second paragraph."
    ]


    second_content = second_part.content_pieces
    assert len(second_content) > 0
    voiced_second_texts = [cp.text for cp in second_content if cp.should_voice]
    assert voiced_second_texts == [
        "Bob (BobScreen) (by AuthorTwo):",
        "Hi Alice!",
        "This is a reply.",
        "With formatted text."
    ]

    # we should have eight content pieces that should be voiced
    assert ContentPiece.get_unvoiced(db_session).count() == 8
