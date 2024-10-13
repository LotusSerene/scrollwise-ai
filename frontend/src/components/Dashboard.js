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
      if (error.response) {
        console.error('Error response:', error.response.data);
      }
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
      
      // Fetch the character to get the embedding ID
      const characterResponse = await axios.get(`${process.env.REACT_APP_API_URL}/api/characters/${characterId}`, { headers: headers });
      const character = characterResponse.data;

      // Delete the character from the normal database
      await axios.delete(`${process.env.REACT_APP_API_URL}/api/characters/${characterId}`, { headers: headers });

      // Remove character from knowledge base
      if (character.embedding_id) {
        await axios.delete(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, {
          headers: headers,
          data: { embedding_id: character.embedding_id }
        });
      }

      // Update the local state
      setCharacters(characters.filter(char => char.id !== characterId));
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
      const updatedHistory = [...chatHistory, newUserMessage];
      setChatHistory(updatedHistory);
      setKnowledgeBaseQuery('');

      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/query-knowledge-base`, {
        query: knowledgeBaseQuery,
        chatHistory: updatedHistory
      }, {
        headers: headers
      });

      const aiResponse = { role: 'ai', content: response.data.result };
      setChatHistory([...updatedHistory, aiResponse]);
    } catch (error) {
      console.error('Error querying knowledge base:', error);
      setError('Error querying knowledge base. Please try again later.');
    }
  };

  const resetChatHistory = async () => {
    try {
      const headers = getAuthHeaders();
      await axios.post(`${process.env.REACT_APP_API_URL}/api/reset-chat-history`, {}, { headers });
      setChatHistory([]);
    } catch (error) {
      console.error('Error resetting chat history:', error);
      setError('Error resetting chat history. Please try again later.');
    }
  };

  useEffect(() => {
    fetchCharacters();
    fetchChapters();
    fetchChatHistory();
  }, []);

  const fetchChatHistory = async () => {
    try {
      const headers = getAuthHeaders();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/chat-history`, { headers });
      setChatHistory(response.data.chatHistory);
    } catch (error) {
      console.error('Error fetching chat history:', error);
      setError('Error fetching chat history. Please try again later.');
    }
  };

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatHistory]);

  const handleSaveCharacter = async (character) => {
    try {
      const headers = getAuthHeaders();
      let response;
      let embeddingId;

      if (character.id) {
        // Update existing character
        response = await axios.put(`${process.env.REACT_APP_API_URL}/api/characters/${character.id}`, character, {
          headers: headers
        });

        embeddingId = response.data.embedding_id;

        // Update in knowledge base
        if (embeddingId) {
          await axios.put(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, {
            embedding_id: embeddingId,
            content: character.description,
            metadata: { name: character.name, characterId: character.id }
          }, { headers: headers });
        } else {
          // If no embedding_id, create new entry in knowledge base
          const knowledgeBaseResponse = await axios.post(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, {
            type: 'Character',
            content: character.description,
            metadata: { name: character.name, characterId: character.id }
          }, { headers: headers });
          embeddingId = knowledgeBaseResponse.data.embedding_id;

          // Update character with new embedding_id
          await axios.put(`${process.env.REACT_APP_API_URL}/api/characters/${character.id}`, {
            embedding_id: embeddingId
          }, { headers: headers });
        }
      } else {
        // Create new character
        response = await axios.post(`${process.env.REACT_APP_API_URL}/api/characters`, character, {
          headers: headers
        });

        // Add to knowledge base
        const knowledgeBaseResponse = await axios.post(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, {
          type: 'Character',
          content: character.description,
          metadata: { name: character.name, characterId: response.data.id }
        }, { headers: headers });

        embeddingId = knowledgeBaseResponse.data.embedding_id;

        // Update character with embedding_id
        await axios.put(`${process.env.REACT_APP_API_URL}/api/characters/${response.data.id}`, {
          embedding_id: embeddingId
        }, { headers: headers });
      }

      fetchCharacters();
    } catch (error) {
      console.error('Error saving character:', error);
      setError('Error saving character. Please try again later.');
    }
  };

  return (
    <div className="dashboard-container">
      <h2>Dashboard</h2>
      {error && (
        <p className="error">{error}</p>
      )}
      <div className="dashboard-content">
        <div className="chat-section">
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
    </div>
  );
}

export default Dashboard;
