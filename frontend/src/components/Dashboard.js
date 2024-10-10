import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import './Dashboard.css';
import { getAuthToken } from '../utils/auth';

const Dashboard = () => {
  const [characters, setCharacters] = useState([]);
  const [chapters, setChapters] = useState([]);
  const [knowledgeBaseQuery, setKnowledgeBaseQuery] = useState('');
  const [error, setError] = useState(null);
  const [queryModel, setQueryModel] = useState('gemini-1.5-pro-002');
  const [chatHistory, setChatHistory] = useState([]);
  const chatContainerRef = useRef(null);

  const fetchCharacters = async () => {
    try {
      const token = getAuthToken();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/characters`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setCharacters(response.data.characters);
    } catch (error) {
      console.error('Error fetching characters:', error);
      setError('Error fetching characters. Please try again later.');
    }
  };

  const fetchChapters = async () => {
    try {
      const token = getAuthToken();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/chapters`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setChapters(response.data.chapters);
    } catch (error) {
      console.error('Error fetching chapters:', error);
      setError('Error fetching chapters. Please try again later.');
    }
  };

  const handleDeleteCharacter = async (characterId) => {
    try {
      const token = getAuthToken();
      await axios.delete(`${process.env.REACT_APP_API_URL}/api/characters/${characterId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
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
      const token = getAuthToken();
      const newUserMessage = { role: 'user', content: knowledgeBaseQuery };
      setChatHistory([...chatHistory, newUserMessage]);
      setKnowledgeBaseQuery('');

      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/query-knowledge-base`, {
        query: knowledgeBaseQuery,
        model: queryModel
      }, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
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
      const token = getAuthToken();
      await axios.post(`${process.env.REACT_APP_API_URL}/api/reset-chat-history`, {}, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
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
          <select value={queryModel} onChange={e => setQueryModel(e.target.value)} className="model-select">
            <option value="gemini-1.5-pro-002">Gemini 1.5 Pro</option>
            <option value="gemini-1.5-flash-002">Gemini 1.5 Flash</option>
            <option value="gemini-1.5-flash-8b">Gemini 1.5 Flash 8B</option>
          </select>
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
