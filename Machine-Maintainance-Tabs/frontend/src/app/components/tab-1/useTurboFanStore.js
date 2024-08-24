import { create } from 'zustand';
import axios from 'axios';

const apiUrl = "http://localhost:5000";

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
  
  fetchData: async () => {
    try {
      const response = await axios.post(`${apiUrl}/sched`, {}, {
        headers: {
          'Content-Type': 'application/json'
        }
      });
      console.log("Schedule endpoint hit", `${apiUrl}/sched`);
      console.log("Schedule data", response.data);

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
