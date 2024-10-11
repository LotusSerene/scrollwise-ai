// frontend/src/components/Dashboard.js
import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import './Dashboard.css';
import { getAuthHeaders } from '../utils/auth';

const Dashboard = () => {
  const [characters, setCharacters] = useState([]);
  const [chapters, setChapters] = useState([]);
  const [knowledgeBaseQuery, setKnowledgeBaseQuery] = useState('');
  const [error, setError] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const chatContainerRef = useRef(null);

  const fetchCharacters = async () => {
    try {
      const headers = getAuthHeaders();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/characters`, {
        headers: headers
      });
      setCharacters(response.data.characters);
    } catch (error) {
      console.error('Error fetching characters:', error);
      setError('Error fetching characters. Please try again later.');
    }
  };

  const fetchChapters = async () => {
    try {
      const headers = getAuthHeaders();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/chapters`, {
        headers: headers
      });
      setChapters(response.data.chapters);
    } catch (error) {
      console.error('Error fetching chapters:', error);
      setError('Error fetching chapters. Please try again later.');
    }
  };

  const handleDeleteCharacter = async (characterId) => {
    try {
      const headers = getAuthHeaders();
      await axios.delete(`${process.env.REACT_APP_API_URL}/api/characters/${characterId}`, {
        headers: headers
      });
      fetchCharacters();
    } catch (error) {
      console.error('Error deleting character:', error);
      setError('Error deleting character. Please try again later.');
    }
  };

  const handleQuerySubmit = async (e) => {
    e.preventDefault();
    if (!knowledgeBaseQuery.trim()) return;

    try {
      const headers = getAuthHeaders();
      const newUserMessage = { role: 'user', content: knowledgeBaseQuery };
      setChatHistory([...chatHistory, newUserMessage]);
      setKnowledgeBaseQuery('');

      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/query-knowledge-base`, {
        query: knowledgeBaseQuery,
        user_id: userId
      }, {
        headers: headers
      });

      const aiResponse = { role: 'ai', content: response.data.result };
      setChatHistory(prevHistory => [...prevHistory, aiResponse]);
    } catch (error) {
      console.error('Error querying knowledge base:', error);
      setError('Error querying knowledge base. Please try again later.');
    }
  };

  const resetChatHistory = async () => {
    try {
      const headers = getAuthHeaders();
      await axios.post(`${process.env.REACT_APP_API_URL}/api/reset-chat-history`, {
        user_id: userId
      }, {
        headers: headers
      });
      setChatHistory([]);
    } catch (error) {
      console.error('Error resetting chat history:', error);
      setError('Error resetting chat history. Please try again later.');
    }
  };

  useEffect(() => {
    fetchCharacters();
    fetchChapters();
  }, []);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatHistory]);

  return (
    <div className="dashboard-container">
      <h2>Dashboard</h2>
      {error && (
        <p className="error">{error}</p>
      )}
      <div className="knowledge-base-section">
        <h3>Chat with AI</h3>
        <div className="chat-container" ref={chatContainerRef}>
          {chatHistory.map((message, index) => (
            <div key={index} className={`chat-message ${message.role}`}>
              <div className="message-content">{message.content}</div>
            </div>
          ))}
        </div>
        <form onSubmit={handleQuerySubmit} className="chat-input-form">
          <input
            type="text"
            value={knowledgeBaseQuery}
            onChange={e => setKnowledgeBaseQuery(e.target.value)}
            placeholder="Type your message..."
            className="chat-input"
          />
          <button type="submit" className="send-button">Send</button>
        </form>
        <button onClick={resetChatHistory} className="reset-chat">Reset Chat History</button>
      </div>
      <div className="characters-section">
        <h3>Characters</h3>
        <ul>
          {characters.map((character) => (
            <li key={character.id}>
              {character.name} - {character.description}
              <span className="remove-icon" onClick={() => handleDeleteCharacter(character.id)}>❌</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="chapters-section">
        <h3>Recent Chapters</h3>
        <ul>
          {chapters.map((chapter) => (
            <li key={chapter.id}>
              <strong>{chapter.title}</strong> - {chapter.content.slice(0, 100)}...
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default Dashboard;
