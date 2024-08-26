"use client";
import React, { useState, useRef, useEffect } from 'react';
//import SimpleProgressBar from'./SimpleProgressBar';

function UploadComponent({ onFileUpload }) {
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (file) {
      onUploadFile();
    }
  }, [file]);

  const handleDragOver = (event) => {
    event.preventDefault();
  };

  const handleDrop = (event) => {
    event.preventDefault();
    if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
      handleFileUpload(event.dataTransfer.files);
    }
  };

  const handleFileUpload = (files) => {
    const file = files[0];
    setFile(file);
  };

  const handleFileChange = (event) => {
    if (event.target.files && event.target.files.length > 0) {
      handleFileUpload(event.target.files);
    }
  };

  const handleBrowseFiles = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const onCancelFile = () => {
    setFile(null);
    setProgress(0);
    setError('');
  };

  const onUploadFile = async () => {
    if (!file) {
      return;
    }

    try {
      let startAt = Date.now();
      await onFileUpload(file, (progressEvent) => {
        const { loaded, total } = progressEvent;

        const percentage = (loaded * 100) / total;
        setProgress(+percentage.toFixed(2));

        const timeElapsed = Date.now() - startAt;
        const uploadSpeed = loaded / timeElapsed;
        const duration = (total - loaded) / uploadSpeed;
        setRemaining(duration);
      });

      setError(''); // Clear any previous errors on successful upload
    } catch (e) {
      console.error(e);
      setError('Error uploading file, please check your connection.');
    }
  };

  return (
    <div onDragOver={handleDragOver} onDrop={handleDrop}>
      <main className="py-10 ml-10">
        <div className="flex max-w-3xl px-3 mx-auto">
          <form className="p-1 w-full" onSubmit={(e) => e.preventDefault()}>
            <div className="flex flex-col md:flex-row gap-1.5 md:py-4">
              <div className="flex-grow">
                <label className="block">
                  <input
                    className="hidden"
                    name="file"
                    type="file"
                    onChange={handleFileChange}
                    ref={fileInputRef}
                  />
                </label>
              </div>
            </div>
          </form>
        </div>
        <div className="flex flex-col items-center mt-8">
          <div className="flex items-center w-full justify-center mb-8">
            <div className="flex items-center gap-1.5 mr-4">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="bg-[#679436] text-center rounded-md px-4 py-3 text-white"
              >
                Upload
              </button>
            </div>
            <SimpleProgressBar
              progress={progress}
              fileName={file?.name}
              fileSize={file ? (file.size / (1024 * 1024)).toFixed(2) : ''}
              onCancelFile={onCancelFile}
            />
          </div>
          {error && <div className="text-red-600 text-xs mt-2">{error}</div>}
        </div>
      </main>
    </div>
  );
}

export default UploadComponent;
