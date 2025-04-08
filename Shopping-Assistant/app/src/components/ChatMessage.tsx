
import React, { ReactNode, useState, useEffect , useRef } from "react";
import {
  Box,
  Container,
  TextField,
  Button,
  CircularProgress,
  LinearProgress,
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableRow,
  TableContainer,
  Paper,
  Alert,
} from "@mui/material";
import parse from "html-react-parser";
import AccountCircleIcon from "@mui/icons-material/AccountCircle";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import { fontSizes, colors_v2, agentName } from "../../config";
import ArticleIcon from "@mui/icons-material/Article";
import QuestionAnswerIcon from "@mui/icons-material/QuestionAnswer";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import FormatListNumberedIcon from "@mui/icons-material/FormatListNumbered";
import Grid from "@mui/material/Grid";
import Divider from "@mui/material/Divider";
import "../../src/index.css";
import { PrePopulatedQuestionsList } from "./ListItems";
import Parser from "html-react-parser";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import ListItem from "@mui/material/ListItem";
import { BASE_URL } from "../services/api";
import { red } from "@mui/material/colors";
import StarIcon from "@mui/icons-material/Star";
import StarBorderIcon from "@mui/icons-material/StarBorder";
import {Sheet} from 'react-modal-sheet';
import WebSearch from './WebSearch'; // Assuming WebSearch is a separate component

interface ChatMessageProps {
  message: string;
  message_list: string[];
  borderPadding: string;
}

export function HumanChatMessage({
  message,
  borderPadding,
  message_list = [],
}: ChatMessageProps) {
  return (
    <Grid
      container
      sx={{
        width: "100%",
        height: "100%",
        backgroundColor: colors_v2.messages.human,
        color: "black",
        display: "flex",
        flexWrap: "wrap", 
        alignItems: "center",
        justifyContent: "start",
        textAlign: "left",
        padding: "20px",
      }}
    >
      <Grid item xs={1} />
      <Grid item xs={1} >
        <AccountCircleIcon
          sx={{
            fontSize: fontSizes.primary.icons,
            color: colors_v2.agent.tertiary.tint,
          }}
        />
      </Grid>
      <Grid item xs={8}>
        <span
          style={{
            height: "100%",
            width: "100%",
            justifyContent: "center",
            padding: "5px",
            fontSize: fontSizes.primary.paragraph,
          }}
        >  
          {parse(message)}
        </span>
      </Grid>
      <Grid item xs={2} />
    </Grid>
  );
}

///////////////////
// DATA INSIGHTS //
///////////////////

interface AIDataInsightsMessageProps {
  summary: string;
  message_list: string[];
  image_path: string;
  // clickEvent: Function;
  borderPadding: string;
  imageLoaded: boolean;
  imageLoadedFn: Function;
  feedbackFn: Function;
}

export function AIDataInsightsMessage({
  summary,
  message_list = [],
  image_path,
  borderPadding,
  imageLoaded,
  imageLoadedFn,
  feedbackFn,
}: AIDataInsightsMessageProps) {
  // CHECK IF IMAGE EXISTS
  function checkIfImageExists(url) {
    var image = new Image();
    image.src = url;
    if (image.width == 0) {
      return false;
    } else {
      return true;
    }
  }

  return (
    <Grid
      container
      display="flex"
      rowSpacing={0}
      sx={{
        backgroundColor: colors_v2.background.primary,
        color: "black",
        alignItems: "left",
        textAlign: "left",
        padding: borderPadding,
        marginTop: "8px",
      }}
    >
      <Grid
        item
        xs={12}
        display="flex"
        justifyContent="center"
        alignContent="center"
        sx={{
          padding: borderPadding,
          maxHeight: "500px",
          maxWidth: "700px",
        }}
      >
        <img
          src={image_path}
          // Image now waits to load until it is available
          onLoad={() => imageLoadedFn(true)}
          style={
            imageLoaded
              ? {
                  maxHeight: "500px",
                  maxWidth: "700px",
                }
              : {
                  maxHeight: "500px",
                  maxWidth: "700px",
                  display: "none",
                }
          }
        />
      </Grid>
      {/*
          To align the icons with question header, use the 1-1-8-2 layout.
        */}
      <Grid item xs={1} />
        <Grid item xs={1}>
          <AutoAwesomeOutlinedIcon
            sx={{
              color: colors_v2.agent.secondary.darkGray,
              fontSize: fontSizes.primary.icons,
              marginRight: "8px",
            }}
          />
        </Grid>
      <Grid item xs={8}>
          <span
            style={{
              fontSize: fontSizes.primary.paragraph,
            }}
          >
            {parseSummaryText(summary.replace(`\u008e`, `é`))}
          </span>
        </Grid>
      <Grid item xs={2} />
      <Grid item xs={12} sx={{ padding: borderPadding }}>
        <Divider />
      </Grid>
      <Grid item xs={12} sx={{
        display:"flex",
        justifyContent:"flex-start",
        alignItems:"flex-start",
      }}>
        <FeedbackButtons feedbackFn={feedbackFn} />
      </Grid>
    </Grid>
  );
}

