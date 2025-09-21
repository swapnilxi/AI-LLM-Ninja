export const API_CONFIG = {
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000',
  endpoints: {
    health: '/',
    queryImage: '/query-image',
    ingestPdf: '/ingest/pdf',
    ingestSegments: '/ingest/segments',
    metrics: '/metrics'
  }
} as const;

export const createApiUrl = (endpoint: keyof typeof API_CONFIG.endpoints) => {
  return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints[endpoint]}`;
};
