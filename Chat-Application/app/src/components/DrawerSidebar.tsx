
import * as React from 'react';
import Drawer from '@mui/material/Drawer';
import Toolbar from '@mui/material/Toolbar';
import Divider from '@mui/material/Divider';

import { fontSizes, colors_v2 } from "../../config";

const drawerWidth = 100;

interface SecondaryContentDrawerRightProps {
    drawerContent: ReactNode;
}

export default function SecondaryContentDrawerRight({drawerContent}: SecondaryContentDrawerRightProps) {
  return (
      <Drawer
        variant="permanent"
        anchor="right"
        sx={{
            //   width: drawerWidth,
            width: "100%",
            height: "100%",
            flexShrink: 0,
            '& .MuiDrawer-paper': {
                width: "30%",
                boxSizing: 'content-box', 
                backgroundColor: colors_v2.background.secondary,
                borderBottomWidth: "0px",
                borderTopWidth: "0px",
                border: "0px",
            },
    }}>
        <Toolbar />
        <Divider />
        {drawerContent}
        <Divider />
    </Drawer>
  );
}

