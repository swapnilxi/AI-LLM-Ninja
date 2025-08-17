import React, { useState, useEffect, useContext, useRef } from "react";
import { colors_v2, useCache } from "../../../config";
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
  AIRelevantDocsMessage,
  RelevantDocumentsList,
  PrePopulatedQuestions,
  ProgressMessage,
} from "../../components/ChatMessage";
import { ChatHistoryList } from "../../components/ListItems";
import Grid from "@mui/material/Grid";
import { useLocation } from "react-router-dom";
import SecondaryContentDrawerRight from "../../components/DrawerSidebar";
import Alert from "@mui/material/Alert";
import { DataContext } from "../../Store";  // Ensure you import DataContext, NOT DataProvider
import { transformProfileOptions, handleErrorResponse } from "../../utils";
import Snackbar from '@mui/material/Snackbar';

function DocumentSearchAndSummarization() {
  // Page mode is either "docsearch" or "datainsight"
  const PAGE_MODE = "docsearch";
  // Persona comes from the link user clicked to reach this page
  const { state } = useLocation();
  const { persona, title, description } = state
    ? state
    : ("Strategist",
      "Document Search",
      "I can assist you in providing insights on, and questions about, in-house documentation for pitch deck support.");

  // Chat identifier is the time in milliseconds
  const now = new Date().getTime();
  const [chatId, setChatId] = useState(now);

  // For debugging
  const [loggedError, setLoggedError] = useState("");
  const { state: guardRailState, dispatch } = useContext(DataContext); // Correct use of useContext

  const userId = transformProfileOptions([guardRailState.user_profiles.profile])[0]['value'];

  // When Page is created, get the recommended questions
  const [isLoadingRecommendedPrompts, setLoadingRecommendedPrompts] = useState(false);
  const [recommendedPrompts, setRecommendedPrompts] = useState([]);

  const getRecommendedPrompts = async (input_query) => {
    setLoadingRecommendedPrompts(true);
    try {
      const recommendedPromptsResponse = await postRecommendedPrompts({
        userId: userId,
        chatId: chatId,
        query: input_query,
        mode: PAGE_MODE,
        persona: persona,
        n: 3,
      });

      let buttonText = "Recommended Prompts";
      const errorString = handleErrorResponse(buttonText, recommendedPromptsResponse);
      if (errorString !== "") {
        setDisplayErrorMessageOnSnackBar(errorString);
        setOpenErrorSnackBar(true);
        return;
      }
      else {
        setRecommendedPrompts(recommendedPromptsResponse.response);
      }
      
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
  const [scannerTriggered, setScannerTriggered] = useState("");
  const [sanitizedText, setSanitizedText] = useState("");
  const [scannerResultsMatrix, setScannerResultsMatrix] = useState("");

  const [responseDocNames, setResponseDocNames] = useState([]);
  const [responseDocPaths, setResponseDocPaths] = useState([]);
  const [responseDocPages, setResponseDocPages] = useState([]);
  const [responseDocScores, setResponseDocScores] = useState([]);
  
  // Booleans to check the state of page
  const [isLoading, setIsLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [isQuestionShowing, setIsQuestionShowing] = useState(true);
  const [openErrorSnackBar, setOpenErrorSnackBar] = useState();
  const [displayErrorMessageOnSnackBar, setDisplayErrorMessageOnSnackBar] = useState("");

  const handleClose = () => {
    setOpenErrorSnackBar(false);
  };

  const handleTextQueryResponse = (textQueryResponse) => {
    // Extracts the response content
    console.log("response resp", textQueryResponse);

    let responseText = textQueryResponse.response.text;

    if (responseText === "") {
      setResponseText("");
    } else {
      setResponseText(responseText);
    }

    if (textQueryResponse.response.doc_metadata === "") {
      setResponseDocNames([]);
    } else {
      setResponseDocNames(textQueryResponse.response.doc_metadata.names);
    }
    if (textQueryResponse.response.doc_metadata === "") {
      setResponseDocPaths([]);
    } else {
      setResponseDocPaths(textQueryResponse.response.doc_metadata.paths);
    }
    if (textQueryResponse.response.doc_metadata === "") {
      setResponseDocPages([]);
    } else {
      setResponseDocPages(textQueryResponse.response.doc_metadata.pages);
    }
    if (textQueryResponse.response.doc_metadata === "") {
      setResponseDocScores([]);
    } else {
      setResponseDocScores(textQueryResponse.response.doc_metadata.scores);
    }

    // Triggers the next recommended questions and
    // hides the question input box
    getRecommendedPrompts(inputText);

    // Update the Chat History with the chat ID from the backend
    setChatId(textQueryResponse.response.chat_id);
    console.log("textQueryResponse: ", textQueryResponse);
    updateChatHistory(textQueryResponse.query, textQueryResponse.response.chat_id);

    setIsComplete(true);
    setIsLoading(false);
    displayQuestionHeader(false);
  }

  const chatContainerRef = useRef(null);
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [responseText, responseDocNames, responseDocPaths, responseDocPages, responseDocScores]);
  
  useEffect(() => {
    getRecommendedPrompts();
    initPageChatHistory();
    setIsComplete(false);
    setIsQuestionShowing(true);
  }, [persona, title]);

  const handleQueryButtonClick = async (input_query) => {
    let usingCelery = false;
    setIsLoading(true);
    setIsComplete(false);
    let buttonText = "Generate Answer"

    try {
      // Assign a new chat ID before querying the backend for a new question
      const newChatID = new Date().getTime();

      const textQueryResponse = await postTextQuery({
        userId: userId,
        chatId: newChatID,
        query: input_query,
        mode: PAGE_MODE,
        persona: persona,
        useCache: useCache,
      });

      const errorString = handleErrorResponse(buttonText, textQueryResponse);
      if (errorString !== "") {
        setDisplayErrorMessageOnSnackBar(errorString);
        setOpenErrorSnackBar(true);
        setIsComplete(true);
        setIsLoading(false);
        return;
      }
      else {
        if (textQueryResponse.task_id !== undefined) {
          usingCelery = true;
          const taskId = textQueryResponse.task_id;
          await listenToTaskStatus(taskId);
        }
        else {
          console.log("textQueryResponse", textQueryResponse);
          handleTextQueryResponse(textQueryResponse);
        }
      }
    } catch (error) {
      console.error("Error:", error);
      setLoggedError(error);
      setIsLoading(false); // TODO: add some UI text for users to understand what's wrong
    }
  };

  const listenToTaskStatus = async (taskId) => {
    const eventSource = new EventSource(`${BASE_URL}/task_status/${taskId}`);

    eventSource.onmessage = function (event) {
      let status = JSON.parse(JSON.stringify(event.data));
      status = JSON.parse(status);
      
      console.log(
        `Task status update status: `,
        status["result"],
        typeof status["result"]
      );
      console.log(`2s: `, status, typeof status);

      if (status.hasOwnProperty("result")) {
        const resp = status["result"];

        console.log("result is ", resp);
        console.log("result after stringify ", JSON.stringify(resp));
        console.log(`Task status update resp: `, resp);
      }

      // Process the status update
      if (
        status.state === "SUCCESS" ||
        status.state === "FAILED" ||
        status.state === "UNFINISHED"
      ) {
        console.log(`Task ${status.state.toLowerCase()}.`);

        if (status.state === "SUCCESS") {
          handleTextQueryResponse(status.result);
        }
        eventSource.close(); // Close the connection when the task is done or failed
      }
    };

    eventSource.onerror = function (error) {
      console.error("SSE error:", error);
      let buttonText = "Upload"
      let errorMessage = `${buttonText} - Message: ${response.message}. Please try again later.`;
      setDisplayErrorMessageOnSnackBar(errorMessage);
      setOpenErrorSnackBar(true);
      setWaitingForUploadResponse(false);
      eventSource.close(); // Close on errors
    };
  };

  const handleOverrideInputAndClick = async (preset_question) => {
    setInputText(preset_question);
    setTimeout(1000);
    handleQueryButtonClick(preset_question);
  };

  const displayQuestionHeader = async (newBoolVal) => {
    setIsQuestionShowing(newBoolVal);
  };

  //////////////////
  // CHAT HISTORY //
  //////////////////

  // The chat history for this specific persona+task
  const [chatHistoryText, setChatHistoryText] = React.useState([]);
  const [chatHistoryIds, setChatHistoryIds] = React.useState([]);

  const updateChatHistory = (chatText, chatId) => {
    try {
      // Update the chat history text
      var updatedChatHistoryText = [chatText].concat([...chatHistoryText]);
      setChatHistoryText(updatedChatHistoryText);

      // Repeat for the IDs
      var updatedChatHistoryIds = [chatId].concat([...chatHistoryIds]);
      setChatHistoryIds(updatedChatHistoryIds);
    } catch (error) {
      setLoggedError(error);
    }
  };

  const initPageChatHistory = async (event) => {
    try {
      const chatHistoryResponse = await postChatHistory({
        userId: userId,
        mode: PAGE_MODE,
        persona: persona,
        n: 5,
      });
      let buttonText = "Page Chat History"
      const errorString = handleErrorResponse(buttonText, chatHistoryResponse);
      if (errorString !== "") {
        setDisplayErrorMessageOnSnackBar(errorString);
        setOpenErrorSnackBar(true);
        return;
      }
      else {
        setChatHistoryText(chatHistoryResponse.response.prompts);
        setChatHistoryIds(chatHistoryResponse.response.chat_ids);
      }
    } catch (error) {
      console.error("Error:", error);
      setLoggedError(error);
    }
  };

  const getChatHistoryFromID = async (chatId) => {
    setIsLoading(true);
    setIsComplete(false);
    try {
      const chatIDResponse = await postChatIDResponse({
        chatId: chatId,
      });

      let buttonText = "Chat History";
      const errorString = handleErrorResponse(buttonText, chatIDResponse);
      if (errorString !== "") {
        setDisplayErrorMessageOnSnackBar(errorString);
        setOpenErrorSnackBar(true);
        return;
      }
      else {
        // Extracts the response content
        setResponseText(chatIDResponse.response.text);
        if (chatIDResponse.response.doc_metadata === "") {
          setResponseDocNames([]);
        } else {
          setResponseDocNames(chatIDResponse.response.doc_metadata.names);
        }
        if (chatIDResponse.response.doc_metadata === "") {
          setResponseDocPaths([]);
        } else {
          setResponseDocPaths(chatIDResponse.response.doc_metadata.paths);
        }
        if (chatIDResponse.response.doc_metadata === "") {
          setResponseDocPages([]);
        } else {
          setResponseDocPages(chatIDResponse.response.doc_metadata.pages);
        }
        if (chatIDResponse.response.doc_metadata === "") {
          setResponseDocScores([]);
        } else {
          setResponseDocScores(chatIDResponse.response.doc_metadata.scores);
        }
        // Triggers the next recommended questions and
        // hides the question input box
        getRecommendedPrompts(inputText);
        displayQuestionHeader(false);
      }
    } catch (error) {
      console.error("Error:", error);
      setLoggedError(error);
    }
    setIsComplete(true);
    setIsLoading(false);
  };

  const clickChatHistory = async (chatId, chatText) => {
    // Set the chat ID to the value from the text query
    setChatId(chatId);
    getChatHistoryFromID(chatId);
    setInputText(chatText);
  };

  ////////////////////////
  // SAVE USER FEEDBACK //
  ////////////////////////

  const sendUserFeedback = async (feedback) => {
    try {
      const saveFeedbackResponse = await postSaveFeedback({
        chatId: chatId,
        feedback: feedback,
      });

      let buttonText = "User Feedback";
      const errorString = handleErrorResponse(buttonText, saveFeedbackResponse);
      if (errorString !== "") {
        setDisplayErrorMessageOnSnackBar(errorString);
        setOpenErrorSnackBar(true);
        return;
      }
    } catch (error) {
      console.error("Error:", error);
      setLoggedError(error);
    }
  };

  /*
   * First time the page is loaded:
   *   1. Loads the recommended prompts
   *   2. Loads the chat history
   *    3. Resets the question by setting isComplete to false and showing
   *      the question input box
   */
  useEffect(() => {
    getRecommendedPrompts();
    initPageChatHistory();
    setIsComplete(false);
    displayQuestionHeader(true);
  }, [persona, title]);

  return (
    <>
      <div
        style={{
          backgroundColor: colors_v2.background.primary,
        }}
        ref={chatContainerRef}
      >
        <Grid container direction="row" display="flex">
          <Grid item xs={7.5}> 
            <PrimaryContent
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
                  borderPadding={"20px"}
                />
              }
              questionMessage={
                (isLoading || isComplete) && (
                  <HumanChatMessage
                    message={inputText}
                  />
                )
              }
              progressStatus={isLoading && <ProgressMessage />}
              agentOutput={
                isComplete && <h1>ResponseDocNames {responseDocNames}</h1> && (
                  <AIRelevantDocsMessage
                    filenames={responseDocNames.slice(
                      0,
                      Math.min(3, responseDocNames.length)
                    )}
                    ranks={["1", "2", "3"].slice(
                      0,
                      Math.min(3, ["1", "2", "3"].length)
                    )}
                    pages={responseDocPages.slice(
                      0,
                      Math.min(3, responseDocPages.length)
                    )}
                    relevances={responseDocScores.slice(
                      0,
                      Math.min(3, responseDocScores.length)
                    )}
                    paths={responseDocPaths.slice(
                      0,
                      Math.min(3, responseDocPaths.length)
                    )}
                    summary={responseText}
                    scannerTriggered={scannerTriggered}
                    sanitizedText={sanitizedText}
                    scannerResultsMatrix={scannerResultsMatrix}
                    feedbackFn={sendUserFeedback}
                  />
                )
              }
            />
          </Grid>
          {/* seconday sidebar */}
          <Grid
            item
            xs={4.5}
            sx={{
              backgroundColor: colors_v2.background.secondary,
            }}
          >
            {(
              <SecondaryContentDrawerRight
                drawerContent={
                  <SecondaryContent
                    recommendedPrompts={
                      <PrePopulatedQuestions
                        header={"Top queries trending amongst your peers"}
                        questions={recommendedPrompts}
                        clickEvent={handleOverrideInputAndClick}
                        loading={isLoadingRecommendedPrompts}
                        borderPadding={"20px"}
                      />
                    }
                    explanationSteps={
                      isComplete && (
                        <RelevantDocumentsList
                          filenames={responseDocNames.slice(0, 3)}
                          ranks={["1", "2", "3"]}
                          pages={responseDocPages.slice(0, 3)}
                          relevances={responseDocScores.slice(0, 3)}
                          paths={responseDocPaths.slice(0, 3)}
                          borderPadding={"20px"}
                        />
                      )
                    }
                    chatHistory={
                      <ChatHistoryList
                        chatTexts={chatHistoryText}
                        chatIds={chatHistoryIds}
                        maxHeight={"220px"} // 55px height row x 4 rows
                        rerunQuestionFn={clickChatHistory}
                        borderPadding={"20px"}
                      />
                    }
                  />
                }
              />
            )}
          </Grid>
        </Grid>
        <Snackbar
          sx={{width: '25%'}}
          open={openErrorSnackBar}
          anchorOrigin={{vertical:'bottom', horizontal: 'left'}}>
          <Alert
          onClose={handleClose}
          severity="error"
          
          variant="filled"
          sx={{ width: '100%' }}
        >
          {displayErrorMessageOnSnackBar}
        </Alert>
        </Snackbar>
      </div>
    </>
  );
}

export default DocumentSearchAndSummarization;
