import * as ReactDOM from "react-dom/client";
import React, { useContext } from "react";
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import { deploymentBaseUrl } from "../config";
import Root from "./routes/root";
import ErrorPage from "./error-page";
import Home from "./routes/Home/Home";
import DataInsights from "./routes/DataInsights/DataInsights";
import DocumentSearchAndSummarization from "./routes/Documentsearchandsummarization/DocumentSearchandSummarization";
import RAGAnalyticsComponent from "./components/RagAnalytics";
import "./index.css";
import { tabTitle } from "./../config";
import 'bootstrap/dist/css/bootstrap.min.css';
import { DataProvider, DataContext } from './Store'; // Ensure DataContext is imported
import UploadComponent from "./components/UploadComponent";
import { MantineProvider } from "@mantine/core";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import "@mantine/core/styles.css";

// Overwrites the name of the tab
document.title = tabTitle;

const router = createBrowserRouter([
    {
        path: "/",
        element: <Root />,
        errorElement: <ErrorPage />,
        children: [
            {
                path: "",
                element: <Home />,
            },
            {
                path: "datainsight",
                element:
                    <PrivateRoute>
                        <DataInsights />
                    </PrivateRoute>
            },
            {
                path: "docsearch",
                element:
                    <PrivateRoute>
                        <DocumentSearchAndSummarization />
                    </PrivateRoute>
            },
            {
                path: "raganalytics",
                element: <PrivateRoute> <RAGAnalyticsComponent /></PrivateRoute>,
            },
            {
                path: "upload",
                element: <PrivateRoute><UploadComponent /></PrivateRoute>,
            },
        ],
    },
], {
    basename: deploymentBaseUrl
});

function PrivateRoute({ children }) {
    const { state } = useContext(DataContext);
    console.log("PrivateRoute State:", state); // Debugging log
    return state.user_profiles.profile !== '' ? children : <Navigate to="/" />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
        <DataProvider>
            <MantineProvider>
                <RouterProvider router={router} />
            </MantineProvider>
        </DataProvider>
    </React.StrictMode>,
);