function tryParseStepsJSON(jsonString, mode) {
  try {
    var cleanJsonString = jsonString.replace(/\'/g, `\"`);
    var parsedString = "";
    if (mode == "step") {
      parsedString = JSON.parse(cleanJsonString).Step;
    } else if (mode == "action") {
      parsedString = JSON.parse(cleanJsonString).Action;
    }

    return parsedString;
  } catch (error) {
    return "";
  }
}

export function AIDataInsightsExplanation({
  summary,
  message_list = [],
  image_path,
  borderPadding,
}: AIDataInsightsMessageProps) {
  var parsedMessageList = message_list.map((message, i) => {
    return {
      step: tryParseStepsJSON(message, "step"),
      action: tryParseStepsJSON(message, "action"),
    };
  });

  // Drop any rows with steps/actions that couldn't be parsed
  parsedMessageList = parsedMessageList.filter(
    (obj) => obj.step != "" && obj.action != ""
  );

  // Drop empty responses as well
  parsedMessageList = parsedMessageList.filter(
    (obj) => JSON.stringify(obj) != "{}"
  );

  const [showBoxBoolList, setShowBox] = React.useState(
    Array(parsedMessageList.length).fill(false)
  );

  const handleBoxClick = (
    event: React.MouseEvent<HTMLDivElement, MouseEvent>,
    index: number
  ) => {
    const updatedShowBoxBoolList = [...showBoxBoolList];
    updatedShowBoxBoolList[index] = !updatedShowBoxBoolList[index];
    setShowBox(updatedShowBoxBoolList);
  };

  return (
    <Grid
      container
      display="flex"
      textAlign="left"
      justifyContent="flex-start"
      alignContent="left"
      sx={{
        padding: borderPadding,
      }}
    >
      <Grid item xs={1.5}>
        <FormatListNumberedIcon
          sx={{
            color: colors_v2.agent.primary.tone,
            fontSize: fontSizes.secondary.icons,
          }}
        />
      </Grid>
      <Grid item xs={10.5}>
        <span
          style={{
            color: colors_v2.agent.primary.tone,
            fontSize: fontSizes.secondary.subtitle,
          }}
        >
          <b>Agent Insights</b>
        </span>
      </Grid>
      {parsedMessageList.map((messageDict, i) => (
        <Grid
          item
          xs={12}
          key={i}
          onClick={(event) => handleBoxClick(event, i)}
          sx={{
            width: "100%",
            height: "80%",
          }}
        >
          <Grid
            container
            display="flex"
            rowSpacing={0}
            sx={{
              minHeight: "50px",
              backgroundColor: colors_v2.agent.primary.tint,
              boxShadow: "0px 5px 5px lightgray",
              borderRadius: "5px",
              paddingLeft: "50px",
              paddingRight: "0px",
              paddingTop: "25px",
              paddingBottom: "25px",
              ":hover": {
                backgroundColor: colors_v2.agent.primary.tone,
                cursor: "pointer",
              },
            }}
          >
            <Grid
              item
              xs={11}
              sx={{
                // Step size is 2 font sizes larger than text
                fontSize:
                  String(
                    Number(fontSizes.primary.paragraph.split("pt")[0]) + 2
                  ) + "pt",
              }}
            >
              <span>
                <b>{messageDict.step}</b>
              </span>
            </Grid>
            <Grid item xs={1}>
              <KeyboardArrowDownIcon />
            </Grid>
            {showBoxBoolList[i] && (
              <Grid
                item
                xs={10}
                sx={{
                  fontSize: fontSizes.primary.paragraph,
                  paddingTop: "25px",
                  paddingBottom: "25px",
                }}
              >
                <span>{messageDict.action}</span>
              </Grid>
            )}
            <Grid item xs={2} />
          </Grid>
        </Grid>
      ))}
      <Grid item xs={12}>
        <Divider sx={{ borderBottomWidth: "3px" }} />
      </Grid>
    </Grid>
  );
}

////////////////////////
// RELEVANT DOCUMENTS //
////////////////////////

type GradientProgressBarProps = {
  valuePercentage: number;
};

const GradientProgressBar = (props: GradientProgressBarProps) => {
  const { valuePercentage: value } = props;
  const fillerRelativePercentage = (100 / value) * 100;

  return (
    <div
      className="wrapper"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
    >
      <div className="barContainer">
        <div className="filler" style={{ width: `${value}%` }}>
          <div
            className="fillerBackground"
            style={{ width: `${fillerRelativePercentage}%` }}
          />
        </div>
      </div>
      <div
        className="textValue"
        style={{ marginLeft: "20px" }}
      >{`${value}%`}</div>
    </div>
  );
};

interface RelevantDocumentRowProps {
  rank: string;
  filename: string;
  page: string;
  relevance: string;
  path: string;
}

function RelevantDocumentRow({
  rank,
  filename,
  page,
  relevance,
  path,
}: RelevantDocumentRowProps) {
  const [showPDF, setShowBox] = React.useState(false);

  const handlePageClick = (
    event: React.MouseEvent<HTMLDivElement, MouseEvent>
  ) => {
    setShowBox(!showPDF);
  };

  return (
    <Grid
      container
      rowSpacing={1}
      justifyContent="flex-start"
      sx={{
        fontSize: fontSizes.primary.paragraph,
      }}
    >
      <Grid item xs={12}>
        <Typography variant="subtitle1">
          <b>{rank}.</b> {filename}
        </Typography>
      </Grid>
      <Grid item xs={12}>
        <Grid container rowSpacing={2} columnSpacing={2} alignItems="center">
          <Grid item xs={3}>
            <Button
              variant="outlined"
              fullWidth
              onClick={(e) => handlePageClick(e)}
              sx={{
                justifyContent: "flex-start",
                textTransform: "none",
                fontSize: fontSizes.primary.paragraph,
              }}
            >
              <Typography variant="body1" color="text.secondary">
                <b>• Page:</b> {page + 1}
              </Typography>
            </Button>
          </Grid>
          <Grid item xs={3}>
            <Box
              sx={{
                justifyContent: "flex-start",
              }}
            >
              <Typography variant="body1" color="text.secondary">
                <b>• Relevance:</b>
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6}>
            <GradientProgressBar
              valuePercentage={(Number(relevance) * 100).toFixed(1)}
            />
          </Grid>
          {showPDF && (
            <Grid item xs={12}>
              <iframe
                src={BASE_URL + "/" + path + "#page=" + String(page + 1)}
                width={"100%"}
                height={"700px"}
              />
            </Grid>
          )}
        </Grid>
      </Grid>
    </Grid>
  );
}

