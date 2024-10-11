// frontend/src/components/KnowledgeBase.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './KnowledgeBase.css';
import { getAuthHeaders } from '../utils/auth';

function KnowledgeBase() {
  const [documents, setDocuments] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [knowledgeBaseContent, setKnowledgeBaseContent] = useState([]);

  useEffect(() => {
    fetchKnowledgeBaseContent();
  }, []);

  const fetchKnowledgeBaseContent = async () => {
    try {
      const headers = getAuthHeaders();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, {
        headers: headers
      });
      setKnowledgeBaseContent(response.data.content);
    } catch (error) {
      console.error('Error fetching knowledge base content:', error);
      setError('Error fetching knowledge base content. Please try again later.');
    }
  };

  const handleAddDocuments = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    try {
      const headers = getAuthHeaders();
      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, {
        documents: documents.split('\n'),
        user_id: userId
      }, {
        headers: headers
      });

      if (response.data.message) {
        setSuccess(response.data.message);
        fetchKnowledgeBaseContent(); // Refresh the content after adding
      } else {
        setError('An unexpected error occurred');
      }
    } catch (error) {
      console.error('Error adding documents to the knowledge base:', error);
      setError(error.response?.data?.message || 'Error adding documents to the knowledge base. Please try again later.');
    }
  };

  const handleFileChange = (e) => {
    setSelectedFile(e.target.files[0]);
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!selectedFile) {
      setError('Please select a file to upload.');
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('user_id', userId);

    try {
      const headers = getAuthHeaders();
      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/upload-document`, formData, {
        headers: {
          ...headers,
          'Content-Type': 'multipart/form-data'
        }
      });

      if (response.data.message) {
        setSuccess(response.data.message);
        setSelectedFile(null); // Clear the selected file
        fetchKnowledgeBaseContent(); // Refresh the content after uploading
      } else {
        setError('An unexpected error occurred.');
      }
    } catch (error) {
      console.error('Error uploading document:', error);
      setError(error.response?.data?.message || 'Error uploading document. Please try again later.');
    }
  };

  return (
    <div className="knowledge-base-container">
      <h2>Knowledge Base</h2>
      {error && <p className="error">{error}</p>}
      {success && <p className="success">{success}</p>}
      
      <h3>Current Knowledge Base Content</h3>
      <div className="knowledge-base-content">
        {knowledgeBaseContent.map((item, index) => (
          <div key={index} className="knowledge-base-item">
            <h4>{item.type}</h4>
            <p>{item.content}</p>
            {item.metadata && (
              <details>
                <summary>Metadata</summary>
                <pre>{JSON.stringify(item.metadata, null, 2)}</pre>
              </details>
            )}
          </div>
        ))}
      </div>

      <h3>Add to Knowledge Base</h3>
      <form onSubmit={handleAddDocuments}>
        <label>
          Documents (one per line):
          <textarea
            value={documents}
            onChange={(e) => setDocuments(e.target.value)}
            rows={10}
            cols={80}
          />
        </label>
        <button type="submit">Add to Knowledge Base</button>
      </form>

      <h3>Upload Document</h3>
      <form onSubmit={handleFileUpload}>
        <input type="file" onChange={handleFileChange} />
        <button type="submit">Upload</button>
      </form>
    </div>
  );
}

export default KnowledgeBase;
