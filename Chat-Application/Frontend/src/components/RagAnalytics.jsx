
import React from "react";
import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import Plot from "react-plotly.js";
import { Button, ButtonGroup } from "@mui/material";
import { fontSizes, colors_v2,  } from "../../config";
import { AgGridReact } from "ag-grid-react";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";
import Container from "react-bootstrap/Container";
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import "./RAGAnalyticsComponent.css";
import Box from "@mui/material/Box";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import FormControl from "@mui/material/FormControl";
import Select from "@mui/material/Select";
import { Text } from "@mantine/core";
//import { AgGridMultiSelectEditor } from "./AgGridMultiSelectEditor";
import "./AgGridStyles.css";
import VisibilityIcon from '@mui/icons-material/Visibility';
import UpdateIcon from '@mui/icons-material/Update';
import BlockIcon from '@mui/icons-material/Block';
import CheckIcon from '@mui/icons-material/Check';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import DoneAllIcon from '@mui/icons-material/DoneAll';
import { CircularProgress, Grid , Alert} from "@mui/material";
import { DataProvider } from "../Store";
import { transformProfileOptions, handleErrorResponse } from "../utils";
import { postRagAnalyticsData, postUpdateEmbeddingFlags, postUpdateEmbeddingRoles } from "../services/api";
import { ThemeProvider, createTheme } from '@mui/material/styles';
import Snackbar from '@mui/material/Snackbar';