interface RelevantDocumentsListProps {
  ranks: string[];
  filenames: string[];
  pages: string[];
  relevances: string[];
  paths: string[];
  borderPadding: string;
}

export function RelevantDocumentsList({
  ranks,
  filenames,
  pages,
  relevances,
  paths,
  borderPadding,
}: RelevantDocumentsListProps) {
  if (filenames.length === 0) {
    return null;
  }

  return (
    <Grid
      container
      rowSpacing={0}
      columnSpacing={0}
      display="flex"
      sx={{
        backgroundColor: "white",
        padding: "16px",
        margin: "0 auto",
        borderRadius: fontSizes.secondary.borderRadius,
        color: "black",
        display:"flex",
        alignItems: "center",
        justifyContent:"center",
        textAlign: "left",
      }}
    >
      <Grid item xs={1.5}>
        <ArticleIcon
          sx={{
            color: colors_v2.agent.secondary.darkGray,
            fontSize: fontSizes.secondary.icons,
          }}
        />
      </Grid>
      <Grid item xs={10.5} sx={{padding:"10px"}}>
        <span
          style={{
            color: colors_v2.agent.secondary.darkGray,
            fontSize: fontSizes.secondary.subtitle,
          }}
        >
          <b>Relevant Documents</b>
        </span>
      </Grid>
      {filenames?.map((filename, i) => (
        <Grid item xs={12} key={i}>
          <RelevantDocumentRow
            filename={filename}
            rank={ranks[i]}
            page={pages[i]}
            relevance={relevances[i]}
            path={paths[i]}
          />
        </Grid>
      ))}
      <Grid item xs={12}>
        <Divider sx={{ borderBottomWidth: "3px" }} />
      </Grid>
    </Grid>
  );
}


