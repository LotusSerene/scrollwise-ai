// Dashboard.js
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './Dashboard.css';
import { getAuthToken } from '../utils/auth';

const Dashboard = () => {
  const [characters, setCharacters] = useState([]);
  const [chapters, setChapters] = useState([]);
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
      {error && <p className="error">{error}</p>}
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
};

export default Dashboard;

