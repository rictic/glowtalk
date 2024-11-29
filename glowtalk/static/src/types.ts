export interface Work {
  id: number;
  url: string;
  title: string | null;
  scrape_date: string;
}

export interface Audiobook {
  id: number;
  original_work_id: number;
  description: string | null;
  default_speaker_id: number | null;
  created_at: string;
}

export interface AudiobookDetail extends Audiobook {
  characters: CharacterVoice[];
}

export interface CharacterVoice {
  character_name: string;
  speaker_id: number | null;
}

export interface ReferenceVoice {
  audio_hash: string;
  name: string;
  description: string | null;
  transcript: string | null;
}

export interface SpeakerModel {
  name: string;
}