////////////////////////
// Summary           //
///////////////////////

function parseHTML(message) {
  // Adds basic markup elements for bold, underline, italics and strike
  var html_message = message;
  html_message = html_message.replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");
  html_message = html_message.replace(/__(.*?)__/g, "<u>$1</u>");
  html_message = html_message.replace(/~~(.*?)~~/g, "<i>$1</i>");
  html_message = html_message.replace(/--(.*?)--/g, "<del>$1</del>");
  html_message = html_message.replace(/<<(.*?)>>/g, "<a href='$1'>Link</a>");

  const parser = new DOMParser();
  const document = parser.parseFromString(html_message, "text/html");
  return document;
}

function parseSummaryText(summary) {
  // Check if summary is an empty string
  if (summary === "") {
    return (
      <Grid container rowSpacing={0}>
        <Grid item xs={12}>
          <span
            style={{
              color: "red", // Sets text color to red to indicate error
              fontSize: fontSizes.primary.subtitle, // Consistent font sizing
            }}
          >
            The chatbot is currently not functional. Please try again later.
          </span>
        </Grid>
      </Grid>
    );
  }

  // Normal functionality if summary is not empty
  return (
    <Grid container rowSpacing={0}>
      <Grid item xs={12}>
        <span
          style={{
            color: colors_v2.agent.secondary.darkGray,
            fontWeight:"700",
            fontSize: fontSizes.primary.subtitle,
          }}
        >
          <b>Summary</b>
        </span>
      </Grid>
      <Grid
        item
        xs={12}
        sx={{
          paddingTop: "20px",
          fontSize: fontSizes.primary.paragraph,
        }}
      >
        <div>{Parser(parseHTML(summary).body.innerHTML)}</div>
      </Grid>
    </Grid>
  );
}

function RelevantDocumentsSummary({
  message,
  borderPadding = "",
}: ChatMessageProps) {
  return parseSummaryText(message);
}

interface AIRelevantDocsMessageProps {
  ranks: string[];
  filenames: string[];
  pages: string[];
  relevances: string[];
  paths: string[];
  summary: string;
  scannerTriggered: boolean;
  sanitizedText: string;
  scannerResultsMatrix: string[];
  borderPadding: string;
  feedbackFn: Function;
}

