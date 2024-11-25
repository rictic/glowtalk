import json
from glowtalk import glowfic_scraper, speak, audiobook, database

def main():
    db = database.init_db()


    # speaker = speak.Speaker()
    # fic = glowfic_scraper.scrape_post(6782)
    # readers = {
    #   "Axis": speak.Reader.from_name("Norm"),
    #   "Judge of the Spire": speak.Reader.from_name("Yinghao"),
    #   "Heaven": speak.Reader.from_name("Becca"),
    #   "Nirvana": speak.Reader.from_name("Alice"),
    #   "Department of Human Resource Acquisition": speak.Reader.from_name("Gavin"),
    #   "Elysium": speak.Reader.from_name("Judith"),
    # }
    # default_reader = readers["Elysium"]
    # book = audiobook.Audiobook(glowfic=fic, default_reader=default_reader, character_readers=readers)
    # for post in fic.posts[4:5]:
    #     reader = book.get_reader_for_post(post)
    #     spoken_text = f"{post.character}, {post.screenname}: {post.content}"
    #     filename = speaker.speak(spoken_text, reader)
    #     print(f"Generated {filename}")

if __name__ == "__main__":
    main()
