import { Outlet, NavLink, useLocation, matchPath, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import * as React from "react";
import { styled, createTheme, ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import MuiDrawer from "@mui/material/Drawer";
import Box from "@mui/material/Box";
import MuiAppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import List from "@mui/material/List";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import { MainListItems } from "../components/ListItems";
import Menu from '@mui/material/Menu';
import MenuItem from "@mui/material/MenuItem";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import { Avatar, Badge } from '@mui/material';
import { InputLabel } from '@mui/material';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import {
  appBarLogoNameWithoutPath,
  sideBarLogoNameWithoutPath,
  sideBarSmallLogoNameWithoutPath,
  homePageBackgroundWithoutPath,
  fontName,
  fontSizes,
  colors_v2,
} from "../../config";
import MenuIcon from "@mui/icons-material/Menu"
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import MenuOpenIcon from '@mui/icons-material/MenuOpen';
import { Button } from "@mui/material";
import Select from "@mui/material/Select";
import Radio from "@mui/material/Radio";
import FormControl from "@mui/material/FormControl";
import FormLabel from "@mui/material/FormLabel";
import RadioGroup from "@mui/material/RadioGroup";
import FormControlLabel from "@mui/material/FormControlLabel";
import { DataContext, DataProvider } from "../Store";
import { transformProfileOptions } from "../utils";
import { useMediaQuery } from "@mui/material";

const drawerWidth = 300;

const AppBar = styled(MuiAppBar, {
  shouldForwardProp: (prop) => prop !== "open",
})(({ theme, open }) => ({
  zIndex: theme.zIndex.drawer + 1,
  transition: theme.transitions.create(["width", "margin"], {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  marginLeft: 0,
  width: "100%",
}));

function RolesProfileMenu() {
  const [anchorEl, setAnchorEl] = useState(null);
  const [roleLetter, setRoleLetter] = useState('');
  const { state, dispatch } = React.useContext(DataContext);
  const [selectedRole, setSelectedRole] = useState(state.user_profiles.profile);
  const open = Boolean(anchorEl);
  const navigate = useNavigate();

  const data = transformProfileOptions(state.user_profiles.profileOptions);

  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = (event) => {
    if (event.currentTarget.textContent) {
      setSelectedRole(event.currentTarget.textContent);
      setRoleLetter(event.currentTarget.textContent.charAt(0));
      navigate("/");
      dispatch({
        type: "GUARDRAILS_PROFILE",
        profile: event.currentTarget.textContent,
      });
    }
    setAnchorEl(null);
  };

  return (
    <React.Fragment>
      <Box sx={{ display: 'flex', alignItems: 'center', textAlign: 'center' }}>
        <Tooltip title="Account settings">
          <Box sx={{ display: 'flex', alignItems: 'center', borderRadius: "25px" }}>
            <Typography sx={{ minWidth: 100, marginRight: "10px" }}>{selectedRole}</Typography>
            <Button
              onClick={handleClick}
              size="small"
              sx={{ display: 'flex', alignItems: 'center', textAlign: 'center',
                backgroundColor: '#ecf0f1', borderRadius: "25px" }}
              aria-controls={open ? 'account-menu' : undefined}
              aria-haspopup="true"
              aria-expanded={open ? 'true' : undefined}
            >
              <Avatar sx={{ width: 32, height: 32, background: '#7FC5B1' }}>{roleLetter}</Avatar>
              <KeyboardArrowDownIcon sx={{color: "black"}}/>
            </Button>
          </Box>
        </Tooltip>
      </Box>
      <Menu
        anchorEl={anchorEl}
        id="account-menu"
        open={open}
        onClose={handleClose}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        {data.map((item, index) => (
          <MenuItem key={index} onClick={handleClose}>
            {item.label}
          </MenuItem>
        ))}
      </Menu>
    </React.Fragment>
  );
};

export const Drawer = styled(MuiDrawer, {
  shouldForwardProp: (prop) => prop !== "open",
})(({ theme, open }) => ({
  "& .MuiDrawer-paper": {
    position: "relative",
    whiteSpace: "nowrap",
    width: drawerWidth,
    top: '64px',
    transition: theme.transitions.create("width", {
      easing: theme.transitions.easing.sharp,
      duration: theme.transitions.duration.enteringScreen,
    }),
    boxSizing: "border-box",
    ...(!open && {
      overflowX: "hidden",
      transition: theme.transitions.create("width", {
        easing: theme.transitions.easing.sharp,
        duration: theme.transitions.duration.leavingScreen,
      }),
      width: theme.spacing(7),
      [theme.breakpoints.up("sm")]: {
        width: theme.spacing(9),
      },
    }),
  },
}));

const { palette } = createTheme();
const { augmentColor } = palette;
const createColor = (mainColor) => augmentColor({ color: { main: mainColor } });

const defaultTheme = createTheme({
  components: {
    MuiListItemButton: {
      styleOverrides: {
        root: {
          "&.Mui-selected": {
            backgroundColor: colors_v2.client.primary,
            color: "white",
          },
          "&.Mui-selected:hover": {
            backgroundColor: colors_v2.client.tertiary,
            color: "black",
          },
        },
      },
    },
  },
  typography: {
    fontFamily: fontName,
  },
  palette: {
    primary: createColor(colors_v2.agent.primary.tone),
    secondary: createColor(colors_v2.agent.secondary.tone),
    tertiary: createColor(colors_v2.agent.tertiary.tone),
  },
});

export default function Dashboard() {
  const { state, dispatch } = React.useContext(DataContext);
  const isMobile = useMediaQuery('(max-width: 700px)');
  const { open } = state;

  const toggleSidebar = () => {
    dispatch({
      type: "TOGGLE_SIDEBAR",
    });
  };

  useEffect(() => {
    if (isMobile) {
      dispatch({
        type: "SET_SIDEBAR_STATE",
        isSidebarOpen: false,
      });
    }
  }, [isMobile, dispatch]);

  const refreshPageTrigger = () => {
    window.location.reload();
  };

  return (
    <ThemeProvider theme={defaultTheme}>
      <>
        <CssBaseline />
        <AppBar position="absolute" open={open}>
          <Toolbar
            sx={{
              pr: "24px",
              color: "black",
              backgroundColor: "#f2f2f2",
            }}
          >
            <IconButton
              edge="start"
              color="inherit"
              aria-label="open drawer"
              onClick={toggleSidebar}
              sx={{
                marginRight: "36px",
                boxShadow: "none",
                ":hover": {
                  backgroundColor: "lightgray",
                  color: "black",
                },
              }}
            >
              {open ? <MenuOpenIcon /> : <MenuIcon />}
            </IconButton>
            <Box sx={{ flexGrow: 1 }}></Box>
            <Box><RolesProfileMenu /></Box>
            <img
              src={`/imgs/${appBarLogoNameWithoutPath}`}
              style={{
                maxWidth: "100%",
                maxHeight: "60px",
                height: "auto",
                width: "auto",
                padding: "5px 10px",
              }}
              alt="logo"
            />
          </Toolbar>
        </AppBar>
        <Drawer
          variant="permanent"
          open={open}
          PaperProps={{
            sx: {
              backgroundColor: (theme) =>
                theme.palette.mode === "light"
                  ? theme.palette.grey[200]
                  : theme.palette.grey[800],
            },
          }}
        >
          <Toolbar
            sx={{
              display: "flex",
              justifyContent: "center",
              px: [1],
            }}
          >
            {open ? (
              <img
                src={`/imgs/${sideBarLogoNameWithoutPath}`}
                style={{
                  maxWidth: "180px",
                  maxHeight: "180px",
                  padding: "20px",
                  height: "auto",
                  width: "auto",
                }}
                alt="logo"
              />
            ) : (
              <img
                src={`/imgs/${sideBarSmallLogoNameWithoutPath}`}
                style={{
                  maxWidth: "80px",
                  maxHeight: "80px",
                  padding: "10px",
                  height: "auto",
                  width: "auto",
                }}
                alt="logo"
              />
            )}
          </Toolbar>
          <Divider sx={{ borderBottomWidth: "2px" }} />
          <MainListItems open={open} />
          <Divider sx={{ borderBottomWidth: "2px" }} />

          {location?.pathname === "/datainsight" && (
            <>
              <Button
                variant="contained"
                onClick={refreshPageTrigger}
                sx={{
                  margin: "10px",
                  color: colors_v2.client.primary,
                  backgroundColor: "white",
                  boxShadow: "0px 3px 5px rgba(0,0,0,0.2)",
                  textTransform: "none",
                  fontWeight: "bold",
                  display: "flex",
                  justifyContent: "center",
                  padding: open ? "10px" : "10px 16px",
                  ":hover": {
                    backgroundColor: "grey.100",
                  },
                }}
              >
                <DeleteOutlineOutlinedIcon sx={{ paddingRight: open ? "5px" : "0px" }} />
                {open && "Clear Screen"}
              </Button>
            </>
          )}
          {(location?.pathname === "/" || location?.pathname === "/docsearch") && (
            <>
              <Button
                variant="contained"
                onClick={refreshPageTrigger}
                sx={{
                  margin: open ? "10px" : "4px",
                  color: colors_v2.client.primary,
                  backgroundColor: "white",
                  boxShadow: "0px 3px 5px rgba(0,0,0,0.2)",
                  textTransform: "none",
                  fontWeight: "bold",
                  display: "flex",
                  alignItems: "center",
                  ":hover": {
                    backgroundColor: "red",
                    color: "grey.100",
                  },
                }}
              >
                <DeleteOutlineOutlinedIcon />
                {open && "Clear Screen"}
              </Button>
            </>
          )}
          <Box flexGrow={1} />
        </Drawer>
        <Box
          component="main"
          sx={{
            backgroundColor: (theme) =>
              theme.palette.mode === "light"
                ? theme.palette.grey[100]
                : theme.palette.grey[900],
            flexGrow: 1,
            height: "100vh",
            width: "100%",
            overflow: "auto",
            maxWidth: "100%",
            padding: 0,
            margin: 0,
          }}
        >
          <Toolbar />
          <Outlet />
        </Box>
      </>
    </ThemeProvider>
  );
}
