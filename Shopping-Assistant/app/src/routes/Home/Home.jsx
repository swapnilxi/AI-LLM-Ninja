
import React, { useState } from "react";
import "./Home.css";
import CardGrid from "./CardGrid";
import { Box } from "@mui/material";
import Grid from "@mui/material/Grid";
import Container from "@mui/material/Container";
import RAGAnalyticsComponent from "../../components/RagAnalytics";

function Home() {
    return (
        <Box
            sx={{
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                alignItems: "center", // Center horizontally
                marginTop: "10%",
            }}
        >
            <Container>
                <Grid>
                    <CardGrid />
                </Grid>
            </Container>
        </Box>
    );
}

export default Home;