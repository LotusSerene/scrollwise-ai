import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { getAuthHeaders } from '../utils/auth';
import './KnowledgeBase.css';
import { toast } from 'react-toastify';

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
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/knowledge-base`, { headers, timeout: 5000 });
      setKnowledgeBaseContent(response.data.content);
    } catch (error) {
      console.error('Error fetching knowledge base content:', error);
      toast.error('Failed to fetch knowledge base content');
    }
  };

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    try {
      const headers = getAuthHeaders();
      headers['Content-Type'] = 'application/x-www-form-urlencoded';
      
      const formData = new URLSearchParams();
      formData.append('documents', textInput);
      formData.append('metadata', JSON.stringify({ type: 'text' })); // Add metadata for text input
      
      await axios.post(
        `${process.env.REACT_APP_API_URL}/knowledge-base/`, 
        formData,
        { headers }
      );
      setTextInput('');
      fetchKnowledgeBaseContent();
      toast.success('Text added to knowledge base');
    } catch (error) {
      console.error('Error adding text to knowledge base:', error);
      if (error.response) {
        console.error('Response data:', error.response.data);
        console.error('Response status:', error.response.status);
        console.error('Response headers:', error.response.headers);
      }
      toast.error('Failed to add text to knowledge base');
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
      formData.append('metadata', JSON.stringify({ type: 'file', filename: file.name })); // Add metadata for file upload
      await axios.post(`${process.env.REACT_APP_API_URL}/knowledge-base`, formData, { headers });
      setFile(null);
      fetchKnowledgeBaseContent();
      toast.success('Document uploaded successfully');
    } catch (error) {
      console.error('Error uploading document:', error);
      toast.error('Failed to upload document');
    }
  };

  const handleDelete = async (embeddingId) => {
    try {
      const headers = getAuthHeaders();
      await axios.delete(`${process.env.REACT_APP_API_URL}/knowledge-base/${embeddingId}`, {
        headers
      });
      fetchKnowledgeBaseContent();
      toast.success('Item deleted from knowledge base');
    } catch (error) {
      console.error('Error deleting item from knowledge base:', error);
      toast.error('Failed to delete item from knowledge base');
    }
  };

  return (
    <div className="knowledge-base-container">
      <h2>Knowledge Base</h2>
      
      <div className="knowledge-base-content">
        <h3>Current Knowledge Base Content</h3>
        <ul className="content-list">
          {knowledgeBaseContent.map((item, index) => {
            const metadata = item.metadata || {}; // Handle missing metadata
            const titleOrName = item.type === 'chapter' ? metadata.title : item.type === 'character' ? metadata.name : '';
            return (
              <li key={index}>
                <div>
                  <strong>Type:</strong> {item.type}
                  {titleOrName && <><br /><strong>{item.type === 'chapter' ? 'Title' : 'Name'}:</strong> {titleOrName}</>}
                  <br />
                  <strong>Content:</strong> {item.content.substring(0, 100)}...
                </div>
                <button onClick={() => handleDelete(item.embedding_id)} className="delete-button">Delete</button>
              </li>
            );
          })}
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
