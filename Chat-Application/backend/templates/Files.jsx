import React, { useState } from 'react';

function App() {
  const [latestFile, setLatestFile] = useState('');
  const [file, setFile] = useState(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    setFile(selectedFile);
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      // Send formData to server for file upload
      // For example, using fetch or axios
      // Replace 'YOUR_UPLOAD_ENDPOINT' with your actual upload endpoint
      const response = await fetch('/static/files', {
        method: 'POST',
        body: formData
      });
      
      if (response.ok) {
        const responseData = await response.json();
        setLatestFile(responseData.fileUrl); // Assuming server responds with uploaded file URL
      } else {
        // Handle error
      }
    } catch (error) {
      // Handle error
    }
  };

  const handleDownload = () => {
    // Handle file download logic here
  };

  return (
    <div>
      <h1>Flask File Uploads</h1>

      <form onSubmit={handleUpload} encType='multipart/form-data'>
        <input type='hidden' name='csrf_token' value='{{ csrf_token() }}' />
        <input type='file' onChange={handleFileChange} />
        <button type='submit'>Upload File</button>
      </form>

      {latestFile && (
        <div>
          <p>Latest uploaded file: <a href={latestFile}>{latestFile}</a></p>
          <form onSubmit={handleDownload}>
            <input type='hidden' name='filename' value={latestFile} />
            <button type='submit'>Download File</button>
          </form>
        </div>
      )}
    </div>
  );
}

export default App;
