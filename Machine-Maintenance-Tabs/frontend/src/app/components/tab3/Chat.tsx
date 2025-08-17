"use client";
import React, { useState } from 'react';
import { RiRobot3Line, RiSendPlane2Line, RiRestartLine } from "react-icons/ri";

function ChatUI() {
  const [userPrompt, setUserPrompt] = useState('');
  const [conversationHistory, setConversationHistory] = useState([
    { role: 'assistant', content: 'Hi Good morning David' },
    { role: 'assistant', content: 'How can I help you today' },
    // Add more initial messages if needed
  ]);

  const handleReset = () => {
    setConversationHistory([]);
    setUserPrompt("");
  };

  return (
    <div className="flex flex-1 flex-col w-full min-w-full p-4 bg-gray-100">
      <h2 className="text-2xl font-extrabold dark:text-white mb-4">Chat</h2>
      <div className="flex flex-col flex-grow overflow-auto bg-white p-4 rounded-lg shadow-md">
        <div className="flex flex-col items-start w-full">
          {conversationHistory.map((message, index) => (
            <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} mb-4 w-full`}>
              <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} w-full`}>
                {message.role === 'assistant' && (
                  <div className="w-10 h-10 rounded-full flex items-center justify-center bg-gray-200 mr-2">
                    <RiRobot3Line size={20} />
                  </div>
                )}
                <div className={`p-4 rounded-lg ${message.role === 'assistant' ? 'bg-gray-200' : 'bg-blue-100'}`}>
                  {message.content}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="p-4 bg-gray-50 border-t border-gray-300 w-full mt-4 rounded-lg">
        <div className="flex w-full">
          <input
            type="text"
            placeholder="Enter prompt here"
            className="w-full p-2 border border-gray-300 rounded-md focus:border-blue-800"
            value={userPrompt}
            onChange={(e) => setUserPrompt(e.target.value)}
          />
          <button type="submit" className="ml-2 p-2 bg-blue-500 text-white rounded-md">
            <RiSendPlane2Line size={18} />
          </button>
          <button onClick={handleReset} className="ml-2 p-2 bg-red-500 text-white rounded-md">
            <RiRestartLine size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatUI;