export function AIRelevantDocsMessage({
  ranks,
  filenames,
  pages,
  relevances,
  paths,
  summary,
  scannerTriggered,
  sanitizedText,
  scannerResultsMatrix,
  borderPadding,
  feedbackFn,
}: AIRelevantDocsMessageProps) {
  return (
    <Grid
      container
      direction="row"
      display="flex"
      sx={{
        width: "100%",
        backgroundColor: colors_v2.background.primary,
        color: "black",
        alignItems: "flex",
        textAlign: "left",
        padding: "15px",
        marginTop:"4px"
      }}
    >
      {/*
          To align the icons with question header, use the 1-1-8-2 layout.
        */}
      <Grid item xs={1} />
      <Grid item xs={1}>
        <AutoAwesomeOutlinedIcon
          sx={{
            color: colors_v2.agent.secondary.darkGray,
            fontSize: fontSizes.primary.icons,
          }}
        />
      </Grid>
      <Grid item xs={8} sx={{  
      display: "flex", 
      alignItems:"center",
    }}
     
      >
        {scannerTriggered && (
          <>
            <Card>
              <Alert severity="error">
                Your request violated the LLM usage policy.
              </Alert>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  TrustworthyAI Scanner Log
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography
                      variant="subtitle1"
                      gutterBottom
                      fontWeight="bold"
                    >
                      Sanitized Text:
                    </Typography>
                    <Typography variant="body1" gutterBottom>
                      {sanitizedText}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography
                      variant="subtitle1"
                      gutterBottom
                      fontWeight="bold"
                    >
                      Scanner Results:
                    </Typography>
                    <TableContainer component={Paper}>
                      <Table aria-label="simple table">
                        <TableBody>
                          {scannerResultsMatrix.map((row, index) => (
                            <TableRow key={index}>
                              <TableCell component="th" scope="row">
                                {row.scanner}
                              </TableCell>
                              <TableCell align="right">{row.is_valid}</TableCell>
                              <TableCell align="right">
                                {row.risk_score.toFixed(2)}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </>
        )}
        <br/>
        {!scannerTriggered && <RelevantDocumentsSummary
            message={summary}
            message_list={[]}
            borderPadding="0px"
        />}
      </Grid>
      <Grid item xs={2} />
      <Grid item xs={12}>
        <Divider />
      </Grid>
      <Grid item xs={12}
      sx={{
        display:'flex',
        alignItems: 'flex-start',
      }}
      >
        {scannerTriggered && (
          <DisableGuardrailFeedbackButtons feedbackFn={feedbackFn} />
        )}
        {!scannerTriggered && <FeedbackButtons feedbackFn={feedbackFn} />}
      </Grid>
    </Grid>
  );
}

interface PrePopulatedQuestionsProps {
  header: string;
  questions: string[];
  clickEvent: Function;
  loading: boolean;
  borderPadding: string;
}

export function PrePopulatedQuestions({
  header,
  questions,
  clickEvent,
  loading,
  borderPadding,
}: PrePopulatedQuestionsProps) {
  const questions_empty = questions.length == 0;

  if (loading) {
    return (
      <Grid
        item
        xs={12}
        textAlign="center"
        sx={{
          backgroundColor: colors_v2.background.secondary,
          padding: borderPadding,
        }}
      >
        <CircularProgress
          sx={{
            height: "100%",
            fontSize: fontSizes.primary.icons,
          }}
        />
      </Grid>
    );
  } else if (questions_empty) {
    return <div />;
  } else {
    return (
      <Grid
        container
        direction="row"
        rowSpacing={0}
        columnSpacing={0}
        display="flex"
        justifyContent="center"
        alignItems="center"
        sx={{
          backgroundColor: colors_v2.background.secondary,  
          color: "black",
          textAlign: "left",
          fontSize: fontSizes.secondary.subtitle,
          margin: "0 auto",
          width:"100%",
          minWidth:"100%",
        }}
      >
        <Grid
        container
        direction="row"
        alignItems="center"
        xs={12}
        sx={{
          backgroundColor: "white",
          padding:"16px",
          borderRadius: fontSizes.secondary.borderRadius,
          display:"flex",
          alignItems:"center",
        }}
        >
        <Grid item xs={1.5}>
          <QuestionAnswerIcon
            sx={{
              color: colors_v2.agent.secondary.darkGray,
              fontSize: fontSizes.secondary.icons,
              marginRight:"4px",
            }}
          />
        </Grid>
        <Grid item xs={10.5}>
          <span
            style={{
              color: colors_v2.agent.secondary.darkGray,
              fontSize: fontSizes.secondary.subtitle,
            }}
          >
            {/** recommended changes header**/}
            <b>{header}</b>
          </span>
        </Grid>
        <Grid item xs={12} />
        <Grid item xs={12} />
        {loading && (
          <Grid item xs={12}
          sx={{padding:"10px"}}
          >
            <CircularProgress
              size={36}
              sx={{
                height: "100%",
                fontSize: fontSizes.secondary.icons,
                color: colors_v2.agent.tertiary.tint,
              }}
            />
          </Grid>
        )}
        {!loading && (
          <Grid item xs={12}>
            <PrePopulatedQuestionsList
              questions={questions}
              clickEvent={clickEvent}
            />
          </Grid>
        )}
        </Grid>
        <Grid item xs={12}>
          <Divider sx={{ borderBottomWidth: "3px" }} />
        </Grid>
      </Grid>
    );
  }
}

/////////////
// GENERAL //
/////////////

interface PrimaryContentProps {
  questionHeader: ReactNode;
  questionMessage: ReactNode;
  progressStatus: ReactNode;
  agentOutput: ReactNode;
  chatMessages: ReactNode[];
}

// The main content on the center of the page:
//   1. Question Header
//   2. Reprinted Question
//   3. Progress Bar
//   4. Agent Output
//      4.a. Summary
//      4.b. Plot (Optional)
export function PrimaryContent({
  questionHeader,
  questionMessage,
  progressStatus,
  agentOutput,
  chatMessages,
}: PrimaryContentProps) {
  const chatContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [chatMessages]);

  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <div className="flex flex-col w-full h-screen overflow-auto" ref={chatContainerRef}>
      {/* QUESTION HEADER */}
      <div className="w-full p-4 mb-2">
        {questionHeader}
      </div>
      {/* REPRINTED QUESTION - HumanChatMessage */}
      <div className="w-full pt-2 mt-3 flex flex-wrap">
        {questionMessage}
      </div>
      {/* PROGRESS STATUS */}
      <div className="w-full">
        {progressStatus}
      </div>
      {/* LLM AGENT OUTPUT */}
      <div className="w-full">
        {agentOutput}
      </div>

      <div className="flex flex-col items-center justify-center m-2 mb-4">
        <button
          onClick={() => setSearchOpen(!searchOpen)}
          className="text-black hover:text-black"
        >
          {searchOpen ? 'Close Web Search' : 'Open Web Search'}
        </button>

        {searchOpen && (
          <div className="fixed inset-0 flex items-center justify-center z-50">
            <Sheet
              isOpen={searchOpen}
              onClose={() => setSearchOpen(false)}
              snapPoints={[450, 300, 100]}
              initialSnap={1}
              className="w-1/2 max-w-lg mx-auto"
              style={{ width: '50%', margin: 'auto' }}
            >
              <Sheet.Container>
                <Sheet.Header />
                <Sheet.Content>
                  <div className="overflow-y-auto h-full">
                    <WebSearch />
                  </div>
                </Sheet.Content>
              </Sheet.Container>
              <Sheet.Backdrop />
            </Sheet>
          </div>
        )}
      </div>
    </div>
  );
}

interface questionHeaderProps {
  pageTitle: string;
  pageDescription: string;
  loadingBool: boolean;
  showQuestionBool: boolean;
  showQuestionFn: Function;
  inputText: string;
  inputTextFn: Function;
  queryButtonClickFn: Function;
  borderPadding: string;
}

export function QuestionHeader({
  pageTitle,
  pageDescription,
  loadingBool,
  showQuestionBool,
  showQuestionFn,
  inputText,
  inputTextFn,
  queryButtonClickFn,
  borderPadding,
}: QuestionHeaderProps) {
  if (!showQuestionBool) {
    return (
      <ButtonUnhideQuestionHeader
        showQuestionBool={showQuestionBool}
        clickEvent={showQuestionFn}
        borderPadding="20px"
      />
    );
  } else {
    return (
      <Grid item xs={12} sx={{ flexGrow:1}}>
        <Typography variant="h4" component="h1" >
          <span
            style={{ 
              fontSize: fontSizes.primary.title, 
              fontWeight: "bold", 
                }}
          >
            {pageTitle}
          </span>
        </Typography>
        
        <Typography
          variant="p"
          component="p"
          style={{paddingBottom:"20px"}}
        >
          <span style={{ fontSize: fontSizes.primary.subtitle }}>
            {pageDescription}
          </span>
        </Typography>

        <TextField
          id="datainsights-input"
          label={"Ask the " + agentName + " something"}
          variant="outlined"
          fullWidth
          multiline
          onChange={(e) => inputTextFn(e.target.value)}
          inputProps={{
            style: {
              display:"flex",
              fontSize: fontSizes.primary.paragraph,
              paddingTop: "20px",
              paddingLeft: "10px",           
            },
          }} // font size of input text
          InputLabelProps={{
            style: { fontSize: fontSizes.primary.paragraph },
          }} // font size of input label
          sx={{
            minHeight: "100px",
            maxHeight:"200px",
            "& .MuiOutlinedInput-root": {
              fontSize: fontSizes.primary.paragraph,
              "&.Mui-focused fieldset": {
                borderColor: colors_v2.client.tertiary,
              },
            },
            "& .MuiInputLabel-outlined": {
              // Regular label color
              // fontSize: fontSizes.primary.paragraph,
              fontSize: "12px",
              color: "grey",
              fontWeight: "400px",
              "&.Mui-focused": {
                // Label color when input is focused
                color: colors_v2.client.tertiary,
              },
            },
            textarea: {
              boxShadow: "none",
            },
          }}
          rows={5}
        />
        <Box sx={{ p: 2, display: "flex", justifyContent: "center" }}>
          <Button
            variant="contained"
            onClick={() => queryButtonClickFn(inputText)}
            disabled={loadingBool}
            sx={{
              backgroundColor: colors_v2.client.tertiary,
              "&:hover": { backgroundColor: colors_v2.agent.primary.tint },
              width: "600px",
              textAlign: "center",
            }}
          >
            <span style={{ fontSize: fontSizes.primary.paragraph }}
            className="font-sans font-bold leading-5"
            >
              Generate Answer
            </span>
          </Button>
        </Box>
      </Grid>
    );
  }
}

interface ButtonUnhideQuestionHeader {
  showQuestionBool: boolean;
  clickEvent: Function;
  borderPadding: string;
}

export function ButtonUnhideQuestionHeader({
  showQuestionBool,
  clickEvent,
  borderPadding,
}: ButtonUnhideQuestionHeader) {
  return (
    <Grid item xs={12}  alignItems="center" sx={{ height: "4px" }}>
      <List>
        <ListItemButton
          onClick={() => clickEvent(!showQuestionBool)}
          sx={{
            padding: "2px 8px",
            justifyContent: "left",
            backgroundColor: colors_v2.messages.question.background,
            ":hover": {
              cursor: "pointer",
            },
          }}
        >
          {/*
            To align the icons with question header, use the 1-1-8-2 layout.
          */}
          <Grid container alignItems="center" spacing={0}>
            <Grid item xs="auto">
              <ListItemIcon
              sx={{marginRight:'4px'}}
              >
                <QuestionAnswerIcon
                  sx={{
                    fontSize: fontSizes.primary.icons,
                    color: colors_v2.agent.tertiary.tint,
                  }}
                />
              </ListItemIcon>
            </Grid>
            <Grid item xs={8}>
              <span
                style={{
                  textAlign: "left",
                  fontSize: fontSizes.primary.paragraph,
                  color: colors_v2.agent.tertiary.tint,
                  display:"flex",
                  alignItems:'center',
                  height:'100%',
                }}
              >
                <b>Click here to ask another question</b>
              </span>
            </Grid>
          </Grid>
          <Grid item xs={2} />
        </ListItemButton>
      </List>
      <Divider sx={{ borderBottomWidth: "2px" }} />
    </Grid>
  );
}

interface SecondaryContentProps {
  recommendedPrompts: ReactNode;
  explanationSteps: ReactNode;
  chatHistory: ReactNode;
}

// The main content on the center of the page:
//   1. Recommended Prompts/Followup Prompts (combined)
//   2. Explanation Steps
//   3. Chat History
export function SecondaryContent({
  recommendedPrompts,
  explanationSteps,
  chatHistory,
}: SecondaryContentProps) {
  return (
    <Grid
      container
      direction="row"
      rowSpacing={0}
      columnSpacing={0}
      sx={{
        backgroundColor: colors_v2.background.secondary,
        fontSize: fontSizes.secondary.subtitle,
      }}
    >
      {/* RECOMMENDED/FOLLOWUP PROMPTS */}
      <Grid item xs={0.5}/>
      <Grid item xs={11.5} sx={{paddingBottom:"8px"}}>
        {recommendedPrompts}
      </Grid>
      {/* LLM AGENT THOUGHT PROCESS */}
      <Grid item xs={0.5}/>
      <Grid item xs={11.5} sx={{paddingBottom:"8px"}}>
        {explanationSteps}
      </Grid>
      {/* PREVIOUS USER QUESTIONS */}
      <Grid item xs={0.5}/>
      <Grid item xs={11.5} sx={{paddingBottom:"8px"}}>
        {chatHistory}
      </Grid>
    </Grid>
  );
}

interface StreamTextProps {
  speed: number;
  text: string;
}

function StreamText({ speed = 25, text = "test" }: StreamTextProps) {
  // NOT SURE WHY THIS WORKS BUT IT DOES .-.
  text = text[1] + text;
  const index = React.useRef(0);
  const [placeholder, setPlaceholder] = React.useState("");
  // const [placeholder, setPlaceholder] = React.useState(text[0]);

  React.useEffect(() => {
    function tick() {
      index.current++;
      setPlaceholder((prev: string) => prev + text[index.current]);
    }
    if (index.current < text.length - 1) {
      let addChar = setInterval(tick, speed);
      return () => clearInterval(addChar);
    }
  }, [placeholder, speed, text]);
  return <span>{placeholder}</span>;
}

export const FeedbackButtons = ({ feedbackFn }) => {
  const [selectedRating, setSelectedRating] = useState(null);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  const handleStarClick = (rating) => {
    setSelectedRating(rating);

    let feedback;
    if (rating <= 2) {
      feedback = "dislike";
    } else if (rating === 3) {
      feedback = "neutral";
    } else {
      feedback = "like";
    }

    feedbackFn(feedback);
    setFeedbackSubmitted(true);
  };

  return (
    <Box
      sx={{
        width: "100%",
        textAlign: "left",
        marginTop: "20px",
        paddingRight: "10%",
        display:"flex",
        flexDirection:"column",
        alignItems:"flex-end",
        justifyContent:"center",
      }}
    >
      <Typography
        variant="body1"
        style={{
          color: "#999999",
          fontSize: "14px",
          marginBottom: "10px",
        }}
      >
        How satisfied are you with the response?
      </Typography>
      <Box sx={{ display: "flex", alignItems: "center" }}>
        <List
          role="menubar"
          sx={{ display: "flex", flexDirection: "row", padding: 0, margin: 0 }}
        >
          {[1, 2, 3, 4, 5].map((rating) => (
            <ListItem role="none" key={rating} sx={{ padding: 0 }}>
              <ListItemButton
                onClick={() => handleStarClick(rating)}
                sx={{ minWidth: "36px", color: "#7FC5B1", padding: 0 }}
                disabled={feedbackSubmitted} // Disable buttons after submission
              >
                {selectedRating >= rating ? <StarIcon /> : <StarBorderIcon />}
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Box>
      {feedbackSubmitted && (
        <Typography sx={{ color: "#5B5B5B", marginTop: "10px" }}>
          Thank you for your feedback!
        </Typography>
      )}
    </Box>
  );
};


export const ProgressMessage = () => {
  return (
    <Grid
      container
      justifyContent="center"
      alignItems="center"
      sx={{
        width: "100%",
        height: "100%",
        padding:"10px"
      }}
    >
      <Grid item xs={3} />
      <Grid item xs={1}>
        <CircularProgress
          sx={{
            height: "100%",
            fontSize: fontSizes.primary.icons,
            color: colors_v2.agent.tertiary.tint,
          }}
        />
      </Grid>
      <Grid item xs={5}>
        <span style={{ color: colors_v2.agent.tertiary.tint }}>
          Please wait, I am processing your request...
        </span>
      </Grid>
      <Grid item xs={3} />
    </Grid>
  );
};

