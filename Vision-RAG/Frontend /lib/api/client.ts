import { HealthResponse, IngestResponse, QueryRequest, QueryResponse } from '@/types/api';
import { createApiUrl } from './config';

class VisionRAGApi {
  async health(): Promise<HealthResponse> {
    const response = await fetch(createApiUrl('health'));
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }
    return response.json();
  }

  async query(request: QueryRequest): Promise<QueryResponse> {
    const formData = new FormData();
    if (request.question) formData.append('question', request.question);
    if (request.image) {
      if (request.image instanceof File) {
        formData.append('image', request.image);
      } else {
        formData.append('image', request.image);
      }
    }
    if (request.k) formData.append('k', request.k.toString());
    // Unified endpoint supports engine/model selection as extra param
    if (request.engine) formData.append('engine', request.engine);
    // Optionally add other unified params here
    const response = await fetch(createApiUrl('query'), {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`Query failed: ${response.statusText}`);
    }
    return response.json();
  }

  async ingestPdf(file: File): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(createApiUrl('ingestPdf'), {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`PDF ingestion failed: ${response.statusText}`);
    }

    return response.json();
  }

  async ingestSegments(configData: any): Promise<IngestResponse> {
    const response = await fetch(createApiUrl('ingestSegments'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(configData),
    });

    if (!response.ok) {
      throw new Error(`Segments ingestion failed: ${response.statusText}`);
    }

    return response.json();
  }
}

export const visionRagApi = new VisionRAGApi();
