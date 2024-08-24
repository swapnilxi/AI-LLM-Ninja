
import { create } from 'zustand';
import axios from 'axios';
//import { apiUrl } from './../app/components/tab-1/config'

const useTurboFanStore = create((set) => ({
  selectedTurboEngine: 'all',
  selectedDateRange: {
    start: new Date('2024-01-01'),
    end: new Date('2024-12-31'),
  },
  selectedStatuses: [],
  statusDropdownOpen: false,
  searchQuery: '',

  TurboFanData: {
    kpis: [{
      avg_rul: 0,
      in_use: 0,
      retired: 0,
      total_assets: 0,
    }],
    rul_predictions: [],
  },
  
  fetchData: async (file, onProgress) => {
    const formData = new FormData();
    if (file) formData.append('file', file);

    try {
      const response = await axios.post(`${apiUrl}/rul`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          if (onProgress) {
            onProgress(progressEvent);
          }
        }
      });
      console.log("turbofan endpoint hit", `${apiUrl}/rul`);
      console.log("turbofan data", response.data);

      set({ TurboFanData: response.data });
    } catch (error) {
      console.error('Error fetching data:', error);
      set({
        TurboFanData: {
          kpis: [{
            avg_rul: 0,
            in_use: 0,
            retired: 0,
            total_assets: 0,
          }],
          rul_predictions: [],
        }
      });
    }
  },

  setSelectedTurboEngine: (engine) => set({ selectedTurboEngine: engine }),
  setSelectedDateRange: (range) => set({ selectedDateRange: range }),
  setSelectedStatuses: (statuses) => set({ selectedStatuses: statuses }),
  setStatusDropdownOpen: (open) => set({ statusDropdownOpen: open }),
  setSearchQuery: (query) => set({ searchQuery: query }),
}));

export default useTurboFanStore;

