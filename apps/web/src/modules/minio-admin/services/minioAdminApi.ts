import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

export interface MinIOBucket {
  name: string;
  display_name: string;
  description: string;
  object_count: number;
  total_size: number;
  total_size_display: string;
  creation_date?: string;
}

export interface MinIOObject {
  name: string;
  display_name: string;
  size: number;
  size_display: string;
  content_type: string;
  last_modified?: string;
  is_dir: boolean;
}

export interface MinIOObjectList {
  bucket: string;
  prefix: string;
  items: MinIOObject[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface MinIOObjectMetadata {
  bucket: string;
  key: string;
  size: number;
  size_display: string;
  content_type: string;
  last_modified?: string;
  etag?: string;
  metadata?: Record<string, string>;
}

export interface MinIOStorageStats {
  total_buckets: number;
  total_objects: number;
  total_size: number;
  total_size_display: string;
  buckets: {
    name: string;
    object_count: number;
    total_size: number;
    total_size_display: string;
    content_types: Record<string, { count: number; size: number }>;
    error?: string;
  }[];
}

const BASE = `${API_BASE}/api/minio-admin`;

export const minioAdminApi = {
  getStatus: (): Promise<{ available: boolean; endpoint?: string }> =>
    fetchJson(`${BASE}/status`),

  listBuckets: (): Promise<MinIOBucket[]> =>
    fetchJson(`${BASE}/buckets`),

  listObjects: (bucket: string, prefix?: string, page = 1, pageSize = 50): Promise<MinIOObjectList> => {
    const params = new URLSearchParams({ bucket, page: String(page), page_size: String(pageSize) });
    if (prefix) params.set('prefix', prefix);
    return fetchJson(`${BASE}/objects?${params}`);
  },

  getObjectMetadata: (bucket: string, key: string): Promise<MinIOObjectMetadata> =>
    fetchJson(`${BASE}/objects/metadata?bucket=${encodeURIComponent(bucket)}&key=${encodeURIComponent(key)}`),

  getPresignedUrl: (bucket: string, key: string, expiresHours = 1): Promise<{ url: string; expires_seconds: number }> =>
    fetchJson(`${BASE}/objects/presigned-url?bucket=${encodeURIComponent(bucket)}&key=${encodeURIComponent(key)}&expires_hours=${expiresHours}`),

  deleteObject: (bucket: string, key: string): Promise<{ message: string }> =>
    fetchJson(`${BASE}/objects?bucket=${encodeURIComponent(bucket)}&key=${encodeURIComponent(key)}`, {
      method: 'DELETE',
    }),

  getStorageStats: (): Promise<MinIOStorageStats> =>
    fetchJson(`${BASE}/stats`),
};
