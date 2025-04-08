import React from "react";
import Grid from "@mui/material/Grid";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import { useNavigate } from "react-router-dom";
import { useTheme } from "@mui/material/styles";
import {
  cardList,
  colors_v2,
  fontSizes,
  agentName,
  homePageBackgroundWithoutPath
} from "../../../config";
import { Divider } from "@mui/material";
import { icons } from "../../components/ListItems";
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import { useData } from "../../Store";

function CardGrid() {
  console.log("CardGrid component rendering");

  const theme = useTheme();
  const navigate = useNavigate();

  const [activeCard, setActiveCard] = React.useState(null);
  const { state, dispatch } = useData();
  const [roleBasedCardList, setRoleBasedCardList] = React.useState(cardList || []);
  const [openList, setOpen] = React.useState(Array(roleBasedCardList.length).fill(false));

  console.log("State in CardGrid:", state);

  React.useEffect(() => {
    console.log("User profiles state:", state.user_profiles);
    if (state.user_profiles && state.user_profiles.profile) {
      updateCardList(state.user_profiles.profile);
    }
  }, [state.user_profiles.profile]);

  const updateCardList = (updatedRole) => {
    console.log("Updating card list for role:", updatedRole);
    let updatedList = cardList;
    if (updatedRole === "Document Owner") {
      updatedList = cardList.filter(i => i.title !== "Admin");
    } else if (updatedRole === "Auditor") {
      updatedList = cardList.filter(i => i.title !== "Document Owner");
    } else if (updatedRole !== "Document Owner" && updatedRole !== "Admin" && updatedRole !== "Auditor") {
      updatedList = cardList.filter(i => i.title !== "Admin" && i.title !== "Document Owner");
    }
    setRoleBasedCardList(updatedList);
    setActiveCard(null);
    setOpen(Array(updatedList.length).fill(false));
  };

  const handleSubCardClick = (index) => {
    const oldSubCardVal = openList[index];
    const updatedOpenList = Array(roleBasedCardList.length).fill(false);
    updatedOpenList[index] = !oldSubCardVal;
    setOpen(updatedOpenList);
    setActiveCard(updatedOpenList[index] ? roleBasedCardList[index] : null);
  };

  const navSubCardClick = (currentCard, subCardIndex) => {
    navigate(
      currentCard.subcards[subCardIndex].route,
      {
        state: {
          persona: currentCard.subcards[subCardIndex].persona,
          title: currentCard.subcards[subCardIndex].title,
          description: currentCard.subcards[subCardIndex].description
        }
      }
    );
  };

  return (
    <Grid
      container
      display="flex"
      direction="row"
      rowSpacing={5}
      sx={{
        width: "100%",
        height: "100%",
      }}
    >
      {/* Top layer of the container is the title and subtitle */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          height: "50vh",
          width: "100%",
          backgroundImage: `url("/imgs/${homePageBackgroundWithoutPath}")`,
          backgroundSize: "cover",
          backgroundRepeat: "no-repeat",
          backgroundPosition: "center",
        }}
      >
        <Grid
          item
          xs={6}
          sx={{
            width: "100%",
            height: "100%",
          }}
        >
          <Typography
            variant="h3"
            component="h3"
            sx={{
              textAlign: "start",
              color: colors_v2.card.primary.text,
              padding: "30px",
              fontSize: fontSizes.home.title,
              // backgroundColor: colors_v2.card.primary.background,
              width: "98%",
              marginTop: "5%",
              borderRadius: "5px",
            }}
          >
            <AutoAwesomeOutlinedIcon />
            {agentName}
            <AutoAwesomeOutlinedIcon />
          </Typography>
          <Typography
            sx={{
              textAlign: "start",
              color: colors_v2.card.primary.text,
              padding: "30px",
              fontSize: fontSizes.home.subtitle,
              // backgroundColor: colors_v2.card.primary.background,
              width: "98%",
              borderRadius: "5px",
            }}
          >
            Driving the industry forward by unlocking the powers of generative
            AI within enterprise search.
          </Typography>
        </Grid>
        <Grid item xs={6} sx={{ height: "100%" }}></Grid>
      </Box>

      {/* Two subcontainers: Left half is personas, right is tasks */}
      {/* PERSONAS container */}
      <Grid item xs={6} sx={{ height: "100%" }}>
        <Grid
          container
          display="flex"
          rowSpacing={2}
          sx={{
            width: "98%",
            height: "100%",
          }}
        >
          {/* LOOPS OVER THE PERSONAS */}
          {roleBasedCardList.map((card, cardIndex) =>
            cardIndex > 0 ? (
              <Grid
                key={cardIndex}
                item
                xs={12}
                sx={{
                  width: "100%",
                  height: "100%",
                }}
              >
                <Grid container columnSpacing={6}>
                  <Grid item xs={12}>
                    {/* changing card with box */}
                    <Box
                      key={cardIndex}
                      sx={{
                        justifyContent: "center",
                        bgcolor: "transparent", // Transparent background
                        color: card.textcolor,
                        display: "flex",
                        flexDirection: "row", // Align items in a row
                        alignItems: "center",
                        height: "125px",
                        width: "100%",
                        transition:
                          "transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out",
                        "&:hover": {
                          transform: "scale(1.05)",
                          boxShadow: "0 4px 20px 0 rgba(0,0,0,0.12)",
                        },
                        cursor: "pointer",
                        padding: "10px",
                        borderRadius: "6px",
                      }}
                      onClick={() => handleSubCardClick(cardIndex)}
                    >
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          backgroundColor: colors_v2.client.primary,
                          padding: "10px",
                          borderRadius: "5px",
                          color: "white",
                          marginRight: "20px",
                          height: "60px",
                          minWidth: "200px",
                        }}
                      >
                        <Box sx={{ marginRight: "5px" }}>
                          {icons[cardIndex]}
                        </Box>
                        <b>{card.cardtitle}</b>
                      </Box>
                      <Box sx={{ flexGrow: 1, textAlign: "left" }}>
                        {card.description}
                      </Box>
                    </Box>
                    {/* card till here */}
                  </Grid>
                </Grid>
              </Grid>
            ) : null
          )}
        </Grid>
      </Grid>
      {/* TASKS container */}
      <Grid item xs={6} sx={{ height: "100%", width: "95%" }}>
        {activeCard != null && activeCard.subcards && (
          <Grid container direction="column" rowSpacing={2}>
            {activeCard.subcards.map((subCard, subCardIndex) => {
              return subCard.active ? (
                <Grid item key={subCardIndex}>
                  <Card
                    orientation="horizontal"
                    sx={{
                      justifyContent: "center",
                      bgcolor: "rgba(255,255,255,0.9)",
                      color: activeCard.textcolor,
                      display: "flex",
                      flexDirection: "column",
                      height: "125px",
                      width: "100%",
                      transition:
                        "transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out",
                      "&:hover": {
                        transform: "scale(1.05)",
                        boxShadow: "0 4px 20px 0 rgba(0,0,0,0.12)",
                      },
                    }}
                    onClick={() => navSubCardClick(activeCard, subCardIndex)}
                  >
                    <CardContent>
                      <Grid
                        container
                        display="flex"
                        sx={{
                          alignItems: "center",
                          textAlign: "center",
                        }}
                      >
                        <Grid item xs={4}>
                          <i>{subCard.title}</i>
                        </Grid>
                        <Grid item xs={8}>
                          {subCard.description}
                        </Grid>
                      </Grid>
                    </CardContent>
                  </Card>
                </Grid>
              ) : null;
            })}
          </Grid>
        )}
      </Grid>
    </Grid>
  );
}

export default CardGrid;
