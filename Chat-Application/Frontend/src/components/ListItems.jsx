
import React, { useEffect, useState } from 'react';
import GridOnIcon from '@mui/icons-material/GridOn';
import ListIcon from '@mui/icons-material/List';
import NoteIcon from '@mui/icons-material/Note';
import CheckBoxIcon from '@mui/icons-material/CheckBox';
import TextFieldsIcon from '@mui/icons-material/TextFields';
import { fontSizes, colors_v2 } from "../../config";
import { NavLink } from "react-router-dom";
import { Divider, ListItem, ListItemText, Collapse } from "@mui/material";
import HistoryIcon from "@mui/icons-material/History";
import CloseFullscreenIcon from '@mui/icons-material/CloseFullscreen';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useNavigate } from "react-router-dom";
import { useData } from "../Store"; // Import useData hook
import * as Muicon from "@mui/icons-material";
import ChatHistoryBox from './ChatHistoryBox';

export const icons = [];

export const generateIcons = (cardList) => {
  icons.length = 0; // Clear existing icons
  for (const card of cardList) {
    if (card.icon && Muicon[card.icon]) {
      const IconComponent = Muicon[card.icon];
      icons.push(React.createElement(IconComponent));
    } else {
      //console.error( "Icon not found or not defined");
      icons.push(React.createElement(ListIcon)); // Fallback icon
    }
  }
};

const normalizeArray = (arr) => {
  if (Array.isArray(arr) && Array.isArray(arr[0])) {
    return arr;
  }
  return [arr];
};

