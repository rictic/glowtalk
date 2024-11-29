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
