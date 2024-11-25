import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from dataclasses import dataclass
import datetime
import re
from sqlalchemy.orm import Session
from .models import OriginalWork, Part, ContentPiece
from .segment import segment

@dataclass
class Post:
    """Represents a single post in a Glowfic story"""
    character: Optional[str]
    screenname: Optional[str]
    author: Optional[str]
    content: str

    def __str__(self) -> str:
        """Pretty string representation of the post"""
        return (
            f"Post by {self.character or 'Unknown Character'}\n"
            f"Screen name: {self.screenname or 'N/A'}\n"
            f"Author: {self.author or 'Unknown'}\n"
            f"\nContent:\n{self.content}\n"
        )

@dataclass
class Glowfic:
    """Represents a Glowfic story"""
    posts: List[Post]
    scraped_at: datetime.datetime

    def characters(self) -> set[Optional[str]]:
        """Returns a set of all characters in the story"""
        return set(post.character for post in self.posts)


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
    return ''.join(filter(None, (_process_content_node(child) for child in node.children)))

def scrape_post(post_id: int, db: Session) -> Glowfic:
    """
    Scrapes a Glowfic post and returns a list of all replies with their metadata.

    Args:
        post_id: The ID of the post to scrape

    Returns:
        List of Post objects containing character, screenname, author, and content for each reply
    """
    url = f"https://glowfic.com/posts/{post_id}?view=flat"
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    # create original work
    original_work = OriginalWork(url=url)
    db.add(original_work)

    results = []
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

            post_icon = info_box.find('div', class_='post-icon')
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

            # Extract content and preserve formatting
            content_div = post.find('div', class_='post-content')
            content = _process_content_node(content_div).strip()
            # Remove any multiple consecutive newlines (more than 2)
            content = re.sub(r'\n{3,}', '\n\n', content)

            results.append(Post(
                character=character,
                screenname=screenname,
                author=author,
                content=content
            ))
        except Exception as e:
            print(f"Error scraping post: {e}")
            print(f"Post HTML: {post}")
            raise

    db.commit()
    return Glowfic(posts=results, scraped_at=datetime.datetime.now())

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


            post_icon = info_box.find('div', class_='post-icon')
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
            for line in by_lines:
                if line:
                    for seg in segment(line):
                        db.add(ContentPiece(part=part, text=seg, should_voice=True))
                # add an unvoiced newline after
                db.add(ContentPiece(part=part, text='\n', should_voice=False))

        except Exception as e:
            print(f"Error scraping post: {e}")
            print(f"Post HTML: {post}")
            raise
    db.commit()
    return original_work


