import { create } from "zustand";

interface AppState {
  sidebarOpen: boolean;
  citationPanelOpen: boolean;

  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  toggleCitationPanel: () => void;
  setCitationPanelOpen: (open: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  sidebarOpen: true,
  citationPanelOpen: false,

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleCitationPanel: () =>
    set((s) => ({ citationPanelOpen: !s.citationPanelOpen })),
  setCitationPanelOpen: (open) => set({ citationPanelOpen: open }),
}));
