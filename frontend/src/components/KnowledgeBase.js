import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './KnowledgeBase.css';
import { getAuthToken } from '../utils/auth';

function KnowledgeBase() {
  const [documents, setDocuments] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const handleAddDocuments = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    try {
      const token = getAuthToken();
      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, {
        documents: documents.split('\n'),
        apiKey: apiKey
      }, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.data.message) {
        setSuccess(response.data.message);
      } else {
        setError('An unexpected error occurred');
      }
    } catch (error) {
      console.error('Error adding documents to the knowledge base:', error);
      setError(error.response?.data?.message || 'Error adding documents to the knowledge base. Please try again later.');
    }
  };

  return (
    <div className="knowledge-base-container">
      <h2>Add to Knowledge Base</h2>
      {error && <p className="error">{error}</p>}
      {success && <p className="success">{success}</p>}
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
        <label>
          API Key:
          <input
            type="text"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </label>
        <button type="submit">Add to Knowledge Base</button>
      </form>
    </div>
  );
}

export default KnowledgeBase;
