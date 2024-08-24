import axios from 'axios';

const API_BASE_URL = 'http://localhost:5000';

export const getRULPredictions = (file) => {
    const formData = new FormData();
    formData.append('file', file);

    return axios.post(`${API_BASE_URL}/rul`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    });
};

export const getSchedule = () => {
    return axios.post(`${API_BASE_URL}/schedule`);
};

export const getChatResponse = (query) => {
    const formData = new FormData();
    formData.append('query', query);

    return axios.post(`${API_BASE_URL}/chat`, formData);
};
