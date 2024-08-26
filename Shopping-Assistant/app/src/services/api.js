import axios from 'axios';

export const BASE_URL = 'http://localhost:5000/api';

// Post a text query
export const postTextQuery = async ({ userId, chatId, query, persona, mode, useCache }) => {
  try {
    const payload = { user_id: userId, chat_id: chatId, persona: persona, query: query, mode: mode, use_cache: useCache };
    const response = await axios.post(`${BASE_URL}/generate`, payload);
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response.data;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Post recommended prompts
export const postRecommendedPrompts = async ({ userId, chatId, query, persona, mode, n, useCache = false }) => {
  try {
    const payload = { user_id: userId, chat_id: chatId, persona: persona, query: query, mode: mode, n: n, use_cache: useCache };
    const response = await axios.post(`${BASE_URL}/recommend-prompt`, payload);
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response.data;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Get chat history corresponding to unique chat_id
export const postChatIDResponse = async ({ chatId }) => {
  try {
    const payload = { chat_id: chatId };
    const response = await axios.post(`${BASE_URL}/get-chat-history`, payload);
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response.data;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Get past session chat history for specific user + persona + mode
export const postChatHistory = async ({ userId, persona, mode, n }) => {
  try {
    const payload = { user_id: userId, persona: persona, mode: mode, n: n };
    const response = await axios.post(`${BASE_URL}/list-chat-history`, payload);
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response.data;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Save user feedback
export const postSaveFeedback = async ({ chatId, feedback }) => {
  try {
    const payload = { chat_id: chatId, feedback: feedback };
    const response = await axios.post(`${BASE_URL}/save-feedback`, payload);
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response.data;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Update embedding roles
export const postUpdateEmbeddingRoles = async ({ user_id, persona, ids_to_update, new_role }) => {
  try {
    const response = await axios.post(`${BASE_URL}/update-embeddings-roles`, { user_id: user_id, persona: persona, ids_to_update: ids_to_update, new_role: new_role });
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response.data;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Update embedding flags
export const postUpdateEmbeddingFlags = async ({ persona, ids_to_update, flag_name, flag_update_mode }) => {
  try {
    const response = await axios.post(`${BASE_URL}/update-embedding-flags`, { persona: persona, ids_to_update: ids_to_update, flag_name: flag_name, flag_update_mode: flag_update_mode });
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response.data;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Get RAG analytics data
export const postRagAnalyticsData = async ({ user_id, chat_id, model_id, mode, persona, use_cache, query }) => {
  try {
    const response = await axios.post(`${BASE_URL}/get-rag-analytics-data`, { user_id: user_id, chat_id: chat_id, model_id: model_id, mode: mode, persona: persona, use_cache: use_cache, query: query });
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response.data;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Upload documents
export const postUploadDocuments = async ({ files_list: file, role, access_roles }) => {
  const formData = new FormData();
  formData.append('files', file);
  formData.append('access_roles', access_roles);

  try {
    const response = await axios.post(`${BASE_URL}/upload_documents/?role=${role}`, formData);
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response.data;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Get document upload status
export const getDocumentUploadStatus = async () => {
  const formData = new FormData();
  try {
    const response = await axios.post(`${BASE_URL}/api/recent_uploads`, formData);
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response?.data?.uploadedFiles;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Get guard rail roles
export const getGuardRailRoles = async () => {
  const formData = new FormData();
  try {
    const response = await axios.post(`${BASE_URL}/api/get_roles`, formData);
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response?.data?.roles;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Get guardrail profiles
export const getGuardrailProfiles = async () => {
  const formData = new FormData();
  try {
    const response = await axios.post(`${BASE_URL}/profiles/list`, formData);
    if (response.status !== 200) {
      return { message: `Error Network response was not ok. ${response.status} : ${response.message}` };
    }
    return response?.data;
  } catch (error) {
    console.error("Error while fetching data: ", error);
    return { message: `Error while fetching data: ${error.message}` };
  }
};

// Fetch roles
export const fetchRoles = async () => {
  const response = await axios.get(`${BASE_URL}/roles`);
  return response.data;
};

// Fetch user profiles
export const fetchUserProfiles = async () => {
  const response = await axios.get(`${BASE_URL}/user_profiles`);
  return response.data;
};

// Fetch profile options
export const fetchProfileOptions = async () => {
  const response = await axios.get(`${BASE_URL}/profile_options`);
  return response.data;
};

// Fetch chat data
export const fetchChatData = async () => {
  const response = await axios.get(`${BASE_URL}/chat_data`);
  return response.data;
};

// Fetch card list
export const fetchCardList = async () => {
  const response = await axios.get(`${BASE_URL}/card_list`);
  return response.data;
};

// Fetch icons list
export const fetchIconsList = async () => {
  const response = await axios.get(`${BASE_URL}/icons_list`);
  return response.data;
};

// Fetch pre-populated questions
export const fetchPrePopulatedQuestions = async () => {
  const response = await axios.get(`${BASE_URL}/pre_populated_questions`);
  return response.data;
};

// Fetch chat histories (new)
export const fetchChatHistory = async () => {
  const response = await axios.get(`${BASE_URL}/chat_history`);
  return response.data;
};

// Fetch web searches (new)
export const fetchWebSearches = async () => {
  const response = await axios.get(`${BASE_URL}/web_searches`);
  return response.data;
};
