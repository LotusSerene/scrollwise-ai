import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { getAuthHeaders } from '../utils/auth';
import './KnowledgeBase.css';

const KnowledgeBase = () => {
  const [knowledgeBaseContent, setKnowledgeBaseContent] = useState([]);
  const [textInput, setTextInput] = useState('');
  const [file, setFile] = useState(null);
  const [error, setError] = useState('');

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
      setError('Failed to fetch knowledge base content');
    }
  };

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    try {
      const headers = getAuthHeaders();
      await axios.post(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, 
        { documents: [textInput], metadata: { type: "doc" } },
        { headers }
      );
      setTextInput('');
      fetchKnowledgeBaseContent();
    } catch (error) {
      console.error('Error adding text to knowledge base:', error);
      setError('Failed to add text to knowledge base');
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
      setError('Failed to upload document');
    }
  };

  const handleDelete = async (embeddingId) => {
    try {
      const headers = getAuthHeaders();
      await axios.delete(`${process.env.REACT_APP_API_URL}/api/knowledge-base/${embeddingId}`, { headers });
      fetchKnowledgeBaseContent();
    } catch (error) {
      console.error('Error deleting item from knowledge base:', error);
      setError('Failed to delete item from knowledge base');
    }
  };

  return (
    <div className="knowledge-base-container">
      <h2>Knowledge Base</h2>
      
      {error && <div className="error">{error}</div>}
      
      <div className="knowledge-base-content">
        <h3>Current Knowledge Base Content</h3>
        <ul className="content-list">
          {knowledgeBaseContent.map((item, index) => (
            <li key={index}>
              <div>
                <strong>Type:</strong> {item.type || item.metadata?.type || 'Unknown'}
                <br />
                <strong>Content:</strong> {(item.content || item.page_content || '').substring(0, 100)}...
                <br />
                <strong>Embedding ID:</strong> {item.embedding_id || item.id || 'Unknown'}
              </div>
              <button onClick={() => handleDelete(item.embedding_id || item.id)} className="delete-button">Delete</button>
            </li>
          ))}
        </ul>
      </div>

      <div className="add-to-knowledge-base">
        <h3>Add to Knowledge Base</h3>
        <form onSubmit={handleTextSubmit}>
          <textarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="Add text to knowledge base"
          />
          <button type="submit">Add Text</button>
        </form>

        <form onSubmit={handleFileUpload}>
          <input
            type="file"
            onChange={(e) => setFile(e.target.files[0])}
          />
          <button type="submit">Upload Document</button>
        </form>
      </div>
    </div>
  );
};

export default KnowledgeBase;
