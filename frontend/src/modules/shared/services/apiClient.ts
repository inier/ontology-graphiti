/* eslint-disable @typescript-eslint/no-explicit-any */
interface RequestConfig extends RequestInit {
  skipAuth?: boolean;
  skipAuthError?: boolean;
}

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

function handleAuthError(): never {
  localStorage.removeItem('token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  window.location.href = '/login';
  throw new Error('登录已过期，请重新登录');
}

class ApiClient {
  private baseURL: string;

  constructor(baseURL?: string) {
    this.baseURL = baseURL || import.meta.env.VITE_API_BASE || '';
  }

  async request<T = any>(url: string, options: RequestConfig = {}): Promise<T> {
    const { skipAuth = false, skipAuthError = false, headers = {}, ...restConfig } = options;

    const fullUrl = url.startsWith('http') ? url : `${this.baseURL}${url}`;
    const authHeaders = skipAuth ? {} : getAuthHeaders();
    const mergedHeaders = { ...authHeaders, ...(headers as Record<string, string>) };

    const mergedOptions: RequestInit = {
      ...restConfig,
      headers: mergedHeaders,
    };

    const response = await fetch(fullUrl, mergedOptions);

    if (!skipAuthError && (response.status === 401 || response.status === 403)) {
      handleAuthError();
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async get<T = any>(url: string, options?: RequestConfig): Promise<T> {
    return this.request<T>(url, { ...options, method: 'GET' });
  }

  async post<T = any>(url: string, data?: unknown, options?: RequestConfig): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data),
      // T049-fix: 显式声明 Content-Type，避免 skipAuth=true 时 Content-Type 丢失
      // 导致 fetch 用 text/plain charset=UTF-8 发送，FastAPI 报 422 json_invalid
      headers: {
        'Content-Type': 'application/json',
        ...((options?.headers as Record<string, string>) || {}),
      },
    });
  }

  async put<T = any>(url: string, data?: unknown, options?: RequestConfig): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data),
      headers: {
        'Content-Type': 'application/json',
        ...((options?.headers as Record<string, string>) || {}),
      },
    });
  }

  async delete<T = any>(url: string, options?: RequestConfig): Promise<T> {
    return this.request<T>(url, { ...options, method: 'DELETE' });
  }

  async upload<T = any>(url: string, formData: FormData, options?: RequestConfig): Promise<T> {
    const token = localStorage.getItem('token');
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const fullUrl = url.startsWith('http') ? url : `${this.baseURL}${url}`;

    const response = await fetch(fullUrl, {
      ...options,
      method: 'POST',
      body: formData,
      headers,
    });

    if (response.status === 401 || response.status === 403) {
      handleAuthError();
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Send a POST request and return the raw Response for streaming (SSE, NDJSON, etc.).
   * Auth headers are applied automatically. The caller is responsible for reading the stream.
   */
  async stream(url: string, data?: unknown, options?: RequestConfig): Promise<Response> {
    const { skipAuth = false, skipAuthError = false, headers = {}, ...restConfig } = options || {};

    const fullUrl = url.startsWith('http') ? url : `${this.baseURL}${url}`;
    const authHeaders = skipAuth ? {} : getAuthHeaders();
    const mergedHeaders = { ...authHeaders, ...(headers as Record<string, string>) };

    const mergedOptions: RequestInit = {
      ...restConfig,
      method: 'POST',
      headers: mergedHeaders,
      body: JSON.stringify(data),
    };

    const response = await fetch(fullUrl, mergedOptions);

    if (!skipAuthError && (response.status === 401 || response.status === 403)) {
      handleAuthError();
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response;
  }
}

export const apiClient = new ApiClient();

export async function fetchJson<T = any>(url: string, options?: RequestInit): Promise<T> {
  return apiClient.request<T>(url, options);
}
