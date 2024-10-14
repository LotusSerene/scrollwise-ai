// frontend/src/components/Dashboard.js
import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import './Dashboard.css';
import { getAuthHeaders } from '../utils/auth';
import { toast } from 'react-toastify';

const Dashboard = () => {
  const [characters, setCharacters] = useState([]);
  const [chapters, setChapters] = useState([]);
  const [knowledgeBaseQuery, setKnowledgeBaseQuery] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const chatContainerRef = useRef(null);
  const [editingCharacter, setEditingCharacter] = useState(null);
  const [newCharacter, setNewCharacter] = useState({ name: '', description: '' });

  const fetchCharacters = async () => {
    try {
      const headers = getAuthHeaders();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/characters`, {
        headers: headers
      });
      console.log('Characters response:', response.data); // Add this line
      setCharacters(response.data.characters);
    } catch (error) {
      console.error('Error fetching characters:', error);
      toast.error('Error fetching characters');
    }
  };

  const fetchChapters = async () => {
    try {
      const headers = getAuthHeaders();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/chapters`, {
        headers: headers
      });
      setChapters(response.data.chapters);
    } catch (error) {
      console.error('Error fetching chapters:', error);
      toast.error('Error fetching chapters');
    }
  };

  const handleDeleteCharacter = async (characterId) => {
    try {
      const headers = getAuthHeaders();
      await axios.delete(`${process.env.REACT_APP_API_URL}/characters/${characterId}`, { headers: headers });
      setCharacters(characters.filter(char => char.id !== characterId));
      toast.success('Character deleted successfully');
    } catch (error) {
      console.error('Error deleting character:', error);
      toast.error('Error deleting character');
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

      const response = await axios.post(
        `${process.env.REACT_APP_API_URL}/knowledge-base/query`,
        {
          query: knowledgeBaseQuery,
          chatHistory: updatedHistory
        },
        { headers: headers }
      );

      const aiResponse = { role: 'ai', content: response.data.result };
      setChatHistory([...updatedHistory, aiResponse]);
    } catch (error) {
      console.error('Error querying knowledge base:', error);
      toast.error('Error querying knowledge base');
    }
  };

  const resetChatHistory = async () => {
    try {
      const headers = getAuthHeaders();
      await axios.post(`${process.env.REACT_APP_API_URL}/knowledge-base/reset-chat-history`, {}, { headers });
      setChatHistory([]);
      toast.success('Chat history reset');
    } catch (error) {
      console.error('Error resetting chat history:', error);
      toast.error('Error resetting chat history');
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
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/chat-history`, { 
        headers,
        timeout: 5000 // 5 seconds timeout
      });
      setChatHistory(response.data.chatHistory);
    } catch (error) {
      console.error('Error fetching chat history:', error);
      toast.error('Error fetching chat history');
    }
  };

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatHistory]);

  const handleEditCharacter = (character) => {
    setEditingCharacter(character);
  };

  const handleCancelEdit = () => {
    setEditingCharacter(null);
  };

  const handleCharacterChange = (e, isEditing = false) => {
    const { name, value } = e.target;
    if (isEditing) {
      setEditingCharacter({ ...editingCharacter, [name]: value });
    } else {
      setNewCharacter({ ...newCharacter, [name]: value });
    }
  };

  const handleSaveCharacter = async (e, isEditing = false) => {
    e.preventDefault();
    try {
      const headers = getAuthHeaders();
      const characterData = isEditing ? editingCharacter : newCharacter;

      if (isEditing) {
        await axios.put(`${process.env.REACT_APP_API_URL}/characters/${characterData.id}`, characterData, { headers });
        toast.success('Character updated successfully');
      } else {
        await axios.post(`${process.env.REACT_APP_API_URL}/characters`, characterData, { headers });
        toast.success('Character created successfully');
      }

      fetchCharacters();
      setEditingCharacter(null);
      setNewCharacter({ name: '', description: '' });
    } catch (error) {
      console.error('Error saving character:', error);
      toast.error('Error saving character');
    }
  };

  return (
    <div className="dashboard-container">
      <h2>Dashboard</h2>
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
                {editingCharacter && editingCharacter.id === character.id ? (
                  <form onSubmit={(e) => handleSaveCharacter(e, true)}>
                    <input
                      type="text"
                      name="name"
                      value={editingCharacter.name}
                      onChange={(e) => handleCharacterChange(e, true)}
                    />
                    <input
                      type="text"
                      name="description"
                      value={editingCharacter.description}
                      onChange={(e) => handleCharacterChange(e, true)}
                    />
                    <button type="submit">Save</button>
                    <button type="button" onClick={handleCancelEdit}>Cancel</button>
                  </form>
                ) : (
                  <>
                    {character.name} - {character.description}
                    <button onClick={() => handleEditCharacter(character)}>Edit</button>
                    <span className="remove-icon" onClick={() => handleDeleteCharacter(character.id)}>❌</span>
                  </>
                )}
              </li>
            ))}
          </ul>
          
          <h4>Create New Character</h4>
          <form onSubmit={handleSaveCharacter}>
            <input
              type="text"
              name="name"
              value={newCharacter.name}
              onChange={handleCharacterChange}
              placeholder="Character Name"
              required
            />
            <input
              type="text"
              name="description"
              value={newCharacter.description}
              onChange={handleCharacterChange}
              placeholder="Character Description"
              required
            />
            <button type="submit">Create Character</button>
          </form>
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
