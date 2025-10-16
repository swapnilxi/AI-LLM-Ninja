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
    bbox?: [number, number, number, number]; // YOLO bounding box [x1, y1, x2, y2]
    cls?: string;           // YOLO class label
    conf?: number;          // YOLO confidence score
    crop_path?: string;     // Path to cropped segment image
    image_id?: number;      // Parent image ID
    [key: string]: any;
  };
  display_info?: {
    caption?: string;
    source?: string;
    engine?: string;
    image_url?: string;
    // optionally provided by backend to prefix local file paths
    image_base_url?: string;
    bbox?: [number, number, number, number]; // YOLO bounding box [x1, y1, x2, y2]
    cls?: string;           // YOLO class label
    conf?: number;          // YOLO confidence score
  };
}

export interface QueryResponse {
  method: string;
  question?: string;
  original_question?: string;
  answer?: string;
  caption?: any;
  caption_used?: boolean;
  images?: VisionRAGResult[];
  segments?: VisionRAGResult[];
  text_chunks?: any[];
  k?: number;
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
  engine?: 'gemini' | 'siglip' | 'yolo';
}
