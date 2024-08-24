import { create } from 'zustand';
import axios from 'axios';

const useScheduleStore = create((set) => ({
    inventory: [],
    staff: [],  
    loading: false,
    error: null,
    earliestDate: new Date(),  // Default to current date
    fetchData: async (location) => {
        set({ loading: true, error: null });
        try {
            const response = await axios.post('http://localhost:5000/sched', 
                { location },
                { headers: { 'Content-Type': 'application/json' } }
            );

            const inventory = response.data.inventory;
            const staff = response.data.staff;

            // Find the earliest date in the inventory and staff data
            const allDates = [
                ...inventory.flatMap(item => item.availability.map(avail => new Date(avail.date.split('/').reverse().join('-')))),
                ...staff.flatMap(item => item.availability.map(avail => new Date(avail.date.split('/').reverse().join('-'))))
            ];
            const earliestDate = new Date(Math.min(...allDates));

            set({
                inventory,
                staff,
                loading: false,
                earliestDate
            });
        } catch (error) {
            set({
                loading: false,
                error: 'Error fetching data',
            });
            console.error('Error fetching data:', error);
        }
    },
}));

export default useScheduleStore;