export function MainListItems() {
  const navigate = useNavigate();
  const { state, dispatch } = useData(); // Use useData hook

  if (!state || !dispatch) {
    return null;
  }

  console.log("State in MainListItems:", state);

  const cardList = state.cardList || [];

  useEffect(() => {
    generateIcons(cardList);
  }, [cardList]);

  const [selectedRole, setSelectedRole] = useState(state.user_profiles.profile);

  useEffect(() => {
    setSelectedRole(state.user_profiles.profile);
  }, [state.user_profiles.profile]);

  const navSidebarLink = (subCard, cardIndex, subcardIndex) => {
    navigate(subCard.route, {
      state: {
        persona: subCard.persona,
        title: subCard.title,
        description: subCard.description,
      },
    });
    applySelectedColor(cardIndex, subcardIndex);
  };

  if (cardList.length > 0 && cardList[0].title !== "Home") {
    console.warn(`Please check that the first item in the config cardList is for the "Home" page.`);
  }

  let cardListNoHome = cardList.filter((i) => i.title !== "Home");

  const resetSubcardsSelected = () => {
    if (cardListNoHome.length > 0 && cardListNoHome[0].title === "Admin" && cardListNoHome[0].subcards) {
      cardListNoHome[0].subcards[0].active = true;
    }
    if (selectedRole === "Document Owner") {
      cardListNoHome = cardList.filter((i) => i.title !== "Admin" && i.title !== "Home");
    } else if (selectedRole === "Auditor") {
      cardListNoHome = cardList.filter((i) => i.title !== "Document Owner" && i.title !== "Home");
      if (cardListNoHome.length > 0 && cardListNoHome[0].title === "Admin" && cardListNoHome[0].subcards) {
        cardListNoHome[0].subcards[0].active = false;
      }
    } else if (selectedRole !== "Document Owner" && selectedRole !== "Admin" && selectedRole !== "Auditor") {
      cardListNoHome = cardList.filter((i) => i.title !== "Admin" && i.title !== "Document Owner" && i.title !== "Home");
    } else {
      cardListNoHome = cardList.filter((i) => i.title !== "Home");
    }

    const allFalseSubcardsSelected = cardListNoHome.map((card) =>
      card.subcards ? Array(card.subcards.length).fill(false) : []
    );

    return allFalseSubcardsSelected;
  };

  const [openList, setOpen] = useState(Array(cardList.length).fill(false));
  const [subcardSelected, setSubcardSelected] = useState(resetSubcardsSelected());

  const handleOpenTasksClick = (index) => {
    let updatedOpenList = [...openList];
    updatedOpenList[index] = !updatedOpenList[index];
    setOpen(updatedOpenList);
  };

  const applySelectedColor = (cardIndex, subcardIndex) => {
    let updatedSubcardSelected = resetSubcardsSelected();
    if (updatedSubcardSelected[cardIndex]) {
      updatedSubcardSelected[cardIndex][subcardIndex] = true;
      setSubcardSelected(updatedSubcardSelected);
    } else {
      console.error("Card index out of bounds:", cardIndex);
    }
  };

  return (
    <div component="nav">
      {cardList.length > 0 && (
        <React.Fragment key={0}>
          <NavLink
            to={String(cardList[0].route)}
            style={{ textDecoration: "none", color: "inherit" }}
          >
            <ListItem>
              <ListIcon sx={{ color: colors_v2.agent.primary.tone }}>
                {icons[0]}
              </ListIcon>
              <ListItemText
                primary={cardList[0].title}
                primaryTypographyProps={{
                  fontWeight: "bold",
                  color: colors_v2.agent.primary.tone,
                }}
              />
            </ListItem>
          </NavLink>
          <Divider sx={{ borderBottomWidth: "2px" }} />
        </React.Fragment>
      )}
      <React.Fragment>
        {cardListNoHome.map((card, index) => {
          const normalizedSubcards = normalizeArray(card.subcards || []);
          return (
            <React.Fragment key={index}>
              <ListItem button onClick={() => handleOpenTasksClick(index)}>
                <ListIcon>{icons[index + 1]}</ListIcon>
                <ListItemText
                  primary={card.title}
                  primaryTypographyProps={{
                    fontWeight: "bold",
                    color: card.textcolor,
                  }}
                />
                {openList[index] ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </ListItem>
              <Collapse in={openList[index]} timeout="auto" unmountOnExit>
                <div component="div">
                  {normalizedSubcards.map((subcardGroup, subcardIndex) =>
                    subcardGroup.map((subcard, jndex) => (
                      <ListItem button key={jndex} onClick={() => navSidebarLink(subcard, index, jndex)}>
                        {subcard.active ? (
                          <div
                            sx={{
                              paddingLeft: 9,
                              backgroundColor:
                                subcardSelected[index] &&
                                subcardSelected[index][jndex]
                                  ? colors_v2.agent.secondary.tint
                                  : colors_v2.background.sidebar,
                            }}
                          >
                            <ListItemText primary={subcard.title} />
                          </div>
                        ) : null}
                      </ListItem>
                    ))
                  )}
                </div>
              </Collapse>
            </React.Fragment>
          );
        })}
      </React.Fragment>
    </div>
  );
}

export const secondaryListItems = <React.Fragment></React.Fragment>;

export function ChatHistoryList({
  chatTexts,
  chatIds,
  maxHeight = 200,
  borderPadding = "0px",
  rerunQuestionFn,
}) {
  const [selectedIndex, setSelectedIndex] = React.useState();

  const handleListItemClick = (event, index) => {
    setSelectedIndex(index);
    rerunQuestionFn(chatIds[index], chatTexts[index]);
  };

  const ChatHistoryHeader = () => (
    <div
      item
      xs={1.5}
    >
      <HistoryIcon
        sx={{
          color: colors_v2.agent.secondary.darkGray,
          fontSize: fontSizes.secondary.icons,
          padding: "4px",
        }}
      />
      <span
        style={{
          color: colors_v2.agent.secondary.darkGray,
          fontSize: fontSizes.secondary.subtitle,
        }}
      >
        <b>Chat History</b>
      </span>
    </div>
  );

  const ChatHistoryItem = ({ chatText, i }) => (
    <ListItem
      button
      selected={selectedIndex === i}
      onClick={(event) => handleListItemClick(event, i)}
      key={i}
    >
      <ListItemText
        primary={chatText}
        primaryTypographyProps={{
          fontSize: fontSizes.primary.paragraph,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      />
    </ListItem>
  );

  return (
    <div
      container
      rowSpacing={1}
      display="flex"
      justifyContent="center"
      sx={{
        padding: "4px",
      }}
    >
      <ChatHistoryBox />
      <div
        item
        xs={12}
        sm={10}
        sx={{
          backgroundColor: "#fff",
          padding: "16px",
          borderRadius: fontSizes.secondary.borderRadius
        }}
      >
        <ChatHistoryHeader />
        <div item xs={12}>
          <div
            sx={{
              minHeight: maxHeight,
              maxHeight: maxHeight,
              overflow: "auto",
              bgcolor: colors_v2.messages.recommended.background,
              padding:"8px",
            }}
          >
            <div>
              {chatTexts.map((chatText, i) => (
                <ChatHistoryItem chatText={chatText} i={i} key={i} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


export function PrePopulatedQuestionsList({ questions, clickEvent }) {
  const [selectedIndex, setSelectedIndex] = React.useState();

  const handleListItemClick = (event, index) => {
    setSelectedIndex(index);
    clickEvent(questions[index]);
  };

  return (
    <div component="nav" aria-label="pre populated questions">
      {questions.map((questionObj, i) => (
        <ListItem
          button
          selected={selectedIndex === i}
          onClick={(event) => handleListItemClick(event, i)}
          sx={{
            borderRadius: "5px",
            "&.Mui-selected": {
              backgroundColor: colors_v2.messages.recommended.background,
              color: "black",
            },
            "&.Mui-focusVisible": {
              backgroundColor: colors_v2.messages.recommended.background,
            },
            "&.Mui-selected:hover": {
              backgroundColor: colors_v2.messages.recommended.background,
            },
            ":hover": {
              backgroundColor: colors_v2.messages.recommended.background,
            },
            backgroundColor: colors_v2.messages.recommended.selected,
            mb: "10px",
            padding: "10px",
          }}
          key={i}
        >
          <ListItemText
            primary={questionObj.prompt}  // Assuming questionObj is an object with a key `prompt`
            primaryTypographyProps={{
              fontWeight: "bold",
              fontSize: fontSizes.secondary.paragraph,
              color: colors_v2.messages.recommended.text,
            }}
          />
        </ListItem>
      ))}
    </div>
  );
}


export default MainListItems;

