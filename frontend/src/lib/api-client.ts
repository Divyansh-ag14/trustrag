import { API_BASE_URL } from "./constants";
import type { ApiError } from "@/types/api";

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };

    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }

    return headers;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (response.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      }
      throw new Error("Unauthorized");
    }

    if (response.status === 429) {
      throw new Error("Rate limit exceeded. Please try again shortly.");
    }

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        detail: `Request failed with status ${response.status}`,
      }));
      throw new Error(error.detail);
    }

    return response.json();
  }

  async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    return this.handleResponse<T>(response);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: this.getHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });
    return this.handleResponse<T>(response);
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "PATCH",
      headers: this.getHeaders(),
      body: JSON.stringify(body),
    });
    return this.handleResponse<T>(response);
  }

  async delete<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: this.getHeaders(),
    });
    return this.handleResponse<T>(response);
  }

  async upload<T>(path: string, formData: FormData): Promise<T> {
    const headers: HeadersInit = {};
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers,
      body: formData,
    });
    return this.handleResponse<T>(response);
  }

  streamUrl(path: string): string {
    return `${this.baseUrl}${path}`;
  }

  getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
  }
}

export const api = new ApiClient(API_BASE_URL);
