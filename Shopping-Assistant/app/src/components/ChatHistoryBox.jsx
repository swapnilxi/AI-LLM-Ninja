import React from 'react';
import { Box, Typography, Button, IconButton, Divider } from '@mui/material';
import StarIcon from '@mui/icons-material/Star';
import StarBorderIcon from '@mui/icons-material/StarBorder';
import ChatBubbleOutlineOutlinedIcon from '@mui/icons-material/ChatBubbleOutlineOutlined';
import TextsmsOutlinedIcon from '@mui/icons-material/TextsmsOutlined';

const ChatHistoryHeader = () => (
  <Typography variant="h6" sx={{ fontSize: '12px', marginBottom: '8px', color: 'black' }}>
    <Box sx={{ display: 'flex', alignItems: 'center' }}>
      <IconButton
        sx={{
          padding: '0px',
          marginRight: '4px',
        }}
      >
        <Box component="span" sx={{ color: '#666666', fontSize: '12px' }}>📄</Box>
      </IconButton>
      Chat History
    </Box>
  </Typography>
);

const ChatHistoryItem = ({ chatText, chatId }) => {
  const getRelativeDate = (date) => {
    const today = new Date();
    const chatDate = new Date(date);
    const timeDiff = today.getTime() - chatDate.getTime();
    const dayDiff = Math.floor(timeDiff / (1000 * 3600 * 24));

    if (dayDiff === 0) return 'Today';
    else if (dayDiff === 1) return 'Yesterday';
    else if (dayDiff <= 7) return 'Previous 7 Days';
    else if (dayDiff <= 30) return 'Previous 30 Days';
    else return 'More Than 30 Days';
  };

  const renderStars = (rating) => {
    return Array.from({ length: 5 }, (_, index) =>
      index < rating ? (
        <StarIcon key={index} sx={{ color: '#05a205', fontSize: '10px' }} />
      ) : (
        <StarBorderIcon key={index} sx={{ color: '#ffa408a7', fontSize: '10px' }} />
      )
    );
  };

  const relativeDate = getRelativeDate(chatId);

  return (
    <Box key={chatId} sx={{ marginBottom: '8px' }}>
      <Typography
        variant="body2"
        sx={{ fontWeight: 'bold', fontSize: '10px', marginBottom: '4px', color: 'black' }}
      >
        {relativeDate}
      </Typography>
      <Box
        sx={{
          padding: '8px',
          borderRadius: '4px',
          backgroundColor: '#fff',
          boxShadow: 1,
          border: '1px solid #e0e0e0',
          width: '100%',
          minHeight: '50px',
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '4px',
          }}
        >
          <Typography variant="body2" sx={{ fontSize: '9px', color: 'black' }}>
            {chatText}
          </Typography>
          <Divider orientation="vertical" flexItem sx={{ margin: '0 4px' }} />
          <Box sx={{ textAlign: 'center' }}>
            <Typography
              variant="body2"
              sx={{ fontWeight: 'bold', fontSize: '9px', color: 'black', marginBottom: '2px' }}
            >
              {chatId.toFixed(1)}
            </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'center' }}>
              {renderStars(chatId)}
            </Box>
          </Box>
        </Box>
        <Divider sx={{ marginBottom: '4px' }} />
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '2px' }}>
          <Button
            variant="text"
            sx={{
              fontSize: '8px',
              padding: '2px 4px',
              minWidth: '48%',
              color: 'black',
              backgroundColor: '#e0e0e0',
              borderRadius: '2px',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <TextsmsOutlinedIcon sx={{ fontSize: '10px', marginRight: '2px' }} />
            Add Feedback
          </Button>
          <Button
            variant="text"
            sx={{
              fontSize: '8px',
              padding: '2px 4px',
              minWidth: '48%',
              color: 'black',
              backgroundColor: '#e0e0e0',
              borderRadius: '2px',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <ChatBubbleOutlineOutlinedIcon sx={{ fontSize: '10px', marginRight: '2px' }} />
            View Feedback
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

const ChatHistoryBox = ({ chatTexts = [], chatIds = [] }) => {
  
  if (!Array.isArray(chatTexts) || !Array.isArray(chatIds)) {
    return null; // or return a fallback UI
  }

  return (
    <Box
      sx={{
        backgroundColor: '#f5f5f5',
        padding: '8px',
        borderRadius: '4px',
        width: '100%',
        boxShadow: 2,
      }}
    >
      <ChatHistoryHeader />
      {chatTexts.map((chatText, index) => (
        <ChatHistoryItem key={chatIds[index]} chatText={chatText} chatId={chatIds[index]} />
      ))}
    </Box>
  );
};

export default ChatHistoryBox;
