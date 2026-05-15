import { create } from "zustand";
import { api } from "@/lib/api-client";
import type { User, Workspace, TokenResponse } from "@/types/api";

interface AuthState {
  user: User | null;
  workspace: Workspace | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (email: string, password: string) => Promise<void>;
  register: (
    workspaceName: string,
    name: string,
    email: string,
    password: string,
  ) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  workspace: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (email, password) => {
    const data = await api.post<TokenResponse>("/auth/login", {
      email,
      password,
    });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    set({
      user: data.user,
      workspace: data.workspace,
      isAuthenticated: true,
    });
  },

  register: async (workspaceName, name, email, password) => {
    const data = await api.post<TokenResponse>("/auth/register", {
      workspace_name: workspaceName,
      name,
      email,
      password,
    });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    set({
      user: data.user,
      workspace: data.workspace,
      isAuthenticated: true,
    });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({
      user: null,
      workspace: null,
      isAuthenticated: false,
    });
  },

  loadUser: async () => {
    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        set({ isLoading: false });
        return;
      }
      const user = await api.get<User>("/auth/me");
      set({
        user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  },
}));
