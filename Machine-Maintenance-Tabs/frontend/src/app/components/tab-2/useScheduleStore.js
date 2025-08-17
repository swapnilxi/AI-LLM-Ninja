import { create } from 'zustand';
import axios from 'axios';
import { apiUrl } from './config'; 

const useScheduleStore = create((set) => ({
    inventory: [],
    staff: [],
    fetchData: async (engine_id, startDate, endDate) => {
        try {
            const response = await axios.post(`${apiUrl}/sched`, {
                engine_id,
                start_date: startDate,
                end_date: endDate
            });
            set({
                inventory: response.data.inventory,
                staff: response.data.staff,
            });
            console.log("Fetched data:", response.data);
        } catch (error) {
            console.error('Error fetching data:', error);
        }
    },
}));

export default useScheduleStore;
