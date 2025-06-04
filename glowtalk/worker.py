import json
import time
import uuid
from pathlib import Path
import tempfile
import requests
from glowtalk import models, speak, idle
import httpx

class Worker:
    def __init__(self, client: httpx.Client, verbose: bool = False, idle_threshold_seconds: int = 30,
                 worker_id: str | None = None, worker_id_dir: Path | None = None):
        self.client = client
        self.verbose = verbose
        self.idle_threshold_seconds = idle_threshold_seconds
        # one speaker per model
        self.speakers: dict[models.SpeakerModel, speak.Speaker] = dict()

        if worker_id:
            # Use provided worker ID (useful for tests)
            self.worker_id = worker_id
        else:
            # Try to get/create persistent worker ID
            if worker_id_dir is None:
                worker_id_dir = Path.home()

            self.worker_id_path = worker_id_dir / ".glowtalk_worker_id"
            try:
                if self.worker_id_path.exists():
                    self.worker_id = self.worker_id_path.read_text().strip()
                else:
                    self.worker_id = str(uuid.uuid4())
                    self.worker_id_path.write_text(self.worker_id)
            except (OSError, PermissionError):
                # Fallback to temporary worker ID if we can't write to filesystem
                # This happens in Nix builds or other restricted environments
                self.worker_id = str(uuid.uuid4())

        self.tempdir = Path(tempfile.TemporaryDirectory().name)
        self.tempdir.mkdir(exist_ok=True)

    def get_speaker(self, model: models.SpeakerModel) -> speak.Speaker:
        if model not in self.speakers:
            self.speakers[model] = speak.Speaker(model)
        return self.speakers[model]

    def api_is_up(self) -> bool:
        try:
            response = self.client.get("/api/ok")
            return response.status_code == 200
        except Exception:
            return False

    def work(self):
        idle_checker = idle.create_idle_checker()
        while True:
            if not self.api_is_up():
                if self.verbose:
                    print("API is down, waiting for it to come back up...")
                while not self.api_is_up():
                    time.sleep(10)
                if self.verbose:
                    print("API is back up, continuing...")

            while idle_checker.get_idle_time() >= self.idle_threshold_seconds:
                start_time = time.time()
                try:
                    response = self.client.post(
                        "/api/queue/take",
                        json={"worker_id": self.worker_id, "version": 1}
                    )
                except Exception as e:
                    if self.verbose:
                        print(f"Error taking work item: {e}")
                    time.sleep(60)
                    continue

                if response.status_code != 200:
                    if self.verbose:
                        print(f"Error getting work item: {response.status_code} {response.text}")
                    time.sleep(60)
                    continue

                work_item = response.json()
                if work_item is None:
                    if self.verbose:
                        print("No work item assigned, waiting for one...")
                    time.sleep(60)
                    continue

                self.work_one_item(work_item)
                if self.verbose:
                    print(f"Generated a voice performance in {time.time() - start_time} seconds")

            if self.verbose:
                print("System is being used by a person, waiting for it to become idle...")
            # Check if system becomes active
            while idle_checker.get_idle_time() < self.idle_threshold_seconds:
                time.sleep(self.idle_threshold_seconds)

    def work_one_item(self, work_item: dict):
        if self.verbose:
            print(f"Performing the line {json.dumps(work_item['text'])}")

        try:
            speaker_model = models.SpeakerModel(work_item['speaker_model'])
            speaker = self.get_speaker(speaker_model)
            output_path = self.tempdir/ f"{work_item['id']}.wav"
            reference_audio_path = self.tempdir / f"{work_item['reference_audio_hash']}.wav"
            if not reference_audio_path.exists():
                response = self.client.get(f"/api/reference_voices/{work_item['reference_audio_hash']}")
                if response.status_code != 200:
                    raise ValueError(f"Error getting reference voice: {response.status_code} {response.text}")
                reference_audio_path.write_bytes(response.content)
            speaker.speak(
                text=work_item['text'],
                speaker_wav=reference_audio_path,
                output_path=output_path,
            )
            files = {'generated_audio': ('audio.wav', output_path.read_bytes(), 'audio/wav')}
            completion_response = self.client.post(
                f"/api/queue/{work_item['id']}/complete/{self.worker_id}",
                files=files
            )

            if completion_response.status_code != 200:
                print(f"Error completing work item: {completion_response.status_code} {completion_response.text}")

        except Exception as e:
            print(f"Failed to process work item: {str(e)}")
            try:
                failure_response = self.client.post(
                    f"/api/queue/{work_item['id']}/fail/{self.worker_id}",
                    json={"error": str(e)}
                )
                if failure_response.status_code != 200:
                    print(f"Error marking work item as failed: {failure_response.status_code} {failure_response.text}")
            except:
                # Don't worry about it, we tried. Probably the API is down.
                pass
