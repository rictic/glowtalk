export interface Work {
  id: number;
  url: string;
  title: string | null;
  scrape_date: string;
  num_content_pieces: number;
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
  default_speaker: CharacterVoice | null;
}

export interface CharacterVoice {
  character_name: string;
  reference_voice: string;
  model: string;
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

// class ContentPieceContentResponse(BaseModel):
//     id: int
//     text: str
//     voiced: bool
//     audio_file_hash: Optional[str]

// class PartContentResponse(BaseModel):
//     id: int
//     character_name: Optional[str]
//     screenname: Optional[str]
//     icon_url: Optional[HttpUrl]
//     icon_title: Optional[str]
//     author_name: Optional[str]
//     content_pieces: ContentPieceContentResponse[];

export interface ContentPiece {
  id: number;
  text: string;
  voiced: boolean;
  audio_file_hash: string | null;
}

export interface Part {
  id: number;
  character_name: string | null;
  screenname: string | null;
  icon_url: string | null;
  icon_title: string | null;
  author_name: string | null;
  content_pieces: ContentPiece[];
}
