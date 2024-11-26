import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from dataclasses import dataclass
import datetime
import re
from sqlalchemy.orm import Session
from .models import OriginalWork, Part, ContentPiece
from .segment import segment

def _process_content_node(node) -> str:
    # Handle different node types
    if isinstance(node, str):
        return node.strip()

    # Handle specific HTML tags
    if node.name == 'em':
        return ' '.join(filter(None, (_process_content_node(child) for child in node.children)))
    elif node.name == 'p':
        return '\n\n' + ' '.join(filter(None, (_process_content_node(child) for child in node.children)))
    elif node.name == 'br':
        return '\n'

    # For all other tags, just process their children
    return ' '.join(filter(None, (_process_content_node(child) for child in node.children)))

def get_or_scrape_post(post_id: int, db: Session) -> OriginalWork:
    url = f"https://glowfic.com/posts/{post_id}?view=flat"
    # get the original work with this url that has the most recent scrape date
    original_work = db.query(OriginalWork)\
        .filter(OriginalWork.url == url)\
        .order_by(OriginalWork.scrape_date.desc())\
        .first()
    if original_work:
        return original_work
    return scrape_post(post_id, db)

def scrape_post(post_id: int, db: Session) -> OriginalWork:
    """
    Scrapes a Glowfic post and returns a list of all replies with their metadata.

    Args:
        post_id: The ID of the post to scrape

    Returns:
        OriginalWork object
    """
    url = f"https://glowfic.com/posts/{post_id}?view=flat"
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    return create_from_glowfic(url, db, soup)

def create_from_glowfic(url: str, db: Session, soup: BeautifulSoup) -> OriginalWork:
    """Creates an original work from a Glowfic page"""
    original_work = OriginalWork(url=url)
    db.add(original_work)

    posts = soup.find_all('div', class_=['post-post', 'post-reply'])
    for post in posts:
        part = Part(original_work=original_work, position=len(original_work.parts))
        db.add(part)
        try:
            # Extract the post info
            info_box = post.find('div', class_='post-info-text')
            character = info_box.find('div', class_='post-character')
            if character:
                part.character = character.text.strip()


            post_icon = post.find('div', class_='post-icon')
            if post_icon:
                post_icon_img = post_icon.find('img', class_='icon')
                if post_icon_img:
                    part.icon_url = post_icon_img['src']
                    part.icon_title = post_icon_img['title']

            screenname = info_box.find('div', class_='post-screenname')
            if screenname:
                part.screenname = screenname.text.strip()


            author = info_box.find('div', class_='post-author')
            if author:
                part.author = author.text.strip()

            # Extract content, removing formatting
            content_div = post.find('div', class_='post-content')
            content = _process_content_node(content_div).strip()
            by_lines = content.split('\n')
            voiced_line_count = 0
            for line in by_lines:
                if line:
                    for seg in segment(line):
                        if seg == '':
                            continue
                        db.add(ContentPiece(part=part, text=seg, should_voice=True))
                        voiced_line_count += 1
                # add an unvoiced newline after
                db.add(ContentPiece(part=part, text='\n', should_voice=False))

            if voiced_line_count == 0:
                content = "(Audio note: this post is empty, perhaps as if to convey a silent look, or a pause)"
                db.add(ContentPiece(part=part, text=content, should_voice=True))

        except Exception as e:
            print(f"Error scraping post: {e}")
            print(f"Post HTML: {post}")
            raise
    db.commit()
    return original_work
