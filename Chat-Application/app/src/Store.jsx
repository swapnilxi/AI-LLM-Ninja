import React, { createContext, useContext, useReducer, useEffect } from 'react';
import { fetchRoles, fetchChatData, fetchChatHistory, fetchCardList } from './services/api';

// Define initial state
const initialState = {
    roles: [],
    chatData: [],
    chatHistory: [],
    cardList: [],
    user_profiles: {
        profile: 'Admin',
        profileOptions: ['Admin', 'User', 'Guest', 'Moderator']
    },
    loading: true,
    error: null
};

// Define actions
const ACTIONS = {
    SET_ROLES: 'set_roles',
    SET_CHAT_DATA: 'set_chat_data',
    SET_CHAT_HISTORY: 'set_chat_history',
    SET_CARD_LIST: 'set_card_list',
    SET_USER_PROFILE: 'set_user_profile',
    SET_LOADING: 'set_loading',
    SET_ERROR: 'set_error'
};

// Define reducer
const reducer = (state, action) => {
    switch (action.type) {
        case ACTIONS.SET_ROLES:
            return { ...state, roles: action.payload };
        case ACTIONS.SET_CHAT_DATA:
            return { ...state, chatData: action.payload };
        case ACTIONS.SET_CHAT_HISTORY:
            return { ...state, chatHistory: action.payload };
        case ACTIONS.SET_CARD_LIST:
            return { ...state, cardList: action.payload };
        case ACTIONS.SET_USER_PROFILE:
            return { ...state, user_profiles: { ...state.user_profiles, profile: action.payload } };
        case ACTIONS.SET_LOADING:
            return { ...state, loading: action.payload };
        case ACTIONS.SET_ERROR:
            return { ...state, error: action.payload };
        default:
            return state;
    }
};

// Create context
export const DataContext = createContext();

// Custom hook to use the DataContext
export const useData = () => {
    const context = useContext(DataContext); // Ensure correct context is being used
    if (!context) {
        throw new Error('useData must be used within a DataProvider');
    }
    return context;
};
// Data provider component
export const DataProvider = ({ children }) => {
    const [state, dispatch] = useReducer(reducer, initialState);

    useEffect(() => {
        const fetchData = async () => {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });
            dispatch({ type: ACTIONS.SET_ERROR, payload: null });

            try {
                const roles = await fetchRoles();
                const chatData = await fetchChatData();
                const chatHistory = await fetchChatHistory();
                const cardList = await fetchCardList();

                dispatch({ type: ACTIONS.SET_ROLES, payload: roles });
                dispatch({ type: ACTIONS.SET_CHAT_DATA, payload: chatData });
                dispatch({ type: ACTIONS.SET_CHAT_HISTORY, payload: chatHistory });
                dispatch({ type: ACTIONS.SET_CARD_LIST, payload: cardList });

                console.log("Fetched data successfully:", { roles, chatData, chatHistory, cardList });
            } catch (err) {
                dispatch({ type: ACTIONS.SET_ERROR, payload: 'Error fetching data' });
                console.error('Error fetching data:', err);
            } finally {
                dispatch({ type: ACTIONS.SET_LOADING, payload: false });
            }
        };

        fetchData();
    }, []);

    console.log("State in DataProvider:", state);

    return (
        <DataContext.Provider value={{ state, dispatch }}>
            {children}
        </DataContext.Provider>
    );
};
