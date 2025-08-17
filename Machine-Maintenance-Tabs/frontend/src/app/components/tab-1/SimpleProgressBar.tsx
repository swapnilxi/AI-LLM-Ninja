import React from "react";
import { XIcon } from '@heroicons/react/solid';

const SimpleProgressBar = ({
  progress = 0,
  fileName,
  fileSize,
  onCancelFile
}: {
  progress?: number;
  fileName?: string;
  fileSize?: string;
  onCancelFile: () => void;
}) => {
  return (
    <div className="flex flex-col items-start w-full max-w-md ml-4">
      {fileName && fileSize && (
        <div className="text-xs text-gray-600 mb-1.5 flex items-center">
          <span className="mr-2">{fileName} - {fileSize} MB</span>
          <button onClick={onCancelFile} className="text-gray-500 hover:text-gray-700">
            <XIcon className="h-5 w-5" />
          </button>
        </div>
      )}
      <div className="flex items-center w-full">
        <div className="flex-grow h-2 relative">
          <div className="absolute top-0 bottom-0 left-0 w-full h-full rounded-md bg-gray-300"></div>
          <div
            style={{
              width: `${progress}%`,
            }}
            className={`absolute top-0 bottom-0 left-0 h-full transition-all duration-150 ${progress > 0 ? 'bg-[#679436]' : 'bg-gray-300'}`}
          ></div>
        </div>
        <div className="ml-2 text-xs font-bold text-black">
          {progress}%
        </div>
      </div>
    </div>
  );
};

export default SimpleProgressBar;
