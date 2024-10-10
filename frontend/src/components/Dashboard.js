import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './Dashboard.css';
import { getAuthToken } from '../utils/auth';

const Dashboard = () => {
  const [characters, setCharacters] = useState([]);
  const [chapters, setChapters] = useState([]);
  const [knowledgeBaseData, setKnowledgeBaseData] = useState('');
  const [knowledgeBaseQuery, setKnowledgeBaseQuery] = useState('');
  const [error, setError] = useState(null);

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

  const fetchKnowledgeBaseData = async () => {
    try {
      const token = getAuthToken();
      const response = await axios.post(`${process.env.REACT_APP_API_URL}/api/knowledge-base`, { query: knowledgeBaseQuery }, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setKnowledgeBaseData(response.data.result);
    } catch (error) {
      console.error('Error fetching knowledge base data:', error);
      setError('Error fetching knowledge base data. Please try again later.');
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

  useEffect(() => {
    fetchCharacters();
    fetchChapters();
  }, []);

  return (
    <div className="dashboard-container">
      <h2>Dashboard</h2>
      {error &amp;&amp; (
        <p className="error">{error}</p>
      )}
      <div className="knowledge-base-section">
        <h3>Knowledge Base</h3>
        <input type="text" value={knowledgeBaseQuery} onChange={e => setKnowledgeBaseQuery(e.target.value)} placeholder="Enter your query" />
        <button onClick={fetchKnowledgeBaseData}>Search</button>
        <p>{knowledgeBaseData}</p>
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
