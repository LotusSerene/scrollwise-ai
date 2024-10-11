import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { getAuthHeaders } from '../utils/auth';
import './KnowledgeBase.css';

const KnowledgeBase = () => {
  const [knowledgeBaseContent, setKnowledgeBaseContent] = useState([]);
  const [textInput, setTextInput] = useState('');
  const [file, setFile] = useState(null);

  useEffect(() => {
    fetchKnowledgeBaseContent();
  }, []);

  const fetchKnowledgeBaseContent = async () => {
    try {
      const headers = getAuthHeaders();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, { headers });
      setKnowledgeBaseContent(response.data.content);
    } catch (error) {
      console.error('Error fetching knowledge base content:', error);
    }
  };

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    try {
      const headers = getAuthHeaders();
      await axios.post(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, 
        { documents: [textInput] },
        { headers }
      );
      setTextInput('');
      fetchKnowledgeBaseContent();
    } catch (error) {
      console.error('Error adding text to knowledge base:', error);
    }
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const headers = getAuthHeaders();
      headers['Content-Type'] = 'multipart/form-data';
      await axios.post(`${process.env.REACT_APP_API_URL}/api/upload-document`, formData, { headers });
      setFile(null);
      fetchKnowledgeBaseContent();
    } catch (error) {
      console.error('Error uploading document:', error);
    }
  };

  return (
    <div className="knowledge-base-container">
      <h2>Knowledge Base</h2>
        
      <h3>Current Knowledge Base Content</h3>
      <ul>
        {knowledgeBaseContent.map((item, index) => (
          <li key={index}>
            <div>
              <strong>Type:</strong> {item.type}
              <br />
              <strong>Content:</strong> <div className="content">{item.content}</div>
              <br />
              <strong>Metadata:</strong> {JSON.stringify(item.metadata, null, 2)}
            </div>
            {index < knowledgeBaseContent.length - 1 && <hr />}
          </li>
        ))}
      </ul>

      <h3 style={{ marginTop: '20px' }}>Add to Knowledge Base</h3>
      <form onSubmit={handleTextSubmit}>
        <label>
          Add text to knowledge base:
          <textarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            style={{ marginBottom: '10px' }}
          />
        </label>
        <button type="submit">Add Text</button>
      </form>

      <form onSubmit={handleFileUpload} style={{ marginTop: '20px' }}>
        <input
          type="file"
          onChange={(e) => setFile(e.target.files[0])}
          style={{ marginBottom: '10px' }}
        />
        <button type="submit">Upload Document</button>
      </form>
    </div>
  );
};

export default KnowledgeBase;
