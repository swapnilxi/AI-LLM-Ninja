export interface VisionRAGResult {
  id: number;
  content: string;
  score: number;
  uri?: string;
  meta?: Record<string, any>;
  meta_parsed?: {
    caption?: string;
    source?: string;
    engine?: string;
    [key: string]: any;
  };
  display_info?: {
    caption?: string;
    source?: string;
    engine?: string;
  image_url?: string;
  // optionally provided by backend to prefix local file paths
  image_base_url?: string;
  };
}

export interface QueryResponse {
  method: string;
  query_text?: string;
  image?: string;
  k: number;
  results: VisionRAGResult[];
  error?: string;
}

export interface HealthResponse {
  status: string;
  app: string;
  db_connection: string;
}

export interface IngestResponse {
  message: string;
  processed_images?: number;
  error?: string;
}

export interface QueryRequest {
  question?: string;
  image?: string | File;
  k?: number;
  engine?: 'gemini' | 'siglip';
}
