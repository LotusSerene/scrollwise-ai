// Dashboard.js
import React, { useEffect, useState } from 'react';
import axios from 'axios';

const Dashboard = () => {
    const [chapters, setChapters] = useState([]);
    const [characters, setCharacters] = useState([]);
    const [newCharacterName, setNewCharacterName] = useState('');
    const [newCharacterDescription, setNewCharacterDescription] = useState('');

    useEffect(() => {
        fetchChapters();
        fetchCharacters();
    }, []);

    const fetchChapters = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/chapters`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setChapters(response.data.chapters);
        } catch (error) {
            console.error('Error fetching chapters:', error);
        }
    };

    const fetchCharacters = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/characters`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setCharacters(response.data.characters);
        } catch (error) {
            console.error('Error fetching characters:', error);
        }
    };

    const handleDeleteCharacter = async (id) => {
        try {
            const token = localStorage.getItem('token');
            await axios.delete(`${process.env.REACT_APP_API_URL}/api/characters/${id}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            fetchCharacters();
        } catch (error) {
            console.error('Error deleting character:', error);
        }
    };

    const handleAddCharacter = async () => {
        if (newCharacterName && newCharacterDescription) {
            try {
                const token = localStorage.getItem('token');
                await axios.post(`${process.env.REACT_APP_API_URL}/api/characters`, {
                    name: newCharacterName,
                    description: newCharacterDescription
                }, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                setNewCharacterName('');
                setNewCharacterDescription('');
                fetchCharacters();
            } catch (error) {
                console.error('Error adding character:', error);
            }
        }
    };

    return (
        <div>
            <h1>Dashboard</h1>
            <h2>Current Chapters</h2>
            <ul>
                {chapters.map(chapter => (
                    <li key={chapter.id}>
                        {chapter.title}
                        <span className="remove-icon" onClick={() => handleDeleteChapter(chapter.id)}>❌</span>
                    </li>
                ))}
            </ul>
            <h2>All Characters</h2>
            <div className="character-container">
                {characters.map(character => (
                    <div key={character.id} className="character-card">
                        <h3>{character.name}</h3>
                        <p>{character.description}</p>
                        <span className="remove-icon" onClick={() => handleDeleteCharacter(character.id)}>❌</span>
                    </div>
                ))}
            </div>
            <div className="add-character-form">
                <h3>Add New Character</h3>
                <label>
                    Name:
                    <input
                        type="text"
                        value={newCharacterName}
                        onChange={(e) => setNewCharacterName(e.target.value)}
                    />
                </label>
                <label>
                    Description:
                    <textarea
                        value={newCharacterDescription}
                        onChange={(e) => setNewCharacterDescription(e.target.value)}
                        rows={3}
                        cols={40}
                    />
                </label>
                <button onClick={handleAddCharacter}>Add Character</button>
            </div>
        </div>
    );
};

export default Dashboard;

