import json
from sqlalchemy.orm import Session
from glowtalk import glowfic_scraper, database, models

def create_audiobook(db: Session) -> models.Audiobook:
    speaking_model = models.SpeakerModel.XTTS_v2
    original_work = glowfic_scraper.get_or_scrape_post(6782, db)
    judith = models.Speaker.get_or_create(db, name="Judith", model=speaking_model)
    audiobook = models.Audiobook(original_work=original_work, default_speaker=judith)
    db.add(audiobook)
    db.add(judith)
    db.commit()

    readers = {
      "Axis": "Norm",
      "Judge of the Spire": "Yinghao",
      "Heaven": "Becca",
      "Nirvana": "Alice",
      "Department of Human Resource Acquisition": "Gavin",
      "Elysium": "Judith",
    }
    for character, reader in readers.items():
        speaker = models.Speaker.get_or_create(db, name=reader, model=speaking_model)
        db.add(speaker)
        cv = models.CharacterVoice.get_or_create(db, audiobook=audiobook, character_name=character, speaker=speaker)
        db.add(cv)
    db.commit()
    return audiobook

def generate_audiobook(db: Session, audiobook: models.Audiobook):
    while True:
        unvoiced: models.ContentPiece = models.ContentPiece.get_unvoiced(db).first()
        if not unvoiced:
            break
        try:
            unvoiced.perform_for_audiobook(db, audiobook)
            db.commit()
        except Exception as e:
            db.rollback()
            raise ValueError(f"Error generating {unvoiced.id}: {e}") from e


def main():
    db = database.init_db()
    # query for the first audiobook in the database
    audiobook = db.query(models.Audiobook).first()
    if not audiobook:
        audiobook = create_audiobook(db)
    generate_audiobook(db, audiobook)

    # speaker = speak.Speaker()

    # default_reader = readers["Elysium"]
    # book = audiobook.Audiobook(glowfic=fic, default_reader=default_reader, character_readers=readers)
    # for post in fic.posts[4:5]:
    #     reader = book.get_reader_for_post(post)
    #     spoken_text = f"{post.character}, {post.screenname}: {post.content}"
    #     filename = speaker.speak(spoken_text, reader)
    #     print(f"Generated {filename}")

if __name__ == "__main__":
    main()
