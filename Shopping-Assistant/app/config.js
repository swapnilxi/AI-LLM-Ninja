export const tabTitle ='';
export const postRagAnalyticsData='';
export const agentName='Shopping Assistant';
export const useCache = () => {
    // Implementation of useCache
};
export const deploymentBaseUrl = '';
export const appBarLogoNameWithoutPath = '/logo.png';
export const homePageBackgroundWithoutPath = '/home.png'
export const sideBarLogoNameWithoutPath =  '/sidebar.jpg'
export const sideBarSmallLogoNameWithoutPath =  '/sidebar.jpg'
export const fontName = 'Sans serif'


export const colors_v2 = {
    client: {
      primary: "#DD1A21",
      secondary: "#EB5936",
      tertiary: "#c1d895",
    },
    agent: {
      primary: {
        shade: "#7a9449",
        tone: "#DD1A21",
        tint: "#c1d895",
      },
      secondary: {
        shade: "#ff7a00",
        tone: "#ffe5a3",
        tint: "#faf3e2",
      },
      tertiary: {
        shade: "#65b7cf",
        tone: "#65b7cf",
        tint: "#65b7cf",
      },
    },
    background: {
      home: "dimgrey",
      primary: "white",
      secondary: "#eeeeee",
      sidebar: "#eeeeee",
    },
    messages: {
      human: "#f1f5ea",
      question: {
        text: "#d9d9d9",
        background: "white",
      },
      recommended: {
        text: "#5c5c5c",
        background: "#d2d2d2",
        selected: "#d9d9d9",
      },
    },
    card: {
      primary: {
        text: "white",
        background: "rgba(56,56,56,0.5)",
      },
    },
    confusion_matrix: [32, 50, 103],
  };

export const fontSizes = {
    home : {
        title : '24px',
        subtitle : '16px',
        paragraph : '12px',
        icons : '38px',
    },
    primary : {
        title : '24px',
        subtitle : '16px',
        paragraph : '12px',
        icons : '38px',
    },
    secondary : {
        title : '24px',
        subtitle : '16px',
        paragraph : '12px',
        icons : '38px',
        borderRadius : '6px'
    },
    sidebar : {
        title : '24px',
        subtitle : '16px',
        paragraph : '12px',
        icons : '38px',
    },
};

export const cardList = [
    {
        title : 'Card 1',
        route : "/",
        icon : 'Home',
    },
    {
        title : 'Card 2',
        cardTitle : 'Card 2',
        route : "",
        icon : 'SmartToyOutlined',
        description : 'Card 2 description',
        color : colors_v2.agent.primary.shade,
        textColor : 'black',
        subCards : [
            {
                title : 'Chat Bot',
                route : '/docsearch',
                description : 'Chat Bot description',
                persona : 'Strategist',
                icon : 'Chatoutlined',
                active : true
            }
        ]
    },
    {
        title : 'Card 3',
        cardTitle : 'Card 3',
        route : "",
        icon : 'SmartToyOutlined',
        description : 'Card 3 description',
        color : colors_v2.agent.primary.shade,
        textColor : 'black',
        subCards : [
            {
                title : 'Upload Document',
                route : '/upload',
                description : 'File upload',
                persona : 'Kam',
                icon : 'DriveFolderUploadOutlined',
                active : true,

            }
        ]
    },
    {
      title: "Admin",
      cardtitle: "Admin",
      icon: "ContactsOutlined",
      description:
        "Manage Database access to IFDA information",
      color: colors_v2.agent.primary.shade,
      textcolor: "dimgray",
      subcards: [
        {
          title: "Database Management",
          route: "/raganalytics",
          description:
            "Monitor and maintain the status and health of the database using guardrail results and usage status",
          persona: "admin",
          icon: "StorageOutlined",
          active: true,
        },
      ],
    },
];
