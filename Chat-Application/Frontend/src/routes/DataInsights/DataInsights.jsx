
import React, { useState, useEffect, useContext } from "react";
import {
  colors_v2,
  useCache
} from "../../../config";
import {
  postTextQuery,
  postRecommendedPrompts,
  postChatHistory,
  postChatIDResponse,
  postSaveFeedback,
  BASE_URL,
} from "../../services/api";
import {
  PrimaryContent,
  SecondaryContent,
  QuestionHeader,
  HumanChatMessage,
  AIDataInsightsMessage,
  AIDataInsightsExplanation,
  PrePopulatedQuestions,
  ProgressMessage,
} from "../../components/ChatMessage";
import {
  ChatHistoryList
} from "../../components/ListItems";
import Grid from "@mui/material/Grid";
import { useLocation } from "react-router-dom";
import { DataContext, DataProvider } from "../../Store";
import { transformProfileOptions } from "../../utils";

import SecondaryContentDrawerRight from "../../components/DrawerSidebar";
import RAGAnalyticsComponent from "../../components/RagAnalytics";

function DataInsights() {
  // Page mode is either "docsearch" or "datainsight"
  const PAGE_MODE = "datainsight"

  // Persona comes from the link user clicked to reach this page
  const { state } = useLocation();
  const { persona, title, description } = state ? state : ("Strategist", "Data Insight", "I can assist you in providing insights on, and questions about, in-house documentation for pitch deck support.");

  // Chat identifier is the time in milliseconds
  const now = new Date().getTime();
  const [chatId, setChatId] = useState(now);
  const [guardRailState, dispatch] = useContext(DataContext);
  const userId = transformProfileOptions([guardRailState.user_profiles.profile])[0]['value'];

  // For debugging
  const [loggedError, setLoggedError] = useState("");

  // When Page is created, get the recommended questions
  const [isLoadingRecommendedPrompts, setLoadingRecommendedPrompts] = useState(false);
  const [recommendedPrompts, setRecommendedPrompts] = useState([]);
  const getRecommendedPrompts = async (input_query) => {
    setLoadingRecommendedPrompts(true);
    try {
      const response = await postRecommendedPrompts({
        userId: userId,
        chatId: chatId,
        query: input_query,
        mode: PAGE_MODE,
        persona: persona,
        n: 3,
      });
      setRecommendedPrompts(response.response);

    } catch (error) {
      console.error("Error:", error);
      setLoggedError(error);
    }
    setLoadingRecommendedPrompts(false);
  };

  // Both the user input and input from recommended prompts 
  const [inputText, setInputText] = useState("");
  // Responses from the backend LLM agent
  const [responseText, setResponseText] = useState("");
  const [responseSteps, setResponseSteps] = useState([]);
  const [responseImage, setResponseImage] = useState("");
  // Booleans to check the state of page
  const [isLoading, setIsLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [isQuestionShowing, setIsQuestionShowing] = useState(true);

  const handleQueryButtonClick = async (input_query) => {
    setIsLoading(true);
    setIsComplete(false);
    try {
      // Assign a new chat ID before querying the backend for a new question
      const newChatID = new Date().getTime();

      const response = await postTextQuery({
        userId: userId,
        chatId: newChatID,
        query: input_query,
        mode: PAGE_MODE,
        persona: persona,
        useCache: useCache,
      });

      // Turns off image display until it becomes available
      setIsImageReady(false);

      // Extracts the response content
      setResponseText(response.response.text);
      setResponseSteps(response.response.steps);
      setResponseImage(BASE_URL+"/"+response.response.image_path);

      // Triggers the next recommended questions and
      // hides the question input box
      getRecommendedPrompts(inputText);

      // Update the Chat History with the chat ID from the backend
      setChatId(response.response.chat_id);
      updateChatHistory(input_query, response.response.chat_id);

    } catch (error) {
      console.error("Error:", error);
      setLoggedError(error);
    }
    setIsComplete(true);
    setIsLoading(false);
    displayQuestionHeader(false);
  };

  const handleOverrideInputAndClick = async (preset_question) => {
    setInputText(preset_question);
    setTimeout(1000);
    handleQueryButtonClick(preset_question);
  };


  const displayQuestionHeader = async (newBoolVal) => {
    setIsQuestionShowing(newBoolVal);
  }

  // New hook to ensure image is ready before rendering
  const [isImageReady, setIsImageReady] = useState(false);

  //////////////////
  // CHAT HISTORY //
  //////////////////

  // The chat history for this specific persona+task
  const [chatHistoryText, setChatHistoryText] = React.useState([])
  const [chatHistoryIds, setChatHistoryIds] = React.useState([])
  
  const updateChatHistory = (chatText, chatId) => {
    try {
      // Update the chat history text
      var updatedChatHistoryText = [chatText].concat([...chatHistoryText]);
      setChatHistoryText(updatedChatHistoryText);

      // Repeat for the IDs
      var updatedChatHistoryIds =[chatId].concat([...chatHistoryIds]);
      setChatHistoryIds(updatedChatHistoryIds);
    } catch(error) {
      setLoggedError(error);
    }
  }

  const initPageChatHistory = async (event) => {
    try {
      const response = await postChatHistory({
        userId: userId,
        mode: PAGE_MODE,
        persona: persona,
        n: 5,
      });
      setChatHistoryText(response.response.prompts);
      setChatHistoryIds(response.response.chat_ids);
    } catch (error) {
      console.error("Error:", error);
      setLoggedError(error);
    }
  }

  const getChatHistoryFromID = async (chatId) => {
    setIsLoading(true);
    setIsComplete(false);
    try {
      const response = await postChatIDResponse({
        chatId: chatId,
      });

      // Extracts the response content
      setResponseText(response.response.text);
      setResponseSteps(response.response.steps);
      setResponseImage(BASE_URL+"/"+response.response.image_path);
      // Triggers the next recommended questions and
      // hides the question input box
      getRecommendedPrompts(inputText);
      displayQuestionHeader(false);
    } catch (error) {
      console.error("Error:", error);
    }
    setIsComplete(true);
    setIsLoading(false);
  }

  const clickChatHistory = async (chatId, chatText) => {
    setChatId(chatId);
    getChatHistoryFromID(chatId);
    setInputText(chatText);
  };

  ////////////////////////
  // SAVE USER FEEDBACK //
  ////////////////////////

  const sendUserFeedback = async (feedback) => {
    try {
      const response = await postSaveFeedback({
        chatId: chatId,
        feedback: feedback,
      });
    } catch (error) {
      console.error("Error:", error);
      setLoggedError(error);
    }
  }

  /*
  * First time the page is loaded:
  *   1. Loads the recommended prompts 
  *   2. Loads the chat history
  *   3. Resets the question by setting isComplete to false and showing
  *      the question input box
  */
  useEffect(() => {
      getRecommendedPrompts();
      initPageChatHistory();
      setIsComplete(false);
      displayQuestionHeader(true);
  },[persona,title]);

  return (
    <>
      <div style={{
        backgroundColor: colors_v2.background.primary,
      }}>
        <Grid container direction="row" display="flex">
          <Grid item xs={7.5}>
            <PrimaryContent
              {...state.title === 'RAG Analytics' ? <RAGAnalyticsComponent /> : null}
              questionHeader={
                <QuestionHeader
                  pageTitle={title}
                  pageDescription={description}
                  loadingBool={isLoading}
                  showQuestionBool={isQuestionShowing}
                  showQuestionFn={displayQuestionHeader}
                  inputText={inputText}
                  inputTextFn={setInputText}
                  queryButtonClickFn={handleQueryButtonClick}
                  borderPadding={"50px"}
              />}
              questionMessage={
                (isLoading || isComplete) &&
                <HumanChatMessage
                  message={inputText}
                  borderPadding={"50px"}
              />}
              progressStatus={isLoading && <ProgressMessage/>}
              agentOutput={
                isComplete &&
                <AIDataInsightsMessage
                  message_list={responseSteps}
                  summary={responseText}
                  image_path={responseImage}
                  borderPadding={"50px"}
                  imageLoaded={isImageReady}
                  imageLoadedFn={setIsImageReady}
                  feedbackFn={sendUserFeedback}
              />}
            />
          </Grid>
          <Grid item xs={4.5} sx={{
          }}>
            <SecondaryContentDrawerRight
              drawerContent={
                <SecondaryContent
                recommendedPrompts={
                  <PrePopulatedQuestions
                    header={"What do you want to search for?"}
                    questions={recommendedPrompts}
                    clickEvent={handleOverrideInputAndClick}
                    loading={isLoadingRecommendedPrompts}
                    borderPadding={"50px"}
                />}
                explanationSteps={
                  isComplete &&
                  <AIDataInsightsExplanation
                    message_list={responseSteps}
                    summary={responseText}
                    image_path={responseImage}
                    borderPadding={"50px"}
                />}
                chatHistory={<ChatHistoryList
                  chatTexts={chatHistoryText}
                  chatIds={chatHistoryIds}
                  maxHeight={"220px"}  // 55px height row x 4 rows
                  rerunQuestionFn={clickChatHistory}
                  borderPadding={"50px"}
                />}
              />
            }/>
          </Grid>
        </Grid>
      </div>
    </>
  );
}

export default DataInsights;

