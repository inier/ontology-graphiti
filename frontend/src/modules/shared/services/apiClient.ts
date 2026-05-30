interface RequestConfig extends RequestInit {
  skipAuth?: boolean;
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

  async request<T>(url: string, options: RequestConfig = {}): Promise<T> {
    const { skipAuth = false, headers = {}, ...restConfig } = options;

    const fullUrl = url.startsWith('http') ? url : `${this.baseURL}${url}`;
    const authHeaders = skipAuth ? {} : getAuthHeaders();
    const mergedHeaders = { ...authHeaders, ...(headers as Record<string, string>) };

    const mergedOptions: RequestInit = {
      ...restConfig,
      headers: mergedHeaders,
    };

    const response = await fetch(fullUrl, mergedOptions);

    if (response.status === 401 || response.status === 403) {
      handleAuthError();
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async get<T>(url: string, options?: RequestConfig): Promise<T> {
    return this.request<T>(url, { ...options, method: 'GET' });
  }

  async post<T>(url: string, data?: unknown, options?: RequestConfig): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async put<T>(url: string, data?: unknown, options?: RequestConfig): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete<T>(url: string, options?: RequestConfig): Promise<T> {
    return this.request<T>(url, { ...options, method: 'DELETE' });
  }

  async upload<T>(url: string, formData: FormData, options?: RequestConfig): Promise<T> {
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
}

export const apiClient = new ApiClient();

export async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  return apiClient.request<T>(url, options);
}
