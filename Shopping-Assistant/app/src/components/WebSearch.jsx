import React from 'react';
import { webSearches } from './data'; // Ensure this path is correct

const WebSearch = () => {
  // Provide a fallback in case webSearches is undefined
  const searches = webSearches || [];

  return (
    <div className="flex flex-col gap-4 p-5 bg-gray-100 rounded-lg max-w-xl mx-auto">
      {searches.map((search) => (
        <div
          key={search.searchId}
          className="flex items-start p-4 bg-white border border-gray-200 rounded-lg shadow"
        >
          <div className="mr-4">
            <img src={search.icon} alt="icon" className="w-10 h-10" />
          </div>
          <div className="flex flex-col">
            <a
              href={search.link}
              className="text-lg font-bold text-gray-800 hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              {search.title}
            </a>
            <p className="text-sm text-gray-600 mt-1">{search.snippet}</p>
          </div>
        </div>
      ))}
    </div>
  );
};

export default WebSearch;
