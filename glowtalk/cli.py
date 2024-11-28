import json
from sqlalchemy.orm import Session
from glowtalk import glowfic_scraper, database, models, idle
from pathlib import Path
import os
import time
import datetime
import sys
from collections import deque
import uuid
import uvicorn
from glowtalk.api import app
import threading


def initialize_reference_voices(db: Session):
    info = {
        "Alice": {
            "description": "Clear enunciation, feminine",
            "transcript": "He never informed them that the death had been imposed."
        },
        "Avery": {
            "description": "Slow, masculine, dramatic, slightly raspy",
            "transcript": "Milked cow, contains the fire"
        },
        "Becca": {
            "description": "Gentle, feminine",
            "transcript": "windows, the wooden shutters to close over them at"
        },
        "Gavin": {
            "description": "Masculine, deliberate, slightly nasal",
            "transcript": "Harry had taken one step toward it, when a slithering sound made him freeze where he stood."
        },
        "Judith": {
            "description": "Bright, warm, feminine. Usually American English.",
            "transcript": "The Hispaniola was rolling scuppers under in the ocean swell. The booms were tearing at the blocks, the rudder was banging to and fro, and the whole ship creaking, groaning, and jumping like a manufactory."
        },
        "Norm": {
            "description": "Masculine, midcentury official, American",
            "transcript": "Right after lunch, you go to the boss's garage and wait for me."
        },
        "Yinghao": {
            "description": "Masculine",
            "transcript": "So diff you have a lot of things in common, but none of 'em's going to work."
        }
    }
    for name, info in info.items():
        models.ReferenceVoice.get_or_create(
            db,
            audio_path=Path(os.getcwd()) / "references" / f"{name}.wav",
            description=info["description"],
            transcript=info["transcript"]
        )


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


class ProgressReporter:
    def __init__(self, outstream=sys.stdout, history_size=50):
        self.previous_measurements = deque(maxlen=history_size)
        self.outstream = outstream

    def report(self, num_remaining: int):
        self.previous_measurements.append((num_remaining, time.time()))
        if len(self.previous_measurements) > 2:
            rates = []
            for i in range(1, len(self.previous_measurements)):
                num_previous, time_previous = self.previous_measurements[i-1]
                num_current, time_current = self.previous_measurements[i]
                posts_processed = num_previous - num_current
                if posts_processed > 0:
                    seconds_per_post = (time_current - time_previous) / posts_processed
                    rates.append(seconds_per_post)

            if rates:
                average_seconds_per_post = sum(rates) / len(rates)
                seconds_remaining = num_remaining * average_seconds_per_post
                formatted_time = datetime.timedelta(seconds=seconds_remaining)
                print(f"{num_remaining} posts remaining, estimated time to completion: {formatted_time}",
                      file=self.outstream)
            else:
                print(f"{num_remaining} posts remaining", file=self.outstream)

def generate_audiobook(db: Session, audiobook: models.Audiobook):
    reporter = ProgressReporter()
    while True:
        reporter.report(models.ContentPiece.get_unvoiced(db).count())
        unvoiced: models.ContentPiece = models.ContentPiece.get_unvoiced(db).first()
        if not unvoiced:
            break
        try:
            unvoiced.perform_for_audiobook(db, audiobook)
            db.commit()
        except Exception as e:
            db.rollback()
            raise ValueError(f"Error generating {unvoiced.id}: {e}") from e

def generate_one_voiced_piece(db: Session, audiobook: models.Audiobook):
    unvoiced: models.ContentPiece = models.ContentPiece.get_unvoiced(db).first()
    if not unvoiced:
        # sleep for ten seconds, so this isn't a busy-wait
        time.sleep(60)
        return
    # Hm, this is wrong. It isn't a ContentPiece that's unvoiced exactly… it's
    # that an audiobook doesn't have a performance for that content piece.
    # TODO: think this through more.
    unvoiced.perform_for_audiobook(db, audiobook)
    db.commit()

def generate_audio_files_when_idle(db: Session, audiobook: models.Audiobook):
    progress_reporter = ProgressReporter()
    idle_checker = idle.create_idle_checker()
    idle_threshold_seconds = 30
    while True:
        while idle_checker.get_idle_time() > idle_threshold_seconds:
            generate_one_voiced_piece(db, audiobook)
            progress_reporter.report(models.ContentPiece.get_unvoiced(db).count())

        # Check if system becomes active
        print("System is active, not working...")
        while idle_checker.get_idle_time() < idle_threshold_seconds:
            time.sleep(10)

class Worker:
    def __init__(self, sessionmaker, verbose: bool = False, idle_threshold_seconds: int = 30):
        self.sessionmaker = sessionmaker
        # we want to store the worker id persistently on the user machine.
        # we use worker id mainly so that if a worker is misconfigured and
        # generates bad audio, we can later easily regenerate just the
        # performances it created.
        # so we want to store the worker id in a file in the user's home
        # directory or similar. note that this needs to work cross platform,
        # including on Windows.
        self.worker_id_path = Path.home() / ".glowtalk_worker_id"
        if not self.worker_id_path.exists():
            self.worker_id = str(uuid.uuid4())
            self.worker_id_path.write_text(self.worker_id)
        else:
            self.worker_id = self.worker_id_path.read_text()
        self.verbose = verbose
        self.idle_threshold_seconds = idle_threshold_seconds

    def work(self):
        idle_checker = idle.create_idle_checker()
        while True:
            while idle_checker.get_idle_time() > self.idle_threshold_seconds:
                start_time = time.time()
                self.work_one_item()
                if self.verbose:
                    print(f"Generated a voice performance in {time.time() - start_time} seconds")

            if self.verbose:
                print("System is being used by a person, waiting for it to become idle...")
            # Check if system becomes active
            while idle_checker.get_idle_time() < self.idle_threshold_seconds:
                time.sleep(self.idle_threshold_seconds)

    def work_one_item(self):
        with self.sessionmaker() as db:
            work_item = models.WorkQueue.assign_work_item(db, self.worker_id)
            if work_item is None:
                if self.verbose:
                    print("No work item assigned, waiting for one...")
                time.sleep(60)
                return

            content_piece: models.ContentPiece = work_item.content_piece
            if self.verbose:
                print(f"Performing the line {json.dumps(content_piece.text)}")
            performance = content_piece.perform_for_audiobook(db, work_item.audiobook)
            try:
                work_item.complete_work_item(db, self.worker_id, performance)
            except Exception as e:
                work_item.fail_work_item(db, self.worker_id, str(e))


def main():
    sessionmaker = database.init_db()
    with sessionmaker() as db:
        initialize_reference_voices(db)
        # query for the first audiobook in the database
        audiobook: models.Audiobook = db.query(models.Audiobook).first()
        if not audiobook:
            audiobook = create_audiobook(db)
            queued = audiobook.add_work_queue_items(db)
            print(f"Queued {queued} work queue items")

    # Start the worker in a background thread
    worker = Worker(sessionmaker, verbose=True, idle_threshold_seconds=5)
    worker_thread = threading.Thread(target=worker.work, daemon=True)
    worker_thread.start()

    # Run the FastAPI server
    print("Running GlowTalk at http://localhost:8585")
    uvicorn.run(app, host="0.0.0.0", port=8585)

if __name__ == "__main__":
    main()