export default function RAGAnalyticsComponent(props) {
  const [masterTableData, setMasterTableData] = useState([]);
  const [selectedTableData, setSelectedTableData] = useState([]);
  const [unselectedTableData, setUnselectedTableData] = useState([]);

  const [loading, setIsLoading] = useState(false);
  const [hueCol, setHueCol] = useState("relevance_score");
  const [xAxisCol, setXAxisCol] = useState("coord_1");
  const [yAxisCol, setYAxisCol] = useState("coord_2");
  const [zAxisCol, setZAxisCol] = useState("coord_3");
  const plotRef = useRef();
  const [filterData, setFilterData] = useState([]);
  const [groupedByDocumentMasterData, setGroupedByDocumentMasterData] = useState([]);
  const [usingGroupedData, setUsingGroupedData] = useState(true);
  const [updatingTableData, setUpdatingTableData] = useState(false);
  const gridRef = useRef();
  const [state, dispatch] = React.useContext(DataProvider);
  const allAccessRoles = transformProfileOptions(state.user_profiles.profileOptions).map((i) => i["label"]).filter((i) => i.length > 0);
  const [isSelectingAllRows, setIsSelectingAllRows] = useState(true);
  const [openErrorSnackBar, setOpenErrorSnackBar] = React.useState(false);
  const [openSnackBar, setOpenSnackBar] = React.useState(false);

  const [displayErrorMessageOnSnackBar, setDisplayErrorMessageOnSnackBar] = useState("");
  const [displayMessageOnSnackBar, setDisplayMessageOnSnackBar] = useState("");

  const [activeView, setActiveView] = useState("document");
  const handleViewChange = (view) => {
    setActiveView(view);
    if (view === "pageSegment") {
      displayChunkView();
    } else {
      displayDocumentView();
    }
  };

  const handleClose = () => {
    setOpenSnackBar(false);
    setOpenErrorSnackBar(false);
  };

  const theme = createTheme({
    palette: {
      primary: {
        main: '#DD1B21'
      },
      secondary: {
        main: '#EB5936'
      }
    }
  });

  const handleHueColChange = (event) => {
    setHueCol(event.target.value);
    sortBySpecifiedColumn(event.target.value);
  };

  const handleXAxisChange = (event) => {
    setXAxisCol(event.target.value);
  };

  const handleYAxisChange = (event) => {
    setYAxisCol(event.target.value);
  };

  const handleZAxisChange = (event) => {
    setZAxisCol(event.target.value);
  };

  const changeHandler = async () => {
    setIsLoading(true);
    try {
       const ragAnalyticsDataResponse = await postRagAnalyticsData({
         user_id: "analyst_123",
         chat_id: 123,
         model_id: "gpt-35-turbo",
         mode: "docsearch",
         persona: "Strategist",
         use_cache: false,
         query:
           "FEMA is not allowed to provide disaster assistance for certain losses covered by the U.S. Small Business Administration (SBA) disaster loans. The SBA provides low-interest disaster loans to individuals and",
       });

      let buttonText = "Rag Analytics";
      const errorString = handleErrorResponse(buttonText, ragAnalyticsDataResponse);
      if (errorString !== "") {
        setDisplayErrorMessageOnSnackBar(errorString);
        setOpenErrorSnackBar(true);
        return;
      }

      ragAnalyticsDataResponse.map((i) => (i["discarded"] = 0));
      ragAnalyticsDataResponse.map((i) => (i["selected"] = 0));
      ragAnalyticsDataResponse.map((i) => (i["page"] = parseInt(i["page"])));
      ragAnalyticsDataResponse.map(
        (i) =>
          (i["relevance_score"] = parseFloat(i["relevance_score"]).toFixed(2))
      );
      ragAnalyticsDataResponse.map(
        (i) =>
          (i["feedback_score"] = parseFloat(i["feedback_score"]).toFixed(2))
      );
      ragAnalyticsDataResponse.map(
        (i) =>
          (i["avg_feedback_score"] = parseFloat(
            i["avg_feedback_score"]
          ).toFixed(2))
      );
      ragAnalyticsDataResponse.map(
        (i) => (i["total_number_used"] = parseInt(i["total_number_used"]))
      );
      ragAnalyticsDataResponse.map((i) => (i["quarantine"] = parseInt(i["quarantine"])));
      ragAnalyticsDataResponse.map(
        (i) =>
          (i["avg_relevance_score_by_source"] = parseFloat(
            i["avg_relevance_score_by_source"]
          ).toFixed(2))
      );
      ragAnalyticsDataResponse.map(
        (i) =>
          (i["avg_feedback_score_by_source"] = parseFloat(
            i["avg_feedback_score_by_source"]
          ).toFixed(2))
      );
      ragAnalyticsDataResponse.map((i) => {
        if (typeof i["access_roles"] === "string") {
          i["access_roles"] = i["access_roles"].replace(/['"]+/g, '').split(",").map(role => role.trim());
        } else if (!Array.isArray(i["access_roles"])) {
          i["access_roles"] = [i["access_roles"]];
        }
        return i;
      });
      ragAnalyticsDataResponse.map((i) => (i["source"] = i["source"]?.split("/").pop()));
      const groupedData=groupData(ragAnalyticsDataResponse);
      setUnselectedTableData(ragAnalyticsDataResponse);
      setMasterTableData(ragAnalyticsDataResponse);
      setFilterData(groupedData);
      setGroupedByDocumentMasterData(groupedData);
      setIsLoading(false);
    } catch (error) {
      console.error("Error fetching data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const effectRan = useRef(false);

  useEffect(() => {
    if (!effectRan.current) {
      changeHandler();
      displayDocumentView();
    }
    return () => (effectRan.current = true);
  }, []);

  // Column Definitions: Defines the columns to be displayed.
  const colDefaultProps = { filter: true,filterParams: {buttons: ["reset", "apply"],}, };
 
  const idColumn = { field: "id", hide: true, ...colDefaultProps, };
  const sourceColumn = { field: "source", headerName: "File Name", checkboxSelection: true, ...colDefaultProps, };
  const pageColumn = { field: "page", ...colDefaultProps, };
  const documentColumn = { field: "document", headerName: "Raw Text", ...colDefaultProps, };
  const relevanceScoreColumn = { field: "relevance_score", headerName: "Relevance", filter: "agNumberColumnFilter"
                                 ,filterParams: { buttons: ["reset", "apply"], },};
  const feedbackScoreColumn = { field: "feedback_score", headerName: "User Satisfaction",  filter: "agNumberColumnFilter"
                                ,filterParams: { buttons: ["reset", "apply"], },};
  const avgFeedbackScoreColumn = { field: "avg_feedback_score", headerName: "Average User Satisfaction", ...colDefaultProps, };
  const totalNumberUsedColumn = { field: "total_number_used", headerName: "Total Number Used", ...colDefaultProps, };
  const quarantineColumn = { field: "quarantine", hide: true, ...colDefaultProps, };
  const avg_relevance_score_by_sourceColumn = { field: "avg_relevance_score_by_source",headerName: "Relevance Grouped by Documents",
                                                filter: "agNumberColumnFilter",filterParams: { buttons: ["reset", "apply"],},};
  const avg_feedback_score_by_sourceColumn = { field: "avg_feedback_score_by_source",headerName: "User Satisfaction Grouped by Documents",
                                               filter: "agNumberColumnFilter", filterParams: { buttons: ["reset", "apply"], }, };
  const uploaderColumn = { field: "uploader_role", headerName: "Uploader Role", ...colDefaultProps, };
  const access_rolesColumn = {
    field: "access_roles",
    headerName: "Access Roles",
    width: 150,
    cellEditor: AgGridMultiSelectEditor,
    editable: true,
    // cellEditorParams: { options: [...extraDropDownOptions, ...allAccessRoles] },
    minWidth: 300,
    maxWidth: 350,
    flex: 2,
    valueFormatter: (params) => {
      return Array.isArray(params.value) ? params.value.join(", ") : params.value;
    },
    cellRenderer: (params) => {
      if (!params.value || params.value.length <= 0) {
        return <Text size="sm">Click to tag access roles</Text>;
      }
      return <Text size="md">{Array.isArray(params.value) ? params.value.join(", ") : params.value}</Text>;
    },
  };
  const creation_dateColumn = { field: "creation_date", headerName: "Date Created", ...colDefaultProps, };

  const colDefs = useMemo(() => {
    const withPageCol = [
      idColumn, sourceColumn, pageColumn, documentColumn, relevanceScoreColumn, feedbackScoreColumn, avgFeedbackScoreColumn,
      totalNumberUsedColumn, quarantineColumn, creation_dateColumn, avg_relevance_score_by_sourceColumn, avg_feedback_score_by_sourceColumn,
      uploaderColumn, access_rolesColumn
    ];
  
    const withoutPageCol = [
      idColumn, sourceColumn, documentColumn, relevanceScoreColumn, feedbackScoreColumn, avgFeedbackScoreColumn,
      totalNumberUsedColumn, quarantineColumn, creation_dateColumn, avg_relevance_score_by_sourceColumn, avg_feedback_score_by_sourceColumn,
      uploaderColumn, access_rolesColumn
    ];
  
    return usingGroupedData ? withoutPageCol : withPageCol;
  }, [usingGroupedData]);
  
  const togglePageCol=()=>{
    setUsingGroupedData(!usingGroupedData);
  }

  const unselectedDataX = filterData.filter((t) => t["selected"] == 0).map((item) => item[xAxisCol]);
  const unselectedDataY = filterData.filter((t) => t["selected"] == 0).map((item) => item[yAxisCol]);
  const unselectedDataZ = filterData.filter((t) => t["selected"] == 0).map((item) => item[zAxisCol]);
  const unselectedHueVar = filterData.filter((t) => t["selected"] == 0).map((item) => item[hueCol]);
  const unselectedSourceArray = filterData.filter((t) => t["selected"] == 0).map((item) => item["source"]);
  const unselectedPageArray = filterData.filter((t) => t["selected"] == 0).map((item) => item["page"]);

  let unselectedDataLabels = [];
  for (let i = 0; i < unselectedSourceArray.length; i++) {
    let dl = "Source : " + unselectedSourceArray[i] + "\nPage: " + unselectedPageArray[i];
    unselectedDataLabels.push(dl);
  }

  const selectedDataX = filterData.filter((t) => t["selected"] == 1).map((item) => item[xAxisCol]);
  const selectedDataY = filterData.filter((t) => t["selected"] == 1).map((item) => item[yAxisCol]);
  const selectedDataZ = filterData.filter((t) => t["selected"] == 1).map((item) => item[zAxisCol]);
  const selectedHueVar = filterData.filter((t) => t["selected"] == 1).map((item) => item[hueCol]);
  const selectedSourceArray = filterData.filter((t) => t["selected"] == 1).map((item) => item["source"]);
  const selectedPageArray = filterData.filter((t) => t["selected"] == 1).map((item) => item["page"]);

  let selectedDataLabels = [];
  for (let i = 0; i < selectedSourceArray.length; i++) {
    let dl = "Source : " + selectedSourceArray[i] + "\nPage: " + selectedPageArray[i];
    selectedDataLabels.push(dl);
  }
  if (sessionStorage.getItem("rowIds") == null) {
    sessionStorage.setItem("rowIds", "");
  }

  const onSelectionChanged = useCallback((event) => {
    const selectedData = gridRef.current.api.getSelectedRows();
    let rowIDs = [];
    selectedData.forEach((item) => {
      rowIDs.push(item["id"]);
    }, []);

    if (rowIDs.length > 1 && !usingGroupedData && event.source !== "apiSelectAllCurrentPage") {
      let firstSelectedItem = filterData.filter((t) => t["id"] == rowIDs[0]);
      let firstSelectedAccessRoles = firstSelectedItem[0]["access_roles"];
      let filterDataToUpdate = filterData;
      
      rowIDs.forEach((id) => {
        filterDataToUpdate.filter((t) => t["id"] == id)[0]["access_roles"] = firstSelectedAccessRoles;
      });

      setFilterData(filterDataToUpdate);

      gridRef.current.api.redrawRows();
      setDisplayMessageOnSnackBar('Please ensure to click the "Update Access Roles" button after modifying access roles to save changes permanently.')
      setOpenSnackBar(true);
    }
    
    sessionStorage.setItem("rowIds", rowIDs.join(","));
  }, [filterData]);

  const sortByCreationDate = useCallback(() => {
    gridRef.current.api.applyColumnState({
      state: [{ colId: "creation_date", sort: "desc" }],
      defaultState: { sort: null },
    });
  }, []);

  const sortBySpecifiedColumn = (columnToSortBy) => {
    gridRef.current.api.applyColumnState({
      state: [{ colId: columnToSortBy, sort: "desc" }],
      defaultState: { sort: null },
    });
  }

  const getRowStyle = (params) => {
    const data = { ...params.data };
    const quarantine = data.quarantine;
    let style = { 'text-align': 'left' };
    if (quarantine === 1) {
      return { ...style, background: "#ff7979", color: "white" };
    }
    if (quarantine === 0) {
      return { ...style, background: "white", color: "black" };
    }
    return undefined;
  };

  const handleFilter = (event) => {
    let savedFilterModel = gridRef.current.api.getFilterModel();
    let keys = Object.keys(savedFilterModel);
    let arr = [];
    if (keys.length > 0) {
      for (let i = 0; i < masterTableData.length; i++) {
        const data = masterTableData[i];
        const value = savedFilterModel[keys[0]].filter;
        const search = data[keys[0]];
        try {
          if (search.indexOf(value) > -1) arr.push(data);
        } catch (error) {}
      }
      setFilterData(arr);
    } else {
      setFilterData(masterTableData);
    }
  };

  const onUpdateViewButtonClick = () => {
    let idsSelected = sessionStorage.getItem("rowIds").split(",");
    filterData.map((i) => (i["selected"] = 0));
    if (idsSelected.length > 1 || idsSelected[0] != "") {
      idsSelected.forEach((id) => {
        filterData.filter((t) => t["id"] == id)[0]["selected"] = 1;
      });
    }
    setSelectedTableData(masterTableData.filter((t) => t["selected"] == 1));
    setUnselectedTableData(masterTableData.filter((t) => t["selected"] == 0));
  }

  const onSelectAllOnCurrentPageButtonClick = () => {
    setIsSelectingAllRows(!isSelectingAllRows);
    if (isSelectingAllRows) {
      gridRef.current.api.selectAllOnCurrentPage();
    } else {
      gridRef.current.api.deselectAllOnCurrentPage();
    }
  }

  const onQuarantineButtonClick = async (event) => {
    setUpdatingTableData(true);
    const buttonText = event.currentTarget.textContent;
    let idsSelected = sessionStorage.getItem("rowIds").split(",");
    let idsQuarantined = [];
    
    if (idsSelected == "") {
      setUpdatingTableData(false);
      return;
    }

    if (!usingGroupedData) {
      idsSelected.forEach((id) => {
        if (filterData.filter((t) => t["id"] == id)[0]["quarantine"] == 0) {
          idsQuarantined.push(id);
        }
      });
    }
    else {
      idsSelected.forEach((id) => {
        const matchingRecordEmbeddings = filterData.filter((t) => t["source"] === id)[0].embedding_ids;
        idsQuarantined = [...idsQuarantined, ...matchingRecordEmbeddings];
      });
    }

    let idsQuarantinedText = idsQuarantined.join(", ");

    if (idsQuarantined.length > 0) {
      const quarantineResponse = await postUpdateEmbeddingFlags({
        persona: "Strategist",
        ids_to_update: idsQuarantinedText,
        flag_name: "quarantine",
        flag_update_mode: "raise_flag"
      });
      
      const errorString = handleErrorResponse(buttonText, quarantineResponse);
      if (errorString !== "") {
        setDisplayErrorMessageOnSnackBar(errorString);
        setOpenErrorSnackBar(true);
        return;
      }
      else{
        idsSelected.forEach((id) => {
          if (filterData.filter((t) => t["id"] == id)[0]["quarantine"] == 0) {
            filterData.filter((t) => t["id"] == id)[0]["quarantine"] = 1;
          }
        });

        if (usingGroupedData) {
          idsQuarantined.forEach((id) => {
            masterTableData.filter((t) => t["id"] == id)[0]["quarantine"] = 1;
          });
        }

        gridRef.current.api.deselectAll();
      }
    }

    setUpdatingTableData(false);
    setFilterData(filterData);
    gridRef.current.api.redrawRows();
  }

  const onUnquarantineButtonClick = async (event) => {
    setUpdatingTableData(true);
    const buttonText = event.currentTarget.textContent;
    let idsSelected = sessionStorage.getItem("rowIds").split(",");
    let idsUnquarantined = [];
    
    if (idsSelected == "") {
      setUpdatingTableData(false);
      return;
    }

    if (!usingGroupedData) {
      idsSelected.forEach((id) => {
        if (filterData.filter((t) => t["id"] == id)[0]["quarantine"] == 1) {
          idsUnquarantined.push(id);
        }
      });
    }
    else {
      idsSelected.forEach((id) => {
        const matchingRecordEmbeddings = filterData.filter((t) => t["source"] === id)[0].embedding_ids;
        idsUnquarantined = [...idsUnquarantined, ...matchingRecordEmbeddings];
      });
    }

    let idsUnquarantinedText = idsUnquarantined.join(", ");

    if (idsUnquarantined.length > 0) {
      const unquarantineResponse = await postUpdateEmbeddingFlags({
        persona: "Strategist",
        ids_to_update: idsUnquarantinedText,
        flag_name: "quarantine",
        flag_update_mode: "drop_flag"
      });

      
      const errorString = handleErrorResponse(buttonText, unquarantineResponse);
      if (errorString != "") {
        setDisplayErrorMessageOnSnackBar(errorString);
        setOpenErrorSnackBar(true);
        return;
      }
      else {
        idsSelected.forEach((id) => {
          if (filterData.filter((t) => t["id"] == id)[0]["quarantine"] == 1) {
            filterData.filter((t) => t["id"] == id)[0]["quarantine"] = 0;
          }
        });

        if (usingGroupedData) {
          idsUnquarantined.forEach((id) => {
            masterTableData.filter((t) => t["id"] == id)[0]["quarantine"] = 0;
          });
        }

        gridRef.current.api.deselectAll();
      }
    }

    setUpdatingTableData(false);
    setFilterData(filterData);
    gridRef.current.api.redrawRows();
  }

  const onUpdateAccessRolesButtonClick = async (event) => {
    setUpdatingTableData(true);
    const buttonText = event.currentTarget.textContent;
    let idsSelected = sessionStorage.getItem("rowIds").split(",");
    
    if (idsSelected == "") {
      setUpdatingTableData(false);
      return;
    }

    let selectedIDsString = idsSelected.join(", ");
    let firstSelectedItem = filterData.filter((t) => t["id"] == idsSelected[0]);
    let firstSelectedAccessRolesString = firstSelectedItem[0]["access_roles"].join(", ");

    const rolesResponse = await postUpdateEmbeddingRoles({
      user_id: "Admin",
      persona: "Strategist",
      ids_to_update: selectedIDsString,
      new_role: firstSelectedAccessRolesString,
    });
    
    const errorString = handleErrorResponse(buttonText, rolesResponse);
    if (errorString !== "") {
      setDisplayErrorMessageOnSnackBar(errorString);
      setOpenErrorSnackBar(true);
      return;
    }
    else{
    console.log("roles response :", rolesResponse);
    
    setUpdatingTableData(false);
    setFilterData(filterData);
    gridRef.current.api.redrawRows();
    }
  };

  const displayChunkView = () => {
    setUsingGroupedData(false);
    setFilterData(masterTableData);
    sessionStorage.setItem("rowIds", "");
    togglePageCol();
  };

  const groupData = (data) => {
    var groupedResult = [];

    data.reduce(function (arr, record) {
      if (!arr[record.source]) {
        arr[record.source] = {
          source: record.source,
          page: record.page,
          document: record.document,
          relevance_score: parseFloat(record.relevance_score),
          feedback_score: parseFloat(record.feedback_score),
          avg_feedback_score: parseFloat(record.avg_feedback_score),
          total_number_used: record.total_number_used,
          quarantine: record.quarantine,
          avg_relevance_score_by_source: parseFloat(record.avg_relevance_score_by_source),
          avg_feedback_score_by_source: parseFloat(record.avg_feedback_score_by_source),
          uploader: record.uploader_role,
          coord_1: record.coord_1,
          coord_2: record.coord_2,
          coord_3: record.coord_3,
          access_roles: record.access_roles,
          embedding_ids: record.id,
          uploader_role: record.uploader_role,
          creation_date: record.creation_date,
          chunks_found: 0,
        };
        groupedResult.push(arr[record.source]);
      }

      if (record.quarantine == 1) {
        arr[record.source].quarantine = 1;
      }

      if (record.total_number_used > arr[record.source].total_number_used) {
        arr[record.source].total_number_used = record.total_number_used;
      }
      
      arr[record.source].relevance_score += parseFloat(record.relevance_score);
      arr[record.source].feedback_score += parseFloat(record.feedback_score);
      arr[record.source].avg_feedback_score += parseFloat(record.avg_feedback_score);
      arr[record.source].avg_relevance_score_by_source += parseFloat(record.avg_relevance_score_by_source);
      arr[record.source].avg_feedback_score_by_source += parseFloat(record.avg_feedback_score_by_source);
      arr[record.source].coord_1 += parseFloat(record.coord_1);
      arr[record.source].coord_2 += parseFloat(record.coord_2);
      arr[record.source].coord_3 += parseFloat(record.coord_3);
      arr[record.source].access_roles = [...arr[record.source].access_roles, ...record.access_roles];
      arr[record.source].embedding_ids = arr[record.source].embedding_ids + ", " + record.id;
      arr[record.source].uploader_role = arr[record.source].uploader_role + ", " + record.uploader_role;
      arr[record.source].chunks_found += 1;
      return arr;
    }, {});
    
    groupedResult.map((i) => (i["relevance_score"] = parseFloat(i["relevance_score"]/i["chunks_found"]).toFixed(2)));
    groupedResult.map((i) => (i["feedback_score"] = parseFloat(i["feedback_score"]/i["chunks_found"]).toFixed(2)));
    groupedResult.map((i) => (i["avg_feedback_score"] = parseFloat(i["avg_feedback_score"]/i["chunks_found"]).toFixed(2)));
    groupedResult.map((i) => (i["avg_relevance_score_by_source"] = parseFloat(i["avg_relevance_score_by_source"]/i["chunks_found"]).toFixed(2)));
    groupedResult.map((i) => (i["avg_feedback_score_by_source"] = parseFloat(i["avg_feedback_score_by_source"]/i["chunks_found"]).toFixed(2)));
    groupedResult.map((i) => (i["coord_1"] = parseFloat(i["coord_1"]/i["chunks_found"]).toFixed(2)));
    groupedResult.map((i) => (i["coord_2"] = parseFloat(i["coord_2"]/i["chunks_found"]).toFixed(2)));
    groupedResult.map((i) => (i["coord_3"] = parseFloat(i["coord_3"]/i["chunks_found"]).toFixed(2)));
    groupedResult.map((i) => (i["selected"] = 0));
    groupedResult.map((i) => (i["id"] = i["source"]));
    groupedResult.map((i) => (i["access_roles"] = [...new Set(i["access_roles"])].sort()));
    groupedResult.map((i) => (i["uploader_role"] = [...new Set(i["uploader_role"].split(", "))]));
    groupedResult.map((i) => (i["embedding_ids"] = [...new Set(i["embedding_ids"].split(", "))]));

    return groupedResult;
  }

  const displayDocumentView = () => {
    setUsingGroupedData(true);
    let groupedResult = groupData(filterData);
    setGroupedByDocumentMasterData(groupedResult);
    setFilterData(groupedResult);
    sessionStorage.setItem("rowIds", "");
    togglePageCol();
  };

  let hueSelector = (
    <Select
      labelId="demo-simple-select-label"
      id="demo-simple-select"
      value={hueCol}
      label="Please select a variable to use as hue for 3D scatter plot"
      onChange={handleHueColChange}
    >
      <MenuItem value={"relevance_score"}>Relevance</MenuItem>
      <MenuItem value={"feedback_score"}>User Satisfaction</MenuItem>
      <MenuItem value={"avg_relevance_score_by_source"}>
        Relevance Score By Source
      </MenuItem>
      <MenuItem value={"avg_feedback_score_by_source"}>
        Feedback Score By Source
      </MenuItem>
    </Select>
  );

  let xAxisSelector = (
    <Select
      labelId="demo-simple-select-label"
      id="demo-simple-select"
      value={xAxisCol}
      label="X axis"
      onChange={handleXAxisChange}
    >
      <MenuItem value={"coord_1"}>UMAP Coordinate X</MenuItem>
      <MenuItem value={"coord_2"}>UMAP Coordinate Y</MenuItem>
      <MenuItem value={"coord_3"}>UMAP Coordinate Z</MenuItem>
      <MenuItem value={"relevance_score"}>Relevance Score</MenuItem>
      <MenuItem value={"feedback_score"}>Feedback Score</MenuItem>
      <MenuItem value={"avg_relevance_score_by_source"}>
        Relevance Score By Source
      </MenuItem>
      <MenuItem value={"avg_feedback_score_by_source"}>
        Feedback Score By Source
      </MenuItem>
    </Select>
  );

  let yAxisSelector = (
    <Select
      labelId="demo-simple-select-label"
      id="demo-simple-select"
      value={yAxisCol}
      label="Y Axis"
      onChange={handleYAxisChange}
    >
      <MenuItem value={"coord_1"}>UMAP Coordinate X</MenuItem>
      <MenuItem value={"coord_2"}>UMAP Coordinate Y</MenuItem>
      <MenuItem value={"coord_3"}>UMAP Coordinate Z</MenuItem>
      <MenuItem value={"relevance_score"}>Relevance Score</MenuItem>
      <MenuItem value={"feedback_score"}>Feedback Score</MenuItem>
      <MenuItem value={"avg_relevance_score_by_source"}>
        Relevance Score By Source
      </MenuItem>
      <MenuItem value={"avg_feedback_score_by_source"}>
        Feedback Score By Source
      </MenuItem>
    </Select>
  );

  let zAxisSelector = (
    <Select
      labelId="demo-simple-select-label"
      id="demo-simple-select"
      value={zAxisCol}
      label="Z Axis"
      onChange={handleZAxisChange}
    >
      <MenuItem value={"coord_1"}>UMAP Coordinate X</MenuItem>
      <MenuItem value={"coord_2"}>UMAP Coordinate Y</MenuItem>
      <MenuItem value={"coord_3"}>UMAP Coordinate Z</MenuItem>
      <MenuItem value={"relevance_score"}>Relevance Score</MenuItem>
      <MenuItem value={"feedback_score"}>Feedback Score</MenuItem>
      <MenuItem value={"avg_relevance_score_by_source"}>
        Relevance Score By Source
      </MenuItem>
      <MenuItem value={"avg_feedback_score_by_source"}>
        Feedback Score By Source
      </MenuItem>
    </Select>
  );

  let dataPlot = (
    <Plot
      ref={plotRef}
      data={[
        {
          x: unselectedDataX,
          y: unselectedDataY,
          z: unselectedDataZ,
          mode: "text+markers",
          type: "scatter3d",
          hovertemplate: "<b>%{hovertext}</b>",
          hovertext: unselectedDataLabels,
          showlegend: false,
          marker: {
            size: 5,
            color: unselectedHueVar,
            colorscale: "Viridis",
            opacity: usingGroupedData ? 0.25 : filterData.filter((t) => t["selected"] == 1).length > 0 ? 0.01 : 0.15
          },
        },
        {
          x: selectedDataX,
          y: selectedDataY,
          z: selectedDataZ,
          mode: "text+markers",
          type: "scatter3d",
          hovertemplate: "<b>%{hovertext}</b>",
          hovertext: selectedDataLabels,
          showlegend: false,
          marker: {
            size: 5,
            color: selectedHueVar,
            colorscale: "Viridis",
            opacity: 1
          },
        },
      ]}
      layout={{
        hovermode: "closest",
        hoverlabel: { bgcolor: "#FFF" },
        legend: { orientation: "h", y: -0.3 },
        width: 1300,
        height: 600,
        uirevision: "time",
        margin: {
          l: 0,
          r: 0,
          t: 0,
          b: 0,
          pad: 0,
        },
        scene: {
          xaxis: {
            visible: false,
            showgrid: false,
            zeroline: false,
          },
          yaxis: {
            visible: false,
            showgrid: false,
            zeroline: false,
          },
          zaxis: {
            visible: false,
            showgrid: false,
            zeroline: false,
          },
        },
      }}
    />
  );

  return (
    <Container fullWidth>
      {loading && (
        <Grid
          item
          xs={12}
          textAlign="center"
          sx={{
            backgroundColor: colors_v2.background.secondary,
          }}
        >
          <CircularProgress
            sx={{
              height: "100%",
              fontSize: fontSizes.primary.icons,
            }}
          />
        </Grid>
      )}
      {!loading ? (
        <>
          <Row>
            <Col>
              <br />
              <div className="selectBox">
                <label>
                  {" "}
                  <Box sx={{ minWidth: 400 }}>
                    <FormControl fullWidth>
                      <InputLabel id="demo-simple-select-label">
                        Please select a variable to use as hue for 3D scatter
                        plot
                      </InputLabel>
                      {hueSelector}
                    </FormControl>
                  </Box>
                </label>
              </div>
              <br />
            </Col>
          </Row>
          <br />
          <Row>
            <Col>
              <Box sx={{ minWidth: 400 }}>{xAxisSelector}</Box>
            </Col>
            <Col>
              <Box sx={{ minWidth: 400 }}>{yAxisSelector}</Box>
            </Col>
            <Col>
              <Box sx={{ minWidth: 400 }}>{zAxisSelector}</Box>
            </Col>
          </Row>
          <br />
          <Row>
            <Col lg="8">{dataPlot}</Col>
          </Row>
          <br />
          <h5 className="center-align"> </h5>
          <Row>
            <ThemeProvider theme={theme}>
              {/* toggleRadio for views */}
              <Box className="mydict flex justify-end p-4">
                <div className="flex">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      name="radio"
                      checked={activeView === "document"}
                      onChange={() => handleViewChange("document")}
                      className="hidden"
                    />
                    <span
                      className={`flex items-center cursor-pointer bg-white py-1.5 px-3 ml-px shadow-sm border text-center transition-colors duration-500 ${
                        activeView === "document"
                          ? "bg-red-200 text-red-600"
                          : "text-gray-800"
                      } ${
                        activeView === "document" ? "first:rounded-l-md" : ""
                      }`}
                    >
                      <VisibilityIcon className="mr-1" />
                      Document View
                    </span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      name="radio"
                      checked={activeView === "pageSegment"}
                      onChange={() => handleViewChange("pageSegment")}
                      className="hidden"
                    />
                    <span
                      className={`flex items-center cursor-pointer bg-white py-1.5 px-3 ml-px shadow-sm border text-center transition-colors duration-500 ${
                        activeView === "pageSegment"
                          ? "bg-red-200 text-red-600"
                          : "text-gray-800"
                      } ${
                        activeView === "pageSegment" ? "last:rounded-r-md" : ""
                      }`}
                    >
                      <TaskAltIcon className="mr-1" />
                      Page Segment View
                    </span>
                  </label>
                </div>
              </Box>
            </ThemeProvider>
          </Row>

          <Row>
            <Col>
              <div className="AgGrid">
                <div style={{ height: "500px", width: "100%" }}>
                  <div
                    className="ag-theme-alpine"
                    style={{ height: "100%", width: "100%" }}
                  >
                    <AgGridReact
                      ref={gridRef}
                      rowData={filterData}
                      columnDefs={colDefs}
                      rowSelection="multiple"
                      pagination={true}
                      paginationPageSize={100}
                      paginationPageSizeSelector={[100, 250, 500]}
                      onSelectionChanged={onSelectionChanged}
                      onFilterChanged={handleFilter}
                      getRowStyle={getRowStyle}
                      singleClickEdit={true}
                      stopEditingWhenCellsLoseFocus={true}
                      editable={true}
                      onGridReady={sortByCreationDate}
                    />
                  </div>
                </div>
              </div>
            </Col>
          </Row>
          <Grid
            sx={{ pt: 2, pb: 2, pl: 5, pr: 5 }}
            container
            direction="row"
            justifyContent="space-between"
            spacing={2}
          >
            {[
              {
                text: isSelectingAllRows
                  ? "Select All On Current Page"
                  : "Deselect All On Current Page",
                icon: <DoneAllIcon />,
                onClick: onSelectAllOnCurrentPageButtonClick,
              },
              {
                text: "Quarantine",
                icon: <BlockIcon />,
                onClick: onQuarantineButtonClick,
              },
              {
                text: "Unquarantine",
                icon: <CheckIcon />,
                onClick: onUnquarantineButtonClick,
              },
              {
                text: "Update Access Roles",
                icon: <UpdateIcon />,
                onClick: onUpdateAccessRolesButtonClick,
              },
              {
                text: "Update Plot",
                icon: <UpdateIcon />,
                onClick: onUpdateViewButtonClick,
              },
            ].map((button, index) => (
              <Grid item xs key={index}>
                <Button
                  sx={{
                    width: "100%",
                    textAlign: "center",
                    padding: "10px",
                    gap:"4px",
                    backgroundColor: "primary.main",
                    "&:hover": {
                      backgroundColor: "primary.dark",
                      color: "white",
                    },
                    "& .MuiButton-startIcon, & .MuiButton-endIcon": {
                      margin: 0,
                    },
                    flex: 1,
                    minWidth: 0,
                  }}
                  variant="contained"
                  className="btn"
                  startIcon={button.icon}
                  onClick={button.onClick}
                >
                  <b className="whitespace-pre-wrap break-words text-sm text-start gap-2">
                    {button.text}
                  </b>
                </Button>
              </Grid>
            ))}
          </Grid>

          <Snackbar
            sx={{ width: "25%" }}
            open={openSnackBar}
            anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
          >
            <Alert
              onClose={handleClose}
              severity="info"
              variant="filled"
              sx={{ width: "100%" }}
            >
              {displayMessageOnSnackBar}
            </Alert>
          </Snackbar>
          <Snackbar
            sx={{ width: "25%" }}
            open={openErrorSnackBar}
            anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
          >
            <Alert
              onClose={handleClose}
              severity="error"
              variant="filled"
              sx={{ width: "100%" }}
            >
              {displayErrorMessageOnSnackBar}
            </Alert>
          </Snackbar>
        </>
      ) : null}
    </Container>
  );
}
